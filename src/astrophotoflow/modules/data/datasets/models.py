from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from astrophotoflow.core.database.base import Base
from astrophotoflow.modules.data.names import SearchableName


class Dataset(SearchableName, Base):
    __tablename__ = "dataset"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_dataset_status"),
        CheckConstraint("revision >= 1", name="ck_dataset_revision"),
        Index("ix_dataset_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_version_id: Mapped[str | None] = mapped_column(ForeignKey("dataset_version.id", use_alter=True, name="fk_dataset_current_version"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())

class DatasetVersion(Base):
    __tablename__ = "dataset_version"
    __table_args__ = (
        UniqueConstraint("dataset_id", "version_number", name="uq_dataset_version_number"),
        CheckConstraint("version_number > 0", name="ck_dataset_version_number"),
        Index("ix_dataset_version_dataset_created", "dataset_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    defaults: Mapped[list[DatasetCalibration]] = relationship(foreign_keys="DatasetCalibration.dataset_version_id", cascade="all, delete-orphan", lazy="selectin")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())

class DatasetMember(Base):
    __tablename__ = "dataset_member"
    __table_args__ = (
        UniqueConstraint("dataset_version_id", "asset_version_id", name="uq_dataset_member_asset_version"),
        UniqueConstraint("dataset_version_id", "position", name="uq_dataset_member_position"),
        CheckConstraint("position >= 0", name="ck_dataset_member_position"),
        Index("ix_dataset_member_version_position", "dataset_version_id", "position"),
        Index("ix_dataset_member_asset_version", "asset_version_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_version.id", ondelete="CASCADE"), nullable=False)
    asset_version_id: Mapped[str] = mapped_column(ForeignKey("asset_version.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    relative_path: Mapped[str | None] = mapped_column(Text)
    overrides: Mapped[list[MemberCalibration]] = relationship(cascade="all, delete-orphan", lazy="selectin")

class DatasetCalibration(Base):
    __tablename__ = "dataset_calibration"
    __table_args__ = (
        CheckConstraint("frame_type IN ('bias', 'dark', 'flat', 'dark_flat')", name="ck_dataset_calibration_frame_type"),
        CheckConstraint("(disabled = 1 AND asset_version_id IS NULL AND target_dataset_version_id IS NULL) OR (disabled = 0 AND ((asset_version_id IS NULL) != (target_dataset_version_id IS NULL)))", name="ck_dataset_calibration_target"),
        Index("ix_dataset_calibration_asset_target", "asset_version_id"),
        Index("ix_dataset_calibration_dataset_target", "target_dataset_version_id"),
    )

    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_version.id", ondelete="CASCADE"), primary_key=True)
    frame_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    asset_version_id: Mapped[str | None] = mapped_column(ForeignKey("asset_version.id", ondelete="CASCADE"))
    target_dataset_version_id: Mapped[str | None] = mapped_column(ForeignKey("dataset_version.id", ondelete="CASCADE"))


class MemberCalibration(Base):
    __tablename__ = "member_calibration"
    __table_args__ = (
        CheckConstraint("frame_type IN ('bias', 'dark', 'flat', 'dark_flat')", name="ck_member_calibration_frame_type"),
        CheckConstraint("(disabled = 1 AND asset_version_id IS NULL AND target_dataset_version_id IS NULL) OR (disabled = 0 AND ((asset_version_id IS NULL) != (target_dataset_version_id IS NULL)))", name="ck_member_calibration_target"),
        Index("ix_member_calibration_asset_target", "asset_version_id"),
        Index("ix_member_calibration_dataset_target", "target_dataset_version_id"),
    )

    member_id: Mapped[str] = mapped_column(ForeignKey("dataset_member.id", ondelete="CASCADE"), primary_key=True)
    frame_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    asset_version_id: Mapped[str | None] = mapped_column(ForeignKey("asset_version.id", ondelete="CASCADE"))
    target_dataset_version_id: Mapped[str | None] = mapped_column(ForeignKey("dataset_version.id", ondelete="CASCADE"))
