from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.import_batches import BatchOut, ImportBatchSubmit, InspectionOut, InspectionPage, SourceInspection
from astrophotoflow.contracts.imports import ImportAccepted, ImportCreate, ImportRootEntryPage, PhotoImportOptions
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("imports")

    @mcp.tool(
        name="upload_one",
        description="Upload one local photo and start ingestion. Omitted classification uses file and frozen preset rules; unknown stays unknown.\n上传一张本机照片并开始入库。省略分类时采用文件资料和受理时固定的预设规则；未知仍保留未知。\n关键词: 导入 文件 来源 检查 上传 批次 ",
    )
    @service_errors
    def import_photo(
        path: str, options: PhotoImportOptions | None = None, *, client: AssetClient = Depends(service_client)
    ) -> ImportAccepted:
        """Upload one local photo and start ingestion. Omitted classification uses file and frozen preset rules; unknown stays unknown."""
        return client.import_photo(Path(path), options)

    @mcp.tool(
        name="upload",
        description="Upload multiple local photos in supplied order. Set options.create_dataset and dataset_name to register a logical group.\n按提供的顺序上传多张本机照片。设置 options.create_dataset 和 dataset_name 可登记逻辑图像组。\n关键词: 导入 文件 来源 检查 上传 批次 ",
    )
    @service_errors
    def import_photos(
        paths: list[str], options: PhotoImportOptions | None = None, *, client: AssetClient = Depends(service_client)
    ) -> ImportAccepted:
        """Upload multiple local photos in supplied order. Set options.create_dataset and dataset_name to register a logical group."""
        return client.import_photos([Path(path) for path in paths], options)

    @mcp.tool(
        name="roots",
        description="List the configured service-side local import roots.\n列出服务端已配置的本机导入根目录。\n关键词: 导入 文件 来源 检查 上传 批次 ",
    )
    @service_errors
    def list_import_roots(*, client: AssetClient = Depends(service_client)) -> dict[str, Any]:
        """List the configured service-side local import roots."""
        return {"items": client.list_import_roots()}

    @mcp.tool(
        name="browse",
        description="Browse files and folders inside one configured root using relative POSIX paths.\n使用相对 POSIX 路径浏览指定根目录内的文件和文件夹。\n关键词: 导入 文件 来源 检查 上传 批次 ",
    )
    @service_errors
    def browse_import_root(
        root_id: str,
        path: str = "",
        limit: int = 50,
        offset: int = 0,
        q: str | None = None,
        *,
        client: AssetClient = Depends(service_client),
    ) -> ImportRootEntryPage:
        """Browse files and folders inside one configured root using relative POSIX paths."""
        return client.browse_import_root(root_id, path, limit, offset, q)

    @mcp.tool(
        name="local",
        description="Import local absolute paths with managed storage and no configured root; folders select their current level only. Existing root_id relative sources also support reference mode. Preset values freeze at acceptance.\n从本机绝对路径导入并托管，无需预设根目录；文件夹仅选择当前层。已有 root_id 相对来源同时支持引用模式。受理时固定预设快照。\n关键词: 导入 文件 来源 检查 上传 批次 ",
    )
    @service_errors
    def import_local(body: ImportCreate, *, client: AssetClient = Depends(service_client)) -> ImportAccepted:
        """Import local absolute paths with managed storage and no configured root; folders select their current level only. Existing root_id relative sources also support reference mode. Preset values freeze at acceptance."""
        return client.import_local(body)

    @mcp.tool(
        name="inspect",
        description="Inspect local files/recursive folders without ingestion. Return a manifest ID, suggested groups and issues for user confirmation.\n只读检查文件／递归目录，返回分组建议、疑义与清单ID。确认前不入库。\n关键词: 导入 文件 来源 检查 上传 批次 检查 只读",
    )
    @service_errors
    def inspect_sources(body: SourceInspection, *, client: AssetClient = Depends(service_client)) -> InspectionOut:
        return client.inspect_import_sources(body)

    @mcp.tool(
        name="get_inspection",
        description="Read an existing inspection summary without rescanning.\n读取扫描摘要，不重新扫描。\n关键词: 导入 文件 来源 检查 上传 批次 读取 查询",
    )
    @service_errors
    def get_inspection(scan_id: str, *, client: AssetClient = Depends(service_client)) -> InspectionOut:
        return client.get_import_inspection(scan_id)

    @mcp.tool(
        name="entries",
        description="Page files, groups, excluded entries or source issues; optionally filter by group_id. Do not load every file into model context routinely.\n按需分页读取扫描文件、分组、排除项或来源错误；可按组筛选。\n关键词: 导入 文件 来源 检查 上传 批次 ",
    )
    @service_errors
    def inspection_entries(
        scan_id: str,
        kind: str = "files",
        group_id: str | None = None,
        limit: Annotated[int, Field(ge=1, le=200)] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
        *,
        client: AssetClient = Depends(service_client),
    ) -> InspectionPage:
        return client.list_inspection_entries(scan_id, kind, group_id, limit, offset)

    @mcp.tool(
        name="submit",
        description="Submit all user-confirmed groups once. Reuse request_id to query/recover the same acceptance; different content conflicts. Groups select group_id or member_ids. options are explicit manual values, not unconfirmed filename guesses. Optional project requires project_revision.\n用户确认后一次提交所有分组；request_id防重复受理，来源变化则拒绝。组用group_id或member_ids；人工options必须是确认内容。项目需project_revision。\n关键词: 导入 文件 来源 检查 上传 批次 提交 确认",
    )
    @service_errors
    def submit_batch(body: ImportBatchSubmit, *, client: AssetClient = Depends(service_client)) -> BatchOut:
        return client.submit_import_batch(body)

    return mcp
