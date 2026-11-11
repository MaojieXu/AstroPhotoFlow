from astrophotoflow.modules.software.development import builder as development_builder
import json
from pathlib import Path
import shutil
import sys
import os

import psutil
import pytest
import subprocess

from astrophotoflow.core.config import Settings
from astrophotoflow.modules.software import bundles, development, public
from astrophotoflow.modules.software.bundles.loader import load_adapter


@pytest.mark.parametrize('develop', [False, True])
def test_installed_and_development_bundle_locales_use_the_same_reader(tmp_path, bundle_install, develop):
    settings = Settings('127.0.0.1', 0, tmp_path / 'data', (), workspace=tmp_path)
    installed = bundle_install(settings)
    manifest = json.loads((installed / 'bundle.json').read_text(encoding='utf-8'))
    expected = {}
    for filename in manifest['operations']:
        operation = json.loads((installed / filename).read_text(encoding='utf-8'))['operation']
        expected[operation['operation_id']] = {
            'name': '节点 ' + operation['operation_id'], 'description': '中文说明', 'help': '中文帮助', 'category': [],
            **{section: {field['name']: {'label': field['name'], 'description': ''} for field in operation[section]}
               for section in ('inputs', 'outputs', 'parameters')},
        }
    manifest['locales'] = {'zh': 'locales/zh.json'}
    (installed / 'locales').mkdir(exist_ok=True)
    (installed / 'locales/zh.json').write_text(json.dumps(expected, ensure_ascii=False), encoding='utf-8')
    (installed / 'bundle.json').write_text(json.dumps(manifest), encoding='utf-8')
    root = installed
    if develop:
        root = tmp_path / 'external-source'
        shutil.copytree(installed, root)
        development.configure(tmp_path, ['siril=' + str(root)], [], sys.executable)
    assert public.get_bundle_display(settings, 'siril')['zh'] == expected


def _source(tmp_path, bundle_install, monkeypatch):
    settings = Settings('127.0.0.1', 8190, tmp_path / 'workspace/data', (), workspace=tmp_path / 'workspace')
    installed = bundle_install(settings)
    source = tmp_path / 'source'
    shutil.copytree(installed, source)
    (source / '.git').mkdir()
    (source / 'authored.json').write_text(json.dumps({'name': 'Source title'}))
    (source / 'development.json').write_text(json.dumps({'build': 'generate', 'watch': ['authored.json']}))
    (source / 'generate.py').write_text('''import json
from pathlib import Path
root = Path(__file__).parent
manifest = json.loads((root / 'bundle.json').read_text())
path = root / manifest['nodes'][0]
value = json.loads(path.read_text())
value['name'] = json.loads((root / 'authored.json').read_text())['name']
path.write_text(json.dumps(value))
''')
    monkeypatch.setattr(development_builder.subprocess, 'check_output', lambda command, **kwargs: 'a' * 40 if command[-2:] == ['rev-parse', 'HEAD'] else ' M authored.json')
    return settings, installed, source


def test_binding_generates_and_restores_without_modifying_installed_bundle(tmp_path, bundle_install, monkeypatch):
    settings, installed, source = _source(tmp_path, bundle_install, monkeypatch)
    before = {path.relative_to(installed): path.read_bytes() for path in installed.rglob('*') if path.is_file()}
    development.configure(settings.workspace, ['siril=' + str(source)], [], sys.executable)
    state = development.source_state(settings.workspace, 'siril')
    assert isinstance(state.root, Path) and state.root == source
    assert state.state == 'ready' and state.dirty
    assert bundles.metadata(settings.workspace, 'siril')[2][0]['name'] == 'Source title'
    package = public.get_package(settings, 'siril')
    assert package.bundle_commit == 'fixture'
    assert package.development_source.head == 'a' * 40
    assert package.effective_bundle_commit == 'a' * 40
    development.configure(settings.workspace, [], ['siril'], sys.executable)
    assert development.source_state(settings.workspace, 'siril') is None
    assert development.source_root(settings.workspace, 'siril') == installed
    assert {path.relative_to(installed): path.read_bytes() for path in installed.rglob('*') if path.is_file()} == before


def test_failed_generation_blocks_use_and_recovers_on_author_change(tmp_path, bundle_install, monkeypatch):
    settings, _, source = _source(tmp_path, bundle_install, monkeypatch)
    development.configure(settings.workspace, ['siril=' + str(source)], [], sys.executable)
    original = (source / 'authored.json').read_bytes()
    (source / 'authored.json').write_text('{invalid')
    development.refresh_sources(settings.workspace)
    development.refresh_sources(settings.workspace)
    assert development.source_state(settings.workspace, 'siril').state == 'failed'
    assert public.get_package(settings, 'siril').effective_availability == 'not_ready'
    (source / 'authored.json').write_bytes(original)
    development.refresh_sources(settings.workspace)
    development.refresh_sources(settings.workspace)
    assert development.source_state(settings.workspace, 'siril').state == 'ready'


def test_helper_changes_invalidate_adapter_cache_and_source_fingerprint(tmp_path, bundle_install, monkeypatch):
    settings, _, source = _source(tmp_path, bundle_install, monkeypatch)
    helper = source / 'adapter/helper.py'
    helper.write_text('VALUE = 1\n')
    adapter = source / 'adapter/siril.py'
    adapter.write_text('from .helper import VALUE\n')
    development.configure(settings.workspace, ['siril=' + str(source)], [], sys.executable)
    first = development.identity(settings.workspace, 'siril')
    old = load_adapter(source, 'adapter/siril.py', first['fingerprint'])
    def unexpected_generation(*args, **kwargs):
        pytest.fail('An adapter-only edit must not run the generator.')
    monkeypatch.setattr(development_builder.subprocess, 'run', unexpected_generation)
    helper.write_text('VALUE = 2\n')
    development.refresh_sources(settings.workspace)
    second = development.identity(settings.workspace, 'siril')
    current = load_adapter(source, 'adapter/siril.py', second['fingerprint'])
    assert second['fingerprint'] != first['fingerprint']
    assert old.VALUE == 1 and current.VALUE == 2

    helper.write_text('VALUE =\n')
    development.refresh_sources(settings.workspace)
    assert development.source_state(settings.workspace, 'siril').state == 'failed'
    helper.write_text('VALUE = 3\n')
    development.refresh_sources(settings.workspace)
    assert development.source_state(settings.workspace, 'siril').state == 'ready'


def test_repository_discovery_adopts_new_ids_and_reports_conflicts(tmp_path, bundle_install):
    workspace = tmp_path / 'workspace'
    settings = Settings('127.0.0.1', 8190, workspace / 'data', (), workspace=workspace)
    installed = bundle_install(settings)
    repository = tmp_path / 'bundles'
    assert development.configure(workspace, [], [], sys.executable, repository=repository) == {}

    checkout = repository / 'checkout with spaces'
    checkout.mkdir()
    development.refresh_sources(workspace)
    assert development.bindings(workspace) == {}
    shutil.copytree(installed, checkout, dirs_exist_ok=True)
    manifest_path = checkout / 'bundle.json'
    manifest = json.loads(manifest_path.read_bytes())
    manifest.update(package_id='sample-tool', name='Sample Tool')
    manifest_path.write_text(json.dumps(manifest))
    for relative in manifest['operations']:
        path = checkout / relative
        value = json.loads(path.read_bytes())
        value['operation']['package_id'] = 'sample-tool'
        path.write_text(json.dumps(value))
    for relative in manifest['nodes']:
        path = checkout / relative
        value = json.loads(path.read_bytes())
        value['execution']['package_id'] = 'sample-tool'
        path.write_text(json.dumps(value))

    development.refresh_sources(workspace)
    assert development.source_state(workspace, 'sample-tool').state == 'ready'
    package = public.get_package(settings, 'sample-tool')
    assert (package.name, package.available_versions, package.installed_version) == ('Sample Tool', [], None)
    assert public.list_releases(settings, 'sample-tool').releases == []

    duplicate = repository / 'duplicate'
    duplicate.mkdir()
    duplicate_manifest = duplicate / 'bundle.json'
    duplicate_manifest.write_bytes(manifest_path.read_bytes())
    development.refresh_sources(workspace)
    conflict = development.source_state(workspace, 'sample-tool')
    assert conflict.state == 'failed'
    assert str(duplicate) in conflict.error and str(checkout) in conflict.error
    duplicate_manifest.unlink()
    duplicate.rmdir()
    development.refresh_sources(workspace)
    assert development.source_state(workspace, 'sample-tool').state == 'ready'

    manifest_path.write_text('{broken')
    development.refresh_sources(workspace)
    assert development.source_state(workspace, 'sample-tool').state == 'failed'
    manifest_path.write_text(json.dumps(manifest))
    development.refresh_sources(workspace)
    assert development.source_state(workspace, 'sample-tool').state == 'ready'

    development.configure(workspace, [], [], sys.executable, clear_repository=True)
    assert public.list_package_ids(workspace) == ['siril']
    assert manifest_path.is_file()


def test_only_the_current_source_observation_controls_native_readiness(tmp_path, bundle_install, monkeypatch):
    settings, _, source = _source(tmp_path, bundle_install, monkeypatch)
    development.configure(settings.workspace, ['siril=' + str(source)], [], sys.executable)
    state = development.source_state(settings.workspace, 'siril')
    observation = development.observation_path(settings.workspace, 'siril')
    values = {'pid': os.getpid(), 'create_time': psutil.Process().create_time(), 'root': str(source),
              'fingerprint': 'previous', 'ready': False, 'reason': 'Previous generation failed'}
    observation.write_text(json.dumps(values))
    assert public.get_package(settings, 'siril').development_source.state == 'building'
    values['fingerprint'] = state.fingerprint
    observation.write_text(json.dumps(values))
    assert public.get_package(settings, 'siril').development_source.state == 'failed'
    values.update(ready=True, reason=None)
    observation.write_text(json.dumps(values))
    assert public.get_package(settings, 'siril').development_source.state == 'ready'


@pytest.mark.parametrize('failure', [subprocess.TimeoutExpired('generate', 120), OSError('cannot start')])
def test_generation_exception_stays_failed_until_author_change(tmp_path, bundle_install, monkeypatch, failure):
    settings, _, source = _source(tmp_path, bundle_install, monkeypatch)
    development.configure(settings.workspace, ['siril=' + str(source)], [], sys.executable)
    (source / 'authored.json').write_text(json.dumps({'name': 'Changed'}))
    original_run = development_builder.subprocess.run
    def fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr(development_builder.subprocess, 'run', fail)
    development.refresh_sources(settings.workspace)
    development.refresh_sources(settings.workspace)
    assert development.source_state(settings.workspace, 'siril').state == 'failed'
    monkeypatch.setattr(development_builder.subprocess, 'run', original_run)
    development.refresh_sources(settings.workspace)
    assert development.source_state(settings.workspace, 'siril').state == 'failed'
    (source / 'authored.json').write_text(json.dumps({'name': 'Fixed'}))
    development.refresh_sources(settings.workspace)
    development.refresh_sources(settings.workspace)
    assert development.source_state(settings.workspace, 'siril').state == 'ready'
