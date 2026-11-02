"""Local workspace/runtime control; business commands are generated from MCP."""

import json
import os
import sys
from pathlib import Path

from cyclopts import App

from astrophotoflow.core import workbench
from astrophotoflow.core.config import resolve_config_path


def workspace_config(workspace: Path | None) -> Path:
    return (workspace.expanduser() / "config.toml").resolve() if workspace else resolve_config_path()


def register_local(app: App) -> None:
    runtime = App(name="runtime", help="Prepare the fixed local CPU runtime.")
    workspace_app = App(name="workspace", help="Manage local workspace configuration.")
    app.command(runtime)
    app.command(workspace_app)

    @runtime.command(name="prepare")
    def runtime_prepare(*, reuse_only: bool = False) -> None:
        print(json.dumps(workbench.prepare_runtime(reuse_only=reuse_only), ensure_ascii=False, indent=2))

    @workspace_app.command(name="create")
    def create(*, workspace: Path, service_port: int = 8190, comfyui_port: int = 8188, frontend_assets: Path | None = None) -> None:
        result = workbench.create_workspace(workspace, service_port, comfyui_port, frontend_assets=frontend_assets)
        print(json.dumps({"workspace": str(result.parent), "config_path": str(result)}, ensure_ascii=False, indent=2))

    @app.command(name="init")
    def initialize(
        *,
        workspace: Path | None = None,
        service_port: int = 8190,
        comfyui_port: int = 8188,
        frontend_assets: Path | None = None,
        reuse_runtime: bool = False,
        activate: bool = True,
    ) -> None:
        if workspace is None:
            text = input("请输入 AstroPhotoFlow workspace 路径：").strip()
            if not text:
                raise workbench.WorkbenchError("workspace 路径不能为空。")
            workspace = Path(text)
        result = workbench.initialize(
            workspace, service_port, comfyui_port, frontend_assets=frontend_assets, activate=activate, reuse_runtime=reuse_runtime
        )
        print(f"workspace 已准备：{result.parent}")

    @app.command(name="status")
    def status(*, workspace: Path | None = None) -> None:
        result = workbench.status(workspace_config(workspace))
        print(result.model_dump_json(indent=2))
        if result.state in {"partial", "unknown"}:
            raise SystemExit(1)

    @app.command(name="start")
    def start(*, workspace: Path | None = None) -> None:
        result = workbench.start(workspace_config(workspace))
        print(result.model_dump_json(indent=2))
        if result.state != "completed":
            raise SystemExit(1)

    @app.command(name="stop")
    def stop(*, workspace: Path | None = None) -> None:
        result = workbench.stop(workspace_config(workspace))
        print(result.model_dump_json(indent=2))
        if result.state != "completed":
            raise SystemExit(1)

    @app.command(name="restart")
    def restart(*, workspace: Path | None = None) -> None:
        result = workbench.restart(workspace_config(workspace))
        print(result.model_dump_json(indent=2))
        if result.state != "completed":
            raise SystemExit(1)

    @app.command(name="mcp")
    def mcp() -> None:
        from astrophotoflow.interfaces.mcp.server import run

        run()

    @app.command(name="mcp-config")
    def mcp_config(*, workspace: Path | None = None) -> None:
        executable = Path(sys.executable).with_name("apf.exe" if os.name == "nt" else "apf").resolve(strict=True)
        config = workspace_config(workspace)
        if os.name == "nt":
            quote = lambda value: "'" + str(value).replace("'", "''") + "'"
            command = "codex mcp add astrophotoflow --env " + quote(f"ASTROPHOTOFLOW_CONFIG={config}")
            command += " -- " + quote(executable) + " mcp"
        else:
            from shlex import quote

            command = f"codex mcp add astrophotoflow --env {quote(f'ASTROPHOTOFLOW_CONFIG={config}')} -- {quote(str(executable))} mcp"
        print(command)
