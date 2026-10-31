import json
from pathlib import Path
import shutil
import sys
import os

import psutil

from astrophotoflow.core.config import Settings
from astrophotoflow.modules.software import bundles, development, public


def _source(tmp_path, bundle_install, monkeypatch):
    settings = Settings('127.0.0.1', 8190, tmp_path / 'workspace/data', (), workspace=tmp_path / 'workspace')
    installed = bundle_install(settings)
    source = tmp_path / 'source'
    shutil.copytree(installed, source)
    (source / 'authored.json').write_text(json.dumps({'name': 'Source title'}))
    (source / 'development.json').write_text(json.dumps({'build': 'generate.py', 'watch': ['authored.json', 'generate.py', 'adapter/*.py']}))
    (source / 'generate.py').write_text('''import json
from pathlib import Path
root = Path(__file__).parent
manifest = json.loads((root / 'bundle.json').read_text())
path = root / manifest['nodes'][0]
value = json.loads(path.read_text())
value['name'] = json.loads((root / 'authored.json').read_text())['name']
path.write_text(json.dumps(value))
''')
    monkeypatch.setattr(development.subprocess, 'check_output', lambda command, **kwargs: 'a' * 40 if command[-2:] == ['rev-parse', 'HEAD'] else ' M authored.json')
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
    adapter.write_text('import runpy\nfrom pathlib import Path\nVALUE = runpy.run_path(str(Path(__file__).with_name("helper.py")))["VALUE"]\n')
    development.configure(settings.workspace, ['siril=' + str(source)], [], sys.executable)
    first = development.identity(settings.workspace, 'siril')
    old = bundles._adapter(str(adapter), first['fingerprint'], adapter.read_bytes())
    helper.write_text('VALUE = 2\n')
    development.refresh_sources(settings.workspace)
    development.refresh_sources(settings.workspace)
    second = development.identity(settings.workspace, 'siril')
    current = bundles._adapter(str(adapter), second['fingerprint'], adapter.read_bytes())
    assert second['fingerprint'] != first['fingerprint']
    assert old.VALUE == 1 and current.VALUE == 2


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
