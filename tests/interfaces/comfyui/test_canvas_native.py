import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

from aiohttp import web
import pytest

from astrophotoflow.contracts.workflows import CanvasPageOut, NativeCanvasCommand, NativeCanvasGraphCommand
from astrophotoflow.interfaces import canvas_native


def command():
    page, workflow, graph = uuid4(), uuid4(), uuid4()
    return NativeCanvasCommand.model_validate({
        "request": {"operation_id": str(uuid4()), "page_id": str(page), "workflow_id": str(workflow), "graph_id": str(graph), "content_token": "content", "source": {"entry_type": "asset", "id": str(uuid4()), "version_id": str(uuid4())}},
        "data": {"native_type": "APF_DATA_REFERENCE", "title": "frame", "reference": {"kind": "asset_version", "asset_version_id": str(uuid4()), "selection": {"kind": "whole_file"}}},
    })


def test_canvas_state_identity_comes_from_socket_and_disconnect_is_unknown():
    async def scenario():
        body = command()
        socket = object()
        native = SimpleNamespace(sockets={"client": socket}, sockets_metadata={"client": {"apf_page_id": str(body.request.page_id)}})
        canvas_native.initialize_canvas(native)
        await canvas_native.handle_canvas_socket(native, socket, {"type": "apf.canvas", "data": {"action": "state", "state": {"workflow_id": str(body.request.workflow_id), "graph_id": str(body.request.graph_id), "title": "active", "content_token": "content"}}})
        assert native.apf_canvas_pages["client"].page_id == body.request.page_id
        future = asyncio.get_running_loop().create_future()
        native.apf_canvas_operations[str(body.request.operation_id)] = {"client_id": "client", "socket": socket, "command": body, "future": future}
        canvas_native.close_canvas_socket(native, "client", socket)
        assert not native.apf_canvas_pages
        assert future.result().applied is None
    asyncio.run(scenario())


def test_wrong_socket_or_wrong_graph_cannot_confirm_application():
    async def scenario():
        body = command()
        socket, other = object(), object()
        native = SimpleNamespace(sockets={"client": socket, "other": other}, sockets_metadata={"client": {"apf_page_id": str(body.request.page_id)}, "other": {"apf_page_id": str(uuid4())}})
        canvas_native.initialize_canvas(native)
        future = asyncio.get_running_loop().create_future()
        native.apf_canvas_operations[str(body.request.operation_id)] = {"client_id": "client", "socket": socket, "command": body, "future": future}
        result = {"operation_id": str(body.request.operation_id), "page_id": str(body.request.page_id), "workflow_id": str(body.request.workflow_id), "graph_id": str(body.request.graph_id), "applied": True, "node_id": 7, "error": None}
        message = {"type": "apf.canvas", "data": {"action": "result", "result": result}}
        await canvas_native.handle_canvas_socket(native, other, message)
        assert not future.done()
        result["graph_id"] = str(uuid4())
        await canvas_native.handle_canvas_socket(native, socket, message)
        assert not future.done()
        result["graph_id"] = str(body.request.graph_id)
        await canvas_native.handle_canvas_socket(native, socket, message)
        assert future.result().node_id == 7
    asyncio.run(scenario())


def test_repeating_operation_returns_same_receipt_without_second_socket_command(monkeypatch):
    async def scenario():
        import sys
        body = NativeCanvasGraphCommand.model_validate({'request': command().request.model_dump(mode='json', exclude={'source'}) |
            {'edit': {'action': 'connect', 'source_node_id': 10, 'source_port': 'science', 'target_node_id': 11, 'target_port': 'image'}}})
        socket = object()
        native = SimpleNamespace(sockets={"client": socket})
        canvas_native.initialize_canvas(native)
        from astrophotoflow.contracts.workflows import CanvasPageOut, CanvasAddResult
        native.apf_canvas_pages["client"] = CanvasPageOut(page_id=body.request.page_id, workflow_id=body.request.workflow_id, graph_id=body.request.graph_id, title="active", content_token="content")
        sends = []
        async def send(event, data, client_id):
            sends.append(data)
            native.apf_canvas_operations[str(body.request.operation_id)]["future"].set_result(CanvasAddResult(operation_id=body.request.operation_id, page_id=body.request.page_id, workflow_id=body.request.workflow_id, graph_id=body.request.graph_id, applied=True, node_id=3, error=None))
        native.send_json = send
        monkeypatch.setitem(sys.modules, "server", SimpleNamespace(PromptServer=SimpleNamespace(instance=native)))
        monkeypatch.setattr(canvas_native, "_authorized", lambda request: True)
        routes = web.RouteTableDef()
        canvas_native.register_canvas_routes(routes)
        add = next(route.handler for route in routes if route.method == "POST")
        async def read_json():
            return body.model_dump(mode="json")
        request = SimpleNamespace(json=read_json)
        first = await add(request)
        second = await add(request)
        assert json.loads(first.text) == json.loads(second.text)
        assert len(sends) == 1
    asyncio.run(scenario())


@pytest.mark.parametrize('changed', ['page_id', 'workflow_id', 'graph_id', 'content_token', 'offline'])
def test_stale_or_offline_target_is_rejected_without_a_socket_write(monkeypatch, changed):
    async def scenario():
        import sys
        body = command()
        socket = object()
        native = SimpleNamespace(sockets={'client': socket})
        canvas_native.initialize_canvas(native)
        native.apf_canvas_pages['client'] = CanvasPageOut(page_id=body.request.page_id,
            workflow_id=body.request.workflow_id, graph_id=body.request.graph_id, title='active', content_token='content')
        sends = []
        async def send(*args):
            sends.append(args)
        native.send_json = send
        if changed == 'offline':
            native.sockets.clear()
        value = body.model_dump(mode='json')
        if changed != 'offline':
            value['request'][changed] = 'stale' if changed == 'content_token' else str(uuid4())
        monkeypatch.setitem(sys.modules, 'server', SimpleNamespace(PromptServer=SimpleNamespace(instance=native)))
        monkeypatch.setattr(canvas_native, '_authorized', lambda request: True)
        routes = web.RouteTableDef()
        canvas_native.register_canvas_routes(routes)
        add = next(route.handler for route in routes if route.method == 'POST')
        async def read_json():
            return value
        response = await add(SimpleNamespace(json=read_json))
        assert response.status == 409
        assert json.loads(response.text)['error']['code'] == ('CANVAS_OFFLINE' if changed in {'page_id', 'offline'} else 'CANVAS_TARGET_CHANGED')
        assert not sends and not native.apf_canvas_operations
    asyncio.run(scenario())
