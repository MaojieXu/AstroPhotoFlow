"""Shipped UI catalogs must cover every supported locale.

CI never runs the frontend vitest project or ``pnpm locale:check`` which both tolerate
strings still waiting for translation, so this guard keeps the state the product
promises: the web app ships English and Simplified Chinese and both are configured.
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LOCALES = ROOT / 'frontend/src/locales'
BUSINESS_UI_LOCALES = ROOT / 'frontend/packages/astrophotoflow-ui/src/core/locales'
SOURCE = 'en'
SHIPPED = ('en', 'zh')
CATALOGS = ('main.json', 'settings.json', 'commands.json', 'nodeDefs.json')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def leaves(value, prefix=''):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, f'{prefix}.{key}' if prefix else key)
        return
    yield prefix


def assert_same_keys(label, source, translated, locale):
    missing = sorted(set(source) - set(translated))
    stale = sorted(set(translated) - set(source))
    assert not missing, f'{locale}/{label} is missing {len(missing)} keys: {missing[:10]}'
    assert not stale, f'{locale}/{label} has {len(stale)} keys absent from {SOURCE}: {stale[:10]}'


@pytest.mark.parametrize('name', CATALOGS)
def test_native_catalog_covers_shipped_locales(name):
    source = set(leaves(load(LOCALES / SOURCE / name)))
    for locale in SHIPPED:
        if locale == SOURCE:
            continue
        assert_same_keys(name, source, set(leaves(load(LOCALES / locale / name))), locale)


def test_business_ui_messages_cover_shipped_locales():
    source = set(load(BUSINESS_UI_LOCALES / f'{SOURCE}.json'))
    for locale in SHIPPED:
        if locale == SOURCE:
            continue
        assert_same_keys(
            f'{locale}.json', source, set(load(BUSINESS_UI_LOCALES / f'{locale}.json')), locale
        )
