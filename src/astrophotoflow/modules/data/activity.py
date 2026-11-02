"""Observe data activity through owner-provided state snapshots."""

from typing import Protocol

from sqlalchemy import select

from astrophotoflow.contracts.workbench import BusyState
from astrophotoflow.core.database.db import Database
from astrophotoflow.modules.data.imports.models import AssetTask
from astrophotoflow.modules.data.media.models import Preview


class ActivitySource(Protocol):
    def busy_blockers(self) -> list[str]: ...


def data_busy(
    database: Database,
    media_views: ActivitySource | None = None,
    exports: ActivitySource | None = None,
) -> BusyState:
    with database.read_session() as session:
        tasks = session.scalars(select(AssetTask.id).where(AssetTask.status.in_({"queued", "running", "cancelling"}))).all()
        previews = session.scalars(select(Preview.id).where(Preview.status == "generating")).all()
    blockers = [f"导入任务 {task}" for task in tasks] + [f"预览生成 {preview}" for preview in previews]
    for source in (exports, media_views):
        if source is not None:
            blockers.extend(source.busy_blockers())
    return BusyState(busy=bool(blockers), unknown=False, blockers=blockers)
