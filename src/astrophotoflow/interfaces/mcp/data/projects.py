from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.import_batches import BatchOut, ImportBatchProjectRetry
from astrophotoflow.contracts.projects import (
    ProjectAssetReferenceOut,
    ProjectAssetReferencePage,
    ProjectCreate,
    ProjectDatasetReferenceCreate,
    ProjectDatasetReferenceOut,
    ProjectDatasetReferencePage,
    ProjectOut,
    ProjectPage,
    ProjectPatch,
    ProjectQuery,
    ProjectReferenceCreate,
    ProjectReferenceDelete,
    ProjectReferenceDeleteResult,
)
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("projects")

    @mcp.tool(
        name="retry_import_links",
        description="Explicitly retry only batch project links after reading/reconciling the current project revision; never re-import files.\n读取并协调项目当前revision后，显式重试导入后的项目关联；不重新导入。\n关键词: 项目 资料 引用 关联 ",
    )
    @service_errors
    def retry_batch_project_links(
        request_id: str, body: ImportBatchProjectRetry, *, client: AssetClient = Depends(service_client)
    ) -> BatchOut:
        return client.retry_batch_project_links(request_id, body)

    @mcp.tool(name="list", description="Page through projects.\n分页读取项目。\n关键词: 项目 资料 引用 关联 列表 分页 查询")
    @service_errors
    def list_projects(query: ProjectQuery | None = None, *, client: AssetClient = Depends(service_client)) -> ProjectPage:
        return client.list_projects(query)

    @mcp.tool(
        name="create",
        description="Create a project organized by target or processing task.\n按拍摄目标或处理任务创建项目。\n关键词: 项目 资料 引用 关联 创建",
    )
    @service_errors
    def create_project(body: ProjectCreate, *, client: AssetClient = Depends(service_client)) -> ProjectOut:
        """Create a project organized by target or processing task."""
        return client.create_project(body)

    @mcp.tool(
        name="get", description="Read a project and its current revision.\n读取项目和当前 revision。\n关键词: 项目 资料 引用 关联 读取 查询"
    )
    @service_errors
    def get_project(project_id: str, *, client: AssetClient = Depends(service_client)) -> ProjectOut:
        """Read a project and its current revision."""
        return client.get_project(project_id)

    @mcp.tool(
        name="update",
        description="Patch or archive a project at base_revision; configuration deletion is archival.\n在 base_revision 上更新项目或归档。配置删除采用归档语义。\n关键词: 项目 资料 引用 关联 修改 更新",
    )
    @service_errors
    def update_project(project_id: str, body: ProjectPatch, *, client: AssetClient = Depends(service_client)) -> ProjectOut:
        """Patch or archive a project at base_revision; configuration deletion is archival."""
        return client.update_project(project_id, body)

    @mcp.tool(
        name="list_assets",
        description="List project references pinned to fixed asset versions.\n列出项目中固定素材版本的引用。\n关键词: 项目 资料 引用 关联 列表 分页 查询",
    )
    @service_errors
    def list_project_assets(
        project_id: str, limit: int = 50, offset: int = 0, *, client: AssetClient = Depends(service_client)
    ) -> ProjectAssetReferencePage:
        """List project references pinned to fixed asset versions."""
        return client.list_project_assets(project_id, limit, offset)

    @mcp.tool(
        name="get_asset",
        description="Read one project asset reference and its pinned version.\n读取项目素材引用及其固定版本。\n关键词: 项目 资料 引用 关联 读取 查询",
    )
    @service_errors
    def get_project_asset(project_id: str, reference_id: str, *, client: AssetClient = Depends(service_client)) -> ProjectAssetReferenceOut:
        """Read one project asset reference and its pinned version."""
        return client.get_project_asset(project_id, reference_id)

    @mcp.tool(
        name="add_asset",
        description="Pin an existing asset version to a project without copying the original. Requires current project revision.\n在项目当前 revision 上加入已有素材固定版本，不复制原件。\n关键词: 项目 资料 引用 关联 ",
    )
    @service_errors
    def add_project_asset(
        project_id: str, body: ProjectReferenceCreate, *, client: AssetClient = Depends(service_client)
    ) -> ProjectAssetReferenceOut:
        """Pin an existing asset version to a project without copying the original. Requires current project revision."""
        return client.add_project_asset(project_id, body)

    @mcp.tool(
        name="remove_asset",
        description="Remove a project asset reference at project base_revision; retain library originals.\n在项目 base_revision 上移除素材引用，保留素材库原件。\n关键词: 项目 资料 引用 关联 移除 删除",
    )
    @service_errors
    def remove_project_asset(
        project_id: str, reference_id: str, body: ProjectReferenceDelete, *, client: AssetClient = Depends(service_client)
    ) -> ProjectReferenceDeleteResult:
        """Remove a project asset reference at project base_revision; retain library originals."""
        return client.remove_project_asset(project_id, reference_id, body)

    @mcp.tool(
        name="list_datasets",
        description="List project references pinned to fixed dataset versions.\n列出项目中固定图像组版本的引用。\n关键词: 项目 资料 引用 关联 列表 分页 查询",
    )
    @service_errors
    def list_project_datasets(
        project_id: str, limit: int = 50, offset: int = 0, *, client: AssetClient = Depends(service_client)
    ) -> ProjectDatasetReferencePage:
        """List project references pinned to fixed dataset versions."""
        return client.list_project_datasets(project_id, limit, offset)

    @mcp.tool(
        name="get_dataset",
        description="Read one pinned project dataset reference.\n读取项目中一个固定图像组引用。\n关键词: 项目 资料 引用 关联 读取 查询",
    )
    @service_errors
    def get_project_dataset(
        project_id: str, reference_id: str, *, client: AssetClient = Depends(service_client)
    ) -> ProjectDatasetReferenceOut:
        """Read one pinned project dataset reference."""
        return client.get_project_dataset(project_id, reference_id)

    @mcp.tool(
        name="add_dataset",
        description="Pin a fixed dataset version to a project at the current project revision.\n在项目当前 revision 上加入固定图像组版本。\n关键词: 项目 资料 引用 关联 ",
    )
    @service_errors
    def add_project_dataset(
        project_id: str, body: ProjectDatasetReferenceCreate, *, client: AssetClient = Depends(service_client)
    ) -> ProjectDatasetReferenceOut:
        """Pin a fixed dataset version to a project at the current project revision."""
        return client.add_project_dataset(project_id, body)

    @mcp.tool(
        name="remove_dataset",
        description="Remove a project dataset reference at project base_revision; retain the logical dataset.\n在项目 base_revision 上移除图像组引用，保留逻辑图像组。\n关键词: 项目 资料 引用 关联 移除 删除",
    )
    @service_errors
    def remove_project_dataset(
        project_id: str, reference_id: str, body: ProjectReferenceDelete, *, client: AssetClient = Depends(service_client)
    ) -> ProjectReferenceDeleteResult:
        """Remove a project dataset reference at project base_revision; retain the logical dataset."""
        return client.remove_project_dataset(project_id, reference_id, body)

    return mcp
