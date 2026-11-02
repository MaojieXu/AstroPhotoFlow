from __future__ import annotations

import json
import re
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from astrophotoflow.contracts.media import MediaSelection
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.media.models import Preview


@dataclass
class MediaLease:
    job: dict
    hold: ExitStack
    released: bool = False


class MediaLeases:
    """Hold viewer cache files until the last response/worker releases them."""

    def __init__(self, database, settings, cache, lock):
        self.database, self.settings = database, settings
        self.cache, self.lock = cache, lock
        self.active: dict[str, int] = {}

    def acquire(self, path: Path, folder: Path, *, preview: Preview | None = None):
        with self.lock:
            manifest = folder / "manifest.json"
            if not manifest.is_file():
                raise ApiError(409, "MEDIA_NOT_READY", "缓存已被回收，请重新打开查看器。", message_key="media_reopen_required")
            job = json.loads(manifest.read_text(encoding="utf-8"))
            stat = path.stat()
            if job["stamp"] != [stat.st_size, stat.st_mtime_ns]:
                raise ApiError(409, "SOURCE_CHANGED", "原件已经变化，请重新检查素材内容。", message_key="the_original_has_changed_check_the_asset_content_again")
            if preview is None and Path(job["path"]).resolve() != path.resolve():
                raise ApiError(409, "SOURCE_CHANGED", "显示缓存与当前完整结果不匹配。", message_key="the_display_cache_does_not_match_the_current_complete_result")
            job["path"], job["folder"] = path, folder
            job["selection"] = MediaSelection.model_validate(job["selection"])
            hold = ExitStack()
            try:
                hold.enter_context(self.cache.hold(folder))
                folder.touch()
            except BaseException:
                hold.close()
                raise
            key = job["key"]
            self.active[key] = self.active.get(key, 0) + 1
            if preview is not None:
                preview.status = "generating"
            lease = MediaLease(job, hold)
            return job, lambda: self.release(lease)

    def acquire_output(self, checked, key: str):
        if not re.fullmatch("[a-f0-9]{40}", key):
            raise not_found()
        folder = self.settings.data_dir / "previews" / "run-outputs" / "media" / key
        return self.acquire(checked.path, folder)

    def release(self, lease: MediaLease) -> None:
        with self.lock:
            if lease.released:
                return
            lease.released = True
            try:
                lease.hold.close()
            finally:
                job = lease.job
                self.active[job["key"]] -= 1
                if not self.active[job["key"]]:
                    del self.active[job["key"]]
                    if not job.get("output_source"):
                        with self.database.write_session() as session:
                            row = session.get(Preview, job["id"])
                            if row and row.status == "generating":
                                row.status = "available"
