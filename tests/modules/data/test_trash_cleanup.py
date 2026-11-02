from pathlib import Path

import pytest

from astrophotoflow.modules.data.trash.cleanup import finalize_cleanup
from astrophotoflow.modules.data.trash.files import delete_owned_files
from astrophotoflow.modules.data.trash.types import CleanupPlan


def test_partial_file_failure_keeps_facts_and_blocks_database_finalization(tmp_path, monkeypatch):
    first, locked, last = [tmp_path / name for name in ("first", "locked", "last")]
    for path in (first, locked, last):
        path.write_bytes(b"science")
    original_unlink = Path.unlink
    failure = PermissionError("file is locked")

    def unlink(path, *args, **kwargs):
        if path == locked:
            raise failure
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)
    plan = CleanupPlan("asset", frozenset({"version"}), (first, locked, last), frozenset(), frozenset())
    result = delete_owned_files(plan)
    assert result.removed_paths == [str(first)]
    assert result.deleted_bytes == 7
    assert result.error is failure
    assert locked.is_file() and last.is_file()
    with pytest.raises(PermissionError) as caught:
        finalize_cleanup(None, result)
    assert caught.value is failure


def test_finite_cleanup_skips_journaled_paths_and_counts_missing_files(tmp_path):
    preserved, missing, removed = [tmp_path / name for name in ("preserved", "missing", "removed")]
    preserved.write_bytes(b"already journaled")
    removed.write_bytes(b"owned")
    plan = CleanupPlan("asset", frozenset(), (preserved, missing, removed), frozenset({str(preserved)}), frozenset())
    result = delete_owned_files(plan)
    assert result.error is None
    assert result.removed_paths == [str(removed)]
    assert result.deleted_bytes == 5 and result.missing_file_count == 1
    assert preserved.read_bytes() == b"already journaled"
