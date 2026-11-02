from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from astrophotoflow.core.database.base import Base
from astrophotoflow.modules.data.names import SearchableName


class Equipment(SearchableName, Base):
    __tablename__ = "equipment"
    __table_args__ = (
        CheckConstraint("kind IN ('camera', 'telescope', 'filter')", name="ck_equipment_kind"),
        CheckConstraint("status IN ('active', 'archived')", name="ck_equipment_status"),
        CheckConstraint("revision >= 1", name="ck_equipment_revision"),
        Index("ix_equipment_kind_status", "kind", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(String)
    specs: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())



class EquipmentSetup(SearchableName, Base):
    __tablename__ = "equipment_setup"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_equipment_setup_status"),
        CheckConstraint("revision >= 1", name="ck_equipment_setup_revision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    members: Mapped[list[EquipmentSetupMember]] = relationship(cascade="all, delete-orphan", order_by="EquipmentSetupMember.position", lazy="selectin")
    presets: Mapped[list[CapturePreset]] = relationship(cascade="all, delete-orphan")
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())



class CapturePreset(SearchableName, Base):
    __tablename__ = "capture_preset"
    __table_args__ = (
        UniqueConstraint("id", "equipment_setup_id", name="uq_preset_setup"),
        CheckConstraint("status IN ('active', 'archived')", name="ck_capture_preset_status"),
        CheckConstraint("revision >= 1", name="ck_capture_preset_revision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    equipment_setup_id: Mapped[str] = mapped_column(ForeignKey("equipment_setup.id"), nullable=False)
    choices: Mapped[list[CapturePresetSelection]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    name: Mapped[str] = mapped_column(String, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())



class EquipmentSetupMember(Base):
    __tablename__ = "equipment_setup_member"
    __table_args__ = (
        UniqueConstraint("setup_id", "id", name="uq_setup_member_identity"),
        UniqueConstraint("setup_id", "position", name="uq_setup_member_position"),
        CheckConstraint("position >= 0", name="ck_setup_member_position"),
        CheckConstraint("(equipment_id IS NULL) != (inline_equipment IS NULL)", name="ck_setup_member_source"),
        Index("ix_setup_member_equipment", "equipment_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    setup_id: Mapped[str] = mapped_column(ForeignKey("equipment_setup.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    equipment_id: Mapped[str | None] = mapped_column(ForeignKey("equipment.id"))
    inline_equipment: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    optical_accessory_id: Mapped[str | None] = mapped_column(String(36))


class CapturePresetSelection(Base):
    __tablename__ = "capture_preset_selection"
    __table_args__ = (
        ForeignKeyConstraint(["preset_id", "setup_id"], ["capture_preset.id", "capture_preset.equipment_setup_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["setup_id", "member_id"], ["equipment_setup_member.setup_id", "equipment_setup_member.id"], ondelete="CASCADE"),
        CheckConstraint("kind = 'filter'", name="ck_preset_selection_kind"),
        Index("ix_preset_selection_member", "member_id"),
    )

    preset_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), primary_key=True)
    setup_id: Mapped[str] = mapped_column(String(36), nullable=False)
    member_id: Mapped[str | None] = mapped_column(String(36))
    # Track this dependency without also writing setup_id (owned by choices).
    # Choices must be deleted before a member's ON DELETE CASCADE can remove them.
    member: Mapped[EquipmentSetupMember | None] = relationship(foreign_keys=[member_id])
