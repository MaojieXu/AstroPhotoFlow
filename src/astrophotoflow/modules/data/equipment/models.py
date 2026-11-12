from __future__ import annotations
from datetime import datetime
from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from astrophotoflow.core.database.base import Base
from astrophotoflow.modules.data.names import SearchableName

class Equipment(SearchableName, Base):
    __tablename__ = 'equipment'
    __table_args__ = (CheckConstraint("kind IN ('camera', 'telescope', 'filter', 'mount')", name='ck_equipment_kind'), CheckConstraint("status IN ('active', 'archived')", name='ck_equipment_status'), CheckConstraint('revision >= 1', name='ck_equipment_revision'), Index('ix_equipment_kind_status', 'kind', 'status'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(String)
    specs: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='active')
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())

class EquipmentSetup(SearchableName, Base):
    __tablename__ = 'equipment_setup'
    __table_args__ = (CheckConstraint("status IN ('active', 'archived')", name='ck_equipment_setup_status'), CheckConstraint('revision >= 1', name='ck_equipment_setup_revision'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    members: Mapped[list[EquipmentSetupMember]] = relationship(cascade='all, delete-orphan', order_by='EquipmentSetupMember.position', lazy='selectin')
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='active')
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())

class EquipmentSetupMember(Base):
    __tablename__ = 'equipment_setup_member'
    __table_args__ = (UniqueConstraint('setup_id', 'id', name='uq_setup_member_identity'), UniqueConstraint('setup_id', 'position', name='uq_setup_member_position'), CheckConstraint('position >= 0', name='ck_setup_member_position'), CheckConstraint('(equipment_id IS NULL) != (inline_equipment IS NULL)', name='ck_setup_member_source'), Index('ix_setup_member_equipment', 'equipment_id'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    setup_id: Mapped[str] = mapped_column(ForeignKey('equipment_setup.id', ondelete='CASCADE'), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    equipment_id: Mapped[str | None] = mapped_column(ForeignKey('equipment.id'))
    inline_equipment: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    optical_accessory_id: Mapped[str | None] = mapped_column(String(36))
