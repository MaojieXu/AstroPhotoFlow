"""Run the import stages, then settle the explicitly accepted batch links."""
from . import pipeline
from .batches import finalize_task_batch


def run_import_task(database, settings, task_id, workers=None):
    try:
        pipeline.process_task(database, settings, task_id, workers)
    finally:
        finalize_task_batch(database, task_id)



def recover_import_tasks(database, *, locale='en') -> int:
    from .batches import recover_batch_links
    from .tasks import mark_interrupted_tasks
    count = mark_interrupted_tasks(database, locale=locale)
    recover_batch_links(database)
    return count
