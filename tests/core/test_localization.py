import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from astrophotoflow.core.config import ConfigurationError
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import error_message, workspace_locale
from astrophotoflow.interfaces.http.errors import error_response
from astrophotoflow.interfaces.http.system import router


def native_settings(workspace, value):
    path = workspace / 'comfyui-user/default/comfy.settings.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')
    return path


@pytest.mark.parametrize(('stored', 'expected'), [('en', 'en'), ('zh', 'zh'), ('zh-TW', 'zh'), ('ZH-cn', 'zh'), ('fr', 'en')])
def test_workspace_reads_native_language_without_writing(tmp_path, stored, expected):
    path = native_settings(tmp_path, {'Comfy.Locale': stored, 'other': 0})
    before = path.read_bytes()
    assert workspace_locale(tmp_path) == expected
    assert path.read_bytes() == before
    assert workspace_locale(tmp_path / 'another') == 'en'
    assert not (tmp_path / 'another').exists()


@pytest.mark.parametrize('content', ['not json', '[]', '{"Comfy.Locale":0}'])
def test_invalid_native_settings_do_not_silently_become_defaults(tmp_path, content):
    path = native_settings(tmp_path, {})
    path.write_text(content, encoding='utf-8')
    with pytest.raises(ConfigurationError):
        workspace_locale(tmp_path)
    assert path.read_text(encoding='utf-8') == content


def test_locale_endpoint_authentication_and_corrupt_file(tmp_path):
    app = FastAPI()
    app.state.token = 'test-token'
    app.state.settings = SimpleNamespace(workspace=tmp_path)
    app.include_router(router)

    @app.exception_handler(ApiError)
    async def errors(request, exc):
        return error_response(request, exc.status_code, exc.code, exc.message, exc.fields,
                               message_key=exc.message_key, message_params=exc.message_params)

    with TestClient(app) as client:
        assert client.get('/api/v1/settings/locale').status_code == 401
        headers = {'Authorization': 'Bearer test-token'}
        assert client.get('/api/v1/settings/locale', headers=headers).json() == {'locale': 'en'}
        path = native_settings(tmp_path, {'Comfy.Locale': 'zh'})
        assert client.get('/api/v1/settings/locale', headers=headers).json() == {'locale': 'zh'}
        path.write_text('broken', encoding='utf-8')
        response = client.get('/api/v1/settings/locale', headers=headers)
        assert response.status_code == 503
        assert response.json()['error']['code'] == 'LOCALE_UNAVAILABLE'
        assert 'request_id' in response.json()


def test_unreadable_settings_report_configuration_error(tmp_path, monkeypatch):
    path = native_settings(tmp_path, {'Comfy.Locale': 'zh'})
    from pathlib import Path
    original = Path.read_text

    def read(selected, *args, **kwargs):
        if selected == path:
            raise PermissionError('denied')
        return original(selected, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', read)
    with pytest.raises(ConfigurationError):
        workspace_locale(tmp_path)


def test_business_error_uses_named_parameters_without_rewriting_diagnostics():
    values = {'p0': 'FITS', 'p1': 0, 'p2': '原始诊断 {literal}'}
    from astrophotoflow.core.localization import error_messages
    key = next(key for key, messages in error_messages()['messages'].items()
               if messages['en'].startswith('Bundle executable version check failed'))
    en = error_message('en', 'SOFTWARE_NOT_READY', key, values)
    zh = error_message('zh', 'SOFTWARE_NOT_READY', key, values)
    assert en != zh
    assert values['p2'] in en and values['p2'] in zh
    assert '0' in en and '0' in zh


@pytest.mark.parametrize('locale', ['en', 'zh'])
def test_nested_install_error_localizes_reason_without_translating_raw_diagnostics(locale):
    reason = ApiError(409, 'BUNDLE_VERSION_CHANGED', '原始中文错误',
                      message_key='bundle_reference_data_does_not_match_the_confirmed_snapshot_nothing_was_ins')
    actual = error_message(locale, 'SOFTWARE_NOT_READY', 'bundle_installation_failed_p0', {'p0': reason})
    assert actual == error_message(locale, '', 'bundle_installation_failed_p0',
                                   {'p0': error_message(locale, reason.code, reason.message_key)})
    assert '原始中文错误' not in actual
    assert error_message(locale, '', 'bundle_installation_failed_p0', {'p0': 'raw 日志 {value}'}).endswith('raw 日志 {value}')
