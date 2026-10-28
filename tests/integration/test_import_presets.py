"""Exercise the settings-to-ingestion contract through the actual HTTP app."""
from io import BytesIO

from astropy.io import fits
from fastapi.testclient import TestClient
import numpy as np
import pytest

from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.core.database.schema import upgrade_database
from astrophotoflow.core.config import Settings


@pytest.mark.parametrize("manual_classification", [None, {"frame_class": "masterframe", "frame_type": "flat"},
                                                   {"frame_type": "flat"}, {"frame_type": None}])
def test_selected_preset_is_frozen_and_observed_values_win(tmp_path, manual_classification):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    upgrade_database(settings)
    app = create_app(settings, "integration-token")
    try:
        with TestClient(app, headers={"Authorization": "Bearer integration-token"}) as client:
            camera_response = client.post("/api/v1/equipment", json={"kind": "camera", "name": "registered camera"})
            assert camera_response.status_code == 201, camera_response.text
            camera = camera_response.json()
            setup_response = client.post("/api/v1/equipment-setups", json={
                "name": "imaging rig", "components": [{"source": "registered", "equipment_id": camera["id"]}],
            })
            assert setup_response.status_code == 201, setup_response.text
            setup = setup_response.json()
            preset_response = client.post(f"/api/v1/equipment-setups/{setup['id']}/presets", json={
                "name": "original preset", "classification": {"frame_class": "subframe", "frame_type": "dark"},
                "parameters": {"parameter_mode": "gain", "gain": 100, "offset": 8, "exposure_seconds": 120},
            })
            assert preset_response.status_code == 201, preset_response.text
            preset = preset_response.json()
            image = fits.PrimaryHDU(np.arange(64, dtype=np.float32).reshape(8, 8))
            image.header["IMAGETYP"] = "Master Light"
            image.header["EXPTIME"] = 30
            image.header["GAIN"] = 4
            content = BytesIO()
            image.writeto(content)
            content = content.getvalue()
            payload = {"files": [{"name": "light.fits", "size": len(content)}],
                       "capture_preset_id": preset["id"], "parameters": {"gain": 0},
                       "create_dataset": True, "dataset_name": "selected preset batch"}
            if manual_classification is not None:
                payload["classification"] = manual_classification
            accepted = client.post("/api/v1/uploads", json=payload)
            assert accepted.status_code == 202, accepted.text
            task_id = accepted.json()["task_id"]
            changed = client.patch(f"/api/v1/capture-presets/{preset['id']}", json={
                "base_revision": preset["revision"], "parameters": {"offset": 44, "exposure_seconds": 600},
            })
            assert changed.status_code == 200, changed.text
            assert client.put(f"/api/v1/uploads/{task_id}/0", content=content).status_code == 200
            started = client.post(f"/api/v1/uploads/{task_id}/start")
            assert started.status_code == 202, started.text
            task = client.get(f"/api/v1/asset-tasks/{task_id}").json()
            assert task["status"] == "completed", task
            assert task["report"]["registration"]["completed"] is True
            asset = client.get(f"/api/v1/library/assets/{task['items'][0]['asset_id']}").json()
            assert asset["parameters"]["camera_id"] == camera["id"]
            assert asset["parameters"]["gain"] == 0
            assert asset["parameters"]["exposure_seconds"] == 30
            assert asset["parameters"]["offset"] == 8
            assert asset["value_sources"]["gain"] == "manual"
            assert asset["value_sources"]["exposure_seconds"] == "file"
            assert asset["value_sources"]["offset"] == "preset"
            expected_classification = {"frame_class": "masterframe", "frame_type": "light"}
            if manual_classification is not None:
                expected_classification.update(manual_classification)
                for key in manual_classification:
                    assert asset["value_sources"]["classification." + key] == "manual"
            assert asset["classification"] == expected_classification
            if manual_classification is None or "frame_class" not in manual_classification:
                assert asset["value_sources"]["classification.frame_class"] == "file"
            snapshot = asset["current_version"]["capture_snapshot"]["import_provenance"]["defaults_snapshot"]
            assert snapshot["capture_preset"]["revision"] == preset["revision"]
            assert snapshot["parameters"]["offset"] == 8
            dataset = client.get(f"/api/v1/datasets/{task['dataset_id']}").json()
            version = client.get(f"/api/v1/datasets/{dataset['id']}/versions/{dataset['current_version_id']}").json()
            assert version["members"][0]["asset_version_id"] == asset["current_version_id"]
    finally:
        app.state.database.close()
