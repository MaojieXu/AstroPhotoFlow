import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from astrophotoflow.interfaces import comfyui


def test_software_page_union_is_parsed_and_identity_comes_from_actual_socket(tmp_path, monkeypatch):
    token = tmp_path / "service.token"
    token.write_text("token", encoding="utf-8")
    monkeypatch.setenv("APF_WORKSPACE", str(tmp_path))
    monkeypatch.setattr(comfyui, "load_running_settings", lambda _path: SimpleNamespace(token_path=token, service_url="http://domain"))
    received = []
    page_id, event_id = str(uuid4()), str(uuid4())

    class Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def json(self):
            return {"event_id": event_id, "page_id": page_id, "page_token": "actual-token", "result": None, "error": None}

    def post(url, **kwargs):
        received.append(kwargs["json"])
        return Response()

    server = SimpleNamespace(sockets_metadata={"client": {"apf_page_id": page_id, "apf_page_token": "actual-token"}},
                             client_session=SimpleNamespace(post=post), send_json=AsyncMock())
    asyncio.run(comfyui.forward_page_event(server, object(), "client", {
        "event_id": event_id, "page_id": str(uuid4()), "page_token": "client-cannot-choose",
        "action": "confirm_software", "payload": {"operation_id": str(uuid4())},
    }))
    assert received[0]["page_id"] == page_id and received[0]["page_token"] == "actual-token"
    assert received[0]["action"] == "confirm_software"
    assert server.send_json.call_args.args[0] == "apf.page_result"
    assert server.send_json.call_args.args[2] == "client"
