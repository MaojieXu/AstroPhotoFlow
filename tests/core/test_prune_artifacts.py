import importlib.util
import os
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/prune_artifacts.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prune_artifacts", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_candidates_and_apply_remove_only_old_scratch(tmp_path, monkeypatch):
    module = load_module()
    artifacts = tmp_path / ".artifacts"
    old_dir = artifacts / "tmp/old-probe"
    fresh_dir = artifacts / "tmp/fresh-probe"
    old_pytest = artifacts / "pytest-old"
    for path in (old_dir, fresh_dir, old_pytest):
        path.mkdir(parents=True)
    stale = time.time() - 8 * 86400
    os.utime(old_dir, (stale, stale))
    monkeypatch.setattr(module, "ARTIFACTS", artifacts)
    monkeypatch.setattr(module, "ROOT", tmp_path)

    names = [path.name for path, _reason, _size in module.candidates(time.time())]
    assert names == ["old-probe"]

    monkeypatch.setattr("sys.argv", ["prune_artifacts.py", "--apply"])
    assert module.main() == 0
    assert not old_dir.exists()
    assert fresh_dir.exists()
    assert old_pytest.exists()


def test_candidates_ignore_missing_artifacts(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "ARTIFACTS", tmp_path / "missing")
    assert module.candidates(time.time()) == []
    monkeypatch.setattr("sys.argv", ["prune_artifacts.py"])
    assert module.main() == 0
