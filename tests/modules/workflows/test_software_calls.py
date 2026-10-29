import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx

from astrophotoflow.core.config import Settings
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.workflows import software_calls


def test_native_call_is_idempotent_and_not_a_public_execution_route(tmp_path, monkeypatch):
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    app = create_app(settings, "token")
    monkeypatch.setattr(software_calls, "_binding", lambda *_args: (SimpleNamespace(ready=True), {}))
    executed = []

    async def run(_app, _settings, body):
        executed.append(body.call_id)
        path = software_calls._record_path(settings, body.prompt_id, body.call_id)
        value = json.loads(path.read_text(encoding="utf-8"))
        value["state"] = "completed"
        software_calls._save(path, value)

    monkeypatch.setattr(software_calls, "_run", run)
    body = {"call_id": str(uuid4()), "prompt_id": str(uuid4()), "node_id": "3",
            "reference": {"kind": "asset_version", "asset_version_id": str(uuid4()), "selection": {"kind": "whole_file"}},
            "definition_id": str(uuid4()), "definition_token":"test", "parameters": {"linked": True, "shadowsclip": -2.8, "targetbg": 0}}

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            path = "/internal/native/bundles/calls"
            assert (await client.post(path, json=body)).status_code == 401
            headers = {"Authorization": "Bearer token"}
            assert (await client.post(path, json={**body, "work_directory": "C:/arbitrary"}, headers=headers)).status_code == 422
            first = await client.post(path, json=body, headers=headers)
            assert first.status_code == 200
            await asyncio.gather(*app.state.siril_calls.values())
            second = await client.post(path, json=body, headers=headers)
            assert second.status_code == 200 and second.json()["state"] == "completed"
            assert len(executed) == 1
            changed = await client.post(path, json={**body, "parameters": {**body["parameters"], "targetbg":0.4}}, headers=headers)
            assert changed.status_code == 409
    try:
        asyncio.run(scenario())
        assert not any("/internal/native/siril" in path for path in app.openapi()["paths"])
    finally:
        app.state.database.close()
