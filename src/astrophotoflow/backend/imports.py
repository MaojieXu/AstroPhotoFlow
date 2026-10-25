from __future__ import annotations
from fastapi import APIRouter

from .dependencies import ERROR_RESPONSES
from . import dependencies as deps
from . import common as shared

import shutil
from typing import Annotated, Literal
from uuid import UUID, uuid4
from fastapi import Depends, Query, Request, BackgroundTasks
from sqlalchemy import func, select
from .errors import ApiError, not_found
from .models import AssetTask, AssetTaskItem, Dataset
from .schemas import AssetTaskOut, AssetTaskPage, ImportAccepted, ImportRootEntryPage, ImportRootOut
from .files import entries_page, find_root, resolve_relative
from .import_schemas import RetryCreate, ImportCreate, UploadImportCreate
from pathlib import Path
from .ingestion import process_task, validate_import_equipment


router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


@router.post("/uploads", status_code=202, dependencies=[Depends(deps.authenticate)])
def create_upload(body: UploadImportCreate, request: Request, session: deps.WriteSession):
    validate_import_equipment(session, body.parameters.model_dump(mode="json"))
    task_id = str(uuid4())
    staging = request.app.state.settings.data_dir / "upload-staging" / task_id
    staging.mkdir(parents=True, exist_ok=True)
    files = []
    sources = []
    now = shared._now()
    for position, file in enumerate(body.files):
        suffix = "".join(Path(file.name).suffixes[-2:]) if file.name.lower().endswith((".fits.fz", ".fit.fz")) else Path(file.name).suffix
        stored_name = f"{position}{suffix.lower()}"
        files.append({"name": file.name, "size": file.size, "received": 0, "stored_name": stored_name})
        sources.append({"root_id": "__upload__", "path": stored_name, "kind": "file", "enumeration_completed": True, "error": None})
        session.add(AssetTaskItem(
            id=str(uuid4()), task_id=task_id, root_item_id=str(uuid4()), retry_of_item_id=None,
            root_id="__upload__", source_path=stored_name, source_identity=f"upload:{task_id}:{position}",
            position=position, status="queued", content_status="pending", metadata_status="pending",
            preview_status="pending", error=None, created_at=now, updated_at=now,
        ))
    create_dataset = body.create_dataset or len(body.files) > 1
    task = AssetTask(
        id=task_id, status="queued", sources=sources, storage_mode="managed",
        classification=body.classification.model_dump(mode="json"), parameters=body.parameters.model_dump(mode="json"),
        notes=body.notes,
        dataset_name=(body.dataset_name or body.files[0].name) if create_dataset else None,
        target_dataset_id=str(uuid4()) if create_dataset else None, dataset_base_revision=None,
        dataset_id=None, enumeration_completed=True, retry_of_task_id=None,
        report={"upload_manifest": True, "upload_files": files}, error=None,
        created_at=now, updated_at=now,
    )
    session.add(task)
    session.flush()
    return {"task_id": UUID(task_id), "status": "queued"}


@router.put("/uploads/{task_id}/{index}", dependencies=[Depends(deps.authenticate)])
async def upload_file(task_id: UUID, index: int, request: Request):
    database = request.app.state.database
    with database.read_session() as session:
        task = session.get(AssetTask, shared._id(task_id))
        files = (task.report or {}).get("upload_files", []) if task else []
        if task is None or not (task.report or {}).get("upload_manifest") or index < 0 or index >= len(files):
            raise not_found()
        entry = dict(files[index])
        if entry["received"] != 0:
            raise ApiError(409, "UPLOAD_ALREADY_RECEIVED", "该文件已上传；请重新选择文件创建导入批次。")
    target = request.app.state.settings.data_dir / "upload-staging" / shared._id(task_id) / entry["stored_name"]
    received = 0
    try:
        with target.open("xb") as stream:
            async for chunk in request.stream():
                stream.write(chunk)
                received += len(chunk)
    except Exception as exc:
        with database.write_session() as session:
            task = session.get(AssetTask, shared._id(task_id))
            if task and task.status == "queued":
                task.status = "failed"
                task.error = {"code": "UPLOAD_FAILED", "message": "文件上传中断，请重新选择文件创建导入批次。"}
                task.updated_at = shared._now()
                for item in session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task.id)).all():
                    item.status, item.content_status, item.error = "failed", "failed", task.error
                    item.updated_at = shared._now()
        shutil.rmtree(request.app.state.settings.data_dir / "upload-staging" / shared._id(task_id), ignore_errors=True)
        raise ApiError(400, "UPLOAD_FAILED", "文件上传中断，请重新选择文件创建导入批次。") from exc
    if received != entry["size"]:
        target.unlink(missing_ok=True)
        raise ApiError(400, "UPLOAD_SIZE_MISMATCH", "上传文件大小与选择时记录不一致，请重新选择文件。")
    with database.write_session() as session:
        task = session.get(AssetTask, shared._id(task_id))
        files = list((task.report or {}).get("upload_files", []))
        files[index] = {**files[index], "received": received}
        task.report = {**(task.report or {}), "upload_files": files}
        task.updated_at = shared._now()
    return {"received": received}


@router.post("/uploads/{task_id}/start", status_code=202, dependencies=[Depends(deps.authenticate)])
def start_upload_import(task_id: UUID, request: Request, background: BackgroundTasks, session: deps.WriteSession):
    task = session.get(AssetTask, shared._id(task_id))
    if task is None or not (task.report or {}).get("upload_manifest"):
        raise not_found()
    if any(file["received"] != file["size"] for file in task.report["upload_files"]):
        raise ApiError(409, "UPLOAD_INCOMPLETE", "所有文件上传完成后才能开始导入。")
    if task.status != "queued":
        raise ApiError(409, "TASK_STATE_CONFLICT", "该上传批次已开始处理。")
    task.report = {**task.report, "upload_complete": True}
    task.updated_at = shared._now()
    background.add_task(process_task, request.app.state.database, request.app.state.settings, task.id)
    return {"task_id": UUID(task.id), "status": "queued"}


@router.post("/uploads/{task_id}/fail", dependencies=[Depends(deps.authenticate)])
def fail_upload(task_id: UUID, request: Request, session: deps.WriteSession):
    task = session.get(AssetTask, shared._id(task_id))
    if task is None or not (task.report or {}).get("upload_manifest"):
        raise not_found()
    if task.status != "queued":
        raise ApiError(409, "TASK_STATE_CONFLICT", "后台处理已开始，不能按上传失败取消。")
    task.status = "failed"
    task.error = {"code": "UPLOAD_FAILED", "message": "文件上传未完成，请重新选择文件创建导入批次。"}
    task.updated_at = shared._now()
    for item in session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task.id)).all():
        item.status = "failed"
        item.content_status = "failed"
        item.error = task.error
        item.updated_at = shared._now()
    shutil.rmtree(request.app.state.settings.data_dir / "upload-staging" / task.id, ignore_errors=True)
    return {"task_id": UUID(task.id), "status": task.status}


def _task_out(session, task: AssetTask, items_limit: int, items_offset: int) -> dict:
    total = session.scalar(
        select(func.count()).select_from(AssetTaskItem).where(AssetTaskItem.task_id == task.id)
    ) or 0
    items = session.scalars(
        select(AssetTaskItem).where(AssetTaskItem.task_id == task.id)
        .order_by(AssetTaskItem.position, AssetTaskItem.id).limit(items_limit).offset(items_offset)
    ).all()
    completed = session.scalar(
        select(func.count()).select_from(AssetTaskItem).where(
            AssetTaskItem.task_id == task.id,
            AssetTaskItem.status.in_({"completed", "completed_with_errors", "failed", "cancelled", "skipped"}),
        )
    ) or 0
    return {
        "id": UUID(task.id), "status": task.status, "sources": task.sources,
        "storage_mode": task.storage_mode, "classification": task.classification,
        "parameters": task.parameters, "notes": task.notes, "dataset_name": task.dataset_name,
        "target_dataset_id": UUID(task.target_dataset_id) if task.target_dataset_id else None,
        "dataset_base_revision": task.dataset_base_revision,
        "dataset_id": UUID(task.dataset_id) if task.dataset_id else None,
        "enumeration_completed": task.enumeration_completed,
        "retry_of_task_id": UUID(task.retry_of_task_id) if task.retry_of_task_id else None,
        "report": task.report or {}, "error": task.error,
        "created_at": shared._utc(task.created_at), "updated_at": shared._utc(task.updated_at),
        "items": [{
            "id": UUID(row.id), "task_id": UUID(row.task_id), "root_item_id": UUID(row.root_item_id),
            "retry_of_item_id": UUID(row.retry_of_item_id) if row.retry_of_item_id else None,
            "root_id": row.root_id, "source_path": row.source_path, "position": row.position,
            "status": row.status, "content_status": row.content_status,
            "metadata_status": row.metadata_status, "preview_status": row.preview_status,
            "asset_id": UUID(row.asset_id) if row.asset_id else None,
            "asset_version_id": UUID(row.asset_version_id) if row.asset_version_id else None,
            "error": row.error, "created_at": shared._utc(row.created_at), "updated_at": shared._utc(row.updated_at),
        } for row in items],
        "items_total": total, "items_completed": completed,
        "items_limit": items_limit, "items_offset": items_offset,
    }


@router.get("/import-roots", response_model=list[ImportRootOut], dependencies=[Depends(deps.authenticate)])
def import_roots(request: Request):
    result = []
    for root in request.app.state.settings.import_roots:
        try:
            available = root.path.resolve(strict=True).is_dir()
        except OSError:
            available = False
        result.append({"id": root.id, "label": root.path.name or root.id, "available": available})
    return result


@router.get("/import-roots/{root_id}/entries", response_model=ImportRootEntryPage, dependencies=[Depends(deps.authenticate)])
def import_root_entries(
    root_id: str, request: Request, path: str = "", limit: deps.Limit = 100,
    offset: deps.Offset = 0, q: str | None = None,
):
    return entries_page(request.app.state.settings, root_id, path, limit, offset, q)


@router.post("/imports", response_model=ImportAccepted, status_code=202, dependencies=[Depends(deps.authenticate)])
def create_import(body: ImportCreate, request: Request, background: BackgroundTasks, session: deps.WriteSession):
    validate_import_equipment(session, body.parameters.model_dump(mode="json"))
    sources = []
    is_dataset = len(body.sources) > 1
    for source in body.sources:
        _, root = find_root(request.app.state.settings, source.root_id)
        selected = resolve_relative(root, source.path, allow_empty=True)
        kind = "directory" if selected.is_dir() else "file"
        if kind == "directory":
            is_dataset = True
        data_root = request.app.state.settings.data_dir.resolve()
        try:
            data_root.relative_to(root)
        except ValueError:
            pass
        else:
            raise ApiError(422, "VALIDATION_ERROR", "素材根目录不能包含 AstroPhotoFlow 数据目录。")
        sources.append({
            "root_id": source.root_id, "path": source.path, "kind": kind,
            "enumeration_completed": False, "error": None,
        })
    task_id = str(uuid4())
    target_dataset_id = str(uuid4()) if is_dataset else None
    dataset_name = body.dataset_name
    if is_dataset and not dataset_name:
        primary = sources[0]
        dataset_name = Path(primary["path"].rstrip("/")).name or next(
            (root.path.name for root in request.app.state.settings.import_roots if root.id == primary["root_id"]), "素材集"
        )
    task = AssetTask(
        id=task_id, status="queued", sources=sources, storage_mode=body.storage_mode,
        classification=body.classification.model_dump(mode="json"),
        parameters=body.parameters.model_dump(mode="json"), notes=body.notes, dataset_name=dataset_name,
        target_dataset_id=target_dataset_id, dataset_base_revision=None, dataset_id=None,
        enumeration_completed=False, retry_of_task_id=None, report={}, error=None,
        created_at=shared._now(), updated_at=shared._now(),
    )
    session.add(task)
    session.flush()
    background.add_task(process_task, request.app.state.database, request.app.state.settings, task_id)
    return {"task_id": UUID(task_id), "status": "queued"}


@router.get("/asset-tasks", response_model=AssetTaskPage, dependencies=[Depends(deps.authenticate)])
def list_asset_tasks(
    session: deps.ReadSession, limit: deps.Limit = 50, offset: deps.Offset = 0,
    status: Literal["queued", "running", "cancelling", "completed", "completed_with_errors", "failed", "cancelled", "interrupted", "all"] = "all",
):
    filters = [] if status == "all" else [AssetTask.status == status]
    total = session.scalar(select(func.count()).select_from(AssetTask).where(*filters)) or 0
    rows = session.scalars(
        select(AssetTask).where(*filters).order_by(AssetTask.created_at.desc(), AssetTask.id).limit(limit).offset(offset)
    ).all()
    return {"items": [_task_out(session, task, 20, 0) for task in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/asset-tasks/{task_id}", response_model=AssetTaskOut, dependencies=[Depends(deps.authenticate)])
def get_asset_task(
    task_id: UUID, session: deps.ReadSession,
    items_limit: Annotated[int, Query(ge=1, le=200)] = 50,
    items_offset: Annotated[int, Query(ge=0)] = 0,
):
    task = session.get(AssetTask, shared._id(task_id))
    if task is None:
        raise not_found()
    return _task_out(session, task, items_limit, items_offset)


@router.post("/asset-tasks/{task_id}/cancel", status_code=202, dependencies=[Depends(deps.authenticate)])
def cancel_asset_task(task_id: UUID, request: Request, session: deps.WriteSession):
    task = session.get(AssetTask, shared._id(task_id))
    if task is None:
        raise not_found()
    if task.status not in {"queued", "running", "cancelling", "interrupted"}:
        raise ApiError(409, "TASK_STATE_CONFLICT", "当前任务状态不能取消。")
    task.status = "cancelling" if task.status in {"running", "cancelling"} else "cancelled"
    task.updated_at = shared._now()
    if task.status == "cancelled":
        for item in session.scalars(select(AssetTaskItem).where(
            AssetTaskItem.task_id == task.id, AssetTaskItem.status.in_({"queued", "interrupted", "running"})
        )).all():
            item.status = "cancelled"
            item.updated_at = shared._now()
    return {"task_id": UUID(task.id), "status": task.status}


@router.post("/asset-tasks/{task_id}/resume", status_code=202, response_model=ImportAccepted, dependencies=[Depends(deps.authenticate)])
def resume_asset_task(task_id: UUID, request: Request, background: BackgroundTasks, session: deps.WriteSession):
    task = session.get(AssetTask, shared._id(task_id))
    if task is None:
        raise not_found()
    if task.status != "interrupted":
        raise ApiError(409, "TASK_STATE_CONFLICT", "只有服务中断的任务可恢复。")
    if (task.report or {}).get("upload_manifest") and not (task.report or {}).get("upload_complete"):
        raise ApiError(409, "UPLOAD_REQUIRES_SELECTION", "上传未完成，请重新选择文件并创建导入批次。")
    task.status = "queued"
    task.error = None
    task.updated_at = shared._now()
    for item in session.scalars(select(AssetTaskItem).where(
        AssetTaskItem.task_id == task.id, AssetTaskItem.status == "interrupted"
    )).all():
        item.status = "queued"
        item.updated_at = shared._now()
    background.add_task(process_task, request.app.state.database, request.app.state.settings, task.id)
    return {"task_id": UUID(task.id), "status": "queued"}


@router.post("/asset-tasks/{task_id}/retry", status_code=202, response_model=ImportAccepted, dependencies=[Depends(deps.authenticate)])
def retry_asset_task(task_id: UUID, body: RetryCreate, request: Request, background: BackgroundTasks, session: deps.WriteSession):
    original = session.get(AssetTask, shared._id(task_id))
    if original is None:
        raise not_found()
    if original.status not in {"failed", "completed_with_errors", "cancelled"}:
        raise ApiError(409, "TASK_STATE_CONFLICT", "当前任务状态不能重试。")
    selected_ids = [shared._id(value) for value in body.item_ids]
    if len(set(selected_ids)) != len(selected_ids):
        raise ApiError(422, "VALIDATION_ERROR", "重试项不能重复。")
    items = session.scalars(select(AssetTaskItem).where(
        AssetTaskItem.task_id == original.id, AssetTaskItem.id.in_(selected_ids)
    ).order_by(AssetTaskItem.position)).all()
    if len(items) != len(selected_ids):
        raise not_found()
    if any(item.status == "skipped" or not (
        item.content_status in {"pending", "failed"} or item.metadata_status == "failed" or item.preview_status == "failed"
    ) for item in items):
        raise ApiError(422, "VALIDATION_ERROR", "所选项没有失败或未完成阶段，不能重试。")
    source_task = session.get(AssetTask, original.retry_of_task_id) if original.retry_of_task_id else original
    retry_task_id = str(uuid4())
    target_dataset_id = source_task.target_dataset_id
    dataset = session.get(Dataset, target_dataset_id) if target_dataset_id else None
    retry_task = AssetTask(
        id=retry_task_id, status="queued",
        sources=[{"root_id": item.root_id, "path": item.source_path, "kind": "file", "enumeration_completed": True, "error": None} for item in items],
        storage_mode=source_task.storage_mode, classification=source_task.classification,
        parameters=source_task.parameters, notes=source_task.notes, dataset_name=source_task.dataset_name,
        target_dataset_id=target_dataset_id, dataset_base_revision=dataset.revision if dataset else None,
        dataset_id=source_task.dataset_id, enumeration_completed=True, retry_of_task_id=original.id,
        report={
            "upload_manifest": bool((source_task.report or {}).get("upload_manifest")),
            "upload_complete": bool((source_task.report or {}).get("upload_complete")),
            "upload_source_task_id": (source_task.report or {}).get("upload_source_task_id", source_task.id),
            "upload_files": (source_task.report or {}).get("upload_files", []),
        }, error=None, created_at=shared._now(), updated_at=shared._now(),
    )
    session.add(retry_task)
    session.flush()
    for position, item in enumerate(items):
        source_item = session.get(AssetTaskItem, item.retry_of_item_id) if item.retry_of_item_id else item
        root_item = source_item.root_item_id if source_item else item.root_item_id
        session.add(AssetTaskItem(
            id=str(uuid4()), task_id=retry_task_id, root_item_id=root_item, retry_of_item_id=item.id,
            root_id=item.root_id, source_path=item.source_path, source_identity=item.source_identity,
            position=position, status="queued", content_status=item.content_status,
            metadata_status=item.metadata_status, preview_status=item.preview_status,
            asset_id=item.asset_id, asset_version_id=item.asset_version_id, error=None,
            created_at=shared._now(), updated_at=shared._now(),
        ))
    session.flush()
    background.add_task(process_task, request.app.state.database, request.app.state.settings, retry_task_id)
    return {"task_id": UUID(retry_task_id), "status": "queued"}
