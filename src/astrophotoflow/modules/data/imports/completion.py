from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from astrophotoflow.core.database.db import Database
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember
from astrophotoflow.modules.data.datasets.service import publish_dataset_members
from astrophotoflow.modules.data.imports.context import ImportTaskContext
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem

logger = logging.getLogger(__name__)

def publish_dataset(database: Database, task_data: ImportTaskContext, task_id: str) -> dict | None:
    target_id = task_data.target_dataset_id
    if not target_id:
        return None
    try:
        with database.write_session() as session:
            task = session.get(AssetTask, task_id)
            successes = session.scalars(
                select(AssetTaskItem).where(
                    AssetTaskItem.task_id == task_id,
                    AssetTaskItem.asset_version_id.is_not(None),
                ).order_by(AssetTaskItem.position)
            ).all()
            if not successes:
                return None
            dataset = session.get(Dataset, target_id)
            if dataset is None:
                source_notes = task.notes
                dataset = Dataset(
                    id=target_id, name=task.dataset_name or "素材集", notes=source_notes,
                    status="active", revision=1, current_version_id=None,
                )
                session.add(dataset)
                session.flush()
                base_members = []
            else:
                base_members = session.scalars(
                    select(DatasetMember).where(DatasetMember.dataset_version_id == dataset.current_version_id)
                    .order_by(DatasetMember.position)
                ).all()
            existing_versions = {member.asset_version_id for member in base_members}
            additions = []
            for item in successes:
                if item.asset_version_id not in existing_versions:
                    additions.append((item.asset_version_id, Path(item.source_path).name if not item.root_id else item.source_path))
                    existing_versions.add(item.asset_version_id)
            if not additions and dataset.current_version_id is not None:
                return None
            if dataset.current_version_id is not None:
                expected = task.dataset_base_revision
                if expected is None or dataset.revision != expected:
                    raise RuntimeError(f"DATASET_REVISION_CONFLICT:{expected}:{dataset.revision}")
            version = publish_dataset_members(
                session, dataset,
                [member.asset_version_id for member in base_members] + [identity for identity, _ in additions],
                relative_paths=dict(additions),
            )
            version_id = version.id
            if version.version_number == 1:
                dataset.revision = 1
            task.dataset_id = target_id
            task.report = {**(task.report or {}), "dataset_id": target_id, "dataset_version_id": version_id}
            session.flush()
            return {"dataset_id": target_id, "dataset_version_id": version_id}
    except RuntimeError as exc:
        text = str(exc)
        if not text.startswith("DATASET_REVISION_CONFLICT:"):
            raise
        _, expected, observed = text.split(":")
        with database.write_session() as session:
            task = session.get(AssetTask, task_id)
            successful = session.scalars(
                select(AssetTaskItem.asset_version_id).where(
                    AssetTaskItem.task_id == task_id,
                    AssetTaskItem.asset_version_id.is_not(None),
                ).order_by(AssetTaskItem.position)
            ).all()
            dataset = session.get(Dataset, target_id)
            current_members = set()
            if dataset is not None and dataset.current_version_id is not None:
                current_members = set(session.scalars(
                    select(DatasetMember.asset_version_id).where(
                        DatasetMember.dataset_version_id == dataset.current_version_id
                    )
                ).all())
            pending = [version_id for version_id in successful if version_id not in current_members]
            conflict = {
                "code": "REVISION_CONFLICT", "dataset_id": target_id,
                "expected_revision": int(expected) if expected != "None" else None,
                "observed_revision": int(observed),
                "pending_asset_version_ids": pending,
            }
            task.report = {**(task.report or {}), "dataset_publish_error": conflict}
        return None


def finish_task(database: Database, task_id: str, was_cancelled: bool) -> None:
    with database.write_session() as session:
        task = session.get(AssetTask, task_id)
        if task.status == "interrupted":
            return
        items = session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task_id)).all()
        successes = sum(item.content_status == "available" for item in items)
        errors = any(item.status in {"failed", "completed_with_errors"} or item.metadata_status == "failed" for item in items)
        skipped = sum(item.status == "skipped" for item in items)
        if was_cancelled:
            status = "cancelled"
        elif not successes:
            status = "failed"
        elif errors or (task.report or {}).get("dataset_publish_error"):
            status = "completed_with_errors"
        else:
            status = "completed"
        task.status = status
        task.report = {
            **(task.report or {}),
            "counts": {
                "enumerated": len(items),
                "content_succeeded": successes,
                "failed": sum(item.status == "failed" for item in items),
                "skipped": skipped,
                "processing_issues": sum(
                    item.status == "completed_with_errors" or item.metadata_status == "failed" for item in items
                ),
                "cancelled": sum(item.status == "cancelled" for item in items),
            },
        }
        task.updated_at = datetime.now(UTC)
