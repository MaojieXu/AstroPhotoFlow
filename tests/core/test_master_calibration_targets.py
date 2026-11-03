"""Master-only migration removes target groups, not provenance source groups."""
import sqlite3
from contextlib import closing

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from astrophotoflow.contracts.image_management import MasterProvenanceChanges
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.schema import _alembic_config, upgrade_database
from astrophotoflow.modules.data.persistence import schema_metadata


def test_master_only_schema_matches_models_and_keeps_dataset_sources(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    upgrade_database(settings)
    with closing(sqlite3.connect(settings.database_path)) as connection:
        for table in ("dataset_calibration", "member_calibration"):
            assert "target_dataset_version_id" not in {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            assert any(row[2] == "asset_version" and row[3] == "asset_version_id"
                       for row in connection.execute(f"PRAGMA foreign_key_list({table})"))
        assert "dataset_version_id" in {row[1] for row in connection.execute("PRAGMA table_info(master_provenance_reference)")}
    engine = create_engine(f"sqlite:///{settings.database_path.as_posix()}")
    try:
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), schema_metadata()) == []
    finally:
        engine.dispose()
    # Only the binding target is narrowed; a fixed raw group remains a source.
    parsed = MasterProvenanceChanges.model_validate_json('{"sources":[{"kind":"dataset_version","dataset_id":"00000000-0000-4000-8000-000000000001","dataset_version_id":"00000000-0000-4000-8000-000000000002"}]}')
    assert parsed.sources[0].kind == "dataset_version"


def test_upgrade_rejects_existing_raw_targets_without_silently_discarding_them(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    settings.data_dir.mkdir()
    command.upgrade(_alembic_config(settings), "0004_remove_capture_presets")
    with closing(sqlite3.connect(settings.database_path)) as connection:
        connection.execute("INSERT INTO dataset_calibration (dataset_version_id,frame_type,disabled,target_dataset_version_id) VALUES ('owner','dark',0,'raw-target')")
        connection.commit()
    with pytest.raises(RuntimeError, match="raw calibration-group"):
        command.upgrade(_alembic_config(settings), "head")
    with closing(sqlite3.connect(settings.database_path)) as connection:
        assert connection.execute("SELECT target_dataset_version_id FROM dataset_calibration").fetchall() == [("raw-target",)]
