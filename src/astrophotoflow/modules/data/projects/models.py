from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from astrophotoflow.core.database.base import Base
from astrophotoflow.modules.data.names import SearchableName


class Project(SearchableName, Base):
    __tablename__ = "project"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_project_status"),
        CheckConstraint("revision >= 1", name="ck_project_revision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    target_name: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())

class ProjectAssetReference(Base):
    __tablename__ = "project_asset_reference"
    __table_args__ = (UniqueConstraint("project_id", "asset_version_id", name="uq_project_asset_version"),
        Index("ix_project_asset_reference_project", "project_id", "added_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    asset_version_id: Mapped[str] = mapped_column(ForeignKey("asset_version.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())

class ProjectDatasetReference(Base):
    __tablename__ = "project_dataset_reference"
    __table_args__ = (
        UniqueConstraint("project_id", "dataset_version_id", name="uq_project_dataset_version"),
        Index("ix_project_dataset_reference_project", "project_id", "added_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset.id", ondelete="CASCADE"), nullable=False)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_version.id"), nullable=False)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
