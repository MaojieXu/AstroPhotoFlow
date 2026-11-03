"""Typed facts frozen at import acceptance, independent of live registry rows."""

from typing import Annotated, Literal

from pydantic import Field

from astrophotoflow.contracts.common import JsonObject, SnapshotModel, UuidInput
from astrophotoflow.contracts.equipment import EquipmentSnapshot, EquipmentSnapshots
from astrophotoflow.contracts.metadata import AssetClassification, AssetParametersPatch


class FrozenEquipmentSelection(SnapshotModel):
    camera: UuidInput | None = None
    optical_system: UuidInput | None = None
    filter: UuidInput | None = None
    mount: UuidInput | None = None


class FrozenRegisteredMember(SnapshotModel):
    id: UuidInput
    source: Literal["registered"]
    equipment_id: UuidInput
    equipment: EquipmentSnapshot
    optical_accessory_id: UuidInput | None = None
    effective_focal_length_mm: float | None = None


class FrozenInlineMember(SnapshotModel):
    id: UuidInput
    source: Literal["inline"]
    equipment: EquipmentSnapshot
    optical_accessory_id: UuidInput | None = None
    effective_focal_length_mm: float | None = None


FrozenSetupMember = Annotated[FrozenRegisteredMember | FrozenInlineMember, Field(discriminator="source")]


class FrozenEquipmentSetup(SnapshotModel):
    id: UuidInput
    revision: int = Field(ge=1)
    name: str
    notes: str | None
    components: list[FrozenSetupMember]


class ImportDefaultsSnapshot(SnapshotModel):
    parameters: AssetParametersPatch = Field(default_factory=AssetParametersPatch)
    classification: AssetClassification = Field(default_factory=AssetClassification)
    selected_equipment: EquipmentSnapshots = Field(default_factory=EquipmentSnapshots)
    selected_members: FrozenEquipmentSelection = Field(default_factory=FrozenEquipmentSelection)
    equipment_setup: FrozenEquipmentSetup | None = None
    equipment_snapshots: dict[str, EquipmentSnapshot] = Field(default_factory=dict)


class ImportProvenance(SnapshotModel):
    value_sources: dict[str, Literal["manual", "file", "unknown"]] = Field(default_factory=dict)
    observed_parameters: JsonObject = Field(default_factory=dict)
    defaults_snapshot: ImportDefaultsSnapshot = Field(default_factory=ImportDefaultsSnapshot)


class VersionCaptureSnapshot(SnapshotModel):
    image_metadata: JsonObject | None = None
    parameters: AssetParametersPatch = Field(default_factory=AssetParametersPatch)
    classification: AssetClassification = Field(default_factory=AssetClassification)
    equipment_snapshot: EquipmentSnapshots = Field(default_factory=EquipmentSnapshots)
    import_provenance: ImportProvenance | None = None
