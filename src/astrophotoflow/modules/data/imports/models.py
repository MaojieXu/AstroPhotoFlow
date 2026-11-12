from datetime import datetime
from typing import get_args
from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from astrophotoflow.contracts.imports import TaskStatus
from astrophotoflow.core.database.base import Base

class AssetTask(Base):
    __tablename__ = 'asset_task'
    __table_args__ = (CheckConstraint(f'status IN {get_args(TaskStatus)!r}', name='ck_asset_task_status'), Index('ix_asset_task_created', 'created_at'), Index('uq_asset_task_request_id', 'request_id', unique=True))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str | None] = mapped_column(String(36))
    request_fingerprint: Mapped[str | None] = mapped_column(String(64))
    image_import_plan: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[TaskStatus] = mapped_column(String(32), nullable=False, default='queued')
    sources: Mapped[list] = mapped_column(JSON, nullable=False)
    storage_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    classification: Mapped[dict] = mapped_column(JSON, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)
    import_defaults_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default='{}')
    notes: Mapped[str | None] = mapped_column(Text)
    dataset_name: Mapped[str | None] = mapped_column(String)
    target_dataset_id: Mapped[str | None] = mapped_column(String(36))
    dataset_base_revision: Mapped[int | None] = mapped_column(Integer)
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey('dataset.id'))
    enumeration_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retry_of_task_id: Mapped[str | None] = mapped_column(ForeignKey('asset_task.id'))
    report: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())

class AssetTaskItem(Base):
    __tablename__ = 'asset_task_item'
    __table_args__ = (UniqueConstraint('task_id', 'id', name='uq_asset_task_item_task_id_id'), UniqueConstraint('task_id', 'position', name='uq_asset_task_item_position'), Index('ix_asset_task_item_task_created', 'task_id', 'created_at'), Index('ix_asset_task_item_root', 'root_item_id'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey('asset_task.id', ondelete='CASCADE'), nullable=False)
    root_item_id: Mapped[str] = mapped_column(String(36), nullable=False)
    retry_of_item_id: Mapped[str | None] = mapped_column(String(36))
    root_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_identity: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='queued')
    content_status: Mapped[str] = mapped_column(String(16), nullable=False, default='pending')
    metadata_status: Mapped[str] = mapped_column(String(16), nullable=False, default='pending')
    preview_status: Mapped[str] = mapped_column(String(16), nullable=False, default='pending')
    asset_id: Mapped[str | None] = mapped_column(ForeignKey('asset.id'))
    error: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
