from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from astrophotoflow.core.config import Settings
from astrophotoflow.modules.data.media.executor import PreviewExecutor

logger = logging.getLogger(__name__)

@contextmanager
def import_workers(settings: Settings):
    # One pair per service; direct maintenance/test callers own their pair.
    with ThreadPoolExecutor(max_workers=settings.file_workers, thread_name_prefix="asset-file") as files,\
            PreviewExecutor(settings.preview_workers) as previews:
        yield files, previews
