from .ingestion import backfill_missing_previews, import_workers, mark_interrupted_tasks
from .previews import DisplayPreviews
from sqlalchemy import select

from astrophotoflow.contracts.workbench import BusyState
from astrophotoflow.core.database.db import Database
from .models import AssetTask, Preview


def data_busy(database: Database) -> BusyState:
    with database.read_session() as session:
        tasks = session.scalars(select(AssetTask.id).where(AssetTask.status.in_({"queued", "running", "cancelling"}))).all()
        previews = session.scalars(select(Preview.id).where(Preview.status == "generating")).all()
    blockers = [f"导入任务 {task}" for task in tasks] + [f"预览生成 {preview}" for preview in previews]
    return BusyState(busy=bool(blockers), unknown=False, blockers=blockers)


__all__ = ["DisplayPreviews", "backfill_missing_previews", "import_workers", "mark_interrupted_tasks", "data_busy"]
