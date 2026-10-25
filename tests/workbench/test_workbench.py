from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

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
    copied_extension = runtime / "comfyui-data" / "custom_nodes" / "AstroPhotoFlow"
    assert (copied_extension / "__init__.py").read_text(encoding="utf-8") == "CPU adapter marker\n"
    assert (copied_extension / "assets" / "adapter.js").is_file()

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

    workbench.start(config_path)
    assert commands[0][1:] == ["-m", "astrophotoflow.backend.cli", "serve"]


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
