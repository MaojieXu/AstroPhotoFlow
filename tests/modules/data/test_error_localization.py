import astrophotoflow.modules.data.imports.stages as owner_stages
import astrophotoflow.modules.data.imports.errors as owner_errors
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import error_message
from astrophotoflow.modules.data.science import inputs as science_input_service, outputs as science_output_service, files as science_files


@pytest.mark.parametrize('locale', ['en', 'zh'])
def test_reference_observation_preserves_specific_error_and_diagnostics(tmp_path, monkeypatch, locale):
    path = tmp_path / 'comfyui-user/default/comfy.settings.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'Comfy.Locale': locale}), encoding='utf-8')
    fields = [{'path': 'read_path', 'message': 'original diagnostic C:/素材/{name}.fit'}]
    def fail(path):
        raise ApiError(422, 'SOURCE_UNAVAILABLE', '原始中文错误', fields=fields,
                       message_key='the_asset_file_cannot_be_read_completely')
    monkeypatch.setattr(science_input_service, 'hash_file', fail)
    inputs = SimpleNamespace(items=[SimpleNamespace(kind='asset_version', preparation='reference', read_path=tmp_path / 'missing.fit')])
    result = science_input_service.observe_reference_inputs(SimpleNamespace(workspace=tmp_path), inputs)[0]
    assert result.state == 'missing' and result.input_index == 0
    assert result.error.message == error_message(locale, '', 'the_asset_file_cannot_be_read_completely')
    assert result.error.fields == fields


@pytest.mark.parametrize('locale', ['en', 'zh'])
def test_import_failures_keep_specific_keys_and_external_diagnostics(tmp_path, locale):
    path = tmp_path / 'comfyui-user/default/comfy.settings.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'Comfy.Locale': locale}), encoding='utf-8')
    settings = SimpleNamespace(workspace=tmp_path)
    error = owner_errors.IngestionError('SOURCE_CHANGED', '原始诊断', message_key='import_source_changed_reading')
    rendered = owner_errors.import_error(settings, error, code='REGISTRATION_FAILED', message_key='import_registration_failed')
    assert rendered['code'] == 'SOURCE_CHANGED'
    assert rendered['message'] == error_message(locale, '', 'import_source_changed_reading')
    external = owner_errors.import_error(settings, OSError('raw 日志 {value}'), code='CONTENT_READ_FAILED', message_key='import_copy_failed')
    assert external['fields'] == [{'path': 'diagnostic', 'message': 'raw 日志 {value}'}]


def test_output_registration_returns_historical_error_without_retranslation():
    historical = {'code': 'SOURCE_UNAVAILABLE', 'message': '历史中文原文', 'fields': [{'path': 'source', 'message': 'old diagnostic'}]}
    task = SimpleNamespace(id=str(uuid4()), status='failed', error=historical)
    session = SimpleNamespace(scalar=lambda statement: None)
    result = science_output_service.output_registration(session, task, False)
    assert result.error.model_dump() == historical
    assert task.error is historical
