"""Read and save fixed calibration relationships without executing processing."""

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.common import UuidInput
from astrophotoflow.contracts.image_calibration import (
    CalibrationCandidatePage,
    CalibrationCheckPage,
    CalibrationCheckProposal,
    CalibrationConsumer,
    CalibrationPatch,
    CalibrationSearch,
    CalibrationSlot,
    DatasetCalibrationOut,
    ImageCalibrationOut,
    ImageOperationOut,
)
from astrophotoflow.contracts.image_imports import ConfirmedFile, ImportDefaults, ImportDestination, ScannedCalibrationCheckPage
from astrophotoflow.contracts.image_management import PageLimit, PageOffset, Revision
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("calibration")

    @mcp.tool(
        name="search",
        description="Find existing same-purpose Master assets and optional consumer compatibility. Every slot is optional; no automatic binding. Raw subframes and datasets are never calibration targets. 校准 Master 暗场 平场 偏置 暗平场 候选 查询",
    )
    @service_errors
    def search(
        slot: CalibrationSlot,
        consumer: CalibrationConsumer | None = None,
        query: CalibrationSearch | None = None,
        *,
        client: AssetClient = Depends(service_client),
    ) -> CalibrationCandidatePage:
        return CalibrationCandidatePage.model_validate(
            client.image_calibration_search(slot=slot, consumer=consumer, query=query), strict=False
        )

    @mcp.tool(
        name="check",
        description="Read-only compatibility/dependency check for fixed consumers and proposed bindings. Distinguishes conflicts and unknowns; targets must be fixed same-purpose Master assets. All bindings are optional; never executes calibration. 校准 检查 匹配 依赖 科学 冲突",
    )
    @service_errors
    def check(
        consumer: CalibrationConsumer,
        proposal: CalibrationCheckProposal | None = None,
        limit: PageLimit = 50,
        offset: PageOffset = 0,
        *,
        client: AssetClient = Depends(service_client),
    ) -> CalibrationCheckPage:
        return CalibrationCheckPage.model_validate(
            client.image_calibration_check(consumer=consumer, proposal=proposal, limit=limit, offset=offset), strict=False
        )

    @mcp.tool(
        name="check_import",
        description="Read-only calibration check of exact scanned files, proposed metadata/equipment and fixed targets BEFORE import. Returns conflicts and unknowns for Agent questions; never registers files or approves unknowns. Explain suggestions and obtain user confirmation before import; unknown values may remain unknown. 校准 导入前 扫描 检查 未知 提问",
    )
    @service_errors
    def check_import(
        scan_id: UuidInput,
        files: list[ConfirmedFile],
        defaults: ImportDefaults | None = None,
        calibration: CalibrationPatch | None = None,
        destination: ImportDestination | None = None,
        limit: PageLimit = 50,
        offset: PageOffset = 0,
        *,
        client: AssetClient = Depends(service_client),
    ) -> ScannedCalibrationCheckPage:
        return ScannedCalibrationCheckPage.model_validate(
            client.image_calibration_check_import(
                scan_id=scan_id,
                files=files,
                defaults=defaults,
                calibration=calibration,
                destination=destination,
                limit=limit,
                offset=offset,
            ),
            strict=False,
        )

    @mcp.tool(name="get_image", description="Read an individual image's current calibration bindings. 校准 单图 绑定 当前状态 读取")
    @service_errors
    def get_image(asset_id: UuidInput, *, client: AssetClient = Depends(service_client)) -> ImageCalibrationOut:
        return ImageCalibrationOut.model_validate(client.image_calibration_get_image(asset_id=asset_id), strict=False)

    @mcp.tool(
        name="update_image",
        description="Save standalone bindings at asset revision and current settings. No inherit; unknown science needs explicit accept_unknown. Query request_id after uncertainty. 校准 单图 绑定 修改",
    )
    @service_errors
    def update_image(
        request_id: UuidInput,
        asset_id: UuidInput,
        expected_revision: Revision,
        changes: CalibrationPatch,
        accept_unknown: bool = False,
        *,
        client: AssetClient = Depends(service_client),
    ) -> ImageOperationOut:
        return ImageOperationOut.model_validate(
            client.image_calibration_update_image(
                request_id=request_id,
                asset_id=asset_id,
                expected_revision=expected_revision,
                changes=changes,
                accept_unknown=accept_unknown,
            ),
            strict=False,
        )

    @mcp.tool(
        name="get_dataset", description="Read the single calibration configuration of a fixed subframe dataset. 校准 子帧 数据集 固定配置"
    )
    @service_errors
    def get_dataset(dataset_id: UuidInput, *, client: AssetClient = Depends(service_client)) -> DatasetCalibrationOut:
        return DatasetCalibrationOut.model_validate(client.image_calibration_get_dataset(dataset_id=dataset_id), strict=False)

    @mcp.tool(
        name="update_dataset",
        description="Save one calibration configuration for all subframes and publish a dataset. Each slot accepts one same-purpose Master. 校准 子帧 数据集 绑定 修改",
    )
    @service_errors
    def update_dataset(
        request_id: UuidInput,
        dataset_id: UuidInput,
        expected_revision: Revision,
        changes: CalibrationPatch,
        accept_unknown: bool = False,
        *,
        client: AssetClient = Depends(service_client),
    ) -> ImageOperationOut:
        return ImageOperationOut.model_validate(
            client.image_calibration_update_dataset(
                request_id=request_id,
                dataset_id=dataset_id,
                expected_revision=expected_revision,
                changes=changes,
                accept_unknown=accept_unknown,
            ),
            strict=False,
        )

    @mcp.tool(
        name="get_operation",
        description="Reconcile an existing calibration/group-write request without repeating any write. 校准 图像组 请求 回执 查询 未知结果",
    )
    @service_errors
    def get_operation(request_id: UuidInput, *, client: AssetClient = Depends(service_client)) -> ImageOperationOut:
        return ImageOperationOut.model_validate(client.image_calibration_get_operation(request_id=request_id), strict=False)

    return mcp
