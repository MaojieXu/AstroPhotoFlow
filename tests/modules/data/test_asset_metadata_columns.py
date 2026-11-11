"""Current editable metadata has one physical source and preserves null/zero."""
from contextlib import closing
from uuid import uuid4
import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import initialize_database
from astrophotoflow.modules.data.assets.metadata import asset_parameters, parameter_columns, set_asset_parameters
from astrophotoflow.modules.data.assets.models import Asset

@pytest.fixture
def database(tmp_path):
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    initialize_database(settings)
    with closing(Database(settings.database_path)) as database:
        yield database

def test_fresh_database_has_scalar_metadata_without_json_or_compatibility_properties(database):
    columns = {column['name'] for column in inspect(database.engine).get_columns('asset')}
    assert {'gain', 'offset', 'frame_type', 'frame_class', 'camera_id', 'exposure_seconds', 'cfa_pattern'} <= columns
    assert 'parameters' not in columns and 'classification' not in columns
    assert not hasattr(Asset, 'parameters') and (not hasattr(Asset, 'classification'))

def test_scalar_metadata_distinguishes_default_mode_null_and_zero(database):
    explicit_id, default_id = (str(uuid4()), str(uuid4()))
    with database.write_session() as session:
        session.add(Asset(id=explicit_id, name='explicit', scope='shared', role='raw', **parameter_columns({'parameter_mode': None, 'gain': 0, 'offset': None}), storage_mode='managed', storage_location='unused.fits'))
        session.add(Asset(id=default_id, name='default', scope='shared', role='raw', storage_mode='managed', storage_location='unused.fits'))
    with database.write_session() as session:
        row = session.get(Asset, explicit_id)
        assert asset_parameters(row)['parameter_mode'] is None
        assert row.gain == 0 and row.offset is None
        assert session.get(Asset, default_id).parameter_mode == 'standard'
        set_asset_parameters(row, {'gain': None, 'offset': 0})
    with database.read_session() as session:
        row = session.get(Asset, explicit_id)
        assert row.gain is None and row.offset == 0

def test_database_rejects_a_video_frame_with_scientific_frame_purpose(database):
    with pytest.raises(IntegrityError), database.write_session() as session:
        session.add(Asset(id=str(uuid4()), name='invalid', scope='shared', role='raw', frame_class='video', frame_type='light', storage_mode='managed', storage_location='unused.fits'))
        session.flush()

def test_fresh_baseline_supports_device_filters_and_member_reverse_lookup(database):
    from sqlalchemy import inspect
    inspector = inspect(database.engine)
    asset_indexes = {tuple(index['column_names']) for index in inspector.get_indexes('asset')}
    for field in ('camera_id', 'optical_system_id', 'filter_id'):
        assert (field, 'scope', 'status', 'created_at', 'id') in asset_indexes
    member_indexes = {tuple(index['column_names']) for index in inspector.get_indexes('dataset_member')}
    assert ('asset_id',) in member_indexes
    with database.engine.connect() as connection:
        plan = connection.exec_driver_sql('EXPLAIN QUERY PLAN SELECT id FROM dataset_member WHERE asset_id=?', ('missing-version',)).all()
    assert any(('SEARCH' in row[3] and 'ix_dataset_member_asset' in row[3] for row in plan))
