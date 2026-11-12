import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from watchfiles import Change

script = Path(__file__).resolve().parents[2] / "scripts/dev_frontend.py"
spec = importlib.util.spec_from_file_location("dev_frontend", script)
dev_frontend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dev_frontend)


def test_first_web_launch_installs_the_build_then_reuses_the_workspace(tmp_path, monkeypatch):
    config = tmp_path / "dev/config.toml"
    assets = tmp_path / "build"
    assets.mkdir()
    (assets / "index.html").touch()
    web_url = "http://127.0.0.1:1234"
    monkeypatch.setattr(dev_frontend, "FRONTEND_ASSETS", assets)
    status = Mock(return_value=SimpleNamespace(ready=False, state="stopped", web_url=None))
    monkeypatch.setattr(dev_frontend, "status", status)
    operations = Mock()
    operations.start.return_value = SimpleNamespace(state="completed", web_url=web_url)
    monkeypatch.setattr(dev_frontend, "initialize", operations.initialize)
    monkeypatch.setattr(dev_frontend, "start", operations.start)

    assert dev_frontend.ensure_workbench(config) == web_url
    assert [call[0] for call in operations.mock_calls] == ["initialize", "start"]
    operations.initialize.assert_called_once_with(config.parent, frontend_assets=assets, activate=False)
    operations.start.assert_called_once_with(config)

    status.return_value = SimpleNamespace(ready=True, state="running", web_url=web_url)
    operations.reset_mock()
    assert dev_frontend.ensure_workbench(config) == web_url
    assert operations.mock_calls == []


def test_web_refuses_to_initialize_without_a_build(tmp_path, monkeypatch):
    monkeypatch.setattr(dev_frontend, "FRONTEND_ASSETS", tmp_path / "missing")
    monkeypatch.setattr(dev_frontend, "status", lambda config: SimpleNamespace(ready=False, state="stopped"))
    initialize = Mock()
    monkeypatch.setattr(dev_frontend, "initialize", initialize)
    with pytest.raises(dev_frontend.WorkbenchError, match="pnpm build"):
        dev_frontend.ensure_workbench(tmp_path / "config.toml")
    initialize.assert_not_called()


def test_python_saves_respect_busy_guard_and_rebind_only_on_address_change(tmp_path, monkeypatch, capsys):
    config = tmp_path / "config.toml"
    original_url = "http://127.0.0.1:1234"
    changed_url = "http://127.0.0.1:1235"
    restart = Mock(side_effect=[
        SimpleNamespace(state="rejected", web_url=None, workspace=str(tmp_path), blockers=["busy"]),
        SimpleNamespace(state="completed", web_url=original_url),
        SimpleNamespace(state="completed", web_url=changed_url),
    ])
    monkeypatch.setattr(dev_frontend, "restart", restart)

    def watch(source, *, watch_filter, **kwargs):
        python = str(source / "module.py")
        assert watch_filter(Change.modified, python)
        assert not watch_filter(Change.modified, str(source / "config.json"))
        yield set()
        for _ in range(3):
            yield {(Change.modified, python)}
        yield set()

    monkeypatch.setattr(dev_frontend, "watch", watch)
    original_process = Mock()
    original_process.poll.return_value = None
    changed_process = Mock()
    changed_process.poll.return_value = 7
    popen = Mock(side_effect=[original_process, changed_process])
    monkeypatch.setattr(dev_frontend.subprocess, "Popen", popen)
    stop = Mock()
    monkeypatch.setattr(dev_frontend, "stop_vite", stop)

    assert dev_frontend.watch_workbench(config, ["vite"], original_url) == 7
    assert restart.call_count == 3
    assert [call.kwargs["env"]["DEV_SERVER_COMFYUI_URL"] for call in popen.call_args_list] == [original_url, changed_url]
    assert [call.args[0] for call in stop.call_args_list] == [original_process, changed_process]
    assert "busy" in capsys.readouterr().err
