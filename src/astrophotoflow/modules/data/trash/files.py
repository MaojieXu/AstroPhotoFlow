"""One filesystem effect; database intent and progress belong to cleanup."""
import logging
from dataclasses import dataclass
from pathlib import Path
from astrophotoflow.modules.data.trash.types import CleanupPlan, FileCleanupResult

@dataclass(frozen=True)
class FileDeletionResult:
    removed: bool
    byte_size: int

def delete_owned_file(path: Path) -> FileDeletionResult:
    if not path.is_file():
        return FileDeletionResult(removed=False, byte_size=0)
    size = path.stat().st_size
    path.unlink()
    return FileDeletionResult(removed=True, byte_size=size)

def delete_owned_files(plan: CleanupPlan) -> FileCleanupResult:
    """Return partial facts even when deletion fails; never write the database."""
    result = FileCleanupResult(plan)
    try:
        for path in plan.paths:
            if str(path) in plan.cleaned_paths:
                continue
            deletion = delete_owned_file(path)
            if deletion.removed:
                result.removed_paths.append(str(path))
                result.deleted_bytes += deletion.byte_size
            else:
                result.missing_file_count += 1
    except Exception as exc:
        logging.getLogger(__name__).exception('Owned file cleanup interrupted', extra={'asset_id': plan.asset_id})
        result.error = exc
    return result
