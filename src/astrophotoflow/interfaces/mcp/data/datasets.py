from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.datasets import (
    DatasetCreate,
    DatasetMemberPage,
    DatasetMemberParametersUpdate,
    DatasetMemberParametersUpdateOut,
    DatasetMemberQuery,
    DatasetMembersCreate,
    DatasetOut,
    DatasetPage,
    DatasetPatch,
    DatasetQuery,
    DatasetVersionOut,
    DatasetVersionPage,
)
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("datasets")

    @mcp.tool(
        name="create",
        description="Create a logical group of fixed asset versions without copying originals.\n使用固定素材版本创建逻辑图像组，不复制原件。\n关键词: 集合 图像组 成员 固定 校准 创建",
    )
    @service_errors
    def create_dataset(body: DatasetCreate, *, client: AssetClient = Depends(service_client)) -> DatasetOut:
        """Create a logical group of fixed asset versions without copying originals."""
        return client.create_dataset(body)

    @mcp.tool(
        name="list", description="Page through logical datasets.\n分页读取逻辑图像组。\n关键词: 集合 图像组 成员 固定 校准 列表 分页 查询"
    )
    @service_errors
    def list_datasets(query: DatasetQuery | None = None, *, client: AssetClient = Depends(service_client)) -> DatasetPage:
        return client.list_datasets(query)

    @mcp.tool(
        name="get",
        description="Read a dataset revision and current version ID.\n读取图像组的 revision 和当前版本 ID。\n关键词: 集合 图像组 成员 固定 校准 读取 查询",
    )
    @service_errors
    def get_dataset(dataset_id: str, *, client: AssetClient = Depends(service_client)) -> DatasetOut:
        """Read a dataset revision and current version ID."""
        return client.get_dataset(dataset_id)

    @mcp.tool(
        name="update",
        description="Update group metadata or archive it using base_revision.\n使用 base_revision 更新图像组资料或归档。\n关键词: 集合 图像组 成员 固定 校准 修改 更新",
    )
    @service_errors
    def update_dataset(dataset_id: str, body: DatasetPatch, *, client: AssetClient = Depends(service_client)) -> DatasetOut:
        """Update group metadata or archive it using base_revision."""
        return client.update_dataset(dataset_id, body)

    @mcp.tool(
        name="list_versions",
        description="List fixed group versions with canonical ordered members and calibration bindings.\n列出组的固定版本、规范有序成员及校准绑定。\n关键词: 集合 图像组 成员 固定 校准 列表 分页 查询",
    )
    @service_errors
    def list_dataset_versions(
        dataset_id: str, limit: int = 50, offset: int = 0, *, client: AssetClient = Depends(service_client)
    ) -> DatasetVersionPage:
        """List fixed group versions with canonical ordered members and calibration bindings."""
        return client.list_dataset_versions(dataset_id, limit, offset)

    @mcp.tool(
        name="get_version",
        description="Read all ordered members and calibration bindings from a fixed group version.\n读取固定图像组版本的全部有序成员和校准绑定。\n关键词: 集合 图像组 成员 固定 校准 读取 查询",
    )
    @service_errors
    def get_dataset_version(dataset_id: str, version_id: str, *, client: AssetClient = Depends(service_client)) -> DatasetVersionOut:
        """Read all ordered members and calibration bindings from a fixed group version."""
        return client.get_dataset_version(dataset_id, version_id)

    @mcp.tool(
        name="publish_version",
        description="Publish complete membership and optional calibration maps. Retained members keep relative order; new members append. Defaults replace when supplied; submitted member maps replace, missing members retain; absent slots inherit and null disables.\n发布完整成员列表及可选校准绑定。保留成员相对顺序，新成员追加。提供的默认绑定整体替换；提供的成员绑定整体替换，未提供的成员保留；省略槽位继承，null 停用。\n关键词: 集合 图像组 成员 固定 校准 发布 固定",
    )
    @service_errors
    def publish_dataset_version(
        dataset_id: str, body: DatasetMembersCreate, *, client: AssetClient = Depends(service_client)
    ) -> DatasetVersionOut:
        """Publish complete membership and optional calibration maps. Retained members keep relative order; new members append. Defaults replace when supplied; submitted member maps replace, missing members retain; absent slots inherit and null disables."""
        return client.publish_dataset_version(dataset_id, body)

    @mcp.tool(
        name="update_members",
        description="Batch patch group member parameters/classification using dataset revision, fixed base version and revisions for ALL current canonical group assets.\n使用组 revision、固定基准版本及全部当前规范组成员的素材 revision，批量更新成员参数或分类。\n关键词: 集合 图像组 成员 固定 校准 修改 更新",
    )
    @service_errors
    def update_dataset_members(
        dataset_id: str, body: DatasetMemberParametersUpdate, *, client: AssetClient = Depends(service_client)
    ) -> DatasetMemberParametersUpdateOut:
        """Batch patch group member parameters/classification using dataset revision, fixed base version and revisions for ALL current canonical group assets."""
        return client.update_dataset_members(dataset_id, body)

    @mcp.tool(
        name="members",
        description="Page ordered members of an exact fixed dataset version without loading the whole group. 集合 图像组 固定 成员 分页 顺序 筛选",
    )
    @service_errors
    def members(
        dataset_id: str, version_id: str, query: DatasetMemberQuery | None = None, *, client: AssetClient = Depends(service_client)
    ) -> DatasetMemberPage:
        return client.list_dataset_members(dataset_id, version_id, query if query is not None else DatasetMemberQuery())

    return mcp
