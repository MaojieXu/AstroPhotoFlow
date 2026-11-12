"""Compose generated business tools with explicit local management commands."""

import sys

import httpx
from cyclopts import App
from fastmcp.exceptions import ToolError

from astrophotoflow.core.config import ConfigurationError
from astrophotoflow.core.workbench import WorkbenchError
from astrophotoflow.interfaces.cli.generated import app as business
from astrophotoflow.interfaces.cli.local import register_local
from astrophotoflow.interfaces.client.errors import ServiceApiError

app = App(name="apf", help="Local AstroPhotoFlow management and typed MCP business tools.")
app.command(business, name="*")
register_local(app)


def main() -> None:
    try:
        app()
    except (ConfigurationError, ServiceApiError, WorkbenchError, httpx.HTTPError, ToolError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
