from threading import Lock
from time import monotonic
from datetime import datetime, timezone

from sqlalchemy import select

from astrophotoflow.modules.data.models import AssetTask, AssetTaskItem, AssetVersion


class ImportProgress:
    def __init__(self, database, task_id):
        self.database, self.task_id = database, task_id
        self._lock = Lock()
        self._bytes = {}
        self._last_flush = 0.0

    def copied(self, item_id, size):
        with self._lock:
            self._bytes[item_id] = size
            self._flush(False)

    def update(self):
        with self._lock:
            self._flush(False)

    def flush(self, *, registration_completed=False, content_completed=False, preview_completed=False):
        with self._lock:
            self._flush(True, registration_completed, content_completed, preview_completed)

    def _flush(self, force, registration_completed=False, content_completed=False, preview_completed=False):
        now = monotonic()
        if not force and now - self._last_flush < 0.5:
            return
        with self.database.write_session() as session:
            task = session.get(AssetTask, self.task_id)
            rows = session.execute(select(AssetTaskItem, AssetVersion).outerjoin(
                AssetVersion, AssetVersion.id == AssetTaskItem.asset_version_id
            ).where(AssetTaskItem.task_id == self.task_id)).all()
            content = dict((task.report or {}).get("content") or {})
            preview = dict((task.report or {}).get("preview") or {})
            sizes = {(entry["root_id"], entry["path"]): (entry.get("source_stamp") or {}).get("size", 0)
                     for source in task.sources for entry in source.get("entries", [])}
            sizes.update({("__upload__", entry["stored_name"]): entry["size"] for entry in (task.report or {}).get("upload_files", [])})
            def expected(item, version):
                if version is not None and version.byte_size is not None:
                    return version.byte_size
                if version is not None:
                    stamp = (version.scientific_metadata or {}).get("registration_source_stamp") or {}
                    if "size" in stamp:
                        return stamp["size"]
                return sizes.get((item.root_id, item.source_path), 0)
            content.update(
                total=len(rows), succeeded=sum(item.content_status == "available" for item, _ in rows),
                failed=sum(item.content_status == "failed" for item, _ in rows),
                skipped=sum(item.content_status == "skipped" for item, _ in rows),
                metadata_failed=sum(item.metadata_status == "failed" for item, _ in rows),
                bytes_total=sum(expected(item, version) for item, version in rows if item.content_status != "skipped"),
                bytes_copied=sum(expected(item, version) if item.content_status == "available" else
                                 self._bytes.get(item.id, 0) if item.content_status != "failed" else 0 for item, version in rows),
                completed=content_completed or content.get("completed", False),
            )
            preview_rows = [item for item, _ in rows if item.content_status == "available"]
            preview.update(total=len(preview_rows), available=sum(item.preview_status == "available" for item in preview_rows),
                           failed=sum(item.preview_status == "failed" for item in preview_rows),
                           unsupported=sum(item.preview_status == "unsupported" for item in preview_rows),
                           completed=preview_completed or preview.get("completed", False))
            report = {**(task.report or {}), "content": content, "preview": preview}
            report["registration"] = {
                "total": len(rows),
                "registered": sum(item.asset_version_id is not None or item.status in {"failed", "skipped"} for item, _ in rows),
                "completed": registration_completed or (task.report or {}).get("registration", {}).get("completed", False),
            }
            task.report = report
            task.updated_at = datetime.now(timezone.utc)
        self._last_flush = now
