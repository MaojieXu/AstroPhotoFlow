"""One HTTP client per server lifetime; catalog construction stays offline."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import Context
from fastmcp.dependencies import CurrentContext
from fastmcp.server.lifespan import lifespan

from astrophotoflow.client import AssetClient


@lifespan
async def service_lifespan(server):
    with AssetClient() as client:
        yield {"client": client}


@asynccontextmanager
async def service_client(ctx: Context = CurrentContext()) -> AsyncIterator[AssetClient]:
    # A mounted Context owns the child's lifespan; the MCP session owns the
    # root lifespan, where the one shared HTTP client was created.
    request = ctx.request_context
    if request is None:
        raise RuntimeError("MCP session has not started")
    # Yield the borrowed client: returning a context-manager object makes the
    # dependency engine enter and close it for each individual tool call.
    yield request.lifespan_context["client"]
