"""Generate the business CLI from the complete offline FastMCP catalog."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from fastmcp.cli.generate import generate_cli_script

from astrophotoflow.interfaces.mcp.server import build_tool_catalog

ROOT = Path(__file__).resolve().parents[1]

_ARGUMENT_FILTER = (
    "async def _call_tool(tool_name: str, arguments: dict) -> None:\n"
    "    # None represents an omitted optional argument; empty arrays are values.\n"
    "    filtered = {k: v for k, v in arguments.items() if v is not None}\n"
)


def _allows_null(schema: dict) -> bool:
    value_type = schema.get("type")
    return (
        value_type == "null"
        or (isinstance(value_type, list) and "null" in value_type)
        or any(branch.get("type") == "null" for branch in schema.get("anyOf", ()))
    )


def _preserve_required_nulls(source: str, tools) -> str:
    if source.count(_ARGUMENT_FILTER) != 1:
        raise RuntimeError("Expected one FastMCP argument filter. Review the CLI template before regenerating.")

    required_nullable = {}
    for tool in tools:
        schema = tool.input_schema
        properties = schema.get("properties", {})
        fields = tuple(
            name for name in sorted(schema.get("required", ()))
            if _allows_null(properties.get(name, {}))
        )
        if fields:
            required_nullable[tool.name] = fields
    required_nullable = dict(sorted(required_nullable.items()))
    replacement = (
        f"_REQUIRED_NULLABLE_ARGUMENTS = {required_nullable!r}\n\n\n"
        "async def _call_tool(tool_name: str, arguments: dict) -> None:\n"
        "    required_nullable = _REQUIRED_NULLABLE_ARGUMENTS.get(tool_name, ())\n"
        "    filtered = {k: v for k, v in arguments.items() if v is not None or k in required_nullable}\n"
    )
    return source.replace(_ARGUMENT_FILTER, replacement, 1)


async def generate() -> None:
    tools = sorted((tool.to_mcp_tool() for tool in await build_tool_catalog().list_tools()), key=lambda tool: tool.name)
    source = generate_cli_script(
        "AstroPhotoFlow",
        "astrophotoflow.interfaces.mcp.server",
        "StdioTransport(command=sys.executable, args=['-m', 'astrophotoflow.interfaces.mcp.server'], env={**({'ASTROPHOTOFLOW_CONFIG': os.environ['ASTROPHOTOFLOW_CONFIG']} if 'ASTROPHOTOFLOW_CONFIG' in os.environ else {}), 'PYTHONUTF8': '1'})",
        {"import os", "from fastmcp.client.transports import StdioTransport"},
        tools,
    )
    source = _preserve_required_nulls(source, tools)
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
