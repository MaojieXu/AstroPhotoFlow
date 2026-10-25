from copy import deepcopy
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from astrophotoflow.backend.api import create_app
from astrophotoflow.backend.models import AssetTask, Equipment
from astrophotoflow.backend.schema import upgrade_database
from astrophotoflow.config import Settings


AUTH = {"Authorization": "Bearer settings-test"}


@pytest.fixture
def service(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "settings-data", ())
    upgrade_database(settings)
    app = create_app(settings, "settings-test")
    with TestClient(app) as client:
        yield client, app.state.database
    app.state.database.close()


@pytest.mark.parametrize("kind,specs,patch", [
    ("camera", {"sensor_width_px": 100, "cfa_pattern": "RGGB"}, {"sensor_width_px": 200}),
    ("telescope", {"aperture_mm": 80, "native_focal_length_mm": 400}, {"aperture_mm": 90}),
    ("filter", {"filter_type": "Ha", "bandwidth_nm": 3}, {"filter_type": "OIII"}),
    ("mount", {"mount_type": "equatorial", "payload_kg": 20}, {"mount_type": "harmonic"}),
    ("accessory", {"accessory_type": "focuser", "connection_note": "USB"}, {"accessory_type": "rotator"}),
    ("optical_system", {"native_focal_length_mm": 400, "effective_focal_length_mm": 320}, {"effective_focal_length_mm": 300}),
])
def test_equipment_categories_keep_unspecified_specs(service, kind, specs, patch):
    client, _ = service
    created = client.post("/api/v1/equipment", headers=AUTH, json={"kind": kind, "name": kind, "specs": specs})
    assert created.status_code == 201, created.text
    row = created.json()
    changed = client.patch("/api/v1/equipment/" + row["id"], headers=AUTH,
                           json={"base_revision": 1, "kind": kind, "specs": patch})
    assert changed.status_code == 200
    assert changed.json()["revision"] == 2
    for key, value in {**specs, **patch}.items():
        assert changed.json()["specs"][key] == value
    assert client.get("/api/v1/equipment", headers=AUTH, params={"kind": kind}).json()["total"] == 1


def test_setup_inline_and_registered_edits_do_not_modify_equipment(service):
    client, database = service
    equipment = client.post("/api/v1/equipment", headers=AUTH, json={"kind": "camera", "name": "registered"}).json()
    components = [
        {"source": "registered", "equipment_id": equipment["id"]},
        {"source": "inline", "equipment": {"kind": "telescope", "name": "inline", "specs": {"aperture_mm": 80}}},
    ]
    created = client.post("/api/v1/equipment-setups", headers=AUTH, json={"name": "Rig", "components": components})
    assert created.status_code == 201, created.text
    row = created.json()
    row["components"][1]["equipment"]["name"] = "edited snapshot"
    changed = client.patch("/api/v1/equipment-setups/" + row["id"], headers=AUTH,
                           json={"base_revision": 1, "components": row["components"]})
    assert changed.status_code == 200, changed.text
    assert changed.json()["components"][1]["equipment"]["name"] == "edited snapshot"
    assert client.get("/api/v1/equipment/" + equipment["id"], headers=AUTH).json() == equipment
    with database.read_session() as session:
        assert len(session.scalars(select(Equipment)).all()) == 1
    rejected = client.patch("/api/v1/equipment-setups/" + row["id"], headers=AUTH, json={
        "base_revision": 2, "name": "must rollback", "components": [{"source": "registered", "equipment_id": str(uuid4())}],
    })
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "INVALID_REFERENCE"
    assert client.get("/api/v1/equipment-setups/" + row["id"], headers=AUTH).json()["name"] == "Rig"


def test_setup_paging_status_revisions_and_standard_errors(service):
    client, _ = service
    assert client.get("/api/v1/equipment-setups").status_code == 401
    assert client.get("/api/v1/equipment-setups/" + str(uuid4()), headers=AUTH).status_code == 404
    for name in ("B rig", "A rig"):
        assert client.post("/api/v1/equipment-setups", headers=AUTH, json={"name": name}).status_code == 201
    page = client.get("/api/v1/equipment-setups", headers=AUTH,
                      params={"sort_by": "name", "order": "asc", "limit": 1}).json()
    assert page["total"] == 2 and page["items"][0]["name"] == "A rig"
    row = page["items"][0]
    assert client.patch("/api/v1/equipment-setups/" + row["id"], headers=AUTH,
                        json={"base_revision": 1, "status": "archived"}).status_code == 200
    stale = client.patch("/api/v1/equipment-setups/" + row["id"], headers=AUTH, json={"base_revision": 1, "name": "stale"})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "REVISION_CONFLICT"
    assert client.get("/api/v1/equipment-setups", headers=AUTH).json()["total"] == 1
    assert client.get("/api/v1/equipment-setups", headers=AUTH, params={"status": "archived"}).json()["total"] == 1
    assert client.patch("/api/v1/equipment-setups/" + row["id"], headers=AUTH,
                        json={"base_revision": 2, "components": None}).status_code == 422


def test_owned_presets_preserve_sparse_null_zero_and_revision(service):
    client, _ = service
    setup = client.post("/api/v1/equipment-setups", headers=AUTH, json={"name": "Rig"}).json()
    missing = client.post("/api/v1/equipment-setups/" + str(uuid4()) + "/presets", headers=AUTH, json={"name": "missing"})
    assert missing.status_code == 404
    created = client.post("/api/v1/equipment-setups/" + setup["id"] + "/presets", headers=AUTH, json={
        "name": "Zero gain", "parameters": {"gain": 0, "offset": None}, "classification": {"frame_type": "light"},
    })
    assert created.status_code == 201, created.text
    preset = created.json()
    assert preset["equipment_setup_id"] == setup["id"]
    assert preset["parameters"] == {"gain": 0, "offset": None}
    assert preset["classification"] == {"frame_type": "light"}
    updated = client.patch("/api/v1/capture-presets/" + preset["id"], headers=AUTH,
                           json={"base_revision": 1, "parameters": {"exposure_seconds": 0, "gain": None}})
    assert updated.status_code == 200, updated.text
    assert updated.json()["parameters"] == {"gain": None, "offset": None, "exposure_seconds": 0}
    assert client.patch("/api/v1/capture-presets/" + preset["id"], headers=AUTH,
                        json={"base_revision": 1, "name": "stale"}).status_code == 409
    video = client.patch("/api/v1/capture-presets/" + preset["id"], headers=AUTH,
                         json={"base_revision": 2, "classification": {"frame_class": "video"}, "status": "archived"})
    assert video.json()["classification"] == {"frame_class": "video", "frame_type": None}
    assert client.get("/api/v1/capture-presets", headers=AUTH).json()["total"] == 0
    assert client.get("/api/v1/capture-presets", headers=AUTH, params={"status": "all"}).json()["items"][0]["parameters"] == updated.json()["parameters"]
    assert client.get("/api/v1/equipment-setups/" + setup["id"] + "/presets", headers=AUTH,
                      params={"status": "all"}).json()["total"] == 1
    rejected = client.patch("/api/v1/capture-presets/" + preset["id"], headers=AUTH,
                            json={"base_revision": 3, "parameters": {"camera_id": str(uuid4())}})
    assert rejected.status_code == 422
    assert client.get("/api/v1/capture-presets/" + preset["id"], headers=AUTH).json()["revision"] == 3


def test_accepted_import_and_retry_keep_configuration_snapshot(service, monkeypatch):
    client, database = service
    camera = client.post("/api/v1/equipment", headers=AUTH, json={"kind": "camera", "name": "original camera"}).json()
    setup = client.post("/api/v1/equipment-setups", headers=AUTH, json={"name": "original rig", "components": [
        {"source": "registered", "equipment_id": camera["id"]},
        {"source": "inline", "equipment": {"kind": "telescope", "name": "inline scope"}},
    ]}).json()
    preset = client.post("/api/v1/equipment-setups/" + setup["id"] + "/presets", headers=AUTH,
                         json={"name": "original preset", "parameters": {"gain": 0}}).json()
    accepted = client.post("/api/v1/uploads", headers=AUTH,
                           json={"files": [{"name": "small.fits", "size": 0}], "capture_preset_id": preset["id"]})
    assert accepted.status_code == 202, accepted.text
    task_id = accepted.json()["task_id"]
    task = client.get("/api/v1/asset-tasks/" + task_id, headers=AUTH).json()
    with database.read_session() as session:
        frozen = deepcopy(session.get(AssetTask, task_id).import_defaults_snapshot)
    assert frozen["parameters"] == {"gain": 0, "camera_id": camera["id"]}
    assert frozen["equipment_setup"]["components"][1]["equipment"]["name"] == "inline scope"
    assert client.patch("/api/v1/equipment/" + camera["id"], headers=AUTH,
                        json={"base_revision": 1, "kind": "camera", "name": "changed camera"}).status_code == 200
    assert client.patch("/api/v1/equipment-setups/" + setup["id"], headers=AUTH,
                        json={"base_revision": 1, "name": "changed rig", "components": []}).status_code == 200
    assert client.patch("/api/v1/capture-presets/" + preset["id"], headers=AUTH,
                        json={"base_revision": 1, "name": "changed preset", "parameters": {"gain": 100}}).status_code == 200
    with database.write_session() as session:
        session.get(AssetTask, task_id).status = "failed"
    monkeypatch.setattr("astrophotoflow.backend.imports.process_task", lambda *args: None)
    retried = client.post("/api/v1/asset-tasks/" + task_id + "/retry", headers=AUTH,
                          json={"item_ids": [task["items"][0]["id"]]})
    assert retried.status_code == 202, retried.text
    with database.read_session() as session:
        assert session.get(AssetTask, retried.json()["task_id"]).import_defaults_snapshot == frozen
        assert session.get(AssetTask, task_id).import_defaults_snapshot == frozen
