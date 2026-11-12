"""Isolated G0 compatibility probe, not a platform business entry point."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import FastAPI, Query, Response
from fastmcp import FastMCP
from fastmcp.server.transforms.search import BM25SearchTransform
from pydantic import BaseModel, Field


class Camera(BaseModel):
    kind: Literal["camera"]
    gain: float


class Filter(BaseModel):
    kind: Literal["filter"]
    bandwidth: float | None


class Sample(BaseModel):
    equipment: Annotated[Camera | Filter, Field(discriminator="kind")]
    observed_at: datetime
    required_nullable: str | None
    optional_nullable: str | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorReply(BaseModel):
    error: ErrorDetail
    request_id: str


def create_contract_app() -> FastAPI:
    app = FastAPI()

    @app.post("/samples", operation_id="probeSample", responses={422: {"model": ErrorReply}})
    def sample(body: Sample) -> Sample:
        return body

    @app.get("/samples", operation_id="probeQuery")
    def query(tags: Annotated[list[str], Query()]) -> list[str]:
        return tags

    @app.get("/binary", operation_id="probeBinary", response_class=Response,
             responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}})
    def binary() -> Response:
        return Response(b"probe", media_type="image/png")

    return app


def build_tool_catalog(*, search: bool = False) -> FastMCP:
    assets = FastMCP("assets")

    @assets.tool
    def inspect(body: Sample) -> Sample:
        """Inspect camera gain and filter metadata. 检查 相机 增益 滤镜 元数据。"""
        return body

    data = FastMCP("data")
    data.mount(assets, namespace="assets")
    server = FastMCP("G0 Contract Probe")
    server.mount(data, namespace="data")
    if search:
        server.add_transform(BM25SearchTransform(max_results=10))
    return server


mcp = build_tool_catalog()


if __name__ == "__main__":
    mcp.run(show_banner=False)
