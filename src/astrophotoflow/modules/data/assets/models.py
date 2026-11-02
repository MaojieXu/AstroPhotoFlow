from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from astrophotoflow.core.database.base import Base
from astrophotoflow.modules.data.names import SearchableName


class Asset(SearchableName, Base):
    __tablename__ = "asset"
    __table_args__ = (
        CheckConstraint("scope IN ('shared', 'project')", name="ck_asset_scope"),
        CheckConstraint("scope = 'shared' OR (scope = 'project' AND owner_project_id IS NOT NULL)", name="ck_asset_owner_scope"),
        CheckConstraint("role IN ('raw', 'calibration', 'intermediate', 'final')", name="ck_asset_role"),
        CheckConstraint("frame_class IS NULL OR frame_class IN ('subframe', 'masterframe', 'video')", name="ck_asset_frame_class"),
        CheckConstraint("frame_type IS NULL OR frame_type IN ('light', 'bias', 'dark', 'flat', 'dark_flat')", name="ck_asset_frame_type"),
        CheckConstraint("frame_class IS NULL OR frame_class != 'video' OR frame_type IS NULL", name="ck_asset_video_frame_type"),
        CheckConstraint("parameter_mode IS NULL OR parameter_mode IN ('standard', 'iso', 'gain')", name="ck_asset_parameter_mode"),
        CheckConstraint("iso IS NULL OR iso > 0", name="ck_asset_iso"),
        CheckConstraint("exposure_seconds IS NULL OR exposure_seconds >= 0", name="ck_asset_exposure"),
        CheckConstraint("integration_seconds IS NULL OR integration_seconds >= 0", name="ck_asset_integration"),
        CheckConstraint("binning_x IS NULL OR binning_x > 0", name="ck_asset_binning_x"),
        CheckConstraint("binning_y IS NULL OR binning_y > 0", name="ck_asset_binning_y"),
        Index("ix_asset_scope_created", "scope", "created_at"),
        Index("ix_asset_status_created", "status", "created_at"),
        Index("ix_asset_owner_project", "owner_project_id"),
        Index("ix_asset_camera_id_visible", "camera_id", "scope", "status", "created_at", "id"),
        Index("ix_asset_optical_system_id_visible", "optical_system_id", "scope", "status", "created_at", "id"),
        Index("ix_asset_filter_id_visible", "filter_id", "scope", "status", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    owner_project_id: Mapped[str | None] = mapped_column(ForeignKey("project.id"))
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(ForeignKey("asset_version.id", use_alter=True, name="fk_asset_current_version"))
    frame_class: Mapped[str | None] = mapped_column(String(16))
    frame_type: Mapped[str | None] = mapped_column(String(16))
    camera_id: Mapped[str | None] = mapped_column(String(36))
    optical_system_id: Mapped[str | None] = mapped_column(String(36))
    filter_id: Mapped[str | None] = mapped_column(String(36))
    parameter_mode: Mapped[str | None] = mapped_column(String(16).evaluates_none(), default="standard", server_default="standard")
    iso: Mapped[int | None] = mapped_column(Integer)
    gain: Mapped[float | None] = mapped_column(Float)
    offset: Mapped[float | None] = mapped_column(Float)
    exposure_seconds: Mapped[float | None] = mapped_column(Float)
    integration_seconds: Mapped[float | None] = mapped_column(Float)
    sensor_temperature_c: Mapped[float | None] = mapped_column(Float)
    binning_x: Mapped[int | None] = mapped_column(Integer)
    binning_y: Mapped[int | None] = mapped_column(Integer)
    cfa_pattern: Mapped[str | None] = mapped_column(String(16))
    equipment_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default=text("'{}'"))
    value_sources: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default=text("'{}'"))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
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
    frame_type: Mapped[str | None] = mapped_column(String(16))
    calibration_level: Mapped[str | None] = mapped_column(String(16))
    capture_snapshot: Mapped[dict | None] = mapped_column(JSON)
    scientific_metadata: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())

class FitsHduMetadata(Base):
    __tablename__ = "fits_hdu_metadata"
    __table_args__ = (
        UniqueConstraint("asset_version_id", "hdu_index", name="uq_fits_hdu_version_index"),
        Index("ix_fits_hdu_version", "asset_version_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    asset_version_id: Mapped[str] = mapped_column(ForeignKey("asset_version.id", ondelete="CASCADE"), nullable=False)
    hdu_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(String)
    hdu_type: Mapped[str] = mapped_column(String(32), nullable=False)
    shape: Mapped[list | None] = mapped_column(JSON)
    bitpix: Mapped[int | None] = mapped_column(Integer)
    pixel_type: Mapped[str | None] = mapped_column(String(64))
    bscale: Mapped[float | None] = mapped_column(Float)
    bzero: Mapped[float | None] = mapped_column(Float)
    bunit: Mapped[str | None] = mapped_column(String(128))
    header_cards: Mapped[list] = mapped_column(JSON, nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    supported_kind: Mapped[str | None] = mapped_column(String(16))
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parse_error: Mapped[str | None] = mapped_column(Text)
