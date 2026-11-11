from datetime import datetime
from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from astrophotoflow.core.database.base import Base


class Preview(Base):
    __tablename__ = "preview"
    __table_args__ = (
        UniqueConstraint("asset_id", "hdu_index", "size", "algorithm_version", name="uq_preview_identity"),
        Index("ix_preview_asset", "asset_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("asset.id", ondelete="CASCADE"), nullable=False)
    hdu_index: Mapped[int] = mapped_column(Integer, nullable=False)
    size: Mapped[str] = mapped_column(String(16), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False, default="image/jpeg")
    display_parameters: Mapped[dict] = mapped_column(JSON, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())


class ThumbnailBatch(Base):
    __tablename__ = "thumbnail_batch"
    __table_args__ = (Index("ix_thumbnail_batch_created", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())


class ThumbnailBatchItem(Base):
    __tablename__ = "thumbnail_batch_item"
    __table_args__ = (
        UniqueConstraint("batch_id", "position", name="uq_thumbnail_batch_position"),
        Index("ix_thumbnail_batch_item_preview", "preview_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("thumbnail_batch.id", ondelete="CASCADE"), nullable=False)
    preview_id: Mapped[str | None] = mapped_column(ForeignKey("preview.id", ondelete="SET NULL"))
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("asset.id", ondelete="SET NULL"))
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("dataset.id", ondelete="SET NULL"))
    position: Mapped[int] = mapped_column(Integer, nullable=False)
