from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

import httpx
from astrophotoflow.backend.import_schemas import AssetParametersPatch

from .client import AssetClient, ServiceApiError, config_path
from .workbench import WorkbenchError, initialize, start, status, stop


PARAMETER_OPTIONS = {
    "parameter_mode": "--parameter-mode",
    "camera_id": "--camera-id",
    "optical_system_id": "--optical-system-id",
    "filter_id": "--filter-id",
    "iso": "--iso",
    "gain": "--gain",
    "offset": "--offset",
    "exposure_seconds": "--exposure-seconds",
    "integration_seconds": "--integration-seconds",
    "sensor_temperature_c": "--sensor-temperature-c",
    "binning_x": "--binning-x",
    "binning_y": "--binning-y",
    "cfa_pattern": "--cfa-pattern",
}


def _parameters_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("asset_id")
    parser.add_argument("--base-revision", type=int, required=True)
    parser.add_argument("--clear", action="append", choices=PARAMETER_OPTIONS, default=[])
    parser.add_argument("--parameter-mode", choices=("iso", "gain", "standard"), default=argparse.SUPPRESS)
    for name in ("camera_id", "optical_system_id", "filter_id", "cfa_pattern"):
        parser.add_argument(PARAMETER_OPTIONS[name], default=argparse.SUPPRESS)
    parser.add_argument("--iso", type=int, default=argparse.SUPPRESS)
    parser.add_argument("--gain", type=float, default=argparse.SUPPRESS)
    parser.add_argument("--offset", type=float, default=argparse.SUPPRESS)
    parser.add_argument("--exposure-seconds", type=float, default=argparse.SUPPRESS)
    parser.add_argument("--integration-seconds", type=float, default=argparse.SUPPRESS)
    parser.add_argument("--sensor-temperature-c", type=float, default=argparse.SUPPRESS)
    parser.add_argument("--binning-x", type=int, default=argparse.SUPPRESS)
    parser.add_argument("--binning-y", type=int, default=argparse.SUPPRESS)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apf")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Initialize workspace and prepare the bundled CPU ComfyUI runtime")
    init.add_argument("--workspace", type=Path)
    init.add_argument("--service-port", type=int, default=8190)
    init.add_argument("--comfyui-port", type=int, default=8188)
    for name in ("start", "status", "stop"):
        command = commands.add_parser(name)
        command.add_argument("--workspace", type=Path)
    mcp_config = commands.add_parser("mcp-config", help="Print the Codex stdio MCP registration details")
    mcp_config.add_argument("--workspace", type=Path)
    photo = commands.add_parser("import-photo", help="Copy and ingest one local photograph")
    photo.add_argument("path", type=Path)
    task = commands.add_parser("task", help="Query an import task")
    task.add_argument("task_id")
    assets = commands.add_parser("assets")
    asset_commands = assets.add_subparsers(dest="asset_command", required=True)
    listing = asset_commands.add_parser("list")
    listing.add_argument("--limit", type=int, default=50)
    listing.add_argument("--offset", type=int, default=0)
    get_asset = asset_commands.add_parser("get")
    get_asset.add_argument("asset_id")
    patch = asset_commands.add_parser("parameters")
    _parameters_parser(patch)
    commands.add_parser("mcp", help="Run the stdio MCP server")
    return parser


def _run_asset_command(args):
    with AssetClient() as client:
        if args.command == "import-photo":
            return client.import_photo(args.path)
        if args.command == "task":
            return client.request("GET", f"/asset-tasks/{args.task_id}")
        if args.asset_command == "list":
            return client.request("GET", "/library/assets", params={"limit": args.limit, "offset": args.offset})
        if args.asset_command == "get":
            return client.request("GET", f"/library/assets/{args.asset_id}")
        parameters = {name: getattr(args, name) for name in PARAMETER_OPTIONS if hasattr(args, name)}
        parameters.update({name: None for name in args.clear})
        patch = AssetParametersPatch.model_validate(parameters).model_dump(mode="json", exclude_unset=True)
        return client.request(
            "PATCH", f"/library/assets/{args.asset_id}",
            json={"base_revision": args.base_revision, "parameters": patch},
        )


def _workspace_config(workspace: Path | None) -> Path:
    return (workspace.expanduser() / "config.toml").resolve() if workspace else config_path().resolve()


def _mcp_registration(workspace_config: Path) -> None:
    executable = Path(sys.executable).with_name("apf.exe" if os.name == "nt" else "apf").resolve(strict=True)
    if os.name == "nt":
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        command = "codex mcp add astrophotoflow --env " + quote(f"ASTROPHOTOFLOW_CONFIG={workspace_config}")
        command += " -- " + quote(executable) + " mcp"
        print("在 PowerShell 中执行以下 Codex 注册命令：\n" + command)
    else:
        print("Codex 注册命令：")
        print(f"codex mcp add astrophotoflow --env ASTROPHOTOFLOW_CONFIG={workspace_config} -- {executable} mcp")


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    if args.command == "mcp":
        from .mcp_server import server
        server.run()
        return
    try:
        if args.command == "init":
            workspace = args.workspace
            if workspace is None:
                workspace_text = input("请输入 AstroPhotoFlow workspace 路径：").strip()
                if not workspace_text:
                    raise WorkbenchError("workspace 路径不能为空。")
                workspace = Path(workspace_text)
            result = initialize(workspace, args.service_port, args.comfyui_port)
            print(f"workspace 已准备：{result.parent}")
        elif args.command == "start":
            print(start(_workspace_config(args.workspace)))
        elif args.command == "status":
            state, processes = status(_workspace_config(args.workspace))
            print(json.dumps({"status": state, "processes": processes}, ensure_ascii=False, indent=2))
            if state == "partial":
                raise WorkbenchError("工作台部分进程未运行；请先 apf stop。")
        elif args.command == "stop":
            print(stop(_workspace_config(args.workspace)))
        elif args.command == "mcp-config":
            _mcp_registration(_workspace_config(args.workspace))
        else:
            result = _run_asset_command(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ServiceApiError, WorkbenchError, httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
