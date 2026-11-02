"""Generate the business CLI from the complete offline FastMCP catalog."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from fastmcp.cli.generate import generate_cli_script

from astrophotoflow.interfaces.mcp.server import build_tool_catalog

ROOT = Path(__file__).resolve().parents[1]


async def generate() -> None:
    tools = sorted((tool.to_mcp_tool() for tool in await build_tool_catalog().list_tools()), key=lambda tool: tool.name)
    source = generate_cli_script(
        "AstroPhotoFlow",
        "astrophotoflow.interfaces.mcp.server",
        "StdioTransport(command=sys.executable, args=['-m', 'astrophotoflow.interfaces.mcp.server'], env={**({'ASTROPHOTOFLOW_CONFIG': os.environ['ASTROPHOTOFLOW_CONFIG']} if 'ASTROPHOTOFLOW_CONFIG' in os.environ else {}), 'PYTHONUTF8': '1'})",
        {"import os", "from fastmcp.client.transports import StdioTransport"},
        tools,
    )
    target = ROOT / "src/astrophotoflow/interfaces/cli/generated.py"
    source = (await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "ruff", "check", "--select", "I", "--fix", "--silent", "--stdin-filename", str(target), "-"],
        input=source, text=True, capture_output=True, check=True,
    )).stdout
    target.write_text(source, encoding="utf-8")
    (ROOT / "docs/api/mcp-tools.json").write_text(
        json.dumps([tool.model_dump(mode="json", by_alias=True, exclude_none=True) for tool in tools], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Generated {len(tools)} tools; no search transform or workspace connection used.")


if __name__ == "__main__":
    asyncio.run(generate())
