from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.import_batches import BatchOut, ImportBatchWait
from astrophotoflow.contracts.imports import AssetTaskOut, AssetTaskPage, ImportAccepted, ImportTaskStateOut, RetryCreate
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
        limit: int = 50, offset: int = 0, status: str | None = None, *, client: AssetClient = Depends(service_client)
    ) -> AssetTaskPage:
        """List import tasks. Registration completion and original/metadata/preview readiness are separate states."""
        return client.list_import_tasks(limit, offset, status)

    @mcp.tool(
        name="get",
        description="Read task progress, paged member outcomes and retry IDs. Registration does not imply original readiness.\n读取导入进度、分页成员结果及重试 ID。登记完成不表示原件已就绪。\n关键词: 任务 进度 等待 取消 重试 读取 查询",
    )
    @service_errors
    def get_import_task(
        task_id: str, items_limit: int = 50, items_offset: int = 0, *, client: AssetClient = Depends(service_client)
    ) -> AssetTaskOut:
        """Read task progress, paged member outcomes and retry IDs. Registration does not imply original readiness."""
        return client.get_import_task(task_id, items_limit, items_offset)

    @mcp.tool(
        name="cancel",
        description="Request cancellation of an import task.\n请求取消导入任务；取消请求不等于实际停止。\n关键词: 任务 进度 等待 取消 重试 取消 停止",
    )
    @service_errors
    def cancel_import_task(task_id: str, *, client: AssetClient = Depends(service_client)) -> ImportTaskStateOut:
        """Request cancellation of an import task."""
        return client.cancel_import_task(task_id)

    @mcp.tool(
        name="resume",
        description="Resume a service-interrupted task while retaining asset identities and accepted preset snapshot.\n恢复被服务中断的任务，保留素材身份和已受理的预设快照。\n关键词: 任务 进度 等待 取消 重试 ",
    )
    @service_errors
    def resume_import_task(task_id: str, *, client: AssetClient = Depends(service_client)) -> ImportAccepted:
        """Resume a service-interrupted task while retaining asset identities and accepted preset snapshot."""
        return client.resume_import_task(task_id)

    @mcp.tool(
        name="retry",
        description="Retry selected task item IDs; retain the original accepted preset snapshot.\n重试所选任务成员 ID，沿用原受理预设快照。\n关键词: 任务 进度 等待 取消 重试 ",
    )
    @service_errors
    def retry_import_items(task_id: str, body: RetryCreate, *, client: AssetClient = Depends(service_client)) -> ImportAccepted:
        """Retry selected task item IDs; retain the original accepted preset snapshot."""
        return client.retry_import_items(task_id, body)

    @mcp.tool(
        name="status",
        description="Read aggregate batch tasks, independent stage readiness and project links without re-executing anything.\n一次查询整批任务、各阶段和项目关联状态；不重跑。\n关键词: 任务 进度 等待 取消 重试 ",
    )
    @service_errors
    def batch_status(request_id: str, *, client: AssetClient = Depends(service_client)) -> BatchOut:
        return client.get_import_batch(request_id)

    @mcp.tool(
        name="wait",
        description="Wait up to 20 seconds for the whole batch. Timeout returns progress and next_poll_seconds; avoid model-side rapid polling. Interrupted/failed tasks require explicit action.\n整批聚合等待最多20秒；超时返回进度与建议查询间隔，不进行模型端秒级轮询。\n关键词: 任务 进度 等待 取消 重试 等待 进度",
    )
    @service_errors
    def wait_batch(body: ImportBatchWait, *, client: AssetClient = Depends(service_client)) -> BatchOut:
        return client.wait_import_batch(body)

    return mcp
