"""Explicit file intake; grouping and metadata decisions belong to the Agent."""

from pathlib import Path
from typing import Literal
from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.common import UuidInput
from astrophotoflow.contracts.image_calibration import CalibrationPatch
from astrophotoflow.contracts.image_imports import (
    ConfirmedFile,
    ImageImportReceipt,
    ImageInspectionOut,
    ImageInspectionPage,
    ImportDefaults,
    InspectionQuery,
)
from astrophotoflow.contracts.image_management import ImageName, Revision
from astrophotoflow.contracts.imports import ImportAccepted, ImportCreate, ImportRootEntryPage, PhotoImportOptions
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client

IMPORT_CONFIRMATION_PROMPT = " Before importing, summarize the exact file scope/order, proposed grouping, equipment, calibration and relevant missing or uncertain facts; ask the user and obtain confirmation. Model knowledge or reliable web sources may inform recommendations, but adopt suggested values only after user confirmation. Unknown values are allowed: the user may leave them unknown or leave calibration unconfigured. Group identical questions across an explicit file selection rather than asking per frame. A selected Master does not mean all unknowns were accepted. Set accept_unknown=true only after explaining and confirming this request's specific calibration unknowns; never bypass known conflicts. Equipment specifications cannot establish actual exposure, gain, offset, temperature or Master processing history. If sources or the confirmed scope/equipment/calibration change, review the differences before import. Few-shot: 'These 147 H frames use MOANA and Master Flat A. The Master temperature is unknown. Keep it unknown and save a pending-verification relation, or leave flat unconfigured?' Only then submit the confirmed choice. No quality analysis or calibration is executed by importing."


def build_server() -> FastMCP:
    mcp = tool_namespace("imports")

    @mcp.tool(
        name="inspect",
        description="Read-only file/directory inspection returning file facts and source stamps, without suggested groups or ingestion. Agent decides grouping/metadata and obtains user confirmation. 图像 导入 检查 文件 事实 来源",
    )
    @service_errors
    def inspect(paths: list[str], recursive: bool = True, *, client: AssetClient = Depends(service_client)) -> ImageInspectionOut:
        return ImageInspectionOut.model_validate(client.image_imports_inspect(paths=paths, recursive=recursive), strict=False)

    @mcp.tool(name="get_inspection", description="Read existing file inspection without rescanning. 图像 导入 扫描 摘要 读取")
    @service_errors
    def get_inspection(scan_id: UuidInput, *, client: AssetClient = Depends(service_client)) -> ImageInspectionOut:
        return ImageInspectionOut.model_validate(client.image_imports_get_inspection(scan_id=scan_id), strict=False)

    @mcp.tool(
        name="entries",
        description="Page file facts, exclusions or issues, never automatic groups. Keep filename hints separate from scientific header facts. 图像 导入 文件 分页 事实 问题",
    )
    @service_errors
    def entries(
        scan_id: UuidInput,
        kind: Literal["files", "excluded", "issues"] = "files",
        query: InspectionQuery | None = None,
        *,
        client: AssetClient = Depends(service_client),
    ) -> ImageInspectionPage:
        return ImageInspectionPage.model_validate(client.image_imports_entries(scan_id=scan_id, kind=kind, query=query), strict=False)

    @mcp.tool(
        name="import_asset",
        description="Import exactly one confirmed scanned file as an independent subframe/Master; no implicit group. request_id reconciles uncertainty. 图像 导入 单张 亮场 校准 Master"
        + IMPORT_CONFIRMATION_PROMPT,
    )
    @service_errors
    def import_asset(
        request_id: UuidInput,
        scan_id: UuidInput,
        file: ConfirmedFile,
        defaults: ImportDefaults | None = None,
        storage_mode: Literal["managed"] = "managed",
        accept_unknown: bool = False,
        project_id: UuidInput | None = None,
        project_base_revision: Revision | None = None,
        *,
        client: AssetClient = Depends(service_client),
    ) -> ImageImportReceipt:
        return ImageImportReceipt.model_validate(
            client.image_imports_import_asset(
                request_id=request_id,
                scan_id=scan_id,
                file=file,
                defaults=defaults,
                storage_mode=storage_mode,
                accept_unknown=accept_unknown,
                project_id=project_id,
                project_base_revision=project_base_revision,
            ),
            strict=False,
        )

    @mcp.tool(
        name="import_dataset",
        description="Import an explicitly confirmed ordered file list into a new named group. Manual common defaults and per-file overrides; no automatic grouping. 图像 导入 新建组 天体 分组 校准"
        + IMPORT_CONFIRMATION_PROMPT,
    )
    @service_errors
    def import_dataset(
        request_id: UuidInput,
        scan_id: UuidInput,
        name: ImageName,
        files: list[ConfirmedFile],
        defaults: ImportDefaults | None = None,
        calibration: CalibrationPatch | None = None,
        notes: str | None = None,
        storage_mode: Literal["managed"] = "managed",
        accept_unknown: bool = False,
        project_id: UuidInput | None = None,
        project_base_revision: Revision | None = None,
        *,
        client: AssetClient = Depends(service_client),
    ) -> ImageImportReceipt:
        return ImageImportReceipt.model_validate(
            client.image_imports_import_dataset(
                request_id=request_id,
                scan_id=scan_id,
                name=name,
                files=files,
                defaults=defaults,
                calibration=calibration,
                notes=notes,
                storage_mode=storage_mode,
                accept_unknown=accept_unknown,
                project_id=project_id,
                project_base_revision=project_base_revision,
            ),
            strict=False,
        )

    @mcp.tool(
        name="append_dataset",
        description="Import files into an existing fixed object group. Only subframes are eligible. The target dataset calibration applies to all new members. 图像 导入 已有组 追加 第二夜 平场 绑定"
        + IMPORT_CONFIRMATION_PROMPT,
    )
    @service_errors
    def append_dataset(
        request_id: UuidInput,
        scan_id: UuidInput,
        dataset_id: UuidInput,
        expected_revision: Revision,
        files: list[ConfirmedFile],
        defaults: ImportDefaults | None = None,
        storage_mode: Literal["managed"] = "managed",
        accept_unknown: bool = False,
        project_id: UuidInput | None = None,
        project_base_revision: Revision | None = None,
        *,
        client: AssetClient = Depends(service_client),
    ) -> ImageImportReceipt:
        return ImageImportReceipt.model_validate(
            client.image_imports_append_dataset(
                request_id=request_id,
                scan_id=scan_id,
                dataset_id=dataset_id,
                expected_revision=expected_revision,
                files=files,
                defaults=defaults,
                storage_mode=storage_mode,
                accept_unknown=accept_unknown,
                project_id=project_id,
                project_base_revision=project_base_revision,
            ),
            strict=False,
        )

    @mcp.tool(
        name="retry_publication",
        description="Retry only failed group publication from an existing import task at the new observed group revision. Never copy or import files again. 图像 导入 关联失败 修复 重试 发布",
    )
    @service_errors
    def retry_publication(
        request_id: UuidInput, task_id: UuidInput, expected_revision: Revision, *, client: AssetClient = Depends(service_client)
    ) -> ImageImportReceipt:
        return ImageImportReceipt.model_validate(
            client.image_imports_retry_publication(request_id=request_id, task_id=task_id, expected_revision=expected_revision),
            strict=False,
        )

    @mcp.tool(
        name="upload_one",
        description="Upload one explicitly selected client-local photo using file/confirmed manual/unknown facts. 图像 导入 上传 单张"
        + IMPORT_CONFIRMATION_PROMPT,
    )
    @service_errors
    def upload_one(
        path: str, options: PhotoImportOptions | None = None, *, client: AssetClient = Depends(service_client)
    ) -> ImportAccepted:
        return client.import_photo(Path(path), options)

    @mcp.tool(
        name="upload",
        description="Upload an explicitly selected ordered list of client-local photos. 图像 导入 上传 多张" + IMPORT_CONFIRMATION_PROMPT,
    )
    @service_errors
    def upload(
        paths: list[str], options: PhotoImportOptions | None = None, *, client: AssetClient = Depends(service_client)
    ) -> ImportAccepted:
        return client.import_photos([Path(path) for path in paths], options)

    @mcp.tool(name="roots", description="List configured service-side local import roots. 图像 导入 根目录")
    @service_errors
    def roots(*, client: AssetClient = Depends(service_client)) -> dict:
        return {"items": client.list_import_roots()}

    @mcp.tool(
        name="browse", description="Browse files/folders inside one configured root with relative POSIX paths. 图像 导入 浏览 目录 分页"
    )
    @service_errors
    def browse(
        root_id: str,
        path: str = "",
        limit: int = 50,
        offset: int = 0,
        q: str | None = None,
        *,
        client: AssetClient = Depends(service_client),
    ) -> ImportRootEntryPage:
        return client.browse_import_root(root_id, path, limit, offset, q)

    @mcp.tool(
        name="local",
        description="Import explicitly selected local sources with the existing managed/reference contract. 图像 本地 导入"
        + IMPORT_CONFIRMATION_PROMPT,
    )
    @service_errors
    def local(body: ImportCreate, *, client: AssetClient = Depends(service_client)) -> ImportAccepted:
        return client.import_local(body)

    return mcp
