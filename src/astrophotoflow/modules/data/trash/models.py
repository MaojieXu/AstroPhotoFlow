from datetime import datetime
from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from astrophotoflow.core.database.base import Base

class LibraryEntryRemoval(Base):
    __tablename__ = 'library_entry_removal'
    __table_args__ = (CheckConstraint("entry_type IN ('asset', 'dataset')", name='ck_library_entry_removal_type'),)
    entry_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    entry_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey('dataset.id'))
    member_asset_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    pending_paths: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cleaned_paths: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cleaned_asset_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cleanup_status: Mapped[str] = mapped_column(String(16), nullable=False, default='trash')
    cleanup_error: Mapped[str | None] = mapped_column(Text)
    removed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
