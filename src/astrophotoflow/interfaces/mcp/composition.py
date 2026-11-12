"""Apply the same error policy to every mounted tool namespace."""

from fastmcp import FastMCP

from astrophotoflow.interfaces.mcp.errors import ServiceErrors


def tool_namespace(name: str) -> FastMCP:
    return FastMCP(name, middleware=[ServiceErrors()], mask_error_details=True)
