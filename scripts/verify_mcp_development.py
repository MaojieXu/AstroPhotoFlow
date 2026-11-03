"""Verify real tool/schema changes through official reload and fresh connections."""

import argparse
import asyncio
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

import psutil
from dev_prepare import ROOT, environment
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from fastmcp.exceptions import ClientError


def probe_source(revision: int) -> str:
    """Synthetic tools only; production catalog and its HTTP client stay real."""
    signature = "amount: int = 1" if revision == 1 else "amount: int, offset: int = 0"
    value = "amount" if revision == 1 else "amount + offset + 100"
    member = "removed" if revision == 1 else "added"
    return dedent(f'''\
        import os
        from fastmcp.server.transforms.search import BM25SearchTransform
        from astrophotoflow.interfaces.mcp.server import build_tool_catalog

        def factory():
            server = build_tool_catalog()
            @server.tool
            def reload_probe({signature}) -> dict:
                """Synthetic read-only hot reload probe, revision {revision}."""
                return {{"revision": {revision}, "value": {value}, "pid": os.getpid(),
                        "config": os.environ["ASTROPHOTOFLOW_CONFIG"]}}
            @server.tool
            def reload_{member}() -> str:
                """Synthetic catalog membership probe."""
                return "{member}"
            server.add_transform(BM25SearchTransform(max_results=10))
            return server
        ''')


async def read_once(target) -> dict:
    async with Client(target, timeout=10) as client:
        assert {tool.name for tool in await client.list_tools()} == {"search_tools", "call_tool"}
        result = await client.call_tool("data_assets_search", {"query": {"limit": 1}})
        assert result.structured_content["limit"] == 1
        return {"total": result.structured_content["total"]}


async def snapshot(url: str) -> dict:
    async with Client(url, timeout=5, init_timeout=5) as client:
        assert {tool.name for tool in await client.list_tools()} == {"search_tools", "call_tool"}
        found = await client.call_tool("search_tools", {"query": "reload_probe"})
        definitions = json.loads(found.content[0].text)
        definition = next(row for row in definitions if row["name"] == "reload_probe")
        result = await client.call_tool("call_tool", {"name": "reload_probe", "arguments": {"amount": 1}})
        # Search-transform forwarding preserves the tool's JSON result in content.
        probe = json.loads(result.content[0].text)
        member = "removed" if probe["revision"] == 1 else "added"
        absent = "added" if member == "removed" else "removed"
        included = await client.call_tool("search_tools", {"query": f"reload_{member}"})
        assert any(row["name"] == f"reload_{member}" for row in json.loads(included.content[0].text))
        available = await client.call_tool(f"reload_{member}", {})
        assert member in available.content[0].text
        missing = await client.call_tool(f"reload_{absent}", {}, raise_on_error=False)
        assert missing.is_error
        invalid = await client.call_tool("reload_probe", {"amount": "not-an-integer"}, raise_on_error=False)
        assert invalid.is_error
        omitted = await client.call_tool("reload_probe", {}, raise_on_error=False)
        assert omitted.is_error == (probe["revision"] == 2)
        page = await client.call_tool("data_assets_search", {"query": {"limit": 1}})
        return {"probe": probe, "definition": definition, "present": member, "absent": absent,
                "invalid_argument_rejected": True, "omitted_argument_rejected": omitted.is_error,
                "asset_total": page.structured_content["total"]}


async def wait_snapshot(url: str, revision: int, process: subprocess.Popen, log: Path) -> dict:
    deadline = time.monotonic() + 40
    failure = None
    while time.monotonic() < deadline and process.poll() is None:
        try:
            result = await snapshot(url)
            if result["probe"]["revision"] == revision:
                return result
        except (OSError, TimeoutError, RuntimeError, ClientError) as exc:
            # Only isolated, read-only observations are retried while the worker starts.
            failure = repr(exc)
        await asyncio.sleep(0.25)
    raise RuntimeError(f"Revision {revision} did not become readable: {failure}\n"
                       f"{log.read_text(encoding='utf-8', errors='replace')[-4000:]}")


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


async def verify(workspace: Path, report: Path) -> dict:
    workspace = workspace.resolve(strict=True)
    private = (ROOT / ".artifacts/workspaces").resolve()
    if not workspace.is_relative_to(private) or workspace == private or workspace.name in {"dev", "default"}:
        raise ValueError("An explicit private Feature workspace in this checkout is required")
    config = (workspace / "config.toml").resolve(strict=True)
    report.mkdir(parents=True, exist_ok=True)
    env = environment(workspace)
    stdio = []
    for _ in range(2):
        stdio.append(await read_once(StdioTransport(
            command=sys.executable, args=["-m", "astrophotoflow.interfaces.mcp.server"],
            env=env, cwd=str(ROOT),
        )))
    assert stdio[0] == stdio[1]
    temporary = ROOT / ".artifacts/tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="mcp-reload-", dir=temporary) as directory:
        source = Path(directory) / "server.py"
        source.write_text(probe_source(1), encoding="utf-8")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        log = report / "reload.log"
        command = [sys.executable, str(ROOT / "scripts/dev_mcp.py"), "--workspace", str(workspace),
                   "--port", str(port), "--server-spec", str(source) + ":factory", "--reload-dir", directory]
        with log.open("w", encoding="utf-8") as stream:
            process = await asyncio.to_thread(
                subprocess.Popen, command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        try:
            url = f"http://127.0.0.1:{port}/mcp"
            before = await wait_snapshot(url, 1, process, log)
            source.write_text(probe_source(2), encoding="utf-8")
            after = await wait_snapshot(url, 2, process, log)
            assert before["probe"]["value"] == 1 and after["probe"]["value"] == 101
            assert before["probe"]["pid"] != after["probe"]["pid"]
            assert before["probe"]["config"] == after["probe"]["config"] == str(config)
            assert "offset" not in before["definition"]["inputSchema"]["properties"]
            assert "offset" in after["definition"]["inputSchema"]["properties"]
            assert "amount" in after["definition"]["inputSchema"]["required"]
            assert before["asset_total"] == after["asset_total"] == stdio[0]["total"]
            result = {"passed": True, "workspace_config": str(config), "stdio_fresh_sessions": 2,
                      "official_reload": True, "explicit_reconnection": True, "url": url,
                      "before": before, "after": after,
                      "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
        finally:
            await asyncio.to_thread(stop_owned, process)
        result["owned_process_tree_stopped"] = True
        (report / "development.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=ROOT / ".artifacts/reports/mcp-development")
    args = parser.parse_args()
    asyncio.run(verify(args.workspace, args.report))
    print("Tool implementation, membership, schemas, real service reads and explicit reconnection passed; owned processes stopped.")
