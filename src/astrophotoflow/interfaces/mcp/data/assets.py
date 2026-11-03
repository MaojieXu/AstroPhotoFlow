"""Conversational image management through the shared HTTP service."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.assets import AssetContentAccept, AssetContentObservation, AssetOut, AssetVersionPage
from astrophotoflow.contracts.common import UuidInput
from astrophotoflow.contracts.image_management import (
    AssetMetadataChange,
    AssetRevisionRef,
    EquipmentApplication,
    ImageBatchResult,
    ImageChanges,
    ImageDetail,
    ImageHeaderPage,
    ImagePage,
    ImageSearch,
    MasterProvenanceChanges,
    MasterProvenanceOut,
    PageLimit,
    PageOffset,
    Revision,
)
from astrophotoflow.contracts.inputs import CanvasDataOut, CanvasDataRequest
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("assets")

    @mcp.tool(name="search", description="Search individual subframes, masters or videos by capture facts, target, equipment and time. 图像 亮场 暗场 平场 偏置 Master 查询 分页 设备")
    @service_errors
    def search(query: ImageSearch | None = None, *, client: AssetClient = Depends(service_client)) -> ImagePage:
        return ImagePage.model_validate(client.image_assets_search(query=query), strict=False)

    @mcp.tool(name="get", description="Read image facts/current revision, optionally selecting an exact fixed version. 图像 素材 读取 版本 设备 时间")
    @service_errors
    def get(asset_id: UuidInput, version_id: UuidInput | None = None, *, client: AssetClient = Depends(service_client)) -> ImageDetail:
        return ImageDetail.model_validate(client.image_assets_get(asset_id=asset_id, version_id=version_id), strict=False)

    @mcp.tool(name="list_versions", description="Page fixed original image versions. 图像 原件 固定版本 分页")
    @service_errors
    def list_versions(asset_id: UuidInput, limit: PageLimit = 50, offset: PageOffset = 0, *, client: AssetClient = Depends(service_client)) -> AssetVersionPage:
        return AssetVersionPage.model_validate(client.image_assets_list_versions(asset_id=asset_id, limit=limit, offset=offset), strict=False)

    @mcp.tool(name="update", description="Update explicit image facts at expected_revision. Omission preserves, supported null clears, zero is valid. Original bytes stay fixed. 图像 资料 分类 参数 时间 修改")
    @service_errors
    def update(asset_id: UuidInput, expected_revision: Revision, changes: ImageChanges, *, client: AssetClient = Depends(service_client)) -> ImageDetail:
        return ImageDetail.model_validate(client.image_assets_update(asset_id=asset_id, expected_revision=expected_revision, changes=changes), strict=False)

    @mcp.tool(name="update_metadata_batch", description="Atomically update only selected images at their individual revisions. 图像 批量 资料 分类 参数 修改")
    @service_errors
    def update_metadata_batch(items: list[AssetMetadataChange], *, client: AssetClient = Depends(service_client)) -> ImageBatchResult:
        return ImageBatchResult.model_validate(client.image_assets_update_metadata_batch(items=items), strict=False)

    @mcp.tool(name="apply_equipment", description="Apply only explicitly selected device or optional setup fields with current revisions. Equipment association never changes image exposure, gain, offset or measured temperature. 图像 设备 组合 关联 快照")
    @service_errors
    def apply_equipment(assets: list[AssetRevisionRef], equipment: EquipmentApplication, *, client: AssetClient = Depends(service_client)) -> ImageBatchResult:
        return ImageBatchResult.model_validate(client.image_assets_apply_equipment(assets=assets, equipment=equipment), strict=False)

    @mcp.tool(name="read_header", description="Read selected scientific FITS header facts from an exact original version. 图像 FITS 文件头 科学 参数 时间")
    @service_errors
    def read_header(asset_id: UuidInput, version_id: UuidInput, hdu_index: Annotated[int, Field(ge=0)] = 0, keywords: list[str] | None = None, limit: PageLimit = 100, offset: PageOffset = 0, *, client: AssetClient = Depends(service_client)) -> ImageHeaderPage:
        return ImageHeaderPage.model_validate(client.image_assets_read_header(asset_id=asset_id, version_id=version_id, hdu_index=hdu_index, keywords=keywords, limit=limit, offset=offset), strict=False)

    @mcp.tool(name="get_master_provenance", description="Read revisioned user-declared Master sources separately from platform provenance. Master 母版 来源 谱系 校准 历史")
    @service_errors
    def get_master_provenance(asset_id: UuidInput, version_id: UuidInput, provenance_version_id: UuidInput | None = None, *, client: AssetClient = Depends(service_client)) -> MasterProvenanceOut:
        return MasterProvenanceOut.model_validate(client.image_assets_get_master_provenance(asset_id=asset_id, version_id=version_id, provenance_version_id=provenance_version_id), strict=False)

    @mcp.tool(name="update_master_provenance", description="Save actual user-declared Master sources/processing. Planned bindings never imply executed calibration. Master 母版 来源 历史 修改")
    @service_errors
    def update_master_provenance(asset_id: UuidInput, version_id: UuidInput, expected_revision: Revision, changes: MasterProvenanceChanges, *, client: AssetClient = Depends(service_client)) -> MasterProvenanceOut:
        return MasterProvenanceOut.model_validate(client.image_assets_update_master_provenance(asset_id=asset_id, version_id=version_id, expected_revision=expected_revision, changes=changes), strict=False)

    @mcp.tool(name="prepare_canvas_data", description="Prepare a fixed scientific reference without editing/executing the canvas. 科学 输入 固定 图像 画布 准备")
    @service_errors
    def prepare_canvas_data(body: CanvasDataRequest, *, client: AssetClient = Depends(service_client)) -> CanvasDataOut:
        return client.prepare_canvas_data(body)

    @mcp.tool(name="observe_content", description="Observe fixed original content without accepting changes. 图像 原件 哈希 内容 检查")
    @service_errors
    def observe_content(asset_id: str, *, client: AssetClient = Depends(service_client)) -> AssetContentObservation:
        return client.observe_asset_content(asset_id)

    @mcp.tool(name="accept_content", description="Accept confirmed original changes at observed hash/revision. Query unknown results rather than replay. 图像 原件 内容 接纳 确认")
    @service_errors
    def accept_content(asset_id: str, body: AssetContentAccept, *, client: AssetClient = Depends(service_client)) -> AssetOut:
        return client.accept_asset_content(asset_id, body)

    return mcp
