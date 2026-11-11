"""The baseline keeps current Master targets and their dataset provenance."""
import sqlite3
from contextlib import closing
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
from astrophotoflow.contracts.image_management import MasterProvenanceChanges
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.schema import initialize_database
from astrophotoflow.modules.data.persistence import schema_metadata

def test_master_only_schema_matches_models_and_keeps_dataset_sources(tmp_path):
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    initialize_database(settings)
    with closing(sqlite3.connect(settings.database_path)) as connection:
        assert connection.execute('PRAGMA table_info(member_calibration)').fetchall() == []
        assert any((row[2] == 'asset' and row[3] == 'asset_id' for row in connection.execute('PRAGMA foreign_key_list(dataset_calibration)')))
        assert 'dataset_id' in {row[1] for row in connection.execute('PRAGMA table_info(master_provenance_reference)')}
    engine = create_engine(f'sqlite:///{settings.database_path.as_posix()}')
    try:
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), schema_metadata()) == []
    finally:
        engine.dispose()
    parsed = MasterProvenanceChanges.model_validate_json('{"sources":[{"kind":"dataset","dataset_id":"00000000-0000-4000-8000-000000000001"}]}')
    assert parsed.sources[0].kind == 'dataset'
