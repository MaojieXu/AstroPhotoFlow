"""Project association settles independently of successful original ingestion."""

from sqlalchemy import select

from astrophotoflow.contracts.projects import ProjectDatasetReferenceCreate, ProjectReferenceCreate
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.assets.references import require_referenceable
from astrophotoflow.modules.data.imports.models import AssetTaskItem
from astrophotoflow.modules.data.projects.models import Project, ProjectAssetReference, ProjectDatasetReference
from astrophotoflow.modules.data.projects.references import add_project_asset_reference, add_project_dataset_reference


def import_destination(session, body):
    if body.project_id is not None:
        project = session.get(Project, str(body.project_id))
        if project is None or project.status != "active" or project.revision != body.project_base_revision:
            raise ApiError(409, "REVISION_CONFLICT", "Read the active project and its current revision before importing.",
                           message_key="read_active_project_before_importing")
    dataset = None
    if body.mode == "append_dataset":
        dataset = require_referenceable(session, "dataset", body.target_dataset_id)
        if dataset.revision != body.dataset_base_revision:
            raise ApiError(409, "REVISION_CONFLICT", "Read the destination dataset before importing.",
                           message_key="read_destination_dataset_before_importing")
    context = {
        "mode": body.mode,
        "project_id": str(body.project_id) if body.project_id else None,
        "project_base_revision": body.project_base_revision,
        "project_name": project.name if body.project_id else None,
        "project_link": {"state": "pending" if body.project_id else "not_requested"},
    }
    return dataset, context


def link_task_project(session, task):
    context = (task.report or {}).get("destination")
    if not context or not context.get("project_id") or context["project_link"]["state"] != "pending":
        return
    try:
        with session.begin_nested():
            project = session.get(Project, context["project_id"])
            if project is None or project.status != "active" or project.revision != context["project_base_revision"]:
                raise ApiError(409, "REVISION_CONFLICT", "Import completed; the destination project changed or is unavailable.",
                               message_key="import_destination_project_changed")
            references = []
            if context["mode"] != "standalone":
                if not task.dataset_id:
                    raise ApiError(409, "DATASET_NOT_READY", "Originals are retained; organize the dataset before linking the project.",
                                   message_key="dataset_not_ready")
                existing = session.scalar(
                    select(ProjectDatasetReference).where(
                        ProjectDatasetReference.project_id == project.id, ProjectDatasetReference.dataset_id == task.dataset_id
                    )
                )
                reference = existing or add_project_dataset_reference(
                    session, project.id, ProjectDatasetReferenceCreate(base_revision=project.revision, dataset_id=task.dataset_id)
                )
                references.append(reference.id)
            else:
                identities = session.scalars(
                    select(AssetTaskItem.asset_id)
                    .where(
                        AssetTaskItem.task_id == task.id, AssetTaskItem.content_status == "available", AssetTaskItem.asset_id.is_not(None)
                    )
                    .order_by(AssetTaskItem.position)
                ).all()
                if not identities:
                    raise ApiError(409, "ORIGINALS_NOT_READY", "No imported originals are ready to associate.",
                                   message_key="originals_not_ready")
                for identity in identities:
                    existing = session.scalar(
                        select(ProjectAssetReference).where(
                            ProjectAssetReference.project_id == project.id, ProjectAssetReference.asset_id == identity
                        )
                    )
                    reference = existing or add_project_asset_reference(
                        session, project.id, ProjectReferenceCreate(base_revision=project.revision, asset_id=identity)
                    )
                    references.append(reference.id)
            result = {"state": "linked", "reference_ids": references, "project_revision": project.revision}
    except ApiError as exc:
        result = {"state": "failed", "code": exc.code, "message": exc.message, "fields": exc.fields}
    task.report = {**task.report, "destination": {**context, "project_link": result}}
    if result["state"] == "failed" and task.status == "completed":
        task.status = "completed_with_errors"


def finalize_import_project(database, task_id):
    with database.write_session() as session:
        from astrophotoflow.modules.data.imports.models import AssetTask

        task = session.get(AssetTask, task_id)
        if task is not None and task.status not in {"queued", "running", "cancelling", "interrupted"}:
            link_task_project(session, task)
