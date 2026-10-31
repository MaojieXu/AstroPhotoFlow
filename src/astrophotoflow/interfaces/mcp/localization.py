import json
from functools import lru_cache
from importlib.resources import files

from astrophotoflow.contracts.localization import Locale


@lru_cache(maxsize=1)
def chinese_descriptions() -> dict[str, str]:
    return json.loads(files('astrophotoflow.interfaces.mcp').joinpath('locales/zh.json').read_text(encoding='utf-8'))


def tool_description(locale: Locale, name: str) -> str | None:
    return chinese_descriptions()[name] if locale == 'zh' else None


def node_display(value: dict, locale: Locale) -> dict:
    display = value.get('display', {}).get(locale)
    return {**value, 'display': {locale: display}, 'help': display['help']} if display else value
