from typing import Annotated

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.common import UuidInput
from astrophotoflow.contracts.image_calibration import ImageOperationOut
from astrophotoflow.contracts.image_imports import ImageImportReceipt
from astrophotoflow.contracts.image_management import PageLimit, PageOffset
from astrophotoflow.contracts.import_batches import BatchOut
from astrophotoflow.contracts.imports import AssetTaskOut, AssetTaskPage, ImportAccepted, ImportTaskStateOut, RetryCreate, ImportRecovery
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("tasks")

    @mcp.tool(
        name="list",
        description="List import tasks. Registration completion and original/metadata/preview readiness are separate states.\n列出导入任务。登记完成、原件就绪、资料解析和预览就绪是独立状态。\n关键词: 任务 进度 等待 取消 重试 列表 分页 查询",
    )
    @service_errors
    def list_import_tasks(
        limit: PageLimit = 50, offset: PageOffset = 0, status: str | None = None, *, client: AssetClient = Depends(service_client)
    ) -> AssetTaskPage:
        """List import tasks. Registration completion and original/metadata/preview readiness are separate states."""
        return client.list_import_tasks(limit, offset, status)

    @mcp.tool(
        name="get",
        description="Read task progress, paged member outcomes and retry IDs. Registration does not imply original readiness.\n读取导入进度、分页成员结果及重试 ID。登记完成不表示原件已就绪。\n关键词: 任务 进度 等待 取消 重试 读取 查询",
    )
    @service_errors
    def get_import_task(
        task_id: UuidInput, items_limit: PageLimit = 50, items_offset: PageOffset = 0, *, client: AssetClient = Depends(service_client)
    ) -> AssetTaskOut | ImageImportReceipt:
        """Read task progress, paged member outcomes and retry IDs. Registration does not imply original readiness."""
        result = client.image_tasks_get(task_id=task_id, items_limit=items_limit, items_offset=items_offset)
        output = ImageImportReceipt if "stages" in result else AssetTaskOut
        return output.model_validate(result, strict=False)

    @mcp.tool(
        name="cancel",
        description="Request cancellation of an import task.\n请求取消导入任务；取消请求不等于实际停止。\n关键词: 任务 进度 等待 取消 重试 取消 停止",
    )
    @service_errors
    def cancel_import_task(task_id: UuidInput, *, client: AssetClient = Depends(service_client)) -> ImportTaskStateOut:
        """Request cancellation of an import task."""
        return client.cancel_import_task(str(task_id))

    @mcp.tool(
        name="resume",
        description="Resume a service-interrupted task while retaining asset identities and accepted equipment snapshot.\n恢复被服务中断的任务，保留素材身份和已受理的设备快照。\n关键词: 任务 进度 等待 取消 重试 ",
    )
    @service_errors
    def resume_import_task(task_id: UuidInput, *, client: AssetClient = Depends(service_client)) -> ImportAccepted:
        """Resume a service-interrupted task while retaining asset identities and accepted equipment snapshot."""
        return client.resume_import_task(str(task_id))

    @mcp.tool(
        name="retry",
        description="Retry selected task item IDs; retain the original accepted equipment snapshot.\n重试所选任务成员 ID，沿用原受理设备快照。\n关键词: 任务 进度 等待 取消 重试 ",
    )
    @service_errors
    def retry_import_items(task_id: UuidInput, item_ids: list[UuidInput], *, client: AssetClient = Depends(service_client)) -> ImportAccepted:
        """Retry selected task item IDs; retain the original accepted equipment snapshot."""
        return client.retry_import_items(str(task_id), RetryCreate(item_ids=item_ids))

    @mcp.tool(
        name="status",
        description="Read aggregate batch tasks, independent stage readiness and project links without re-executing anything.\n一次查询整批任务、各阶段和项目关联状态；不重跑。\n关键词: 任务 进度 等待 取消 重试 ",
    )
    @service_errors
    def batch_status(request_id: UuidInput, *, client: AssetClient = Depends(service_client)) -> ImageImportReceipt | BatchOut | AssetTaskOut:
        result = client.image_tasks_status(request_id=request_id)
        output = ImageImportReceipt if "stages" in result else AssetTaskOut if "sources" in result else BatchOut
        return output.model_validate(result, strict=False)

    @mcp.tool(
        name="wait",
        description="Wait up to 20 seconds for the whole batch. Timeout returns progress and next_poll_seconds; avoid model-side rapid polling. Interrupted/failed tasks require explicit action.\n整批聚合等待最多20秒；超时返回进度与建议查询间隔，不进行模型端秒级轮询。\n关键词: 任务 进度 等待 取消 重试 等待 进度",
    )
    @service_errors
    def wait_batch(request_id: UuidInput, wait_seconds: Annotated[float, Field(ge=0, le=20, allow_inf_nan=False)] = 20, *, client: AssetClient = Depends(service_client)) -> ImageImportReceipt | BatchOut | AssetTaskOut:
        result = client.image_tasks_wait(request_id=request_id, wait_seconds=wait_seconds)
        output = ImageImportReceipt if "stages" in result else AssetTaskOut if "sources" in result else BatchOut
        return output.model_validate(result, strict=False)

    @mcp.tool(name='recover_organization', description='Organize successful imported materials or retry project association using existing originals. Query the operation receipt after an uncertain result. 修复导入分组 项目关联')
    @service_errors
    def recover_organization(task_id: UuidInput, body: ImportRecovery, *, client: AssetClient = Depends(service_client)) -> ImageOperationOut:
        return client.recover_import_organization(str(task_id), body)

    return mcp
