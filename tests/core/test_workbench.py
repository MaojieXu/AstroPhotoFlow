from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import logging.config
from pathlib import Path
from uuid import uuid4
import zipfile

import httpx
import pytest
from filelock import FileLock
from fastapi.testclient import TestClient

from astrophotoflow.core import workbench
from astrophotoflow.contracts.workbench import WorkbenchState
from astrophotoflow.core.database.schema import database_lock, upgrade_database
from astrophotoflow.interfaces.http.app import create_app


@pytest.fixture(autouse=True)
def isolated_default(tmp_path, monkeypatch):
    monkeypatch.setattr(workbench.app_config, "CONFIG_PATH", tmp_path / "user/config.toml")
    monkeypatch.delenv("APF_WORKSPACE", raising=False)
    monkeypatch.delenv("ASTROPHOTOFLOW_CONFIG", raising=False)


def test_initialize_copies_native_web_and_start_uses_builtin_gateway(tmp_path, monkeypatch):
    package = tmp_path / "package"
    vendor = package / "vendor"
    web = package / "web"
    vendor.mkdir(parents=True)
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("AstroPhotoFlow", encoding="utf-8")
    (web / "assets/app.js").write_text("native", encoding="utf-8")
    archive_path = vendor / "comfyui-0.42.0.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("ComfyUI/main.py", "")
        archive.writestr("ComfyUI/requirements.txt", "")
    (vendor / "comfyui-source.json").write_text(
        json.dumps({"commit": workbench.COMFY_COMMIT, "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(), "comfyui_version": "0.42.0"}),
        encoding="utf-8",
    )

    runtime = tmp_path / "runtime"
    monkeypatch.setattr(workbench, "__file__", str(package / "core" / "workbench.py"))
    monkeypatch.setattr(workbench, "_runtime_dir", lambda: runtime)
    monkeypatch.setattr(workbench, "_uv", lambda: "uv")
    monkeypatch.setattr(workbench, "_run", lambda command, env=None: None)
    monkeypatch.setattr(workbench.app_config, "CONFIG_PATH", tmp_path / "user/config.toml")

    workspace = tmp_path / "workspace"
    config_path = workbench.initialize(workspace, service_port=18190, comfyui_port=18188)
    assert workbench.app_config.resolve_config_path() == config_path
    assert not (workbench.app_config.CONFIG_PATH.parent / "active-workspace").exists()
    assert (workspace / "web/index.html").read_text(encoding="utf-8") == "AstroPhotoFlow"
    assert (workspace / "web/assets/app.js").is_file()
    assert not (workspace / "comfyui-data/custom_nodes/AstroPhotoFlow").exists()
    runtime_python = runtime / "comfyui-env" / ("Scripts/python.exe" if workbench.os.name == "nt" else "bin/python")
    runtime_python.parent.mkdir(parents=True, exist_ok=True)
    runtime_python.touch()
    activations = []
    monkeypatch.setattr(workbench, "_activate_workspace", lambda config_path: activations.append(config_path))
    monkeypatch.setattr(workbench, "_run", lambda *args, **kwargs: pytest.fail("reuse must not reinstall CPU dependencies"))
    templates = workspace / "comfyui-user/default/comfy.templates.json"
    templates.write_text('[{"name":"saved","data":"graph"}]', encoding="utf-8")
    workbench.initialize(workspace, reuse_runtime=True, activate=False)
    assert json.loads(templates.read_text(encoding="utf-8"))[0]["name"] == "saved"
    assert (workspace / "comfyui-user/default/workflows").is_dir()
    assert (workspace / "comfyui-user/default/subgraphs").is_dir()
    second_workspace = tmp_path / "second-workspace"
    workbench.initialize(second_workspace, service_port=18290, comfyui_port=18288,
                         reuse_runtime=True, activate=False)
    assert (second_workspace / "web/assets/app.js").is_file()
    assert activations == []

    commands = []

    class FakeProcess:
        pid = 12345

        def poll(self):
            return None

    monkeypatch.setattr(workbench, "_port_available", lambda host, port: True)
    monkeypatch.setattr(workbench, "_health", lambda path: True)
    monkeypatch.setattr(workbench, "_launch", lambda command, cwd, env, log_path: (commands.append(command) or FakeProcess()))
    monkeypatch.setattr(workbench, "_record", lambda process, role, cwd, command: {
        "role": role, "command": command, "pid": process.pid, "create_time": 1.0, "executable": command[0],
        "workspace": str(cwd), "started_at": datetime.now(timezone.utc).isoformat()})
    monkeypatch.setattr(workbench, "_web_health", lambda url, workspace: True)

    result = workbench.start(config_path)
    assert result.state == "completed" and result.web_url == "http://127.0.0.1:18188"
    assert activations == []
    assert commands[0][1:] == ["-m", "astrophotoflow.interfaces.http.cli", "serve"]
    assert commands[1][commands[1].index("--base-directory") + 1] == str(workspace / "comfyui-data")
    assert commands[1][commands[1].index("--front-end-root") + 1] == str(workspace / "web")
    assert "--disable-all-custom-nodes" in commands[1]


def test_workspace_native_web_assets_are_complete_and_isolated(tmp_path, monkeypatch):
    package = tmp_path / "package"
    monkeypatch.setattr(workbench, "__file__", str(package / "core" / "workbench.py"))
    assets = tmp_path / "build"
    assets.mkdir()
    (assets / "chunks").mkdir()
    for name in ("index.html", "chunks/app.js", "chunks/app.css"):
        (assets / name).write_text("first", encoding="utf-8")
    first = workbench.install_frontend(tmp_path / "first", assets)
    for name in ("index.html", "chunks/app.js", "chunks/app.css"):
        (assets / name).write_text("second", encoding="utf-8")
    second = workbench.install_frontend(tmp_path / "second", assets)
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
    monkeypatch.setattr(workbench, "_identity", lambda record: parent)
    monkeypatch.setattr(
        workbench.psutil, "wait_procs",
        lambda processes, timeout: ([p for p in processes if not p.running], [p for p in processes if p.running]),
    )
    workbench.stop(tmp_path / "config.toml")
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
        "effective_settings": workbench.app_config.get_configuration(config).saved.model_dump(), "processes": [
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

    monkeypatch.setattr(workbench, "_identity", lambda record: ServiceProcess() if record["role"] == "asset-service" else None)
    monkeypatch.setattr(workbench.httpx, "post", shutdown)
    workbench.stop(config)
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
            assert workbench._read_state(workspace)["processes"]
            calls.append("wait")
            self.waits += 1
            if drain_times_out and self.waits == 1:
                raise workbench.psutil.TimeoutExpired(timeout, pid=self.pid)

        def terminate(self):
            pytest.fail("a ready domain service must drain, not be terminated")

        def kill(self):
            pytest.fail("a ready domain service must drain, not be killed")

    domain = DomainProcess()
    with ExitStack() as resources:
        def launch(command, cwd, env, log_path):
            if not clients:
                adopted = workbench.app_config.load_running_settings(workspace)
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
            assert workbench._recent(workspace).state == "in_progress"
            raise OSError("native process launch failed")

        monkeypatch.setattr(workbench, "_launch", launch)
        monkeypatch.setattr(workbench, "_port_available", lambda host, port: True)
        monkeypatch.setattr(workbench, "_identity", lambda record: domain if record["role"] == "asset-service" else None)
        monkeypatch.setattr(workbench, "_record", lambda child, role, target, command: {
            "pid": child.pid, "role": role, "command": command, "create_time": 1.0, "executable": command[0],
            "workspace": str(target), "started_at": datetime.now(timezone.utc).isoformat(),
        })
        monkeypatch.setattr(workbench, "_health", lambda target: clients[0].get(
            "/api/v1/health", headers={"Authorization": "Bearer test-token"}).status_code == 200)
        monkeypatch.setattr(workbench.httpx, "post", lambda url, *, headers, timeout: (
            calls.append("shutdown-request") or clients[0].post("/internal/shutdown", headers=headers)
        ))

        with pytest.raises(workbench.WorkbenchError, match="native process launch") as failure:
            workbench.start(config)

        assert calls[:3] == ["accepted-upload", "shutdown-request", "shutdown"]
        assert calls[3] == "wait"
        processes = workbench._read_state(workspace)["processes"]
        if drain_times_out:
            assert "启动失败后的停止未完成" in str(failure.value)
            assert "导入或预览仍在排空" in str(failure.value)
            assert [item["role"] for item in processes] == ["asset-service"]
            assert workbench._recent(workspace).state == "failed"
            assert workbench.stop(config).state == "completed"
            assert [item["role"] for item in workbench._read_state(workspace)["processes"]] == []
            assert calls.count("shutdown-request") == 2
            assert calls.count("wait") == 2
        else:
            assert processes == []
            assert workbench._recent(workspace).state == "failed"
            assert calls.count("shutdown-request") == 1
            assert calls.count("wait") == 1

        clients[0].app.state.database.close()


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
                pending = json.loads(workbench._control_path(workspace).read_text(encoding="utf-8"))["pending_process"]
                assert pending["pid"] == self.pid and pending["launch_started"] <= pending["launch_finished"]
                raise workbench.subprocess.TimeoutExpired("asset-service", timeout)
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
            raise workbench.psutil.AccessDenied(pid=child.pid)
        return {"pid": child.pid, "role": role, "command": command, "create_time": 1.0,
                "executable": command[0], "workspace": str(target), "started_at": datetime.now(timezone.utc).isoformat()}

    def shutdown(url, *, headers, timeout):
        calls.append("shutdown")
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(workbench, "_launch", lambda *args: domain)
    monkeypatch.setattr(workbench, "_record", record)
    monkeypatch.setattr(workbench, "_port_available", lambda host, port: True)
    monkeypatch.setattr(workbench, "_identity", lambda item: domain if domain.running else None)
    monkeypatch.setattr(workbench.httpx, "post", shutdown)

    with pytest.raises(workbench.WorkbenchError, match="排空"):
        workbench.start(config)
    assert workbench._read_state(workspace)["processes"] == []
    control = json.loads(workbench._control_path(workspace).read_text(encoding="utf-8"))
    assert control["pending_process"]["pid"] == domain.pid
    assert control["pending_process"]["create_time"] == 1.0
    assert workbench.status(config).state == "unknown"
    assert workbench.stop(config).state == "completed"
    assert calls == ["shutdown", "wait", "shutdown", "wait"]
    assert workbench.status(config).state == "stopped"


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
                raise workbench.psutil.AccessDenied(pid=self.pid)
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
                raise workbench.subprocess.TimeoutExpired("asset-service", timeout)
            self.running = False

        def terminate(self):
            pytest.fail("an unrecorded domain service must still drain")

    domain = DomainProcess()
    process = workbench.psutil.Process

    def lookup(pid=None):
        if pid == domain.pid:
            if domain.running:
                return domain
            raise workbench.psutil.NoSuchProcess(pid)
        return process() if pid is None else process(pid)

    def cannot_record(*args):
        raise OSError("identity unavailable")

    monkeypatch.setattr(workbench, "_launch", lambda *args: domain)
    monkeypatch.setattr(workbench, "_record", cannot_record)
    monkeypatch.setattr(workbench, "_port_available", lambda host, port: True)
    monkeypatch.setattr(workbench.httpx, "post", lambda url, **kwargs: httpx.Response(200, request=httpx.Request("POST", url)))

    with pytest.raises(workbench.WorkbenchError, match="身份尚未确认"):
        workbench.start(config)
    monkeypatch.setattr(workbench.psutil, "Process", lookup)
    control = json.loads(workbench._control_path(workspace).read_text(encoding="utf-8"))
    pending = control["pending_process"]
    assert pending["pid"] == domain.pid and "create_time" not in pending
    domain.command = pending["command"]
    domain.birth = (pending["launch_started"] + pending["launch_finished"]) / 2
    assert workbench.status(config).state == "unknown"
    with pytest.raises(workbench.WorkbenchError, match="无法确认记录进程的身份"):
        workbench.stop(config)
    assert workbench.status(config).state == "unknown"
    domain.metadata_allowed = True
    domain.birth = pending["launch_finished"] + 10
    with pytest.raises(workbench.WorkbenchError, match="无法确认待登记进程的启动时间"):
        workbench.stop(config)
    domain.birth = (pending["launch_started"] + pending["launch_finished"]) / 2
    assert workbench.stop(config).state == "completed"
    assert workbench.status(config).state == "stopped"


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
                pending = json.loads(workbench._control_path(workspace).read_text(encoding="utf-8"))["pending_process"]
                assert pending["pid"] == engine.pid
                raise workbench.psutil.TimeoutExpired(timeout, pid=self.pid)
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
    original_process = workbench.psutil.Process
    original_update = workbench.app_config._update_running_state
    failed_write = []

    def lookup(pid=None):
        if pid == engine.pid:
            if engine.running:
                return engine
            raise workbench.psutil.NoSuchProcess(pid)
        return original_process() if pid is None else original_process(pid)

    def launch(*args):
        child = next(launches)
        if child is engine:
            monkeypatch.setattr(workbench.psutil, "Process", lookup)
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

    monkeypatch.setattr(workbench, "_launch", launch)
    monkeypatch.setattr(workbench, "_record", record)
    monkeypatch.setattr(workbench, "_identity", identity)
    monkeypatch.setattr(workbench, "_port_available", lambda host, port: True)
    monkeypatch.setattr(workbench, "_health", lambda path: True)
    monkeypatch.setattr(workbench.app_config, "_update_running_state", update)
    monkeypatch.setattr(workbench.psutil, "wait_procs", lambda processes, timeout: (processes, []))
    monkeypatch.setattr(workbench.httpx, "post", shutdown)

    with pytest.raises(workbench.WorkbenchError, match="engine record write failed") as failure:
        workbench.start(config)
    assert "排空" in str(failure.value)
    assert [item["role"] for item in workbench._read_state(workspace)["processes"]] == ["asset-service"]
    control = json.loads(workbench._control_path(workspace).read_text(encoding="utf-8"))
    assert control["pending_process"]["pid"] == engine.pid
    assert workbench.status(config).state == "unknown"
    assert workbench.stop(config).state == "completed"
    assert calls == ["engine-terminate", "shutdown", "domain-wait", "shutdown", "domain-wait"]
    assert workbench._read_state(workspace)["processes"] == []
    assert workbench.status(config).state == "stopped"


def test_interrupted_launch_without_pid_stays_unknown(tmp_path, monkeypatch):
    config = write_workspace(tmp_path / "workspace")
    workspace = config.parent
    with pytest.raises(KeyboardInterrupt):
        with workbench._control_operation(config, "start") as (_, control):
            control["pending_process"] = {"role": "asset-service", "pid": None}
            workbench._write_control(workspace, control)
            raise KeyboardInterrupt()

    control = json.loads(workbench._control_path(workspace).read_text(encoding="utf-8"))
    control["result"].update({"action": "stop", "state": "in_progress"})
    control["controller"] = {"pid": 123456, "create_time": 1.0}
    workbench._write_control(workspace, control)
    original_process = workbench.psutil.Process

    def lookup(pid=None):
        if pid == 123456:
            raise workbench.psutil.NoSuchProcess(pid)
        return original_process() if pid is None else original_process(pid)

    monkeypatch.setattr(workbench.psutil, "Process", lookup)
    assert workbench.status(config).state == "unknown"
    with pytest.raises(workbench.WorkbenchError, match="身份尚未登记"):
        workbench.stop(config)
    assert workbench.status(config).state == "unknown"


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
    original_write = workbench._write_control

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

    monkeypatch.setattr(workbench, "_launch", launch)
    monkeypatch.setattr(workbench, "_record", lambda child, role, target, command: {
        "pid": child.pid, "role": role, "command": command, "create_time": 1.0, "executable": command[0],
        "workspace": str(target), "started_at": datetime.now(timezone.utc).isoformat(),
    })
    monkeypatch.setattr(workbench, "_identity", lambda item: domain)
    monkeypatch.setattr(workbench, "_port_available", lambda host, port: True)
    monkeypatch.setattr(workbench, "_health", lambda path: True)
    monkeypatch.setattr(workbench, "_write_control", write_control)
    monkeypatch.setattr(workbench.httpx, "post", shutdown)

    with pytest.raises(workbench.WorkbenchError) as failure:
        workbench.start(config)
    message = str(failure.value)
    assert "native launch failed" in message
    assert "shutdown unavailable" in message
    assert "control result write failed" in message
    assert [item["role"] for item in workbench._read_state(workspace)["processes"]] == ["asset-service"]
    assert json.loads(workbench._control_path(workspace).read_text(encoding="utf-8"))["pending_process"]["pid"] is None



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
    monkeypatch.setattr(workbench, "_port_available", available)
    assert workbench._choose_port("127.0.0.1", 31388, exclude=31390) == 31391
    assert checked == [31388, 31389, 31391]


def test_actual_port_writeback_preserves_newly_saved_performance_and_current_values(tmp_path):
    config = write_workspace(tmp_path / "workspace")
    before = workbench.app_config.get_configuration(config)
    adopted = {"workspace": str(config.parent), "config_path": str(config),
               "effective_settings": before.saved.model_dump(), "processes": [{"role": "asset-service"}]}
    workbench._write_state(config.parent, adopted)
    changed = workbench.app_config.save_configuration(
        config, before.saved.model_copy(update={"file_workers": 7}), before.config_token)
    workbench._write_actual_ports(config, 31490, ["http://127.0.0.1:31488"])
    current = workbench.app_config.get_configuration(config)
    assert current.saved.file_workers == 7
    assert current.saved.service_port == 31490
    assert current.saved.allowed_origins == ["http://127.0.0.1:31488"]
    assert current.effective == changed.effective
    assert current.restart_required


def test_repeated_start_returns_actual_addresses_without_launch_or_default_change(tmp_path, monkeypatch):
    config = write_workspace(tmp_path / "workspace")
    ready = WorkbenchState(workspace=str(config.parent), config_path=str(config), state="running", ready=True,
                           web_url="http://127.0.0.1:31488", service_url="http://127.0.0.1:31490",
                           processes=[], effective_settings=None, versions={}, reason=None, recent=None)
    monkeypatch.setattr(workbench, "status", lambda path: ready)
    monkeypatch.setattr(workbench, "_launch", lambda *args: pytest.fail("must reuse"))
    result = workbench.start(config)
    assert result.reused and result.state == "completed"
    assert result.web_url == ready.web_url and result.service_url == ready.service_url
    assert not workbench.app_config.CONFIG_PATH.exists()
    assert workbench._recent(config.parent).operation_id == result.operation_id


def test_same_workspace_control_is_mutually_exclusive(tmp_path):
    config = write_workspace(tmp_path / "workspace")
    with FileLock(str(config.parent / "run/control.lock")):
        with pytest.raises(workbench.WorkbenchError, match="已有启停"):
            workbench.start(config)
    assert not workbench._control_path(config.parent).exists()


def test_interrupted_control_is_unknown_and_not_reported_completed(tmp_path):
    config = write_workspace(tmp_path / "workspace")
    with pytest.raises(KeyboardInterrupt):
        with workbench._control_operation(config, "start"):
            raise KeyboardInterrupt()
    assert workbench._recent(config.parent).state == "unknown"
    with pytest.raises(workbench.WorkbenchError, match="尚未确认"):
        workbench.start(config)
    assert workbench.stop(config).state == "completed"
    assert workbench._recent(config.parent).action == "stop"


def test_explicit_stop_reconciles_partial_interrupted_start_before_replacing_record(tmp_path, monkeypatch):
    config = write_workspace(tmp_path / "workspace")
    with pytest.raises(KeyboardInterrupt):
        with workbench._control_operation(config, "start"):
            raise KeyboardInterrupt()
    workbench._write_state(config.parent, {"processes": [{"role": "asset-service"}]})
    calls = []
    def stop(path, *, control):
        assert workbench._recent(path.parent).state == "unknown"
        calls.append(path)
        workbench._write_state(path.parent, {"processes": []})
    monkeypatch.setattr(workbench, "_stop", stop)
    assert workbench.stop(config).state == "completed"
    assert calls == [config]


def test_status_requires_health_and_actual_process_identity(tmp_path, monkeypatch):
    config = write_workspace(tmp_path / "workspace")
    records = [{"role": role, "pid": index + 1, "create_time": 1.0, "executable": "python", "command": ["python"],
                "workspace": str(config.parent), "started_at": datetime.now(timezone.utc).isoformat()}
               for index, role in enumerate(("asset-service", "comfyui"))]
    workbench._write_state(config.parent, {"workspace": str(config.parent), "config_path": str(config),
        "processes": records, "effective_settings": workbench.app_config.get_configuration(config).saved.model_dump(),
        "web_url": "http://127.0.0.1:31388", "service_url": "http://127.0.0.1:31390"})
    monkeypatch.setattr(workbench, "_identity", lambda record: object())
    monkeypatch.setattr(workbench, "_health", lambda path: False)
    observed = workbench.status(config)
    assert observed.state == "partial" and not observed.ready
    monkeypatch.setattr(workbench, "_health", lambda path: True)
    monkeypatch.setattr(workbench, "_web_health", lambda url, workspace: True)
    state = workbench._read_state(config.parent)
    state["maintenance_operation_id"] = str(uuid4())
    workbench._write_state(config.parent, state)
    assert not workbench.status(config).ready
    monkeypatch.setattr(workbench, "_identity", lambda record: None)
    assert workbench.status(config).state == "stopped"


def test_restart_rejects_busy_without_stopping_or_scheduling(tmp_path, monkeypatch):
    config = write_workspace(tmp_path / "workspace")
    (config.parent / "data").mkdir()
    (config.parent / "data/service.token").write_text("test-token", encoding="utf-8")
    settings = workbench.app_config.load_settings(config)
    record = {"role": "asset-service", "pid": 1, "create_time": 1.0, "executable": "python", "command": ["python"],
              "workspace": str(config.parent), "started_at": datetime.now(timezone.utc).isoformat()}
    ready = WorkbenchState(workspace=str(config.parent), config_path=str(config), state="running", ready=True,
                           web_url="http://127.0.0.1:31388", service_url=settings.service_url,
                           processes=[workbench.ProcessInfo.model_validate_json(json.dumps(record))],
                           effective_settings=None, versions={}, reason=None, recent=None)
    monkeypatch.setattr(workbench, "status", lambda path: ready)
    workbench._write_state(config.parent, {"workspace": str(config.parent), "config_path": str(config),
        "processes": [record], "effective_settings": workbench.app_config.get_configuration(config).saved.model_dump()})
    controls = []
    def maintenance(url, **kwargs):
        controls.append(kwargs["json"])
        releasing = kwargs["json"]["action"] == "release"
        return httpx.Response(200, json={"busy": not releasing, "unknown": False,
            "blockers": [] if releasing else ["导入任务 test"]}, request=httpx.Request("POST", url))
    monkeypatch.setattr(workbench.httpx, "post", maintenance)
    monkeypatch.setattr(workbench, "_stop", lambda *args: pytest.fail("busy must not stop"))
    result = workbench.restart(config)
    assert result.state == "rejected" and result.blockers == ["导入任务 test"]
    assert [item["action"] for item in controls] == ["enter", "release"]
    assert all(item["operation_id"] == str(result.operation_id) for item in controls)
    assert workbench._recent(config.parent).state == "rejected"
    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("test maintenance unavailable")
    monkeypatch.setattr(workbench.httpx, "post", unavailable)
    assert workbench.restart(config).state == "rejected"



def test_managed_service_stop_drains_before_engine_has_been_recorded(tmp_path, monkeypatch):
    config = write_workspace(tmp_path / "workspace")
    data = config.parent / "data"
    data.mkdir()
    (data / "service.token").write_text("test-token", encoding="utf-8")
    values = workbench.app_config.get_configuration(config).saved.model_dump()
    workbench._write_state(config.parent, {"workspace": str(config.parent), "config_path": str(config),
        "effective_settings": values, "processes": [{"role": "asset-service"}]})
    calls = []
    class Service:
        def wait(self, timeout):
            calls.append("drained")
        def terminate(self):
            pytest.fail("must not terminate a managed domain service")
    monkeypatch.setattr(workbench, "_identity", lambda record: Service())
    def shutdown(url, **kwargs):
        calls.append("shutdown")
        return httpx.Response(200, request=httpx.Request("POST", url))
    monkeypatch.setattr(workbench.httpx, "post", shutdown)
    assert workbench.stop(config).state == "completed"
    assert calls == ["shutdown", "drained"]
    assert workbench._read_state(config.parent)["processes"] == []



def test_web_restart_launches_external_controller_and_correlates_result(tmp_path, monkeypatch):
    from types import SimpleNamespace
    config = write_workspace(tmp_path)
    launched = []
    monkeypatch.setattr(workbench, "_launch", lambda *args: launched.append(args) or SimpleNamespace(pid=workbench.os.getpid()))
    operation_id = uuid4()
    accepted = workbench.request_restart(config, operation_id)
    assert accepted.state == "in_progress"
    command, cwd, env, log = launched[0]
    assert command[0] == workbench.sys.executable
    assert command[-2:] == [str(config), str(operation_id)]
    assert cwd == tmp_path and log == tmp_path / "logs/web-restart.log"
    assert workbench.restart_result(config, operation_id).state == "in_progress"
    assert workbench.request_restart(config, operation_id) == accepted
    assert len(launched) == 1
    with pytest.raises(workbench.WorkbenchError, match="网页重启"):
        workbench.request_restart(config, uuid4())
    rejected = accepted.model_copy(update={"state": "rejected", "blockers": ["导入尚未完成"]})
    monkeypatch.setattr(workbench, "restart", lambda *args, **kwargs: rejected)
    workbench._web_restart(config, operation_id)
    observed = workbench.restart_result(config, operation_id)
    assert observed.state == "rejected" and observed.blockers == ["导入尚未完成"]
    assert workbench.restart_result(config, uuid4()) is None


def test_web_restart_control_lock_rejects_before_launch(tmp_path, monkeypatch):
    config = write_workspace(tmp_path)
    monkeypatch.setattr(workbench, "_launch", lambda *args: pytest.fail("must not launch"))
    with FileLock(str(tmp_path / "run/control.lock")):
        with pytest.raises(workbench.WorkbenchError, match="已有启停"):
            workbench.request_restart(config, uuid4())


def test_web_restart_worker_reports_failure_before_control_record(tmp_path, monkeypatch):
    from types import SimpleNamespace
    config = write_workspace(tmp_path)
    monkeypatch.setattr(workbench, "_launch", lambda *args: SimpleNamespace(pid=workbench.os.getpid()))
    operation_id = uuid4()
    workbench.request_restart(config, operation_id)
    def failed(*args, **kwargs):
        raise workbench.WorkbenchError("控制锁未获得")
    monkeypatch.setattr(workbench, "restart", failed)
    workbench._web_restart(config, operation_id)
    observed = workbench.restart_result(config, operation_id)
    assert observed.state == "unknown" and "控制锁未获得" in observed.detail


def test_web_restart_launch_failure_is_terminal_and_allows_later_request(tmp_path, monkeypatch):
    from types import SimpleNamespace
    config = write_workspace(tmp_path)
    def failed(*args):
        raise OSError("controller executable unavailable")
    monkeypatch.setattr(workbench, "_launch", failed)
    operation_id = uuid4()
    with pytest.raises(OSError, match="executable"):
        workbench.request_restart(config, operation_id)
    assert workbench.restart_result(config, operation_id).state == "failed"
    monkeypatch.setattr(workbench, "_launch", lambda *args: SimpleNamespace(pid=workbench.os.getpid()))
    assert workbench.request_restart(config, uuid4()).state == "in_progress"
