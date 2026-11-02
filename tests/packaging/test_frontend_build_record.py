import importlib.util
import json
from pathlib import Path


def test_reuse_requires_unchanged_inputs_and_output(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'scripts/frontend_build_record.py'
    spec = importlib.util.spec_from_file_location('frontend_build_record_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assets = tmp_path / 'assets'
    assets.mkdir()
    (assets / 'index.html').write_text('first', encoding='utf-8')
    (assets / 'build-manifest.json').write_text(json.dumps({'commit': 'abc', 'distribution': 'localhost'}))
    state = {'files': 'first'}
    monkeypatch.setattr(module, 'inputs', lambda *args: dict(state))
    (assets / 'build-record.json').write_text(json.dumps({'inputs': state, 'output': module.output_digest(assets)}))
    assert module.matches(assets, tmp_path, 'abc', 'node', 'pnpm', {})
    state['files'] = 'changed'
    assert not module.matches(assets, tmp_path, 'abc', 'node', 'pnpm', {})
    state['files'] = 'first'
    (assets / 'index.html').write_text('changed', encoding='utf-8')
    assert not module.matches(assets, tmp_path, 'abc', 'node', 'pnpm', {})
    assert not module.matches(assets, tmp_path, 'other', 'node', 'pnpm', {})
