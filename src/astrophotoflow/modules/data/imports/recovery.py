"""Repair organization using already registered import identities and receipts."""

from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from astrophotoflow.contracts.image_calibration import DatasetMemberInput, ImageDatasetCreate, ImageDatasetEditMembers
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.calibration.service import (
    create_image_dataset,
    edit_image_dataset_members,
    replay_operation,
    save_operation,
)
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
from astrophotoflow.modules.data.imports.project_links import link_task_project


def recover_import_organization(session, task_id, body):
    payload = {"task_id": str(task_id), **body.model_dump(mode="json")}
    replay = replay_operation(session, body.request_id, "recover_import", payload)
    if replay is not None:
        return replay
    task = session.get(AssetTask, str(task_id))
    if task is None:
        raise not_found()
    if task.status in {"queued", "running", "cancelling", "interrupted"}:
        raise ApiError(409, "IMPORT_ACTIVE", "Finish or cancel the import before repairing its organization.")
    successful = set(
        session.scalars(
            select(AssetTaskItem.asset_id).where(
                AssetTaskItem.task_id == task.id, AssetTaskItem.content_status == "available", AssetTaskItem.asset_id.is_not(None)
            )
        )
    )
    ids = [str(value) for value in body.asset_ids]
    if set(ids) - successful:
        raise ApiError(422, "INVALID_REFERENCE", "Select only successful materials registered by this import task.")
    if body.mode == "new_dataset":
        command = ImageDatasetCreate(
            request_id=uuid5(NAMESPACE_URL, str(body.request_id) + "/dataset"),
            name=body.name,
            accept_unknown=body.accept_unknown,
            members=[DatasetMemberInput(asset_id=identity) for identity in ids],
        )
        result = create_image_dataset(session, command)["result"]
        task.dataset_id = str(result["dataset_id"])
    elif body.mode == "append_dataset":
        command = ImageDatasetEditMembers(
            request_id=uuid5(NAMESPACE_URL, str(body.request_id) + "/append"),
            expected_revision=body.expected_revision,
            accept_unknown=body.accept_unknown,
            add=[DatasetMemberInput(asset_id=identity) for identity in ids],
        )
        result = edit_image_dataset_members(session, body.dataset_id, command)["result"]
        task.dataset_id = str(body.dataset_id)
    else:
        result = {"dataset_id": task.dataset_id} if task.dataset_id else {}
    if body.mode != "link_project":
        task.report = {key: value for key, value in task.report.items() if key != "dataset_publish_error"}
    if body.project_id is not None:
        context = {
            **(task.report.get("destination") or {}),
            "mode": "new_dataset" if task.dataset_id else "standalone",
            "project_id": str(body.project_id),
            "project_base_revision": body.project_base_revision,
            "project_link": {"state": "pending"},
        }
        task.report = {**task.report, "destination": context}
        link_task_project(session, task)
    task.report = {**task.report, "organization_recovery": {"request_id": str(body.request_id), "mode": body.mode, **result}}
    return save_operation(
        session,
        body.request_id,
        "recover_import",
        payload,
        {**result, "project_link": (task.report.get("destination") or {}).get("project_link")},
    )
