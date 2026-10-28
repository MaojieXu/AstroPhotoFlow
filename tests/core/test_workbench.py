from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile
import httpx
import pytest

from astrophotoflow.core import workbench


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
    monkeypatch.setattr(workbench, "_record", lambda process, role, cwd, command: {"role": role, "command": command})
    monkeypatch.setattr(workbench, "_web_health", lambda url: True)

    assert workbench.start(config_path, activate=False) == "AstroPhotoFlow 已启动：http://127.0.0.1:18188/#/workflows"
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
    assert json.loads(state.read_text(encoding="utf-8")) == {"processes": []}


def test_stop_waits_for_domain_service_before_clearing_state(tmp_path, monkeypatch):
    (tmp_path / "run").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "data/service.token").write_text("private-token", encoding="utf-8")
    config = tmp_path / "config.toml"
    config.write_text('[server]\nhost="127.0.0.1"\nport=8190\n[storage]\ndata_dir="data"\n'
                      '[comfyui]\nallowed_origins=["http://127.0.0.1:8188"]\n', encoding="utf-8")
    state = tmp_path / "run/processes.json"
    state.write_text(json.dumps({"processes": [
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
    assert json.loads(state.read_text(encoding="utf-8")) == {"processes": []}
