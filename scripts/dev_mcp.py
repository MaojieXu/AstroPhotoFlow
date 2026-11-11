"""Run the official FastMCP HTTP reloader against one explicit workspace."""

import argparse
import os
import socket
import subprocess
import sys
from pathlib import Path

from astrophotoflow.core.workbench import status

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--server-spec", default="src/astrophotoflow/interfaces/mcp/server.py:create_server",
                        help="FastMCP factory; override for an isolated development probe")
    parser.add_argument("--reload-dir", type=Path, action="append",
                        help="Watch directories; defaults to this checkout's src/astrophotoflow")
    arguments = parser.parse_args()
    workspace = arguments.workspace.resolve()
    private = (ROOT / ".artifacts/workspaces").resolve()
    if not workspace.is_relative_to(private) or workspace == private or workspace.name in {"dev", "default"}:
        parser.error("Use an isolated test workspace below .artifacts/workspaces.")
    config = workspace / "config.toml"
    if not config.is_file():
        parser.error(f"Workspace is not prepared: {config}")
    if not 1 <= arguments.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    state = status(config)
    if not state.ready:
        parser.error(f"Workspace is not ready: {state.reason or state.state}")
    # Fail before starting the watcher; never select another port silently.
    with socket.socket() as listener:
        if os.name == "nt":
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", arguments.port))
    executable = Path(sys.executable).with_name("fastmcp.exe" if os.name == "nt" else "fastmcp")
    command = [str(executable), "run", arguments.server_spec, "--transport", "http",
               "--host", "127.0.0.1", "--port", str(arguments.port), "--reload", "--skip-env", "--no-banner"]
    for directory in arguments.reload_dir or [ROOT / "src/astrophotoflow"]:
        command.extend(["--reload-dir", str(directory.resolve(strict=True))])
    print(f"Workspace: {workspace}\nMCP: http://127.0.0.1:{arguments.port}/mcp\n"
          "After reload, reconnect your client and search tools again. Domain service Python changes require its restart.",
          flush=True)
    return subprocess.call(command, cwd=ROOT, env={**os.environ, "ASTROPHOTOFLOW_CONFIG": str(config)})


if __name__ == "__main__":
    raise SystemExit(main())
