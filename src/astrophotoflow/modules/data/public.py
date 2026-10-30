from .ingestion import backfill_missing_previews, import_workers, mark_interrupted_tasks
from .previews import DisplayPreviews
from .media_view import LeasedFileResponse, MediaViews
from .siril_preview import prepare_siril_sample, direct_fits_image
from .canvas import prepare_canvas_data
from sqlalchemy import select
from .projects import get_project
from .science_inputs import accept_asset_content, check_output, get_output_registration, observe_asset_content, observe_reference_inputs, register_output, render_output_preview, resolve_inputs, resolve_canvas_inputs, validate_input_references
from .trash import preview_library_removal

from astrophotoflow.contracts.workbench import BusyState
from astrophotoflow.core.database.db import Database
from .models import AssetTask, Preview


def data_busy(database: Database, media_views: MediaViews | None = None) -> BusyState:
    with database.read_session() as session:
        tasks = session.scalars(select(AssetTask.id).where(AssetTask.status.in_({"queued", "running", "cancelling"}))).all()
        previews = session.scalars(select(Preview.id).where(Preview.status == "generating")).all()
    blockers = [f"导入任务 {task}" for task in tasks] + [f"预览生成 {preview}" for preview in previews]
    if media_views is not None:
        with media_views.lock:
            blockers.extend('完整结果显示准备 ' + key for key in media_views.preparing if key in media_views.output_jobs)
            blockers.extend('完整结果显示读取 ' + key for key in media_views.using if key in media_views.output_jobs)
    return BusyState(busy=bool(blockers), unknown=False, blockers=blockers)


__all__ = ["DisplayPreviews", "MediaViews", "LeasedFileResponse", "backfill_missing_previews", "import_workers", "mark_interrupted_tasks", "data_busy",
           "prepare_siril_sample", "direct_fits_image",
           "prepare_canvas_data",
           "get_project", "validate_input_references", "resolve_inputs", "resolve_canvas_inputs", "observe_reference_inputs",
           "observe_asset_content", "accept_asset_content", "check_output", "render_output_preview",
           "register_output", "get_output_registration", "preview_library_removal"]
