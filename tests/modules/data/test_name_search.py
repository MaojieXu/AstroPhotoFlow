"""Unicode searches and stable pagination use keys updated by actual write paths."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import upgrade_database
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.models import Dataset
from astrophotoflow.modules.data.equipment.models import CapturePreset, Equipment, EquipmentSetup
from astrophotoflow.modules.data.projects.models import Project


@pytest.fixture
def name_library(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    upgrade_database(settings)
    database = Database(settings.database_path)
    with TestClient(create_app(settings, "name-test"), headers={"Authorization": "Bearer name-test"}) as client:
        yield client, database
    database.close()


@pytest.mark.parametrize("domain", ["asset", "dataset", "equipment", "setup", "project"])
def test_unicode_search_after_create_patch_and_orm_rename(name_library, domain):
    client, database = name_library
    paths = {"asset": "/library/assets", "dataset": "/datasets", "equipment": "/equipment",
             "setup": "/equipment-setups", "preset": "/capture-presets", "project": "/projects"}
    models = {"asset": Asset, "dataset": Dataset, "equipment": Equipment, "setup": EquipmentSetup,
              "preset": CapturePreset, "project": Project}
    collection = "/api/v1" + paths[domain]
    create_path = collection
    if domain == "preset":
        setup = client.post("/api/v1/equipment-setups", json={"name": "Support"})
        assert setup.status_code == 201, setup.text
        create_path = f"/api/v1/equipment-setups/{setup.json()['id']}/presets"
    records = []
    for name in ("Straße", "STRASSE"):
        if domain == "asset":
            identity = str(uuid4())
            with database.write_session() as session:
                session.add(Asset(id=identity, name=name, scope="shared", role="raw"))
            response = client.get(f"{collection}/{identity}")
            assert response.status_code == 200, response.text
        else:
            body = {"name": name, **({"kind": "camera"} if domain == "equipment" else {}), **({"asset_version_ids": []} if domain == "dataset" else {})}
            response = client.post(create_path, json=body)
            assert response.status_code == 201, response.text
        records.append(response.json())
    for direction in ("asc", "desc"):
        found = client.get(collection, params={"q": "strasse", "sort_by": "name", "order": direction})
        assert found.status_code == 200, found.text
        assert found.json()["total"] == 2
        assert [row["id"] for row in found.json()["items"]] == sorted(row["id"] for row in records)
        assert {row["name"] for row in found.json()["items"]} == {"Straße", "STRASSE"}
    record = records[0]
    renamed = client.patch(f"{collection}/{record['id']}", json={"base_revision": record["revision"], "name": "Kelvin_K", **({"kind": "camera"} if domain == "equipment" else {})})
    assert renamed.status_code == 200, renamed.text
    found = client.get(collection, params={"q": "KELVIN_K"})
    assert found.status_code == 200, found.text
    assert [row["id"] for row in found.json()["items"]] == [record["id"]]
    assert found.json()["items"][0]["name"] == "Kelvin_K"
    unchanged_name = client.patch(f"{collection}/{record['id']}", json={"base_revision": renamed.json()["revision"], "notes": "metadata only", **({"kind": "camera"} if domain == "equipment" else {})})
    assert unchanged_name.status_code == 200, unchanged_name.text
    assert client.get(collection, params={"q": "KELVIN_K"}).json()["total"] == 1
    with database.write_session() as session:
        session.get(models[domain], record["id"]).name = "Ångström"
    found = client.get(collection, params={"q": "ångSTRÖM"})
    assert found.status_code == 200, found.text
    assert [row["id"] for row in found.json()["items"]] == [record["id"]]
    assert client.get(collection, params={"q": "KELVIN_K"}).json()["total"] == 0


def test_generated_preset_names_use_the_same_search_index(name_library):
    client, database = name_library
    preset_ids = []
    for name in ("Straße", "STRASSE"):
        setup = client.post("/api/v1/equipment-setups", json={"name": name}).json()
        created = client.post(f"/api/v1/equipment-setups/{setup['id']}/presets", json={})
        assert created.status_code == 201, created.text
        preset_ids.append(created.json()["id"])
    found = client.get("/api/v1/capture-presets", params={"q": "strasse"}).json()
    assert {row["id"] for row in found["items"]} == set(preset_ids)
    updated = client.patch(f"/api/v1/capture-presets/{preset_ids[0]}", json={"base_revision": 1, "parameters": {"exposure_seconds": 1}})
    assert updated.status_code == 200, updated.text
    assert "1 s" in updated.json()["name"]
    assert client.get("/api/v1/capture-presets", params={"q": "1 s"}).json()["total"] == 1
    with database.write_session() as session:
        session.get(CapturePreset, preset_ids[0]).name = "Ångström"
    assert client.get("/api/v1/capture-presets", params={"q": "ångSTRÖM"}).json()["total"] == 1
