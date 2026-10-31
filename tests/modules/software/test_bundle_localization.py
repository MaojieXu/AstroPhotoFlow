import json

import pytest

from astrophotoflow.contracts.bundles import BundleManifest
from astrophotoflow.modules.software.bundles import operation_from_entry
from astrophotoflow.modules.software.metadata import catalog, read_bundle_locales


def test_display_changes_preserve_operation_identity_and_legacy_fallback(tmp_path):
    release = catalog()['siril']
    manifest = BundleManifest.model_validate(release['manifest'])
    entries = release['operations']
    assert read_bundle_locales(tmp_path, manifest.model_copy(update={'locales': {}}), entries) == {}
    path = tmp_path / 'en.json'
    translated = {}
    for entry in entries:
        operation = entry['operation']
        translated[operation['operation_id']] = {
            'name': 'Display title', 'description': 'Display description', 'help': 'Help',
            **{section: {item['name']: {'label': item['name'], 'description': 'Hint'} for item in operation[section]}
               for section in ('parameters', 'inputs', 'outputs')}
        }
    path.write_text(json.dumps(translated), encoding='utf-8')
    localized = manifest.model_copy(update={'locales': {'en': 'en.json'}})
    token = operation_from_entry(entries[0], True, None).content_token
    first = read_bundle_locales(tmp_path, localized, entries)
    identity = entries[0]['operation']['operation_id']
    translated[identity]['name'] = 'Another display title'
    path.write_text(json.dumps(translated), encoding='utf-8')
    assert read_bundle_locales(tmp_path, localized, entries) != first
    assert operation_from_entry(entries[0], True, None).content_token == token
    translated[identity]['parameters']['unknown'] = {'label': 'Unknown'}
    path.write_text(json.dumps(translated), encoding='utf-8')
    with pytest.raises(ValueError, match='parameters'):
        read_bundle_locales(tmp_path, localized, entries)
