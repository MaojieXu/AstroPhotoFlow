"""Finite per-asset cleanup scope and filesystem facts; no ORM objects."""
from dataclasses import dataclass, field
from pathlib import Path

@dataclass(frozen=True)
class CleanupPlan:
    asset_id: str
    paths: tuple[Path, ...]
    cleaned_paths: frozenset[str]
    selected_group_ids: frozenset[str]

@dataclass
class FileCleanupResult:
    plan: CleanupPlan
    removed_paths: list[str] = field(default_factory=list)
    deleted_bytes: int = 0
    missing_file_count: int = 0
    error: Exception | None = None
