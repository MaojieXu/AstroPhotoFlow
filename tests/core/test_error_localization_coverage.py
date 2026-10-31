import ast
from pathlib import Path
from string import Formatter

import pytest

from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import error_messages, exception_error, localized_error


@pytest.mark.parametrize('locale', ['en', 'zh'])
def test_specific_nested_errors_keep_diagnostics_and_field_paths(locale):
    cause = ApiError(409, 'SOFTWARE_ACTION_EXPIRED', '原始中文提示',
                     fields=[{'path': 'parameters.gain', 'message': '原始诊断 {gain}=0'},
                             {'path': 'asset_version_ids', 'message': '成员版本 ID 不能重复。'}],
                     message_key='action_package_changed',
                     field_message_keys={'asset_version_ids': 'field_member_duplicate'})
    wrapper = ApiError(503, 'SOFTWARE_NOT_READY', '旧的中文外层', fields=cause.fields,
                       message_key='bundle_installation_failed_p0', message_params={'p0': cause},
                       field_message_keys=cause.field_message_keys)
    result = exception_error(locale, wrapper, code='INTERNAL_ERROR', message_key='internal_error')
    assert result.code == wrapper.code
    assert result.fields[0] == cause.fields[0]
    assert result.fields[1]['path'] == 'asset_version_ids'
    assert result.fields[1]['message'] == error_messages()['messages']['field_member_duplicate'][locale]
    assert '旧的中文外层' not in result.message and '原始中文提示' not in result.message
    assert cause.fields[1]['message'] == '成员版本 ID 不能重复。'
    assert set(result.model_dump()) == {'code', 'message', 'fields'}


@pytest.mark.parametrize('locale', ['en', 'zh'])
def test_unclassified_diagnostic_is_not_translated_or_formatted(locale):
    diagnostic = 'Siril 原始日志 C:/素材/{name}.fit, exit=0'
    result = exception_error(locale, OSError(diagnostic), code='OBSERVATION_FAILED',
                             message_key='observation_result_failed')
    assert result.message == error_messages()['messages']['observation_result_failed'][locale]
    assert result.fields == [{'path': 'diagnostic', 'message': diagnostic}]
    exit_error = localized_error(locale, 'SOFTWARE_EXECUTION_FAILED', 'software_exit_failed',
                                 parameters={'exit_code': 9}, fields=result.fields)
    assert '9' in exit_error.message and exit_error.fields == result.fields
    legacy = exception_error(locale, ApiError(422, 'EXTERNAL_BUNDLE_ERROR', diagnostic),
                             code='SOFTWARE_EXECUTION_FAILED', message_key='software_execution_failed')
    assert legacy.code == 'EXTERNAL_BUNDLE_ERROR'
    assert legacy.fields == [{'path': 'diagnostic', 'message': diagnostic}]


def test_all_error_catalog_entries_have_matching_locales_and_interpolation_fields():
    def parameters(text):
        return {field for _, field, _, _ in Formatter().parse(text) if field is not None}
    for key, messages in error_messages()['messages'].items():
        assert set(messages) == {'en', 'zh'}, key
        assert messages['en'].strip() and messages['zh'].strip(), key
        assert parameters(messages['en']) == parameters(messages['zh']), key


def test_platform_error_constructors_cannot_bypass_message_keys():
    root = Path(__file__).resolve().parents[2] / 'src/astrophotoflow'
    catalog = error_messages()['messages']
    failures = []
    for path in root.rglob('*.py'):
        if 'vendor' in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                values = {key.value: value for key, value in zip(node.keys, node.values)
                          if isinstance(key, ast.Constant)}
                if 'code' in values and isinstance(values.get('message'), (ast.Constant, ast.JoinedStr)):
                    failures.append(f'{path}:{node.lineno}: error message bypasses the catalog')
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(function):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                    continue
                name = node.func.id
                if name == 'localized_error' and len(node.args) >= 3 and isinstance(node.args[2], ast.Constant):
                    assert node.args[2].value in catalog, (path, node.lineno, node.args[2].value)
                if name in {'ApiError', 'IngestionError', 'ProxyError', '_binding_error', '_raise'}:
                    if not any(keyword.arg == 'message_key' for keyword in node.keywords):
                        failures.append(f'{path}:{node.lineno}: missing message_key')
                if name == 'ErrorDetail' and not (
                    path == root / 'core/localization.py' or
                    path == root / 'modules/data/science_inputs.py' and function.name == '_output_registration'
                ):
                    failures.append(f'{path}:{node.lineno}: use the localized constructor')
                for keyword in node.keywords:
                    if keyword.arg == 'message_key' and isinstance(keyword.value, ast.Constant):
                        assert keyword.value.value in catalog, (path, node.lineno, keyword.value.value)
    assert not failures, '\n'.join(failures)
