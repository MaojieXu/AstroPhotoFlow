"""A fresh workspace matches the current schema and rejects old databases."""
import sqlite3

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import (
    SchemaError,
    current_revision,
    ensure_schema_for_serve,
    initialize_database,
)
from astrophotoflow.modules.data.persistence import schema_metadata


def test_existing_old_schema_is_rejected_without_modification(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, ("http://127.0.0.1:8188",), workspace=tmp_path)
    with sqlite3.connect(settings.database_path) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES ('0001_baseline')")
    before = settings.database_path.read_bytes()
    with pytest.raises(SchemaError, match="reinitialize this workspace"):
        ensure_schema_for_serve(settings)
    with pytest.raises(SchemaError, match="reinitialize this workspace"):
        initialize_database(settings)
    assert settings.database_path.read_bytes() == before
    assert current_revision(settings.database_path) == "0001_baseline"


def test_fresh_migration_matches_owned_metadata(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, ("http://127.0.0.1:8188",), workspace=tmp_path)
    initialize_database(settings)
    database = Database(settings.database_path)
    try:
        with database.engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            assert compare_metadata(context, schema_metadata()) == []
    finally:
        database.close()
