from __future__ import annotations
from datetime import UTC, datetime
from uuid import UUID
from sqlalchemy import update
from sqlalchemy.orm import Session
from astrophotoflow.core.errors import ApiError, not_found

def now_utc() -> datetime:
    return datetime.now(UTC)

def utc_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

def uuid_text(value: UUID | str) -> str:
    return str(value)

def raise_record_conflict(session: Session, model, record_id: str) -> None:
    if session.get(model, record_id) is None:
        raise not_found()
    raise ApiError(409, 'REVISION_CONFLICT', '配置已被其他窗口修改，请重新读取后保存。', message_key='another_window_changed_the_configuration_read_it_again_before_saving')

def update_record(session: Session, model, record_id: str, base_revision: int, changes: dict) -> None:
    now = now_utc()
    result = session.execute(update(model).where(model.id == record_id, model.revision == base_revision).values(**changes, revision=base_revision + 1, updated_at=now))
    if result.rowcount != 1:
        raise_record_conflict(session, model, record_id)
