from uuid import uuid4

from fastapi.testclient import TestClient

from astrophotoflow.contracts.inputs import CanvasDataOut
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.schema import database_lock, upgrade_database
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.workflows import canvas


def test_canvas_http_preserves_target_and_unknown_native_result(tmp_path, monkeypatch):
    settings = Settings("127.0.0.1", 8190, tmp_path, ("http://127.0.0.1:8188",), workspace=tmp_path)
    with database_lock(settings):
        upgrade_database(settings)
    app = create_app(settings, "canvas-http")
    request = {"operation_id": str(uuid4()), "page_id": str(uuid4()), "workflow_id": str(uuid4()), "graph_id": str(uuid4()), "content_token": "content", "source": {"entry_type": "asset", "id": str(uuid4()), "version_id": str(uuid4())}}
    prepared = CanvasDataOut.model_validate({"title": "Fixed asset", "reference": {"kind": "asset_version", "asset_version_id": request["source"]["version_id"], "selection": {"kind": "whole_file"}}})
    seen = []
    monkeypatch.setattr(canvas, "prepare_canvas_data", lambda database, source: prepared)
    async def native(incoming, method, path, body=None):
        seen.append((method, path, body))
        if path == "/pages":
            return [{"page_id": request["page_id"], "workflow_id": request["workflow_id"], "graph_id": request["graph_id"], "content_token": "content", "title": "Active"}]
        return {key: request[key] for key in ("operation_id", "page_id", "workflow_id", "graph_id")} | {"applied": None, "node_id": None, "error": {"code": "CANVAS_RESULT_UNKNOWN", "message": "Query before retry", "fields": []}}
    monkeypatch.setattr(canvas, "_native", native)
    try:
        with TestClient(app, headers={"Authorization": "Bearer canvas-http"}) as client:
            assert client.get("/api/v1/canvas/pages").json()[0]["page_id"] == request["page_id"]
            result = client.post("/api/v1/canvas/requests", json=request)
            assert result.status_code == 200
            assert result.json()["applied"] is None
            assert seen[-1][2]["request"]["page_id"] == request["page_id"]
            assert seen[-1][2]["data"]["reference"]["asset_version_id"] == request["source"]["version_id"]
            assert client.get("/api/v1/canvas/requests/" + request["operation_id"]).json()["applied"] is None
            count = len(seen)
            assert client.post("/api/v1/canvas/requests", json=request, headers={"Authorization": "Bearer wrong"}).status_code == 401
            app.state.maintenance = True
            assert client.post("/api/v1/canvas/requests", json=request).status_code == 409
            assert len(seen) == count
    finally:
        app.state.database.close()
