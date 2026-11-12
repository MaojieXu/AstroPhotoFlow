from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from astrophotoflow.core.database.base import Base
from astrophotoflow.modules.data.names import SearchableName

class Dataset(SearchableName, Base):
    __tablename__ = 'dataset'
    __table_args__ = (CheckConstraint("manifest_status IN ('pending', 'ready', 'failed')", name='ck_dataset_manifest_status'), CheckConstraint("status IN ('active', 'archived')", name='ck_dataset_status'), CheckConstraint('revision >= 1', name='ck_dataset_revision'), Index('ix_dataset_status_created', 'status', 'created_at'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    library_directory: Mapped[str | None] = mapped_column(Text)
    manifest_status: Mapped[str] = mapped_column(String(16), nullable=False, default='pending', server_default='pending')
    manifest_error: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='active')
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
    calibration: Mapped[list[DatasetCalibration]] = relationship(foreign_keys='DatasetCalibration.dataset_id', cascade='all, delete-orphan', lazy='selectin')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())

class DatasetMember(Base):
    __tablename__ = 'dataset_member'
    __table_args__ = (UniqueConstraint('asset_id', name='uq_dataset_member_asset'), UniqueConstraint('dataset_id', 'position', name='uq_dataset_member_position'), CheckConstraint('position >= 0', name='ck_dataset_member_position'), Index('ix_dataset_member_position', 'dataset_id', 'position'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey('dataset.id', ondelete='CASCADE'), nullable=False)
    asset_id: Mapped[str] = mapped_column(ForeignKey('asset.id'), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    relative_path: Mapped[str | None] = mapped_column(Text)

class DatasetCalibration(Base):
    __tablename__ = 'dataset_calibration'
    __table_args__ = (CheckConstraint("frame_type IN ('bias', 'dark', 'flat', 'dark_flat')", name='ck_dataset_calibration_frame_type'), CheckConstraint('(disabled = 1 AND asset_id IS NULL) OR (disabled = 0 AND asset_id IS NOT NULL)', name='ck_dataset_calibration_target'), Index('ix_dataset_calibration_asset_target', 'asset_id'))
    dataset_id: Mapped[str] = mapped_column(ForeignKey('dataset.id', ondelete='CASCADE'), primary_key=True)
    frame_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    state: Mapped[str | None] = mapped_column(String(16))
    asset_id: Mapped[str | None] = mapped_column(ForeignKey('asset.id', ondelete='CASCADE'))
