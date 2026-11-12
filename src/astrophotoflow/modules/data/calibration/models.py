"""Immutable standalone configurations and idempotent mutation receipts."""
from datetime import datetime
from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from astrophotoflow.core.database.base import Base

class ImageCalibrationOperation(Base):
    __tablename__ = 'image_calibration_operation'
    request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
