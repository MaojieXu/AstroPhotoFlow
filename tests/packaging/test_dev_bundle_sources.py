import json
import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope='module')
def isolated_bundle_python(tmp_path_factory):
    import venv

    root = tmp_path_factory.mktemp('bundle-helper-interpreters')
    for name in ('launcher', 'private'):
        venv.EnvBuilder(with_pip=False).create(root / name)
    relative = 'Scripts/python.exe' if os.name == 'nt' else 'bin/python'
    launcher, private = (root / name / relative for name in ('launcher', 'private'))
    env = {key: value for key, value in os.environ.items() if key not in {'PYTHONPATH', 'PYTHONHOME'}}
    site = Path(subprocess.check_output([str(private), '-c', 'import sysconfig; print(sysconfig.get_path("purelib"))'],
                                      env=env, text=True).strip())
    package = site / 'astrophotoflow/modules/software'
    package.mkdir(parents=True)
    (package / 'development.py').write_text(
        'import json\nfrom pathlib import Path\nfrom types import SimpleNamespace\n'
        'def configure(workspace, sources, clear, python):\n'
        '    return {"configured": {"workspace":str(workspace), "sources":sources, "clear":clear, "python":python}}\n'
        'def bindings(workspace):\n'
        '    path=Path(workspace)/"existing.json"\n'
        '    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}\n'
        'def source_state(workspace, key):\n'
        '    return SimpleNamespace(model_dump=lambda **kwargs: bindings(workspace)[key])\n', encoding='utf-8')
    probe = subprocess.run([str(launcher), '-c', 'import astrophotoflow'], env=env, capture_output=True, text=True, check=False)
    assert probe.returncode != 0 and 'ModuleNotFoundError' in probe.stderr
    return launcher, private, env


@pytest.mark.parametrize('mode', ['none', 'bind', 'clear', 'existing'])
def test_bundle_helper_uses_real_private_subprocess_without_parent_imports(isolated_bundle_python, tmp_path, mode):
    launcher, private, env = isolated_bundle_python
    helper = Path(__file__).resolve().parents[2] / 'scripts/dev_bundle_sources.py'
    arguments = ['--workspace', str(tmp_path)]
    if mode == 'bind':
        arguments += ['--bundle-source', 'sample-tool=' + str(tmp_path / 'source with spaces')]
    elif mode == 'clear':
        arguments += ['--clear-bundle-source', 'sample-tool']
    elif mode == 'existing':
        (tmp_path / 'existing.json').write_text('{"sample-tool":{"state":"ready"}}', encoding='utf-8')
    driver = 'import subprocess,sys; raise SystemExit(subprocess.call(sys.argv[1:]))'
    result = subprocess.run([str(launcher), '-c', driver, str(private), str(helper), *arguments],
                            cwd=tmp_path, env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    if mode in {'bind', 'clear'}:
        assert Path(value['configured']['python']) == private
        assert value['configured']['workspace'] == str(tmp_path)
        assert value['configured']['sources'] == ([arguments[-1]] if mode == 'bind' else [])
        assert value['configured']['clear'] == (['sample-tool'] if mode == 'clear' else [])
    else:
        assert value == ({'sample-tool': {'state': 'ready'}} if mode == 'existing' else {})
