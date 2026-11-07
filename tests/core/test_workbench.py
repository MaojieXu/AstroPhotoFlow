from __future__ import annotations

import hashlib
import json
import logging.config
import os
import subprocess
import sys
import zipfile
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import psutil
import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from astrophotoflow.contracts.workbench import ProcessInfo, WorkbenchState
from astrophotoflow.core import config as app_config
from astrophotoflow.core import workbench
from astrophotoflow.core.database.schema import database_lock, upgrade_database
from astrophotoflow.core.workbench import constants as wb_constants
from astrophotoflow.core.workbench import control as wb_control
from astrophotoflow.core.workbench import errors as wb_errors
from astrophotoflow.core.workbench import observations as wb_observations
from astrophotoflow.core.workbench import operations as wb_operations
from astrophotoflow.core.workbench import paths as wb_paths
from astrophotoflow.core.workbench import processes as wb_processes
from astrophotoflow.core.workbench import runtime as wb_runtime
from astrophotoflow.core.workbench import state as wb_state
from astrophotoflow.core.workbench import workspaces as wb_workspaces
from astrophotoflow.interfaces.http.app import create_app


@pytest.fixture(autouse=True)
def isolated_default(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "CONFIG_PATH", tmp_path / "user/config.toml")
    monkeypatch.delenv("APF_WORKSPACE", raising=False)
    monkeypatch.delenv("ASTROPHOTOFLOW_CONFIG", raising=False)
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "cache"))


def test_initialize_copies_native_web_and_start_uses_builtin_gateway(tmp_path, monkeypatch):
    package = tmp_path / "package"
    vendor = package / "vendor"
    web = package / "web"
    vendor.mkdir(parents=True)
    (vendor / "comfyui-0.42.0-windows-py312.lock").write_text("numpy==2.4.6\n", encoding="utf-8")
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("AstroPhotoFlow", encoding="utf-8")
    (web / "assets/app.js").write_text("native", encoding="utf-8")
    archive_path = vendor / "comfyui-0.42.0.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("ComfyUI/main.py", "")
        archive.writestr("ComfyUI/requirements.txt", "")
    (vendor / "comfyui-source.json").write_text(
        json.dumps({"commit": wb_constants.COMFY_COMMIT, "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(), "comfyui_version": "0.42.0"}),
        encoding="utf-8",
    )

    runtime = tmp_path / "runtime"
    monkeypatch.setattr(wb_paths, "package_directory", lambda: Path(package / "core" / "workbench.py").parents[1])
    monkeypatch.setattr(wb_paths, 'runtime_dir', lambda: runtime)
    monkeypatch.setattr(wb_runtime, 'uv_executable', lambda: "uv")
    monkeypatch.setattr(wb_runtime, 'run_command', lambda command, env=None: None)
    monkeypatch.setattr(wb_runtime, 'probe_python',
                        lambda python, *, timeout=120: {"version": "3.12.15", "base_prefix": str(tmp_path / "managed"), "torch": "2.14.1+cpu"})
    monkeypatch.setattr(app_config, "CONFIG_PATH", tmp_path / "user/config.toml")

    workspace = tmp_path / "workspace"
    config_path = wb_workspaces.initialize(workspace, service_port=18190, comfyui_port=18188)
    assert app_config.resolve_config_path() == config_path
    assert not (app_config.CONFIG_PATH.parent / "active-workspace").exists()
    assert (workspace / "web/index.html").read_text(encoding="utf-8") == "AstroPhotoFlow"
    assert (workspace / "web/assets/app.js").is_file()
    assert not (workspace / "comfyui-data/custom_nodes/AstroPhotoFlow").exists()
    runtime_python = runtime / "comfyui-env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    runtime_python.parent.mkdir(parents=True, exist_ok=True)
    runtime_python.touch()
    activations = []
    monkeypatch.setattr(wb_workspaces, 'activate_workspace', lambda config_path: activations.append(config_path))
    monkeypatch.setattr(wb_runtime, 'run_command', lambda *args, **kwargs: pytest.fail("reuse must not reinstall CPU dependencies"))
    templates = workspace / "comfyui-user/default/comfy.templates.json"
    templates.write_text('[{"name":"saved","data":"graph"}]', encoding="utf-8")
    wb_workspaces.initialize(workspace, reuse_runtime=True, activate=False)
    assert json.loads(templates.read_text(encoding="utf-8"))[0]["name"] == "saved"
    assert (workspace / "comfyui-user/default/workflows").is_dir()
    assert (workspace / "comfyui-user/default/subgraphs").is_dir()
    second_workspace = tmp_path / "second-workspace"
    wb_workspaces.initialize(second_workspace, service_port=18290, comfyui_port=18288,
                         reuse_runtime=True, activate=False)
    assert (second_workspace / "web/assets/app.js").is_file()
    assert activations == []

    commands = []

    class FakeProcess:
        pid = 12345

        def poll(self):
            return None

    monkeypatch.setattr(wb_processes, 'port_available', lambda host, port: port != 18190)
    monkeypatch.setattr(wb_observations, 'service_healthy', lambda path: True)
    monkeypatch.setattr(wb_processes, 'launch_process', lambda command, cwd, env, log_path: (commands.append(command) or FakeProcess()))
    monkeypatch.setattr(wb_processes, 'record_process', lambda process, role, cwd, command: {
        "role": role, "command": command, "pid": process.pid, "create_time": 1.0, "executable": command[0],
        "workspace": str(cwd), "started_at": datetime.now(timezone.utc).isoformat()})
    monkeypatch.setattr(wb_observations, 'web_healthy', lambda url, workspace: True)

    result = wb_control.start(config_path)
    assert result.state == "completed" and result.web_url == "http://127.0.0.1:18188"
    assert activations == []
    assert commands[0][1:] == ["-m", "astrophotoflow.interfaces.http.cli", "serve"]
    assert commands[1][commands[1].index("--base-directory") + 1] == str(workspace / "comfyui-data")
    assert commands[1][commands[1].index("--front-end-root") + 1] == str(workspace / "web")
    assert "--disable-all-custom-nodes" in commands[1]
    record = json.loads((workspace / "run/processes.json").read_text(encoding="utf-8"))
    assert record["actual_ports"] == {"service": 18191, "web": 18188}
    assert (workspace / "config.toml").read_text(encoding="utf-8").count("port = 18190") == 1


def test_create_workspace_needs_no_runtime_or_frontend_and_keeps_default(tmp_path, monkeypatch):
    monkeypatch.setattr(wb_runtime, 'prepare_runtime', lambda **kwargs: pytest.fail("workspace creation must not install software"))
    workspace = tmp_path / "empty"
    config = wb_workspaces.create_workspace(workspace, service_port=18190, comfyui_port=18188)
    assert config == workspace / "config.toml"
    assert app_config.load_settings(config).workspace == workspace
    assert (workspace / "comfyui-user/default/workflows").is_dir()
    assert not (workspace / "data/service.token").exists()
    assert not (workspace / "data/astrophotoflow.sqlite3").exists()
    assert not app_config.CONFIG_PATH.exists()


def test_runtime_receipt_skips_install_and_failed_update_cannot_be_reused(tmp_path, monkeypatch):
    vendor = tmp_path / "package/vendor"
    vendor.mkdir(parents=True)
    archive = vendor / "comfyui-0.42.0.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("ComfyUI/main.py", "")
        bundle.writestr("ComfyUI/requirements.txt", "numpy\n")
    manifest = {"commit": wb_constants.COMFY_COMMIT, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
    (vendor / "comfyui-source.json").write_text(json.dumps(manifest), encoding="utf-8")
    lock = vendor / "comfyui-0.42.0-windows-py312.lock"
    lock.write_text("numpy==2.4.6\n", encoding="utf-8")
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(wb_paths, "package_directory", lambda: Path(vendor.parent / "core/workbench.py").parents[1])
    monkeypatch.setattr(wb_paths, 'runtime_dir', lambda: runtime)
    monkeypatch.setattr(wb_runtime, 'uv_executable', lambda: "uv")
    commands = []

    def install(command, env=None):
        commands.append(command)
        python = runtime / "comfyui-env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        python.parent.mkdir(parents=True, exist_ok=True)
        python.touch()

    probes = []

    def probe(python, *, timeout=120):
        probes.append(python)
        return {"version": "3.12.15", "base_prefix": str(tmp_path / "managed"), "torch": "2.14.1+cpu"}

    monkeypatch.setattr(wb_runtime, 'probe_python', probe)
    monkeypatch.setattr(wb_runtime, 'run_command', install)
    assert wb_runtime.prepare_runtime()["reused"] is False
    if os.name == "nt":
        assert any(command[1:3] == ["python", "install"] and "--no-registry" in command for command in commands)
    count = len(commands)
    assert wb_runtime.prepare_runtime()["reused"] is True
    assert len(commands) == count
    receipt = runtime / ".apf-runtime.json"
    saved = json.loads(receipt.read_text(encoding="utf-8"))
    assert saved["python"]["torch"] == "2.14.1+cpu"
    assert probes and probes[0] == runtime / "comfyui-env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    saved["fingerprint"]["archive_sha256"] = "outdated"
    receipt.write_text(json.dumps(saved), encoding="utf-8")

    def fail(command, env=None):
        raise wb_errors.WorkbenchError("installation interrupted")

    monkeypatch.setattr(wb_runtime, 'run_command', fail)
    with pytest.raises(wb_errors.WorkbenchError, match="interrupted"):
        wb_runtime.prepare_runtime()
    assert not receipt.exists()
    with pytest.raises(wb_errors.WorkbenchError, match="未准备完成"):
        wb_runtime.prepare_runtime(reuse_only=True)


def test_runtime_reuse_requires_a_runnable_embedded_python(tmp_path, monkeypatch):
    vendor = tmp_path / "package/vendor"
    vendor.mkdir(parents=True)
    archive = vendor / "comfyui-0.42.0.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("ComfyUI/main.py", "")
        bundle.writestr("ComfyUI/requirements.txt", "numpy\n")
    manifest = {"commit": wb_constants.COMFY_COMMIT, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
    (vendor / "comfyui-source.json").write_text(json.dumps(manifest), encoding="utf-8")
    (vendor / "comfyui-0.42.0-windows-py312.lock").write_text("numpy==2.4.6\n", encoding="utf-8")
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(wb_paths, "package_directory", lambda: Path(vendor.parent / "core/workbench.py").parents[1])
    monkeypatch.setattr(wb_paths, "runtime_dir", lambda: runtime)
    monkeypatch.setattr(wb_runtime, "uv_executable", lambda: "uv")

    def install(command, env=None):
        python = runtime / "comfyui-env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        python.parent.mkdir(parents=True, exist_ok=True)
        python.touch()

    monkeypatch.setattr(wb_runtime, "run_command", install)
    working = {"version": "3.12.15", "base_prefix": str(tmp_path / "managed"), "torch": "2.14.1+cpu"}
    monkeypatch.setattr(wb_runtime, "probe_python", lambda python, *, timeout=120: dict(working))
    assert wb_runtime.prepare_runtime()["reused"] is False
    assert wb_runtime.prepare_runtime()["reused"] is True
    monkeypatch.setattr(wb_runtime, "probe_python", lambda python, *, timeout=120: None)
    with pytest.raises(wb_errors.WorkbenchError, match="未准备完成"):
        wb_runtime.prepare_runtime(reuse_only=True)
    with pytest.raises(wb_errors.WorkbenchError, match="无法运行"):
        wb_runtime.prepare_runtime()


def test_workspace_native_web_assets_are_complete_and_isolated(tmp_path, monkeypatch):
    package = tmp_path / "package"
    monkeypatch.setattr(wb_paths, "package_directory", lambda: Path(package / "core" / "workbench.py").parents[1])
    assets = tmp_path / "build"
    assets.mkdir()
    (assets / "chunks").mkdir()
    for name in ("index.html", "chunks/app.js", "chunks/app.css"):
        (assets / name).write_text("first", encoding="utf-8")
    first = wb_runtime.install_frontend(tmp_path / "first", assets)
    for name in ("index.html", "chunks/app.js", "chunks/app.css"):
        (assets / name).write_text("second", encoding="utf-8")
    second = wb_runtime.install_frontend(tmp_path / "second", assets)
    assert (first / "chunks/app.js").read_text(encoding="utf-8") == "first"
    assert (second / "chunks/app.js").read_text(encoding="utf-8") == "second"
    assert (first / "index.html").is_file() and (second / "chunks/app.css").is_file()
    assert first != second


@pytest.mark.parametrize("role", ["comfyui", "asset-service"])
def test_stop_terminates_legacy_children_before_clearing_process_state(tmp_path, monkeypatch, role):
    (tmp_path / "run").mkdir()
    state = tmp_path / "run/processes.json"
    state.write_text(json.dumps({"processes": [{"pid": 1, "role": role, "command": ["python", "main.py"]}]}), encoding="utf-8")
    terminated = []

    class Process:
        def __init__(self, pid):
            self.pid = pid
            self.running = True

        def children(self, recursive=False):
            return [child]

        def environ(self):
            return {"APF_WORKSPACE": str(tmp_path)}

        def terminate(self):
            self.running = False
            terminated.append(self.pid)

        def wait(self, timeout=None):
            return 0

    parent, child = Process(1), Process(2)
    monkeypatch.setattr(wb_processes, 'identify_process', lambda record: parent)
    monkeypatch.setattr(
        psutil, "wait_procs",
        lambda processes, timeout: ([p for p in processes if not p.running], [p for p in processes if p.running]),
    )
    wb_control.stop(tmp_path / "config.toml")
    assert terminated == [2, 1]
    assert not parent.running and not child.running
    assert json.loads(state.read_text(encoding="utf-8"))["processes"] == []


def test_stop_waits_for_domain_service_before_clearing_state(tmp_path, monkeypatch):
    (tmp_path / "run").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "data/service.token").write_text("private-token", encoding="utf-8")
    config = tmp_path / "config.toml"
    config.write_text('[server]\nhost="127.0.0.1"\nport=8190\n[storage]\ndata_dir="data"\n'
                      '[comfyui]\nallowed_origins=["http://127.0.0.1:8188"]\n', encoding="utf-8")
    state = tmp_path / "run/processes.json"
    state.write_text(json.dumps({"workspace": str(tmp_path), "config_path": str(config),
        "effective_settings": app_config.get_configuration(config).saved.model_dump(), "processes": [
        {"pid": 1, "role": "asset-service", "command": ["python", "serve"]},
        {"pid": 2, "role": "comfyui", "command": ["python", "main.py", "--front-end-root", "web"]},
    ]}), encoding="utf-8")
    calls = []

    class ServiceProcess:
        def wait(self, timeout):
            assert json.loads(state.read_text(encoding="utf-8"))["processes"]
            calls.append("drained")

    def shutdown(url, *, headers, timeout):
        assert url == "http://127.0.0.1:8190/internal/shutdown"
        assert headers == {"Authorization": "Bearer private-token"}
        calls.append("requested")
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(wb_processes, 'identify_process', lambda record: ServiceProcess() if record["role"] == "asset-service" else None)
    monkeypatch.setattr(httpx, "post", shutdown)
    wb_control.stop(config)
    assert calls == ["requested", "drained"]
    assert json.loads(state.read_text(encoding="utf-8"))["processes"] == []


@pytest.mark.parametrize("drain_times_out", [False, True])
def test_native_start_failure_drains_ready_domain_and_preserves_it_until_confirmed(tmp_path, monkeypatch, drain_times_out):
    # The schema setup must not replace pytest's logging configuration.
    monkeypatch.setattr(logging.config, "fileConfig", lambda *args, **kwargs: None)
    config = write_workspace(tmp_path / "workspace")
    workspace = config.parent
    (workspace / "web").mkdir()
    (workspace / "web/index.html").write_text("AstroPhotoFlow", encoding="utf-8")
    (workspace / "data").mkdir()
    (workspace / "data/service.token").write_text("test-token", encoding="utf-8")
    calls = []
    clients = []

    class DomainProcess:
        pid = 123456
        waits = 0

        def poll(self):
            return None

        def wait(self, timeout):
            assert wb_state.read_state(workspace)["processes"]
            calls.append("wait")
            self.waits += 1
            if drain_times_out and self.waits == 1:
                raise psutil.TimeoutExpired(timeout, pid=self.pid)

        def terminate(self):
            pytest.fail("a ready domain service must drain, not be terminated")

        def kill(self):
            pytest.fail("a ready domain service must drain, not be killed")

    domain = DomainProcess()
    with ExitStack() as resources:
        def launch(command, cwd, env, log_path):
            if not clients:
                adopted = app_config.load_running_settings(workspace)
                with database_lock(adopted):
                    upgrade_database(adopted)
                app = create_app(adopted, "test-token")
                app.state.shutdown = lambda: calls.append("shutdown")
                clients.append(resources.enter_context(TestClient(app)))
                return domain
            response = clients[0].post(
                "/api/v1/uploads", headers={"Authorization": "Bearer test-token"},
                json={"files": [{"name": "accepted-during-start.png", "size": 10}]},
            )
            assert response.status_code == 202, response.text
            calls.append("accepted-upload")
            assert wb_state.recent_result(workspace).state == "in_progress"
            raise OSError("native process launch failed")

        monkeypatch.setattr(wb_processes, 'launch_process', launch)
        monkeypatch.setattr(wb_processes, 'port_available', lambda host, port: True)
        monkeypatch.setattr(wb_processes, 'identify_process', lambda record: domain if record["role"] == "asset-service" else None)
        monkeypatch.setattr(wb_processes, 'record_process', lambda child, role, target, command: {
            "pid": child.pid, "role": role, "command": command, "create_time": 1.0, "executable": command[0],
            "workspace": str(target), "started_at": datetime.now(timezone.utc).isoformat(),
        })
        monkeypatch.setattr(wb_observations, 'service_healthy', lambda target: clients[0].get(
            "/api/v1/health", headers={"Authorization": "Bearer test-token"}).status_code == 200)
        monkeypatch.setattr(httpx, "post", lambda url, *, headers, timeout: (
            calls.append("shutdown-request") or clients[0].post("/internal/shutdown", headers=headers)
        ))

        with pytest.raises(wb_errors.WorkbenchError, match="native process launch") as failure:
            wb_control.start(config)

        assert calls[:3] == ["accepted-upload", "shutdown-request", "shutdown"]
        assert calls[3] == "wait"
        processes = wb_state.read_state(workspace)["processes"]
        if drain_times_out:
            assert "启动失败后的停止未完成" in str(failure.value)
            assert "导入或预览仍在排空" in str(failure.value)
            assert [item["role"] for item in processes] == ["asset-service"]
            assert wb_state.recent_result(workspace).state == "failed"
            assert wb_control.stop(config).state == "completed"
            assert [item["role"] for item in wb_state.read_state(workspace)["processes"]] == []
            assert calls.count("shutdown-request") == 2
            assert calls.count("wait") == 2
        else:
            assert processes == []
            assert wb_state.recent_result(workspace).state == "failed"
            assert calls.count("shutdown-request") == 1
            assert calls.count("wait") == 1



@pytest.mark.parametrize("identity_failure", ["os", "psutil"])
def test_unrecorded_domain_is_retained_when_drain_times_out(tmp_path, monkeypatch, identity_failure):
    config = write_workspace(tmp_path / "workspace")
    workspace = config.parent
    (workspace / "web").mkdir()
    (workspace / "web/index.html").write_text("AstroPhotoFlow", encoding="utf-8")
    (workspace / "data").mkdir()
    (workspace / "data/service.token").write_text("test-token", encoding="utf-8")
    calls = []

    class DomainProcess:
        pid = 123456
        running = True
        waits = 0

        def poll(self):
            return None if self.running else 0

        def wait(self, timeout):
            calls.append("wait")
            self.waits += 1
            if self.waits == 1:
                pending = json.loads(wb_state.control_record_path(workspace).read_text(encoding="utf-8"))["pending_process"]
                assert pending["pid"] == self.pid and pending["launch_started"] <= pending["launch_finished"]
                raise subprocess.TimeoutExpired("asset-service", timeout)
            self.running = False

        def terminate(self):
            pytest.fail("an unrecorded domain service must still drain")

        def kill(self):
            pytest.fail("an unrecorded domain service must still drain")

    domain = DomainProcess()
    record_attempts = []

    def record(child, role, target, command):
        record_attempts.append(role)
        if len(record_attempts) == 1:
            if identity_failure == "os":
                raise OSError("identity read failed")
            raise psutil.AccessDenied(pid=child.pid)
        return {"pid": child.pid, "role": role, "command": command, "create_time": 1.0,
                "executable": command[0], "workspace": str(target), "started_at": datetime.now(timezone.utc).isoformat()}

    def shutdown(url, *, headers, timeout):
        calls.append("shutdown")
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(wb_processes, 'launch_process', lambda *args: domain)
    monkeypatch.setattr(wb_processes, 'record_process', record)
    monkeypatch.setattr(wb_processes, 'port_available', lambda host, port: True)
    monkeypatch.setattr(wb_processes, 'identify_process', lambda item: domain if domain.running else None)
    monkeypatch.setattr(httpx, "post", shutdown)

    with pytest.raises(wb_errors.WorkbenchError, match="排空"):
        wb_control.start(config)
    assert wb_state.read_state(workspace)["processes"] == []
    control = json.loads(wb_state.control_record_path(workspace).read_text(encoding="utf-8"))
    assert control["pending_process"]["pid"] == domain.pid
    assert control["pending_process"]["create_time"] == 1.0
    assert wb_observations.status(config).state == "unknown"
    assert wb_control.stop(config).state == "completed"
    assert calls == ["shutdown", "wait", "shutdown", "wait"]
    assert wb_observations.status(config).state == "stopped"


def test_unrecorded_domain_with_unknown_identity_cannot_report_stopped(tmp_path, monkeypatch):
    config = write_workspace(tmp_path / "workspace")
    workspace = config.parent
    (workspace / "web").mkdir()
    (workspace / "web/index.html").write_text("AstroPhotoFlow", encoding="utf-8")
    (workspace / "data").mkdir()
    (workspace / "data/service.token").write_text("test-token", encoding="utf-8")

    class DomainProcess:
        pid = 123456
        running = True
        metadata_allowed = False
        waits = 0
        birth = 0.0
        command = []

        def poll(self):
            return None if self.running else 0

        def create_time(self):
            if not self.metadata_allowed:
                raise psutil.AccessDenied(pid=self.pid)
            return self.birth

        def exe(self):
            return self.command[0]

        def cmdline(self):
            return self.command

        def environ(self):
            return {"APF_WORKSPACE": str(workspace)}

        def is_running(self):
            return self.running

        def wait(self, timeout):
            self.waits += 1
            if self.waits == 1:
                raise subprocess.TimeoutExpired("asset-service", timeout)
            self.running = False

        def terminate(self):
            pytest.fail("an unrecorded domain service must still drain")

    domain = DomainProcess()
    process = psutil.Process

    def lookup(pid=None):
        if pid == domain.pid:
            if domain.running:
                return domain
            raise psutil.NoSuchProcess(pid)
        return process() if pid is None else process(pid)

    def cannot_record(*args):
        raise OSError("identity unavailable")

    monkeypatch.setattr(wb_processes, 'launch_process', lambda *args: domain)
    monkeypatch.setattr(wb_processes, 'record_process', cannot_record)
    monkeypatch.setattr(wb_processes, 'port_available', lambda host, port: True)
    monkeypatch.setattr(httpx, "post", lambda url, **kwargs: httpx.Response(200, request=httpx.Request("POST", url)))

    with pytest.raises(wb_errors.WorkbenchError, match="身份尚未确认"):
        wb_control.start(config)
    monkeypatch.setattr(psutil, "Process", lookup)
    control = json.loads(wb_state.control_record_path(workspace).read_text(encoding="utf-8"))
    pending = control["pending_process"]
    assert pending["pid"] == domain.pid and "create_time" not in pending
    domain.command = pending["command"]
    domain.birth = (pending["launch_started"] + pending["launch_finished"]) / 2
    assert wb_observations.status(config).state == "unknown"
    with pytest.raises(wb_errors.WorkbenchError, match="无法确认记录进程的身份"):
        wb_control.stop(config)
    assert wb_observations.status(config).state == "unknown"
    domain.metadata_allowed = True
    domain.birth = pending["launch_finished"] + 10
    with pytest.raises(wb_errors.WorkbenchError, match="无法确认待登记进程的启动时间"):
        wb_control.stop(config)
    domain.birth = (pending["launch_started"] + pending["launch_finished"]) / 2
    assert wb_control.stop(config).state == "completed"
    assert wb_observations.status(config).state == "stopped"


def test_engine_registration_write_failure_tracks_it_and_drains_domain(tmp_path, monkeypatch):
    config = write_workspace(tmp_path / "workspace")
    workspace = config.parent
    (workspace / "web").mkdir()
    (workspace / "web/index.html").write_text("AstroPhotoFlow", encoding="utf-8")
    (workspace / "data").mkdir()
    (workspace / "data/service.token").write_text("test-token", encoding="utf-8")
    calls = []

    class DomainProcess:
        pid = 123456
        running = True
        waits = 0

        def poll(self):
            return None if self.running else 0

        def wait(self, timeout):
            calls.append("domain-wait")
            self.waits += 1
            if self.waits == 1:
                pending = json.loads(wb_state.control_record_path(workspace).read_text(encoding="utf-8"))["pending_process"]
                assert pending["pid"] == engine.pid
                raise psutil.TimeoutExpired(timeout, pid=self.pid)
            self.running = False

        def terminate(self):
            pytest.fail("the domain service must drain")

    class EngineProcess:
        pid = 123457
        running = True

        def poll(self):
            return None if self.running else 0

        def children(self, recursive=False):
            return []

        def environ(self):
            return {"APF_WORKSPACE": str(workspace)}

        def terminate(self):
            calls.append("engine-terminate")
            self.running = False

    domain, engine = DomainProcess(), EngineProcess()
    launches = iter((domain, engine))
    original_process = psutil.Process
    original_update = wb_state.update_running_state
    failed_write = []

    def lookup(pid=None):
        if pid == engine.pid:
            if engine.running:
                return engine
            raise psutil.NoSuchProcess(pid)
        return original_process() if pid is None else original_process(pid)

    def launch(*args):
        child = next(launches)
        if child is engine:
            monkeypatch.setattr(psutil, "Process", lookup)
        return child

    def update(target, changes):
        if not failed_write and any(item["role"] == "comfyui" for item in changes.get("processes", [])):
            failed_write.append(True)
            raise OSError("engine record write failed")
        original_update(target, changes)

    def record(child, role, target, command):
        return {"pid": child.pid, "role": role, "command": command, "create_time": 1.0,
                "executable": command[0], "workspace": str(target), "started_at": datetime.now(timezone.utc).isoformat()}

    def identity(item):
        return domain if item["role"] == "asset-service" and domain.running else None

    def shutdown(url, *, headers, timeout):
        calls.append("shutdown")
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(wb_processes, 'launch_process', launch)
    monkeypatch.setattr(wb_processes, 'record_process', record)
    monkeypatch.setattr(wb_processes, 'identify_process', identity)
    monkeypatch.setattr(wb_processes, 'port_available', lambda host, port: True)
    monkeypatch.setattr(wb_observations, 'service_healthy', lambda path: True)
    monkeypatch.setattr(wb_state, "update_running_state", update)
    monkeypatch.setattr(psutil, "wait_procs", lambda processes, timeout: (processes, []))
    monkeypatch.setattr(httpx, "post", shutdown)

    with pytest.raises(wb_errors.WorkbenchError, match="engine record write failed") as failure:
        wb_control.start(config)
    assert "排空" in str(failure.value)
    assert [item["role"] for item in wb_state.read_state(workspace)["processes"]] == ["asset-service"]
    control = json.loads(wb_state.control_record_path(workspace).read_text(encoding="utf-8"))
    assert control["pending_process"]["pid"] == engine.pid
    assert wb_observations.status(config).state == "unknown"
    assert wb_control.stop(config).state == "completed"
    assert calls == ["engine-terminate", "shutdown", "domain-wait", "shutdown", "domain-wait"]
    assert wb_state.read_state(workspace)["processes"] == []
    assert wb_observations.status(config).state == "stopped"


def test_interrupted_launch_without_pid_stays_unknown(tmp_path, monkeypatch):
    config = write_workspace(tmp_path / "workspace")
    workspace = config.parent
    with pytest.raises(KeyboardInterrupt):
        with wb_operations.control_operation(config, "start") as (_, control):
            control["pending_process"] = {"role": "asset-service", "pid": None}
            wb_state.write_control(workspace, control)
            raise KeyboardInterrupt()

    control = json.loads(wb_state.control_record_path(workspace).read_text(encoding="utf-8"))
    control["result"].update({"action": "stop", "state": "in_progress"})
    control["controller"] = {"pid": 123456, "create_time": 1.0}
    wb_state.write_control(workspace, control)
    original_process = psutil.Process

    def lookup(pid=None):
        if pid == 123456:
            raise psutil.NoSuchProcess(pid)
        return original_process() if pid is None else original_process(pid)

    monkeypatch.setattr(psutil, "Process", lookup)
    assert wb_observations.status(config).state == "unknown"
    with pytest.raises(wb_errors.WorkbenchError, match="身份尚未登记"):
        wb_control.stop(config)
    assert wb_observations.status(config).state == "unknown"


def test_control_write_failure_reports_startup_and_cleanup_errors(tmp_path, monkeypatch):
    config = write_workspace(tmp_path / "workspace")
    workspace = config.parent
    (workspace / "web").mkdir()
    (workspace / "web/index.html").write_text("AstroPhotoFlow", encoding="utf-8")
    (workspace / "data").mkdir()
    (workspace / "data/service.token").write_text("test-token", encoding="utf-8")

    class DomainProcess:
        pid = 123456

        def poll(self):
            return None

    domain = DomainProcess()
    launches = []
    original_write = wb_state.write_control

    def launch(*args):
        launches.append(True)
        if len(launches) == 1:
            return domain
        raise OSError("native launch failed")

    def write_control(target, control):
        if control["result"]["state"] == "failed":
            raise OSError("control result write failed")
        original_write(target, control)

    def shutdown(*args, **kwargs):
        raise httpx.ConnectError("shutdown unavailable")

    monkeypatch.setattr(wb_processes, 'launch_process', launch)
    monkeypatch.setattr(wb_processes, 'record_process', lambda child, role, target, command: {
        "pid": child.pid, "role": role, "command": command, "create_time": 1.0, "executable": command[0],
        "workspace": str(target), "started_at": datetime.now(timezone.utc).isoformat(),
    })
    monkeypatch.setattr(wb_processes, 'identify_process', lambda item: domain)
    monkeypatch.setattr(wb_processes, 'port_available', lambda host, port: True)
    monkeypatch.setattr(wb_observations, 'service_healthy', lambda path: True)
    monkeypatch.setattr(wb_state, 'write_control', write_control)
    monkeypatch.setattr(httpx, "post", shutdown)

    with pytest.raises(wb_errors.WorkbenchError) as failure:
        wb_control.start(config)
    message = str(failure.value)
    assert "native launch failed" in message
    assert "shutdown unavailable" in message
    assert "control result write failed" in message
    assert [item["role"] for item in wb_state.read_state(workspace)["processes"]] == ["asset-service"]
    assert json.loads(wb_state.control_record_path(workspace).read_text(encoding="utf-8"))["pending_process"]["pid"] is None



def write_workspace(path):
    path.mkdir(parents=True, exist_ok=True)
    config = path / "config.toml"
    config.write_text('[server]\nhost="127.0.0.1"\nport=31390\n[storage]\ndata_dir="data"\n'
                      '[comfyui]\nallowed_origins=["http://127.0.0.1:31388"]\n', encoding="utf-8")
    (path / "run").mkdir()
    return config


def test_port_choice_skips_occupied_and_other_service_port(monkeypatch):
    checked = []
    def available(host, port):
        checked.append(port)
        return port not in {31388, 31389}
    monkeypatch.setattr(wb_processes, 'port_available', available)
    assert wb_control.choose_port("127.0.0.1", 31388, exclude=31390) == 31391
    assert checked == [31388, 31389, 31391]


def test_workspace_ports_come_from_existing_config_and_mismatch_is_rejected(tmp_path):
    config = write_workspace(tmp_path / "workspace")
    assert wb_workspaces.resolve_workspace_ports(config.parent, None, None) == (31390, 31388)
    assert wb_workspaces.resolve_workspace_ports(config.parent, 31390, 31388) == (31390, 31388)
    with pytest.raises(wb_errors.WorkbenchError, match="不一致"):
        wb_workspaces.resolve_workspace_ports(config.parent, 31490, 31388)
    with pytest.raises(wb_errors.WorkbenchError, match="不一致"):
        wb_workspaces.resolve_workspace_ports(config.parent, 31390, 31389)
    empty = tmp_path / "empty"
    assert wb_workspaces.resolve_workspace_ports(empty, None, None) == (8190, 8188)
    assert wb_workspaces.resolve_workspace_ports(empty, 9000, None) == (9000, 8188)


def test_repeated_start_returns_actual_addresses_without_launch_or_default_change(tmp_path, monkeypatch):
    config = write_workspace(tmp_path / "workspace")
    ready = WorkbenchState(workspace=str(config.parent), config_path=str(config), state="running", ready=True,
                           web_url="http://127.0.0.1:31488", service_url="http://127.0.0.1:31490",
                           processes=[], effective_settings=None, versions={}, reason=None, recent=None)
    monkeypatch.setattr(wb_observations, 'status', lambda path: ready)
    monkeypatch.setattr(wb_processes, 'launch_process', lambda *args: pytest.fail("must reuse"))
    result = wb_control.start(config)
    assert result.reused and result.state == "completed"
    assert result.web_url == ready.web_url and result.service_url == ready.service_url
    assert not app_config.CONFIG_PATH.exists()
    assert wb_state.recent_result(config.parent).operation_id == result.operation_id


def test_same_workspace_control_is_mutually_exclusive(tmp_path):
    config = write_workspace(tmp_path / "workspace")
    with FileLock(str(config.parent / "run/control.lock")):
        with pytest.raises(wb_errors.WorkbenchError, match="已有启停"):
            wb_control.start(config)
    assert not wb_state.control_record_path(config.parent).exists()


def test_interrupted_control_is_unknown_and_not_reported_completed(tmp_path):
    config = write_workspace(tmp_path / "workspace")
    with pytest.raises(KeyboardInterrupt):
        with wb_operations.control_operation(config, "start"):
            raise KeyboardInterrupt()
    assert wb_state.recent_result(config.parent).state == "unknown"
    with pytest.raises(wb_errors.WorkbenchError, match="尚未确认"):
        wb_control.start(config)
    assert wb_control.stop(config).state == "completed"
    assert wb_state.recent_result(config.parent).action == "stop"


def test_explicit_stop_reconciles_partial_interrupted_start_before_replacing_record(tmp_path, monkeypatch):
    config = write_workspace(tmp_path / "workspace")
    with pytest.raises(KeyboardInterrupt):
        with wb_operations.control_operation(config, "start"):
            raise KeyboardInterrupt()
    wb_state.write_state(config.parent, {"processes": [{"role": "asset-service"}]})
    calls = []
    def stop(path, *, control):
        assert wb_state.recent_result(path.parent).state == "unknown"
        calls.append(path)
        wb_state.write_state(path.parent, {"processes": []})
    monkeypatch.setattr(wb_processes, 'stop_processes', stop)
    assert wb_control.stop(config).state == "completed"
    assert calls == [config]


def test_status_requires_health_and_actual_process_identity(tmp_path, monkeypatch):
    config = write_workspace(tmp_path / "workspace")
    records = [{"role": role, "pid": index + 1, "create_time": 1.0, "executable": "python", "command": ["python"],
                "workspace": str(config.parent), "started_at": datetime.now(timezone.utc).isoformat()}
               for index, role in enumerate(("asset-service", "comfyui"))]
    wb_state.write_state(config.parent, {"workspace": str(config.parent), "config_path": str(config),
        "processes": records, "effective_settings": app_config.get_configuration(config).saved.model_dump(),
        "web_url": "http://127.0.0.1:31388", "service_url": "http://127.0.0.1:31390"})
    monkeypatch.setattr(wb_processes, 'identify_process', lambda record: object())
    monkeypatch.setattr(wb_observations, 'service_healthy', lambda path: False)
    observed = wb_observations.status(config)
    assert observed.state == "partial" and not observed.ready
    monkeypatch.setattr(wb_observations, 'service_healthy', lambda path: True)
    monkeypatch.setattr(wb_observations, 'web_healthy', lambda url, workspace: True)
    state = wb_state.read_state(config.parent)
    state["maintenance_operation_id"] = str(uuid4())
    wb_state.write_state(config.parent, state)
    assert not wb_observations.status(config).ready
    monkeypatch.setattr(wb_processes, 'identify_process', lambda record: None)
    assert wb_observations.status(config).state == "stopped"


def test_restart_rejects_busy_without_stopping_or_scheduling(tmp_path, monkeypatch):
    config = write_workspace(tmp_path / "workspace")
    (config.parent / "data").mkdir()
    (config.parent / "data/service.token").write_text("test-token", encoding="utf-8")
    settings = app_config.load_settings(config)
    record = {"role": "asset-service", "pid": 1, "create_time": 1.0, "executable": "python", "command": ["python"],
              "workspace": str(config.parent), "started_at": datetime.now(timezone.utc).isoformat()}
    ready = WorkbenchState(workspace=str(config.parent), config_path=str(config), state="running", ready=True,
                           web_url="http://127.0.0.1:31388", service_url=settings.service_url,
                           processes=[ProcessInfo.model_validate_json(json.dumps(record))],
                           effective_settings=None, versions={}, reason=None, recent=None)
    monkeypatch.setattr(wb_observations, 'status', lambda path: ready)
    wb_state.write_state(config.parent, {"workspace": str(config.parent), "config_path": str(config),
        "processes": [record], "effective_settings": app_config.get_configuration(config).saved.model_dump()})
    controls = []
    def maintenance(url, **kwargs):
        controls.append(kwargs["json"])
        releasing = kwargs["json"]["action"] == "release"
        return httpx.Response(200, json={"busy": not releasing, "unknown": False,
            "blockers": [] if releasing else ["导入任务 test"]}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", maintenance)
    monkeypatch.setattr(wb_processes, 'stop_processes', lambda *args: pytest.fail("busy must not stop"))
    result = wb_control.restart(config)
    assert result.state == "rejected" and result.blockers == ["导入任务 test"]
    assert [item["action"] for item in controls] == ["enter", "release"]
    assert all(item["operation_id"] == str(result.operation_id) for item in controls)
    assert wb_state.recent_result(config.parent).state == "rejected"
    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("test maintenance unavailable")
    monkeypatch.setattr(httpx, "post", unavailable)
    assert wb_control.restart(config).state == "rejected"



def test_managed_service_stop_drains_before_engine_has_been_recorded(tmp_path, monkeypatch):
    config = write_workspace(tmp_path / "workspace")
    data = config.parent / "data"
    data.mkdir()
    (data / "service.token").write_text("test-token", encoding="utf-8")
    values = app_config.get_configuration(config).saved.model_dump()
    wb_state.write_state(config.parent, {"workspace": str(config.parent), "config_path": str(config),
        "effective_settings": values, "processes": [{"role": "asset-service"}]})
    calls = []
    class Service:
        def wait(self, timeout):
            calls.append("drained")
        def terminate(self):
            pytest.fail("must not terminate a managed domain service")
    monkeypatch.setattr(wb_processes, 'identify_process', lambda record: Service())
    def shutdown(url, **kwargs):
        calls.append("shutdown")
        return httpx.Response(200, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", shutdown)
    assert wb_control.stop(config).state == "completed"
    assert calls == ["shutdown", "drained"]
    assert wb_state.read_state(config.parent)["processes"] == []



def test_web_restart_launches_external_controller_and_correlates_result(tmp_path, monkeypatch):
    from types import SimpleNamespace
    config = write_workspace(tmp_path)
    launched = []
    monkeypatch.setattr(wb_processes, 'launch_process', lambda *args: launched.append(args) or SimpleNamespace(pid=os.getpid()))
    operation_id = uuid4()
    accepted = wb_control.request_restart(config, operation_id)
    assert accepted.state == "in_progress"
    command, cwd, env, log = launched[0]
    assert command[0] == sys.executable
    assert command[-2:] == [str(config), str(operation_id)]
    assert cwd == tmp_path and log == tmp_path / "logs/web-restart.log"
    assert wb_control.restart_result(config, operation_id).state == "in_progress"
    assert wb_control.request_restart(config, operation_id) == accepted
    assert len(launched) == 1
    with pytest.raises(wb_errors.WorkbenchError, match="网页重启"):
        wb_control.request_restart(config, uuid4())
    rejected = accepted.model_copy(update={"state": "rejected", "blockers": ["导入尚未完成"]})
    monkeypatch.setattr(wb_control, 'restart', lambda *args, **kwargs: rejected)
    wb_control.run_web_restart(config, operation_id)
    observed = wb_control.restart_result(config, operation_id)
    assert observed.state == "rejected" and observed.blockers == ["导入尚未完成"]
    assert wb_control.restart_result(config, uuid4()) is None


def test_web_restart_control_lock_rejects_before_launch(tmp_path, monkeypatch):
    config = write_workspace(tmp_path)
    monkeypatch.setattr(wb_processes, 'launch_process', lambda *args: pytest.fail("must not launch"))
    with FileLock(str(tmp_path / "run/control.lock")):
        with pytest.raises(wb_errors.WorkbenchError, match="已有启停"):
            wb_control.request_restart(config, uuid4())


def test_web_restart_worker_reports_failure_before_control_record(tmp_path, monkeypatch):
    from types import SimpleNamespace
    config = write_workspace(tmp_path)
    monkeypatch.setattr(wb_processes, 'launch_process', lambda *args: SimpleNamespace(pid=os.getpid()))
    operation_id = uuid4()
    wb_control.request_restart(config, operation_id)
    def failed(*args, **kwargs):
        raise wb_errors.WorkbenchError("控制锁未获得")
    monkeypatch.setattr(wb_control, 'restart', failed)
    wb_control.run_web_restart(config, operation_id)
    observed = wb_control.restart_result(config, operation_id)
    assert observed.state == "unknown" and "控制锁未获得" in observed.detail


def test_web_restart_launch_failure_is_terminal_and_allows_later_request(tmp_path, monkeypatch):
    from types import SimpleNamespace
    config = write_workspace(tmp_path)
    def failed(*args):
        raise OSError("controller executable unavailable")
    monkeypatch.setattr(wb_processes, 'launch_process', failed)
    operation_id = uuid4()
    with pytest.raises(OSError, match="executable"):
        wb_control.request_restart(config, operation_id)
    assert wb_control.restart_result(config, operation_id).state == "failed"
    monkeypatch.setattr(wb_processes, 'launch_process', lambda *args: SimpleNamespace(pid=os.getpid()))
    assert wb_control.request_restart(config, uuid4()).state == "in_progress"



def test_process_registration_uses_the_shared_typed_process_contract(tmp_path):
    from types import SimpleNamespace
    process = psutil.Process()
    value = wb_processes.record_process(SimpleNamespace(pid=process.pid), 'asset-service', tmp_path, ['test-process'])
    parsed = ProcessInfo.model_validate_json(json.dumps(value))
    assert parsed.pid == process.pid and parsed.role == 'asset-service'
    assert parsed.workspace == str(tmp_path) and parsed.command == ['test-process']
    with pytest.raises(ValueError):
        wb_processes.record_process(SimpleNamespace(pid=process.pid), 'foreign-process', tmp_path, [])
