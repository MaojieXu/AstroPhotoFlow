import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import error_message
from astrophotoflow.interfaces.native import canvas as canvas_native, pages as comfyui
from astrophotoflow.interfaces.native import context as native_context


@pytest.fixture(params=['en', 'zh'])
def locale(request, tmp_path, monkeypatch):
    path = tmp_path / 'comfyui-user/default/comfy.settings.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'Comfy.Locale': request.param}), encoding='utf-8')
    monkeypatch.setenv('APF_WORKSPACE', str(tmp_path))
    return request.param


def test_canvas_unknown_result_remains_unknown_in_both_languages(locale):
    request = SimpleNamespace(operation_id=uuid4(), page_id=uuid4(), workflow_id=uuid4(), graph_id=uuid4())
    result = canvas_native._unknown(request)
    assert result.applied is None and result.node_id is None
    assert result.error.code == 'CANVAS_RESULT_UNKNOWN'
    assert result.error.message == error_message(locale, '', 'canvas_result_unknown')
    assert result.operation_id == request.operation_id
    response = canvas_native._error(409, 'CANVAS_TARGET_CHANGED', 'canvas_target_changed')
    assert json.loads(response.body)['error']['message'] == error_message(locale, '', 'canvas_target_changed')


def test_disconnected_native_bridge_sends_localized_failure(locale, tmp_path, monkeypatch):
    token = tmp_path / 'service.token'
    token.write_text('test-token', encoding='utf-8')
    monkeypatch.setattr(native_context, 'load_running_settings', lambda _: SimpleNamespace(token_path=token, workspace=tmp_path))
    server = SimpleNamespace(sockets_metadata={'client': {'apf_page_id': str(uuid4()), 'apf_page_token': 'page-token'}},
                             client_session=None, send_json=AsyncMock())
    asyncio.run(comfyui.forward_page_event(server, object(), 'client', {
        'action': 'confirm_software', 'event_id': str(uuid4()), 'payload': {'operation_id': str(uuid4())},
    }))
    error = server.send_json.call_args.args[1]['error']
    assert error['code'] == 'NATIVE_BRIDGE_UNAVAILABLE'
    assert error['message'] == error_message(locale, '', 'native_bridge_unavailable')
    server.send_json.assert_awaited_once()


def test_proxy_errors_keep_request_identity(locale):
    from astrophotoflow.comfyui.proxy import _error_response
    response = _error_response('request-identity', 503, 'SERVICE_UNAVAILABLE', 'proxy_unavailable')
    result = json.loads(response.body)
    assert result['request_id'] == response.headers['X-Request-ID'] == 'request-identity'
    assert result['error']['code'] == 'SERVICE_UNAVAILABLE'
    assert result['error']['message'] == error_message(locale, '', 'proxy_unavailable')


def test_mcp_platform_error_keeps_specific_reason_and_diagnostics(locale):
    from fastmcp.exceptions import ToolError
    from astrophotoflow.interfaces.mcp.errors import service_errors
    from astrophotoflow.interfaces.client.errors import ServiceApiError
    @service_errors
    def operation():
        raise ServiceApiError(409, 'SOFTWARE_ACTION_EXPIRED', error_message(locale, '', 'action_package_changed'),
            request_id='diagnostic-request', fields=[{'path': 'graph.id', 'message': 'raw {diagnostic} 原文'}])
    with pytest.raises(ToolError) as failure:
        operation()
    assert error_message(locale, '', 'action_package_changed') in str(failure.value)
    assert 'graph.id' in str(failure.value) and 'raw {diagnostic} 原文' in str(failure.value)
    assert 'diagnostic-request' in str(failure.value)
