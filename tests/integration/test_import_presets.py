"""Removed capture presets cannot re-enter ingestion through old HTTP inputs."""
from uuid import uuid4

from fastapi.testclient import TestClient

from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.schema import upgrade_database
from astrophotoflow.interfaces.http.app import create_app


def test_preset_routes_removed_and_import_rejects_preset_input(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    upgrade_database(settings)
    with TestClient(create_app(settings, "integration-token"), headers={"Authorization": "Bearer integration-token"}) as client:
        assert client.get("/api/v1/capture-presets").status_code == 404
        assert client.post(f"/api/v1/equipment-setups/{uuid4()}/presets", json={}).status_code == 404
        rejected = client.post("/api/v1/imports", json={
            "sources": [{"type": "absolute_path", "path": str(tmp_path / "source.fits")}],
            "capture_preset_id": str(uuid4()),
        })
        assert rejected.status_code == 422
        assert "capture_preset_id" in rejected.text
