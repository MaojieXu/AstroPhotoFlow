from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "project"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_project_status"),
        CheckConstraint("revision >= 1", name="ck_project_revision"),
        Index("ix_project_name", "name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    target_name: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())


class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = (
        CheckConstraint("kind IN ('camera', 'optical_system', 'filter')", name="ck_equipment_kind"),
        CheckConstraint("status IN ('active', 'archived')", name="ck_equipment_status"),
        CheckConstraint("revision >= 1", name="ck_equipment_revision"),
        Index("ix_equipment_kind_status", "kind", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str | None] = mapped_column(String)
    serial_number: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(String)
    specs: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())


class CaptureProfile(Base):
    __tablename__ = "capture_profile"
    __table_args__ = (
        CheckConstraint("frame_type IN ('light', 'bias', 'dark', 'flat', 'dark_flat')", name="ck_capture_profile_frame_type"),
        CheckConstraint("exposure_seconds IS NULL OR exposure_seconds >= 0", name="ck_capture_profile_exposure"),
        CheckConstraint("binning_x IS NULL OR binning_x > 0", name="ck_capture_profile_binning_x"),
        CheckConstraint("binning_y IS NULL OR binning_y > 0", name="ck_capture_profile_binning_y"),
        CheckConstraint("status IN ('active', 'archived')", name="ck_capture_profile_status"),
        CheckConstraint("revision >= 1", name="ck_capture_profile_revision"),
        Index("ix_capture_profile_camera_status", "camera_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    camera_id: Mapped[str] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    optical_system_id: Mapped[str | None] = mapped_column(ForeignKey("equipment.id"))
    filter_id: Mapped[str | None] = mapped_column(ForeignKey("equipment.id"))
    frame_type: Mapped[str] = mapped_column(String(16), nullable=False)
    exposure_seconds: Mapped[float | None] = mapped_column(Float)
    gain: Mapped[float | None] = mapped_column(Float)
    offset: Mapped[float | None] = mapped_column(Float)
    sensor_temperature_c: Mapped[float | None] = mapped_column(Float)
    binning_x: Mapped[int | None] = mapped_column(Integer)
    binning_y: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())


class ProjectCaptureProfile(Base):
    __tablename__ = "project_capture_profile"
    __table_args__ = (UniqueConstraint("project_id", "capture_profile_id", name="uq_project_capture_profile"),)

    project_id: Mapped[str] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), primary_key=True)
    capture_profile_id: Mapped[str] = mapped_column(ForeignKey("capture_profile.id", ondelete="CASCADE"), primary_key=True)


class Asset(Base):
    __tablename__ = "asset"
    __table_args__ = (
        CheckConstraint("scope IN ('shared', 'project')", name="ck_asset_scope"),
        CheckConstraint("scope = 'shared' OR (scope = 'project' AND owner_project_id IS NOT NULL)", name="ck_asset_owner_scope"),
        CheckConstraint("role IN ('raw', 'calibration', 'intermediate', 'final')", name="ck_asset_role"),
        Index("ix_asset_scope_created", "scope", "created_at"),
        Index("ix_asset_owner_project", "owner_project_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    owner_project_id: Mapped[str | None] = mapped_column(ForeignKey("project.id"))
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(ForeignKey("asset_version.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())


class AssetVersion(Base):
    __tablename__ = "asset_version"
    __table_args__ = (UniqueConstraint("asset_id", "version_number", name="uq_asset_version_number"),
        CheckConstraint("version_number > 0", name="ck_asset_version_number"),
        CheckConstraint("storage_mode IN ('reference', 'managed')", name="ck_asset_version_storage_mode"),
        CheckConstraint("byte_size IS NULL OR byte_size >= 0", name="ck_asset_version_byte_size"),
        CheckConstraint("availability IN ('unknown', 'available', 'changed', 'missing')", name="ck_asset_version_availability"),
        CheckConstraint("frame_type IS NULL OR frame_type IN ('light', 'bias', 'dark', 'flat', 'dark_flat')", name="ck_asset_version_frame_type"),
        CheckConstraint("calibration_level IS NULL OR calibration_level IN ('individual', 'master')", name="ck_asset_version_calibration_level"),
        Index("ix_asset_version_asset_created", "asset_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("asset.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_location: Mapped[str] = mapped_column(String, nullable=False)
    byte_size: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String(71))
    availability: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    camera_id: Mapped[str | None] = mapped_column(ForeignKey("equipment.id"))
    optical_system_id: Mapped[str | None] = mapped_column(ForeignKey("equipment.id"))
    filter_id: Mapped[str | None] = mapped_column(ForeignKey("equipment.id"))
    capture_profile_id: Mapped[str | None] = mapped_column(ForeignKey("capture_profile.id"))
    frame_type: Mapped[str | None] = mapped_column(String(16))
    calibration_level: Mapped[str | None] = mapped_column(String(16))
    capture_snapshot: Mapped[dict | None] = mapped_column(JSON)
    scientific_metadata: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())


class ProjectAssetReference(Base):
    __tablename__ = "project_asset_reference"
    __table_args__ = (UniqueConstraint("project_id", "asset_version_id", name="uq_project_asset_version"),
        Index("ix_project_asset_reference_project", "project_id", "added_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    asset_version_id: Mapped[str] = mapped_column(ForeignKey("asset_version.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
