from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile
import pytest

from astrophotoflow import workbench


def test_initialize_copies_extension_and_start_uses_backend_module(tmp_path, monkeypatch):
    package = tmp_path / "package"
    vendor = package / "vendor"
    extension = package / "comfyui" / "extension"
    vendor.mkdir(parents=True)
    extension.mkdir(parents=True)
    (extension / "__init__.py").write_text("CPU adapter marker\n", encoding="utf-8")
    (extension / "assets").mkdir()
    (extension / "assets" / "adapter.js").write_text("export const adapter = true;\n", encoding="utf-8")
    archive_path = vendor / "comfyui-0.42.0.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("ComfyUI/main.py", "")
        archive.writestr("ComfyUI/requirements.txt", "")
    (vendor / "comfyui-source.json").write_text(
        json.dumps({"commit": workbench.COMFY_COMMIT, "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(), "comfyui_version": "0.42.0"}),
        encoding="utf-8",
    )

    runtime = tmp_path / "runtime"
    monkeypatch.setattr(workbench, "__file__", str(package / "workbench.py"))
    monkeypatch.setattr(workbench, "_runtime_dir", lambda: runtime)
    monkeypatch.setattr(workbench, "_uv", lambda: "uv")
    monkeypatch.setattr(workbench, "_run", lambda command, env=None: None)
    monkeypatch.setattr(workbench, "_activate_workspace", lambda config_path: None)

    workspace = tmp_path / "workspace"
    config_path = workbench.initialize(workspace, service_port=18190, comfyui_port=18188)
    copied_extension = workspace / "comfyui-data" / "custom_nodes" / "AstroPhotoFlow"
    assert (copied_extension / "__init__.py").read_text(encoding="utf-8") == "CPU adapter marker\n"
    assert (copied_extension / "assets" / "adapter.js").is_file()
    runtime_python = runtime / "comfyui-env" / ("Scripts/python.exe" if workbench.os.name == "nt" else "bin/python")
    runtime_python.parent.mkdir(parents=True, exist_ok=True)
    runtime_python.touch()
    activations = []
    monkeypatch.setattr(workbench, "_activate_workspace", lambda config_path: activations.append(config_path))
    monkeypatch.setattr(workbench, "_run", lambda *args, **kwargs: pytest.fail("reuse must not reinstall CPU dependencies"))
    second_workspace = tmp_path / "second-workspace"
    workbench.initialize(second_workspace, service_port=18290, comfyui_port=18288,
                         reuse_runtime=True, activate=False)
    assert (second_workspace / "comfyui-data/custom_nodes/AstroPhotoFlow/assets/adapter.js").is_file()
    assert activations == []

    commands = []

    class FakeProcess:
        pid = 12345

        def poll(self):
            return None

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return None

    monkeypatch.setattr(workbench, "_port_available", lambda host, port: True)
    monkeypatch.setattr(workbench, "_health", lambda path: True)
    monkeypatch.setattr(workbench, "_launch", lambda command, cwd, env, log_path: (commands.append(command) or FakeProcess()))
    monkeypatch.setattr(workbench, "_record", lambda process, role, cwd, command: {"role": role, "command": command})
    monkeypatch.setattr(workbench.socket, "create_connection", lambda address, timeout=None: FakeConnection())

    workbench.start(config_path, activate=False)
    assert activations == []
    assert commands[0][1:] == ["-m", "astrophotoflow.backend.cli", "serve"]
    assert commands[1][commands[1].index("--base-directory") + 1] == str(workspace / "comfyui-data")


def test_workspace_plugins_and_development_assets_are_isolated(tmp_path, monkeypatch):
    package = tmp_path / "package"
    extension = package / "comfyui" / "extension"
    extension.mkdir(parents=True)
    (extension / "__init__.py").write_text("adapter", encoding="utf-8")
    monkeypatch.setattr(workbench, "__file__", str(package / "workbench.py"))
    assets = tmp_path / "build"
    assets.mkdir()
    for name in ("astrophotoflow.js", "astrophotoflow.css"):
        (assets / name).write_text("first", encoding="utf-8")
    first = workbench.install_extension(tmp_path / "first", assets)
    for name in ("astrophotoflow.js", "astrophotoflow.css"):
        (assets / name).write_text("second", encoding="utf-8")
    second = workbench.install_extension(tmp_path / "second", assets)
    assert (first / "assets/astrophotoflow.js").read_text(encoding="utf-8") == "first"
    assert (second / "assets/astrophotoflow.js").read_text(encoding="utf-8") == "second"
    assert first != second


def test_stop_terminates_children_before_clearing_process_state(tmp_path, monkeypatch):
    (tmp_path / "run").mkdir()
    state = tmp_path / "run/processes.json"
    state.write_text('{"processes": [{"pid": 1}]}', encoding="utf-8")
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
