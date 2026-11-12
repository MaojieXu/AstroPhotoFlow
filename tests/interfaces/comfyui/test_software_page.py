import asyncio
import pytest
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from astrophotoflow.interfaces.native import pages as comfyui
from astrophotoflow.interfaces.native import context as native_context
from astrophotoflow.interfaces.native import bootstrap as native_bootstrap


def test_software_page_union_is_parsed_and_identity_comes_from_actual_socket(tmp_path, monkeypatch):
    token = tmp_path / "service.token"
    token.write_text("token", encoding="utf-8")
    monkeypatch.setenv("APF_WORKSPACE", str(tmp_path))
    monkeypatch.setattr(native_context, "load_running_settings", lambda _path: SimpleNamespace(token_path=token, service_url="http://domain"))
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

        async def text(self):
            return json.dumps(await self.json())

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
    assert server.send_json.call_args.args[1]["error"] is None
    assert server.send_json.call_args.args[1]["event_id"] == event_id


def test_bundle_reload_route_requires_service_token(monkeypatch):
    import sys
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer
    from astrophotoflow.comfyui import proxy

    reload = AsyncMock()
    monkeypatch.setattr(native_bootstrap, "service_context", lambda: SimpleNamespace(token="secret"))
    monkeypatch.setitem(sys.modules, "server", SimpleNamespace(PromptServer=SimpleNamespace(instance=object())))
    monkeypatch.setitem(sys.modules, "astrophotoflow.interfaces.native.bundles.catalog", SimpleNamespace(reload_bundle_nodes=reload))

    async def scenario():
        app = web.Application()
        routes = web.RouteTableDef()
        native_bootstrap.register_bundle_routes(routes)
        app.add_routes(routes)
        async with TestClient(TestServer(app)) as client:
            assert (await client.post("/astrophotoflow/internal/bundles/reload")).status == 401
            reload.assert_not_awaited()
            result = await client.post("/astrophotoflow/internal/bundles/reload", headers={"Authorization": "Bearer secret"})
            assert result.status == 200 and await result.json() == {"status": "loaded"}
            reload.assert_awaited_once()
    asyncio.run(scenario())



@pytest.mark.parametrize('field', ['event_id', 'page_id', 'page_token'])
def test_mismatched_page_reply_is_unknown_without_replaying_the_request(tmp_path, monkeypatch, field):
    token = tmp_path / 'service.token'
    token.write_text('secret')
    monkeypatch.setenv('APF_WORKSPACE', str(tmp_path))
    monkeypatch.setattr(native_context, 'load_running_settings', lambda _: SimpleNamespace(
        token_path=token, service_url='http://domain', workspace=tmp_path))
    page, event = str(uuid4()), str(uuid4())
    value = dict(event_id=event, page_id=page, page_token='actual-token', result=None, error=None)
    value[field] = str(uuid4()) if field != 'page_token' else 'other-token'
    sent = []
    class Reply:
        status = 200
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def text(self): return json.dumps(value)
    def post(*args, **kwargs):
        sent.append(kwargs['json'])
        return Reply()
    server = SimpleNamespace(client_session=SimpleNamespace(post=post), send_json=AsyncMock(),
        sockets_metadata={'client': {'apf_page_id': page, 'apf_page_token': 'actual-token'}})
    asyncio.run(comfyui.forward_page_event(server, object(), 'client', {
        'action': 'confirm_software', 'event_id': event, 'payload': {'operation_id': str(uuid4())}}))
    assert len(sent) == 1
    reply = server.send_json.call_args.args[1]
    assert reply['error']['code'] == 'NATIVE_BRIDGE_UNAVAILABLE' and reply['result'] is None
    assert reply['event_id'] == event and reply['page_id'] == page
