import json
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from astrophotoflow.contracts.localization import Locale
from astrophotoflow.contracts.common import ErrorDetail
from astrophotoflow.core.config import ConfigurationError
from astrophotoflow.core.errors import ApiError


def normalize_locale(value: str | None) -> Locale:
    return 'zh' if value and value.lower().split('-')[0] == 'zh' else 'en'


def workspace_locale(workspace: Path) -> Locale:
    path = workspace / 'comfyui-user/default/comfy.settings.json'
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return 'en'
    except (OSError, ValueError) as exc:
        raise ConfigurationError('Cannot read the workspace language setting.') from exc
    if not isinstance(raw, dict) or ('Comfy.Locale' in raw and not isinstance(raw['Comfy.Locale'], str)):
        raise ConfigurationError('The workspace language setting is invalid.')
    return normalize_locale(raw.get('Comfy.Locale'))


@lru_cache(maxsize=1)
def error_messages() -> dict:
    return json.loads(files('astrophotoflow.core').joinpath('locales/errors.json').read_text(encoding='utf-8'))


def error_message(locale: Locale, code: str, key: str | None = None, parameters: dict | None = None) -> str:
    catalog = error_messages()
    selected = key or catalog['codes'].get(code, 'request_failed')
    values = {name: error_message(locale, value.code, value.message_key, value.message_params)
              if isinstance(value, ApiError) else value for name, value in (parameters or {}).items()}
    return catalog['messages'][selected][locale].format_map(values)


def localized_error(locale: Locale, code: str, message_key: str, *, parameters: dict | None = None,
                    fields: list[dict[str, str]] | None = None) -> ErrorDetail:
    """Render a newly produced platform error without changing its diagnostics."""
    return ErrorDetail(code=code, message=error_message(locale, code, message_key, parameters),
                       fields=list(fields or []))


def exception_error(locale: Locale, exc: Exception, *, code: str, message_key: str) -> ErrorDetail:
    """Keep API causes specific; separate unclassified external diagnostics."""
    if isinstance(exc, ApiError):
        fields = error_fields(locale, exc)
        if exc.message_key is None:
            fields.append({'path': 'diagnostic', 'message': exc.message})
        return localized_error(locale, exc.code, exc.message_key or message_key,
                               parameters=exc.message_params, fields=fields)
    return localized_error(locale, code, message_key,
                           fields=[{'path': 'diagnostic', 'message': str(exc)}])


def error_fields(locale: Locale, exc: ApiError) -> list[dict[str, str]]:
    """Translate authored field guidance only; raw diagnostics pass through."""
    return [{**item, 'message': error_message(locale, exc.code, exc.field_message_keys[item['path']])}
            if item['path'] in exc.field_message_keys else dict(item) for item in exc.fields]
