"""Repeatable G0 probes; no workspace, database or running service required."""

import asyncio
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.cli.generate import generate_cli_script
from fastmcp.client.transports import StdioTransport
from modernization.contract_sample import Sample, build_tool_catalog, create_contract_app

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".artifacts/reports/modernization/g0"
PAYLOAD = {
    "equipment": {"kind": "camera", "gain": 0},
    "observed_at": "2026-10-31T00:00:00Z",
    "required_nullable": None,
}


async def verify_mcp() -> None:
    async with Client(build_tool_catalog()) as client:
        tools = await client.list_tools()
        assert [tool.name for tool in tools] == ["data_assets_inspect"]
        result = await client.call_tool("data_assets_inspect", {"body": PAYLOAD})
        assert result.structured_content["equipment"]["gain"] == 0
    async with Client(build_tool_catalog(search=True)) as client:
        assert {tool.name for tool in await client.list_tools()} == {"search_tools", "call_tool"}
        for query in ("camera gain", "相机 增益"):
            found = await client.call_tool("search_tools", {"query": query})
            assert "data_assets_inspect" in str(found.content)
            assert "inputSchema" in str(found.content)
        direct = await client.call_tool("data_assets_inspect", {"body": PAYLOAD})
        assert direct.structured_content["equipment"]["gain"] == 0
    transport = StdioTransport(command=sys.executable, args=["-m", "scripts.modernization.contract_sample"], cwd=str(ROOT))
    async with Client(transport) as client:
        result = await client.call_tool("data_assets_inspect", {"body": PAYLOAD})
        assert result.structured_content["equipment"]["gain"] == 0
    source = generate_cli_script(
        "G0 Probe", "scripts.modernization.contract_sample",
        "StdioTransport(command=sys.executable, args=['-m', 'scripts.modernization.contract_sample'])",
        {"from fastmcp.client.transports import StdioTransport"}, tools,
    )
    (OUTPUT / "cli.py").write_text(source, encoding="utf-8")
    completed = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, str(OUTPUT / "cli.py"), "call-tool", "data_assets_inspect", "--body", json.dumps(PAYLOAD)],
        cwd=ROOT, capture_output=True, text=True, timeout=45, check=True,
    )
    assert '"gain": 0' in completed.stdout
    (OUTPUT / "cli-result.txt").write_text(completed.stdout, encoding="utf-8")
    (OUTPUT / "root_cli.py").write_text(
        'from cyclopts import App\nfrom cli import app as business\n'
        'app = App(name="apf-probe")\napp.command(business, name="*")\n'
        '@app.command\ndef status():\n    print("isolated probe")\n'
        'if __name__ == "__main__":\n    app()\n', encoding="utf-8",
    )
    composed = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, str(OUTPUT / "root_cli.py"), "call-tool", "data_assets_inspect", "--body", json.dumps(PAYLOAD)],
        cwd=ROOT, capture_output=True, text=True, timeout=45, check=True,
    )
    assert '"gain": 0' in composed.stdout
    (OUTPUT / "mcp.json").write_text(json.dumps({
        "passed": True,
        "checks": ["typed input/output", "nested mount", "English BM25", "Chinese BM25", "known tool direct call",
                   "real stdio", "official generated CLI", "Cyclopts flattened composition"],
        "versions": {name: importlib.metadata.version(name) for name in
                     ("fastmcp", "cyclopts", "watchfiles", "ruff", "pytest-asyncio", "pydantic", "fastapi", "httpx")},
    }, indent=2), encoding="utf-8")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "openapi.json").write_text(json.dumps(create_contract_app().openapi(), indent=2), encoding="utf-8")
    Sample.model_validate(PAYLOAD)
    asyncio.run(verify_mcp())
    print("G0 MCP: mount, typed schema, bilingual BM25, direct call, stdio and generated CLI passed")


if __name__ == "__main__":
    main()
