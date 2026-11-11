"""Frozen-at-intake values shared by the real import processing stages."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from pydantic import JsonValue
if TYPE_CHECKING:
    from .progress import ImportProgress

@dataclass(slots=True)
class ImportTaskContext:
    id: str
    sources: list[dict[str, JsonValue]]
    storage_mode: str
    classification: dict[str, JsonValue]
    parameters: dict[str, JsonValue]
    import_defaults_snapshot: dict[str, JsonValue] | None
    notes: str | None
    dataset_name: str | None
    target_dataset_id: str | None
    dataset_base_revision: int | None
    retry_of_task_id: str | None
    upload_manifest: bool
    upload_files: list[dict[str, JsonValue]]
    upload_source_task_id: str
    output_registration: bool
    output_name: str | None
    output_colour_layout: str | None
    output_provenance: dict[str, JsonValue] | None
    calibration_status: str = 'Unknown'
    calibration_reason: str | None = None
    calibration_evidence: dict | None = None
    processing_calibration: dict | None = None
    output_value_sources: dict = field(default_factory=dict)
    image_import_plan: dict | None = None
    progress: ImportProgress | None = None
    metadata_snapshots: dict = field(default_factory=dict)
    source_stamps: dict[tuple[str, str], dict[str, JsonValue]] = field(default_factory=dict)

    @classmethod
    def from_task(cls, task) -> ImportTaskContext:
        return cls(processing_calibration=deepcopy((task.report or {}).get('output_processing_calibration')), output_value_sources=deepcopy((task.report or {}).get('output_value_sources') or {}), calibration_evidence=deepcopy((task.report or {}).get('output_calibration_evidence')), calibration_status=(task.report or {}).get('calibration_status', 'Unknown'), calibration_reason=(task.report or {}).get('calibration_reason'), id=task.id, sources=list(task.sources), storage_mode=task.storage_mode, classification=dict(task.classification), parameters=dict(task.parameters), import_defaults_snapshot=deepcopy(task.import_defaults_snapshot), notes=task.notes, dataset_name=task.dataset_name, target_dataset_id=task.target_dataset_id, dataset_base_revision=task.dataset_base_revision, retry_of_task_id=task.retry_of_task_id, upload_manifest=bool((task.report or {}).get('upload_manifest')), upload_files=(task.report or {}).get('upload_files', []), upload_source_task_id=(task.report or {}).get('upload_source_task_id', task.id), output_registration=bool((task.report or {}).get('output_registration')), output_name=(task.report or {}).get('output_name'), output_colour_layout=(task.report or {}).get('output_colour_layout'), output_provenance=(task.report or {}).get('output_provenance'), image_import_plan=deepcopy(task.image_import_plan))
