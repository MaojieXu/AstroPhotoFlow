from copy import deepcopy
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import select

from astrophotoflow.backend import imports, ingestion
from astrophotoflow.backend.api import create_app
from astrophotoflow.backend.models import AssetTask, AssetVersion
from astrophotoflow.backend.schema import upgrade_database
from astrophotoflow.config import ImportRoot, Settings


AUTH = {"Authorization": "Bearer snapshot-test"}


@pytest.fixture
def service(tmp_path, monkeypatch):
    root = tmp_path / "originals"
    root.mkdir()
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), (ImportRoot("source", root),))
    upgrade_database(settings)
    app = create_app(settings, "snapshot-test")
    # Acceptance and execution are deliberately separated to exercise queued imports.
    monkeypatch.setattr(imports, "process_task", lambda *_args: None)
    with TestClient(app) as client:
        yield client, app, settings, root
    app.state.database.close()


def checked(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def equipment(client):
    return checked(client.post("/api/v1/equipment", headers=AUTH, json={
        "kind": "camera", "name": "At acceptance", "model": "Camera model", "serial_number": "SN-1",
        "notes": "Original equipment notes", "specs": {"pixel_size_x_um": 3.76},
    }), 201)


def selection(row):
    return {"items": [{"entry_type": "equipment", "id": row["id"], "revision": row["revision"]}]}


def remove_equipment(client, row):
    checked(client.post("/api/v1/settings/trash/archive", headers=AUTH, json=selection(row)))
    archived = checked(client.get("/api/v1/equipment/" + row["id"], headers=AUTH))
    body = selection(archived)
    preview = checked(client.post("/api/v1/settings/trash/delete-preview", headers=AUTH, json=body))
    assert preview["blocked"] is False
    checked(client.post("/api/v1/settings/trash/delete", headers=AUTH,
                        json={**body, "preview_fingerprint": preview["preview_fingerprint"]}))
    assert client.get("/api/v1/equipment/" + row["id"], headers=AUTH).status_code == 404


def accept(client, root, camera, via, entry, count=1):
    stream = BytesIO()
    Image.new("RGB", (16, 12), (20, 40, 80)).save(stream, format="PNG")
    content = stream.getvalue()
    body = {"parameters": {"camera_id": camera["id"], "gain": 0, "exposure_seconds": 0}}
    if via == "preset":
        setup = checked(client.post("/api/v1/equipment-setups", headers=AUTH, json={
            "name": "Rig", "components": [{"source": "registered", "equipment_id": camera["id"]}],
        }), 201)
        preset = checked(client.post(f"/api/v1/equipment-setups/{setup['id']}/presets", headers=AUTH, json={
            "name": "Defaults", "parameters": {"gain": 0, "exposure_seconds": 0},
        }), 201)
        body = {"capture_preset_id": preset["id"]}
    names = [f"photo-{index}.png" for index in range(count)]
    for name in names:
        (root / name).write_bytes(content)
    if entry == "upload":
        accepted = checked(client.post("/api/v1/uploads", headers=AUTH, json={
            **body, "files": [{"name": name, "size": len(content)} for name in names],
        }), 202)
        task_id = accepted["task_id"]
        for index in range(count):
            checked(client.put(f"/api/v1/uploads/{task_id}/{index}", headers=AUTH, content=content))
        checked(client.post(f"/api/v1/uploads/{task_id}/start", headers=AUTH), 202)
    else:
        accepted = checked(client.post("/api/v1/imports", headers=AUTH, json={
            **body, "sources": [{"root_id": "source", "path": name} for name in names], "storage_mode": "managed",
        }), 202)
        task_id = accepted["task_id"]
    return task_id, content


@pytest.mark.parametrize("via", ["explicit", "preset"])
@pytest.mark.parametrize("entry", ["upload", "root"])
@pytest.mark.parametrize("mutation", ["rename", "archive", "restore", "delete"])
def test_accepted_import_keeps_frozen_equipment(service, via, entry, mutation):
    client, app, settings, root = service
    camera = equipment(client)
    task_id, content = accept(client, root, camera, via, entry)
    with app.state.database.read_session() as session:
        frozen = deepcopy(session.get(AssetTask, task_id).import_defaults_snapshot)
    if mutation == "rename":
        checked(client.patch("/api/v1/equipment/" + camera["id"], headers=AUTH, json={
            "base_revision": 1, "kind": "camera", "name": "Changed later", "specs": {"pixel_size_x_um": 9},
        }))
    elif mutation == "delete":
        remove_equipment(client, camera)
    else:
        checked(client.post("/api/v1/settings/trash/archive", headers=AUTH, json=selection(camera)))
        if mutation == "restore":
            archived = checked(client.get("/api/v1/equipment/" + camera["id"], headers=AUTH))
            checked(client.post("/api/v1/settings/trash/restore", headers=AUTH, json=selection(archived)))
    ingestion.process_task(app.state.database, settings, task_id, app.state.import_workers)
    task = checked(client.get("/api/v1/asset-tasks/" + task_id, headers=AUTH))
    assert task["status"] == "completed", task
    asset = checked(client.get("/api/v1/library/assets/" + task["items"][0]["asset_id"], headers=AUTH))
    expected = frozen["equipment_snapshots"][camera["id"]]
    assert asset["equipment_snapshot"]["camera_id"] == expected
    assert asset["parameters"]["camera_id"] == camera["id"]
    assert asset["parameters"]["gain"] == asset["parameters"]["exposure_seconds"] == 0
    version = asset["current_version"]
    assert version["camera_id"] == (None if mutation == "delete" else camera["id"])
    assert version["capture_snapshot"]["equipment_snapshot"]["camera_id"] == expected
    assert (root / "photo-0.png").read_bytes() == content
    with app.state.database.read_session() as session:
        assert session.get(AssetTask, task_id).import_defaults_snapshot == frozen


@pytest.mark.parametrize("via", ["explicit", "preset"])
def test_failed_registration_retry_uses_deleted_equipment_snapshot(service, via, monkeypatch):
    client, app, settings, root = service
    camera = equipment(client)
    task_id, content = accept(client, root, camera, via, "root")
    def unavailable(*_args):
        raise ingestion.IngestionError("SOURCE_UNAVAILABLE", "injected registration failure")
    with monkeypatch.context() as patch:
        patch.setattr(ingestion, "_register_asset", unavailable)
        ingestion.process_task(app.state.database, settings, task_id, app.state.import_workers)
    failed = checked(client.get("/api/v1/asset-tasks/" + task_id, headers=AUTH))
    assert failed["items"][0]["status"] == "failed"
    remove_equipment(client, camera)
    retry = checked(client.post(f"/api/v1/asset-tasks/{task_id}/retry", headers=AUTH,
                                json={"item_ids": [failed["items"][0]["id"]]}), 202)
    ingestion.process_task(app.state.database, settings, retry["task_id"], app.state.import_workers)
    completed = checked(client.get("/api/v1/asset-tasks/" + retry["task_id"], headers=AUTH))
    assert completed["status"] == "completed", completed
    asset = checked(client.get("/api/v1/library/assets/" + completed["items"][0]["asset_id"], headers=AUTH))
    assert asset["equipment_snapshot"]["camera_id"]["name"] == "At acceptance"
    assert asset["current_version"]["camera_id"] is None
    with app.state.database.read_session() as session:
        assert session.get(AssetTask, task_id).import_defaults_snapshot == session.get(AssetTask, retry["task_id"]).import_defaults_snapshot


def test_partial_registration_resumes_after_equipment_deletion(service, monkeypatch):
    client, app, settings, root = service
    camera = equipment(client)
    task_id, _ = accept(client, root, camera, "explicit", "root", count=2)
    register = ingestion._register_asset
    calls = 0
    def interrupted(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt("simulated process interruption")
        return register(*args)
    monkeypatch.setattr(ingestion, "_register_asset", interrupted)
    with pytest.raises(KeyboardInterrupt):
        ingestion.process_task(app.state.database, settings, task_id, app.state.import_workers)
    assert ingestion.mark_interrupted_tasks(app.state.database) == 1
    remove_equipment(client, camera)
    monkeypatch.setattr(ingestion, "_register_asset", register)
    checked(client.post(f"/api/v1/asset-tasks/{task_id}/resume", headers=AUTH), 202)
    ingestion.process_task(app.state.database, settings, task_id, app.state.import_workers)
    task = checked(client.get("/api/v1/asset-tasks/" + task_id, headers=AUTH))
    assert task["status"] == "completed", task
    for item in task["items"]:
        asset = checked(client.get("/api/v1/library/assets/" + item["asset_id"], headers=AUTH))
        assert asset["equipment_snapshot"]["camera_id"]["name"] == "At acceptance"
        assert asset["current_version"]["camera_id"] is None


def test_material_history_sorting_filter_labels_and_explicit_edit(service):
    client, app, settings, root = service
    camera = equipment(client)
    first, _ = accept(client, root, camera, "explicit", "root")
    ingestion.process_task(app.state.database, settings, first, app.state.import_workers)
    camera = checked(client.patch("/api/v1/equipment/" + camera["id"], headers=AUTH, json={
        "kind": "camera", "base_revision": 1, "name": "Z later name",
    }))
    second, _ = accept(client, root, camera, "explicit", "root")
    ingestion.process_task(app.state.database, settings, second, app.state.import_workers)
    page = checked(client.get("/api/v1/library/items?sort_by=camera&order=asc", headers=AUTH))
    assert [row["asset"]["equipment_snapshot"]["camera_id"]["name"] for row in page["items"]] == ["At acceptance", "Z later name"]
    options = checked(client.get("/api/v1/library/filter-options", headers=AUTH))
    assert options["equipment"]["camera_id"] == [{"id": camera["id"], "name": "At acceptance / Z later name"}]
    old_asset = page["items"][0]["asset"]
    version_id = old_asset["current_version_id"]
    edited = checked(client.patch("/api/v1/library/assets/" + old_asset["id"], headers=AUTH, json={
        "base_revision": old_asset["revision"], "parameters": {"camera_id": camera["id"]},
    }))
    assert edited["equipment_snapshot"]["camera_id"]["name"] == "Z later name"
    with app.state.database.read_session() as session:
        assert session.get(AssetVersion, version_id).capture_snapshot["equipment_snapshot"]["camera_id"]["name"] == "At acceptance"
    remove_equipment(client, camera)
    after = checked(client.get("/api/v1/library/assets/" + old_asset["id"], headers=AUTH))
    assert after["equipment_snapshot"] == edited["equipment_snapshot"]


def test_legacy_api_and_project_field_are_removed(service):
    client, _, _, _ = service
    assert client.get("/api/v1/capture-profiles", headers=AUTH).status_code == 404
    assert client.post("/api/v1/projects", headers=AUTH, json={"name": "Project", "capture_profile_ids": []}).status_code == 422
    project = checked(client.post("/api/v1/projects", headers=AUTH, json={"name": "Project"}), 201)
    assert "capture_profile_ids" not in project
