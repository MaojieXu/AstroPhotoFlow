"""Run the import stages, then settle the explicitly accepted batch links."""
from . import pipeline
from .batches import finalize_task_batch

def run_import_task(database, settings, task_id, workers=None):
    try:
        pipeline.process_task(database, settings, task_id, workers)
    finally:
        finalize_task_batch(database, task_id)
        from .explicit import finish_image_import
        finish_image_import(database, task_id)
        from .project_links import finalize_import_project
        finalize_import_project(database, task_id)

def recover_import_tasks(database, *, locale='en') -> int:
    from .batches import recover_batch_links
    from .tasks import mark_interrupted_tasks
    count = mark_interrupted_tasks(database, locale=locale)
    recover_batch_links(database)
    from sqlalchemy import select
    from .models import AssetTask
    from .project_links import finalize_import_project
    with database.read_session() as session:
        pending = list(session.scalars(select(AssetTask.id).where(
            AssetTask.status.not_in({'queued', 'running', 'cancelling', 'interrupted'}),
            AssetTask.report['destination']['project_link']['state'].as_string() == 'pending')))
    for identity in pending:
        finalize_import_project(database, identity)
    return count
