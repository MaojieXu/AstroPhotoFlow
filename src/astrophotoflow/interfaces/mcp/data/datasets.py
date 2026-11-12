"""Current subframe groups and their shared calibration."""

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.common import UuidInput
from astrophotoflow.contracts.datasets import DatasetMembersCreate, DatasetOut
from astrophotoflow.contracts.image_calibration import CalibrationPatch, DatasetMemberInput, ImageOperationOut
from astrophotoflow.contracts.image_management import (
    DatasetChanges,
    DatasetImageDetail,
    DatasetImageMemberPage,
    DatasetImagePage,
    DatasetMemberSearch,
    DatasetSearch,
    ImageName,
    Revision,
)
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("datasets")

    @mcp.tool(
        name="search",
        description="Search groups by name and same-member capture predicates; match any/all members. 图像组 天体 设备 校准 查询 分页",
    )
    @service_errors
    def search(query: DatasetSearch | None = None, *, client: AssetClient = Depends(service_client)) -> DatasetImagePage:
        return DatasetImagePage.model_validate(client.image_datasets_search(query=query), strict=False)

    @mcp.tool(name="get", description="Read group revision and current member summary without loading all members. 图像组 读取 当前状态")
    @service_errors
    def get(dataset_id: UuidInput, *, client: AssetClient = Depends(service_client)) -> DatasetImageDetail:
        return DatasetImageDetail.model_validate(client.image_datasets_get(dataset_id=dataset_id), strict=False)

    @mcp.tool(
        name="create",
        description="Create an explicit group from subframes and one optional calibration configuration. 图像组 创建 固定 成员 校准",
    )
    @service_errors
    def create(
        request_id: UuidInput,
        name: ImageName,
        members: list[DatasetMemberInput],
        project_id: UuidInput | None = None,
        project_base_revision: Revision | None = None,
        calibration: CalibrationPatch | None = None,
        notes: str | None = None,
        accept_unknown: bool = False,
        *,
        client: AssetClient = Depends(service_client),
    ) -> ImageOperationOut:
        return ImageOperationOut.model_validate(
            client.image_datasets_create(
                request_id=request_id, name=name, members=members, calibration=calibration, notes=notes, accept_unknown=accept_unknown, project_id=project_id, project_base_revision=project_base_revision
            ),
            strict=False,
        )

    @mcp.tool(
        name="update", description="Update name/notes/status at revision without changing membership or bindings. 图像组 资料 修改 归档"
    )
    @service_errors
    def update(
        dataset_id: UuidInput, expected_revision: Revision, changes: DatasetChanges, *, client: AssetClient = Depends(service_client)
    ) -> DatasetImageDetail:
        return DatasetImageDetail.model_validate(
            client.image_datasets_update(dataset_id=dataset_id, expected_revision=expected_revision, changes=changes), strict=False
        )

    @mcp.tool(
        name="members",
        description="Page exact fixed group members in canonical order; archived members remain visible by default. 图像组 成员 分页 原序",
    )
    @service_errors
    def members(
        dataset_id: UuidInput, query: DatasetMemberSearch | None = None, *, client: AssetClient = Depends(service_client)
    ) -> DatasetImageMemberPage:
        return DatasetImageMemberPage.model_validate(client.image_datasets_members(dataset_id=dataset_id, query=query), strict=False)

    @mcp.tool(
        name="edit_members",
        description="Edit fixed subframes in member order. The dataset calibration applies to all members, including additions. 图像组 追加 移除 成员 校准",
    )
    @service_errors
    def edit_members(
        request_id: UuidInput,
        dataset_id: UuidInput,
        expected_revision: Revision,
        add: list[DatasetMemberInput] | None = None,
        remove: list[UuidInput] | None = None,
        accept_unknown: bool = False,
        *,
        client: AssetClient = Depends(service_client),
    ) -> ImageOperationOut:
        return ImageOperationOut.model_validate(
            client.image_datasets_edit_members(
                request_id=request_id,
                dataset_id=dataset_id,
                expected_revision=expected_revision,
                add=add,
                remove=remove,
                accept_unknown=accept_unknown,
            ),
            strict=False,
        )

    @mcp.tool(
        name="replace_members",
        description="Replace the current ordered subframe list at the observed dataset revision. Omitted calibration preserves the current configuration. 数据集 成员 排序 移除 替换",
    )
    @service_errors
    def replace_members(dataset_id: UuidInput, body: DatasetMembersCreate, *, client: AssetClient = Depends(service_client)) -> DatasetOut:
        return client.update_dataset_members(dataset_id, body)

    return mcp
