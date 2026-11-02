"""Exercise official reload and explicit reconnection against a chosen workspace."""

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import psutil
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).resolve().parents[1]


async def read_once(target) -> dict:
    async with Client(target, timeout=5) as client:
        assert {tool.name for tool in await client.list_tools()} == {"search_tools", "call_tool"}
        result = await client.call_tool("data_assets_list", {"query": {"limit": 1}})
        assert result.structured_content["limit"] == 1
        return {"total": result.structured_content["total"]}


async def wait_read(url: str, process: subprocess.Popen, log: Path) -> dict:
    deadline = time.monotonic() + 30
    failure = None
    while time.monotonic() < deadline and process.poll() is None:
        try:
            parsed = urlsplit(url)
            _, writer = await asyncio.wait_for(asyncio.open_connection(parsed.hostname, parsed.port), timeout=1)
        except (OSError, TimeoutError) as exc:
            failure = exc
            await asyncio.sleep(0.2)
        else:
            writer.close()
            await writer.wait_closed()
            return await read_once(url)
    raise RuntimeError(f"Reload server did not become readable: {failure}\n{log.read_text(encoding='utf-8', errors='replace')[-3000:]}")


def stop_owned(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    parent = psutil.Process(process.pid)
    children = parent.children(recursive=True)
    for child in reversed(children):
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    parent.terminate()
    _, alive = psutil.wait_procs([*children, parent], timeout=5)
    for owned in alive:
        owned.kill()
    process.wait(timeout=5)


async def verify(config: Path, report: Path) -> None:
    config = config.resolve(strict=True)
    report.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "ASTROPHOTOFLOW_CONFIG": str(config), "PYTHONUTF8": "1"}
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    # These are two fresh stdio sessions, not replay of a prior write.
    stdio = []
    for _ in range(2):
        stdio.append(await read_once(StdioTransport(
            command=sys.executable, args=["-m", "astrophotoflow.interfaces.mcp.server"],
            env={"ASTROPHOTOFLOW_CONFIG": str(config), "PYTHONUTF8": "1"}, cwd=str(ROOT),
        )))
    assert stdio[0] == stdio[1]
    temporary = ROOT / ".artifacts/tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="mcp-reload-", dir=temporary) as directory:
        source = Path(directory) / "server.py"
        prefix = "import sys\nfrom astrophotoflow.interfaces.mcp.server import create_server\n"
        suffix = "\ndef build():\n    return create_server()\n"
        source.write_text(prefix + "print('APF_RELOAD=first',file=sys.stderr,flush=True)" + suffix, encoding="utf-8")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        log = report / "reload.log"
        command = [str(Path(sys.executable).with_name("fastmcp.exe" if os.name == "nt" else "fastmcp")),
                   "run", str(source) + ":build", "--transport", "http", "--host", "127.0.0.1",
                   "--port", str(port), "--reload", "--reload-dir", directory]
        with log.open("w", encoding="utf-8") as stream:
            process = await asyncio.to_thread(
                subprocess.Popen, command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        try:
            url = f"http://127.0.0.1:{port}/mcp"
            first = await wait_read(url, process, log)
            before = [child.pid for child in psutil.Process(process.pid).children(recursive=True)]
            source.write_text(prefix + "print('APF_RELOAD=second-revision',file=sys.stderr,flush=True)" + suffix, encoding="utf-8")
            deadline = time.monotonic() + 30
            while "APF_RELOAD=second-revision" not in log.read_text(encoding="utf-8", errors="replace"):
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("Official reload did not adopt the changed factory module")
                await asyncio.sleep(0.2)
            second = await wait_read(url, process, log)
            after = [child.pid for child in psutil.Process(process.pid).children(recursive=True)]
            assert first == second
            assert before and after and before != after
            (report / "development.json").write_text(json.dumps({
                "passed": True, "workspace_config": str(config), "stdio_fresh_sessions": len(stdio),
                "official_reload": True, "before_worker_pids": before, "after_worker_pids": after,
                "explicit_reconnection": True, "read_only_totals": [first["total"], second["total"]],
            }, indent=2) + "\n", encoding="utf-8")
        finally:
            await asyncio.to_thread(stop_owned, process)
    print("Official reload and fresh stdio/HTTP reconnection passed; test process tree stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(verify(args.workspace / "config.toml", ROOT / ".artifacts/reports/modernization/g4/development"))
