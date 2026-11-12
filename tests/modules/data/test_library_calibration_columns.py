"""Existing library rows carry fixed calibration projections without per-row IO."""
from uuid import UUID, uuid4
import pytest
from sqlalchemy import event
from astrophotoflow.contracts.assets import LibraryQuery
from astrophotoflow.contracts.datasets import DatasetMemberQuery
from astrophotoflow.contracts.image_management import DatasetMemberSearch
from astrophotoflow.core.database.db import Database
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.bindings import set_dataset_bindings
from astrophotoflow.modules.data.datasets.image_queries import list_image_dataset_members
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember
from astrophotoflow.modules.data.datasets.queries import list_dataset_members
from astrophotoflow.modules.data.library.queries import get_library_change_state, search_library
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.persistence import schema_metadata

@pytest.fixture
def database(tmp_path):
    database = Database(tmp_path / 'columns.sqlite3')
    schema_metadata().create_all(database.engine)
    yield database
    database.close()

def image(session, name, frame_type='light', master=False):
    asset = Asset(id=str(uuid4()), name=name, scope='shared', role='raw', frame_class='masterframe' if master else 'subframe', frame_type=frame_type, exposure_seconds=60, storage_mode='managed', storage_location='unused.fits', byte_size=1, content_hash='blake3:' + 'a' * 64, availability='available', calibration_level='master' if master else 'individual', capture_snapshot={'classification': {'frame_class': 'masterframe' if master else 'subframe', 'frame_type': frame_type}, 'parameters': {'exposure_seconds': 60}})
    session.add(asset)
    session.flush()
    session.flush()
    return asset

def group(session, name, versions, defaults=None):
    dataset = Dataset(id=str(uuid4()), name=name)
    session.add(dataset)
    session.flush()
    session.flush()
    set_dataset_bindings(dataset, defaults or {})
    members = []
    for position, item in enumerate(versions):
        member = DatasetMember(id=str(uuid4()), dataset_id=dataset.id, asset_id=item.id, position=position)
        session.add(member)
        members.append(member)
    session.flush()
    return (dataset, members)

def target(version):
    return {'kind': 'asset', 'id': version.id}

def test_change_state_tracks_records_and_thumbnails_without_reading_large_json(database):
    with database.write_session() as session:
        asset = image(session, 'changing')
        asset_id, version_id = (asset.id, asset.id)
    statements = []

    def record(_connection, _cursor, statement, *_):
        statements.append(statement)
    event.listen(database.engine, 'before_cursor_execute', record)
    try:
        with database.read_session() as session:
            before = get_library_change_state(session)
            assert before == get_library_change_state(session)
        assert not any(('capture_snapshot' in statement or 'header_cards' in statement or 'asset_task.sources' in statement for statement in statements))
        with database.write_session() as session:
            asset = session.get(Asset, asset_id)
            asset.gain = 0
            asset.revision += 1
        with database.read_session() as session:
            changed = get_library_change_state(session)
            assert changed.revision_token != before.revision_token
            assert changed.thumbnail_token == before.thumbnail_token
        with database.write_session() as session:
            session.add(Preview(id=str(uuid4()), asset_id=version_id, hdu_index=0, size='thumbnail', algorithm_version='library-thumb-1', width=100, height=100, storage_path='unused.jpg', mime_type='image/jpeg', display_parameters={}, status='available'))
        with database.read_session() as session:
            ready = get_library_change_state(session)
            assert ready.revision_token == changed.revision_token
            assert ready.thumbnail_token != changed.thumbnail_token
    finally:
        event.remove(database.engine, 'before_cursor_execute', record)

def test_member_summaries_keep_fixed_identity_without_loading_capture_json(database):
    with database.write_session() as session:
        asset = image(session, 'first')
        asset.gain, asset.offset, asset.sensor_temperature_c = (0, 0, -16)
        asset.capture_snapshot = {**(asset.capture_snapshot or {}), 'large_frozen_payload': 'never-list-this' * 10000}
        asset.scientific_metadata = {'large_science_payload': 'never-list-this' * 10000}
        second = image(session, 'second')
        dataset, _ = group(session, 'summary', [asset, second])
        ids = (dataset.id, dataset.id, asset.id, asset.id)
    statements = []

    def record(_connection, _cursor, statement, *_):
        statements.append(statement)
    event.listen(database.engine, 'before_cursor_execute', record)
    try:
        with database.read_session() as session:
            page = list_dataset_members(session, UUID(ids[0]), DatasetMemberQuery(limit=1), summaries=True)
            row = page.items[0]
            assert page.total == 2 and row.member_position == 0
            assert str(row.id) == ids[3]
            assert row.summary.parameters.gain.value == row.summary.parameters.offset.value == 0
            assert row.summary.parameters.sensor_temperature_c.value == -16
            assert row.calibration_projection is None
            assert 'capture_snapshot' not in row.model_dump_json()
        assert not any(('asset.capture_snapshot' in statement or 'asset.scientific_metadata' in statement for statement in statements))
    finally:
        event.remove(database.engine, 'before_cursor_execute', record)

def test_standalone_columns_return_current_binding_and_flat_appropriate_slots(database):
    with database.write_session() as session:
        asset = image(session, 'Standalone flat', 'flat')
        dark_flat = image(session, 'Master dark-flat', 'dark_flat', True)
        asset.calibration = {'dark_flat': target(dark_flat)}
        session.flush()
        row = search_library(session, LibraryQuery(q='Standalone')).items[0]
        assert str(row.id) == asset.id
        projection = row.calibration_projection
        assert projection.slots['dark_flat'].target_detail.name == 'Master dark-flat'
        assert projection.slots['dark_flat'].source == 'standalone'
        assert projection.slots['bias'].status == 'unconfigured'
        assert projection.slots['flat'].status == 'not_applicable'

def test_group_projection_queries_are_bounded_as_members_grow(database):
    with database.write_session() as session:
        flat = image(session, 'Flat', 'flat', True)
        versions = [image(session, f'light-{index}') for index in range(100)]
        group(session, 'Large', versions, {'flat': target(flat)})
    statements = []

    def record(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)
    event.listen(database.engine, 'before_cursor_execute', record)
    try:
        with database.read_session() as session:
            row = search_library(session, LibraryQuery(q='Large')).items[0]
            assert row.member_count == 100
            assert row.calibration_projection.slots['flat'].status == 'target'
        assert len(statements) <= 8
        assert all(('member_calibration' not in statement for statement in statements))
    finally:
        event.remove(database.engine, 'before_cursor_execute', record)
