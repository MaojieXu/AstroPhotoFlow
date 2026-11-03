"""A real baseline upgrade preserves user records and legacy calibration intent."""
import sqlite3

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import (
    SCHEMA_REVISION,
    SchemaError,
    _alembic_config,
    current_revision,
    ensure_schema_for_serve,
    upgrade_database,
)
from astrophotoflow.modules.data.persistence import schema_metadata


def test_upgrade_preserves_baseline_and_backs_up(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, ("http://127.0.0.1:8188",), workspace=tmp_path)
    command.upgrade(_alembic_config(settings), "0001_baseline")
    with sqlite3.connect(settings.database_path) as connection:
        connection.execute("INSERT INTO equipment (id,kind,name,model,notes,specs,status,revision,name_search_key) VALUES (?,?,?,?,?,?,?,?,?)",
                           ("scope", "telescope", "user scope", None, "preserve me", "{}", "active", 7, "user scope"))
        connection.execute("INSERT INTO dataset (id,name,status,revision,name_search_key) VALUES ('group','M31','active',1,'m31')")
        connection.execute("INSERT INTO dataset_version (id,dataset_id,version_number) VALUES ('v1','group',1)")
        connection.execute("INSERT INTO dataset_calibration (dataset_version_id,frame_type,disabled) VALUES ('v1','flat',1)")
        before = connection.execute("SELECT * FROM equipment").fetchall()
    with pytest.raises(SchemaError, match="explicit database upgrade"):
        ensure_schema_for_serve(settings)
    upgrade_database(settings)
    assert current_revision(settings.database_path) == SCHEMA_REVISION
    backups = list((settings.database_path.parent / "backups").glob("before-image-management-*.sqlite3"))
    assert len(backups) == 1
    assert current_revision(backups[0]) == "0001_baseline"
    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT * FROM equipment").fetchall() == before
        assert connection.execute("SELECT disabled,state FROM dataset_calibration").fetchall() == [(1, None)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT COUNT(*) FROM image_metadata_state").fetchone()[0] == 0
    upgrade_database(settings)
    assert len(list((settings.database_path.parent / "backups").glob("*.sqlite3"))) == 1


def test_fresh_migration_matches_owned_metadata(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, ("http://127.0.0.1:8188",), workspace=tmp_path)
    upgrade_database(settings)
    database = Database(settings.database_path)
    try:
        with database.engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            assert compare_metadata(context, schema_metadata()) == []
    finally:
        database.close()
