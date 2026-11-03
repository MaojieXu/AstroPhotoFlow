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
    DatasetCalibrationPage,
    ImageCalibrationOut,
    ImageOperationOut,
    MemberCalibrationChange,
)
from astrophotoflow.contracts.image_imports import ConfirmedFile, ImportDefaults, ScannedCalibrationCheckPage
from astrophotoflow.contracts.image_management import PageLimit, PageOffset, Revision
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("calibration")

    @mcp.tool(name="search", description="Find existing same-purpose Master asset versions and optional consumer compatibility. Every slot is optional; no automatic binding. Raw subframes and datasets are never calibration targets. 校准 Master 暗场 平场 偏置 暗平场 候选 查询")
    @service_errors
    def search(slot: CalibrationSlot, consumer: CalibrationConsumer | None = None, query: CalibrationSearch | None = None, *, client: AssetClient = Depends(service_client)) -> CalibrationCandidatePage:
        return CalibrationCandidatePage.model_validate(client.image_calibration_search(slot=slot, consumer=consumer, query=query), strict=False)

    @mcp.tool(name="check", description="Read-only compatibility/dependency check for fixed consumers and proposed bindings. Distinguishes conflicts and unknowns; targets must be fixed same-purpose Master assets. All bindings are optional; never executes calibration. 校准 检查 匹配 依赖 科学 冲突")
    @service_errors
    def check(consumer: CalibrationConsumer, proposal: CalibrationCheckProposal | None = None, limit: PageLimit = 50, offset: PageOffset = 0, *, client: AssetClient = Depends(service_client)) -> CalibrationCheckPage:
        return CalibrationCheckPage.model_validate(client.image_calibration_check(consumer=consumer, proposal=proposal, limit=limit, offset=offset), strict=False)

    @mcp.tool(name="check_import", description="Read-only calibration check of exact scanned files, proposed metadata/equipment and fixed targets BEFORE import. Returns conflicts and unknowns for Agent questions; never registers files or approves unknowns. Explain suggestions and obtain user confirmation before import; unknown values may remain unknown. 校准 导入前 扫描 检查 未知 提问")
    @service_errors
    def check_import(scan_id: UuidInput, files: list[ConfirmedFile], defaults: ImportDefaults | None = None, calibration_defaults: CalibrationPatch | None = None, limit: PageLimit = 50, offset: PageOffset = 0, *, client: AssetClient = Depends(service_client)) -> ScannedCalibrationCheckPage:
        return ScannedCalibrationCheckPage.model_validate(client.image_calibration_check_import(scan_id=scan_id, files=files, defaults=defaults, calibration_defaults=calibration_defaults, limit=limit, offset=offset), strict=False)

    @mcp.tool(name="get_image", description="Read an individual image's fixed calibration binding version; no group inheritance. 校准 单图 绑定 固定版本 读取")
    @service_errors
    def get_image(asset_id: UuidInput, asset_version_id: UuidInput, binding_version_id: UuidInput | None = None, *, client: AssetClient = Depends(service_client)) -> ImageCalibrationOut:
        return ImageCalibrationOut.model_validate(client.image_calibration_get_image(asset_id=asset_id, asset_version_id=asset_version_id, binding_version_id=binding_version_id), strict=False)

    @mcp.tool(name="update_image", description="Save standalone bindings at asset revision and required nullable base_binding_version_id. No inherit; unknown science needs explicit accept_unknown. Query request_id after uncertainty. 校准 单图 绑定 修改")
    @service_errors
    def update_image(request_id: UuidInput, asset_id: UuidInput, asset_version_id: UuidInput, expected_revision: Revision, base_binding_version_id: UuidInput | None, changes: CalibrationPatch, accept_unknown: bool = False, *, client: AssetClient = Depends(service_client)) -> ImageOperationOut:
        return ImageOperationOut.model_validate(client.image_calibration_update_image(request_id=request_id, asset_id=asset_id, asset_version_id=asset_version_id, expected_revision=expected_revision, base_binding_version_id=base_binding_version_id, changes=changes, accept_unknown=accept_unknown), strict=False)

    @mcp.tool(name="get_dataset", description="Page fixed group effective calibration with target names, versions, sources and whole-group combination counts. Filter combination_key from the returned summary. Browsing never executes scientific checks or calibration. Member overrides outrank defaults; standalone bindings never dynamically inherit. 校准 图像组 成员 有效绑定 分页 搭配 汇总")
    @service_errors
    def get_dataset(dataset_id: UuidInput, version_id: UuidInput, member_asset_version_ids: list[UuidInput] | None = None, limit: PageLimit = 50, offset: PageOffset = 0, combination_key: str | None = None, *, client: AssetClient = Depends(service_client)) -> DatasetCalibrationPage:
        return DatasetCalibrationPage.model_validate(client.image_calibration_get_dataset(dataset_id=dataset_id, version_id=version_id, member_asset_version_ids=member_asset_version_ids, limit=limit, offset=offset, combination_key=combination_key), strict=False)

    @mcp.tool(name="update_defaults", description="Patch group calibration defaults and publish a fixed version, preserving members and overrides. No inherit at default level. Relations only, no execution. 校准 图像组 默认 绑定 修改")
    @service_errors
    def update_defaults(request_id: UuidInput, dataset_id: UuidInput, expected_revision: Revision, base_version_id: UuidInput, changes: CalibrationPatch, accept_unknown: bool = False, *, client: AssetClient = Depends(service_client)) -> ImageOperationOut:
        return ImageOperationOut.model_validate(client.image_calibration_update_defaults(request_id=request_id, dataset_id=dataset_id, expected_revision=expected_revision, base_version_id=base_version_id, changes=changes, accept_unknown=accept_unknown), strict=False)

    @mcp.tool(name="update_members", description="Patch only selected fixed member overrides; inherit removes an override, unconfigured blocks inheritance, disabled opts out. All other members/slots remain. 校准 指定成员 绑定 修改 继承")
    @service_errors
    def update_members(request_id: UuidInput, dataset_id: UuidInput, expected_revision: Revision, base_version_id: UuidInput, members: list[MemberCalibrationChange], accept_unknown: bool = False, *, client: AssetClient = Depends(service_client)) -> ImageOperationOut:
        return ImageOperationOut.model_validate(client.image_calibration_update_members(request_id=request_id, dataset_id=dataset_id, expected_revision=expected_revision, base_version_id=base_version_id, members=members, accept_unknown=accept_unknown), strict=False)

    @mcp.tool(name="get_operation", description="Reconcile an existing calibration/group-write request without repeating any write. 校准 图像组 请求 回执 查询 未知结果")
    @service_errors
    def get_operation(request_id: UuidInput, *, client: AssetClient = Depends(service_client)) -> ImageOperationOut:
        return ImageOperationOut.model_validate(client.image_calibration_get_operation(request_id=request_id), strict=False)

    return mcp
