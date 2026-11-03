"""Immutable standalone configurations and idempotent mutation receipts."""

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from astrophotoflow.core.database.base import Base


class ImageCalibrationConfiguration(Base):
    __tablename__ = "image_calibration_configuration"
    __table_args__ = (
        UniqueConstraint("asset_version_id", "version_number", name="uq_image_calibration_version"),
        CheckConstraint("version_number >= 1", name="ck_image_calibration_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    asset_version_id: Mapped[str] = mapped_column(ForeignKey("asset_version.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    bindings: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())


class ImageCalibrationOperation(Base):
    __tablename__ = "image_calibration_operation"

    request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
