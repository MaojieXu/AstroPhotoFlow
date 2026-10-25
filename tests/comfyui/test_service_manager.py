from pathlib import Path
import os

import pytest

from astrophotoflow.comfyui import proxy
from astrophotoflow.comfyui import service_manager as service_manager_module
from astrophotoflow.comfyui.service_manager import ServiceManager


class FakeProcess:
    def __init__(self, pid: int):
        self.pid = pid
        self.returncode = None
        self.waited = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.waited = True
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def terminate(self):
        self.returncode = 0

    def kill(self):
        self.returncode = -9


def config_file(path: Path, data_dir: Path, port: int = 8190) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (path.parent / "pyproject.toml").write_text("[project]\nname = \"test-service\"\n", encoding="utf-8")
    path.write_text(
        "[server]\nhost = \"127.0.0.1\"\n"
        f"port = {port}\n\n"
        "[storage]\n"
        f'data_dir = "{data_dir.as_posix()}"\n\n'
        "[comfyui]\n"
        'allowed_origins = ["http://127.0.0.1:8188"]\n',
        encoding="utf-8",
    )


@pytest.mark.parametrize("uv_from_path", [True, False])
def test_manager_launches_locked_uv_service_and_stops_owned_process(tmp_path, monkeypatch, uv_from_path):
    config = tmp_path / "config.toml"
    data_dir = tmp_path / "data"
    config_file(config, data_dir)
    monkeypatch.setattr(proxy, "CONFIG_PATH", config)
    if uv_from_path:
        expected_uv = "/usr/bin/uv"
        monkeypatch.setattr(service_manager_module.shutil, "which", lambda _name: expected_uv)
    else:
        expected_uv = tmp_path / ".local" / "bin" / "uv"
        expected_uv.parent.mkdir(parents=True)
        expected_uv.write_text("test uv executable", encoding="utf-8")
        expected_uv.chmod(0o755)
        monkeypatch.setattr(service_manager_module.shutil, "which", lambda _name: None)
        monkeypatch.setattr(service_manager_module.Path, "home", staticmethod(lambda: tmp_path))

    healthy = {"value": False}
    monkeypatch.setattr(
        service_manager_module,
        "_service_is_ready",
        lambda _upstream, _token: healthy["value"],
    )
    process = FakeProcess(1001)
    commands = []

    def popen(command, **kwargs):
        commands.append((command, kwargs))
        (data_dir / "service.token").write_text("test-token", encoding="utf-8")
        healthy["value"] = True
        return process

    monkeypatch.setattr(service_manager_module.subprocess, "Popen", popen)
    manager = ServiceManager(
        tmp_path,
        startup_timeout=1,
        health_interval=60,
    )
    terminated = []
    manager._terminate_process = lambda child: terminated.append(child)

    try:
        assert manager.start()
        assert len(commands) == 1
        command, kwargs = commands[0]
        assert command[:2] == [str(expected_uv), "run"]
        assert "--project" in command
        assert "--locked" in command
        assert "--no-sync" in command
        assert command[-2:] == ["apf-service", "serve"]
        assert kwargs["cwd"] == tmp_path
        assert kwargs["start_new_session"] is (os.name == "posix")
        manager.ensure_available()
    finally:
        manager.stop()

    assert terminated == [process]


def test_manager_reuses_authenticated_healthy_service_without_owning_it(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    data_dir = tmp_path / "data"
    config_file(config, data_dir)
    (data_dir / "service.token").write_text("existing-token", encoding="utf-8")
    monkeypatch.setattr(proxy, "CONFIG_PATH", config)
    monkeypatch.setattr(service_manager_module, "_service_is_ready", lambda _upstream, _token: True)

    def unexpected_popen(*_args, **_kwargs):
        pytest.fail("a healthy existing service must be reused")

    monkeypatch.setattr(service_manager_module.subprocess, "Popen", unexpected_popen)
    manager = ServiceManager(tmp_path, health_interval=60)
    manager._terminate_process = lambda _child: pytest.fail("an adopted service must not be stopped")

    try:
        assert manager.start()
        assert not manager._owns_process
        manager.ensure_available()
    finally:
        manager.stop()


def test_manager_surfaces_start_failure_without_raising_into_comfyui(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config_file(config, tmp_path / "data")
    monkeypatch.setattr(proxy, "CONFIG_PATH", config)
    monkeypatch.setattr(service_manager_module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(service_manager_module.Path, "home", staticmethod(lambda: tmp_path))

    manager = ServiceManager(tmp_path)
    assert not manager.start()
    with pytest.raises(proxy.ProxyError, match="未找到可运行的 uv"):
        manager.ensure_available()


def test_manager_restarts_unexpected_exit_only_once(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    data_dir = tmp_path / "data"
    config_file(config, data_dir)
    monkeypatch.setattr(proxy, "CONFIG_PATH", config)
    monkeypatch.setattr(service_manager_module.shutil, "which", lambda _name: "/usr/bin/uv")

    healthy = {"value": False}
    monkeypatch.setattr(
        service_manager_module,
        "_service_is_ready",
        lambda _upstream, _token: healthy["value"],
    )
    processes = []

    def popen(_command, **_kwargs):
        process = FakeProcess(2000 + len(processes))
        processes.append(process)
        (data_dir / "service.token").write_text("test-token", encoding="utf-8")
        healthy["value"] = True
        return process

    monkeypatch.setattr(service_manager_module.subprocess, "Popen", popen)
    manager = ServiceManager(tmp_path, startup_timeout=1, health_interval=60)
    manager._terminate_process = lambda _child: None

    try:
        assert manager.start()
        processes[0].returncode = 1
        healthy["value"] = False
        manager._monitor_once()
        assert len(processes) == 2
        assert manager._restart_count == 1
        assert manager._running

        processes[1].returncode = 1
        healthy["value"] = False
        manager._monitor_once()
        assert len(processes) == 2
        assert not manager._running
        with pytest.raises(proxy.ProxyError, match="再次退出"):
            manager.ensure_available()
    finally:
        manager.stop()


def test_manager_marks_repeated_health_failure_unavailable(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    data_dir = tmp_path / "data"
    config_file(config, data_dir)
    (data_dir / "service.token").write_text("existing-token", encoding="utf-8")
    monkeypatch.setattr(proxy, "CONFIG_PATH", config)
    healthy = {"value": True}
    monkeypatch.setattr(
        service_manager_module,
        "_service_is_ready",
        lambda _upstream, _token: healthy["value"],
    )
    monkeypatch.setattr(
        service_manager_module.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("healthy existing service must be reused"),
    )
    manager = ServiceManager(tmp_path, health_interval=60)
    try:
        assert manager.start()
        healthy["value"] = False
        manager._monitor_once()
        manager._monitor_once()
        manager._monitor_once()
        with pytest.raises(proxy.ProxyError, match="连续未通过健康检查"):
            manager.ensure_available()
    finally:
        manager.stop()
