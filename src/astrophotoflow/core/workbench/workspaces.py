from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from astrophotoflow.core import config as app_config
from astrophotoflow.core.config import Settings, load_settings

from . import observations, operations, runtime
from .errors import WorkbenchError


def load_workspace_config(path: Path) -> tuple[Settings, int, str, int]:
    settings = load_settings(path)
    parsed = urlsplit(settings.allowed_origins[0])
    if settings.port == parsed.port:
        raise WorkbenchError("资产服务与 ComfyUI 必须使用不同端口。")
    return settings, settings.port, settings.host, parsed.port


def resolve_workspace_ports(workspace: Path, service_port: int | None, comfyui_port: int | None) -> tuple[int, int]:
    """Return the ports a workspace must use; an existing config owns its ports."""
    for name, port in (("service-port", service_port), ("comfyui-port", comfyui_port)):
        if port is not None and not 1 <= port <= 65535:
            raise WorkbenchError(f"--{name} 必须是 1–65535 的端口。")
    config_path = workspace / "config.toml"
    if config_path.is_file():
        settings, stored_service, _host, stored_comfy = load_workspace_config(config_path)
        for name, requested, stored in (("service-port", service_port, stored_service),
                                        ("comfyui-port", comfyui_port, stored_comfy)):
            if requested is not None and requested != stored:
                raise WorkbenchError(
                    f"workspace 已存在且端口为 {stored_service}/{stored_comfy}；--{name} {requested} 与配置不一致。"
                    f"请改用配置端口，或停止后修改 {settings.workspace / 'config.toml'} 再重试。")
        return stored_service, stored_comfy
    resolved_service = service_port if service_port is not None else 8190
    resolved_comfy = comfyui_port if comfyui_port is not None else 8188
    if resolved_service == resolved_comfy:
        raise WorkbenchError("资产服务与 ComfyUI 必须使用不同端口。")
    return resolved_service, resolved_comfy


def prepare_workspace(workspace: Path, service_port: int | None = None, comfyui_port: int | None = None) -> Path:
    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    config_path = workspace / "config.toml"
    service_port, comfyui_port = resolve_workspace_ports(workspace, service_port, comfyui_port)

    for relative in ("data", "input", "output", "logs", "context", "comfyui-user", "comfyui-data", "run"):
        (workspace / relative).mkdir(parents=True, exist_ok=True)
    for relative in ("workflows", "subgraphs"):
        (workspace / "comfyui-user/default" / relative).mkdir(parents=True, exist_ok=True)
    templates = workspace / "comfyui-user/default/comfy.templates.json"
    if not templates.exists():
        templates.write_text("[]\n", encoding="utf-8")
    if not config_path.exists():
        config_path.write_text(
            "[server]\n"
            f'host = "127.0.0.1"\nport = {service_port}\n\n'
            '[storage]\ndata_dir = "data"\n\n'
            "[comfyui]\n"
            f'allowed_origins = ["http://127.0.0.1:{comfyui_port}", "http://localhost:{comfyui_port}"]\n',
            encoding="utf-8",
        )
    return config_path


def activate_workspace(config_path: Path) -> None:
    app_config.set_default_workspace(config_path.parent)


def initialize(workspace: Path, service_port: int | None = None, comfyui_port: int | None = None, *,
               frontend_assets: Path | None = None, activate: bool = True, reuse_runtime: bool = False) -> Path:
    workspace = workspace.expanduser().resolve()
    with operations.control_operation(workspace / "config.toml", "initialize"):
        observed = observations.status(workspace / "config.toml")
        if observed.processes or observed.state == "unknown":
            raise WorkbenchError("workspace仍在使用或状态无法确认；先停止后再初始化。")
        config_path = prepare_workspace(workspace, service_port, comfyui_port)
        runtime.prepare_runtime(reuse_only=reuse_runtime)
        runtime.install_frontend(workspace, frontend_assets)
        if activate:
            activate_workspace(config_path)
        return config_path


def create_workspace(workspace: Path, service_port: int | None = None, comfyui_port: int | None = None, *,
                     frontend_assets: Path | None = None) -> Path:
    workspace = workspace.expanduser().resolve()
    with operations.control_operation(workspace / "config.toml", "initialize"):
        observed = observations.status(workspace / "config.toml")
        if observed.ready and frontend_assets is None:
            load_workspace_config(workspace / "config.toml")
            return workspace / "config.toml"
        if observed.processes or observed.state == "unknown":
            raise WorkbenchError("workspace仍在使用或状态无法确认；先停止后再修改。")
        config_path = prepare_workspace(workspace, service_port, comfyui_port)
        if frontend_assets is not None:
            runtime.install_frontend(workspace, frontend_assets)
        return config_path
