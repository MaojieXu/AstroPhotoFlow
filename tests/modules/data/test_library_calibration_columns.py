"""Existing library rows carry fixed calibration projections without per-row IO."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import event

from astrophotoflow.contracts.assets import LibraryQuery
from astrophotoflow.contracts.datasets import DatasetMemberQuery
from astrophotoflow.contracts.image_management import DatasetMemberSearch
from astrophotoflow.core.database.db import Database
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.calibration.models import ImageCalibrationConfiguration
from astrophotoflow.modules.data.datasets.bindings import set_default_bindings, set_member_bindings
from astrophotoflow.modules.data.datasets.image_queries import list_image_dataset_members
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion
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
    asset = Asset(id=str(uuid4()), name=name, scope='shared', role='raw',
        frame_class='masterframe' if master else 'subframe', frame_type=frame_type, exposure_seconds=60)
    session.add(asset)
    session.flush()
    version = AssetVersion(id=str(uuid4()), asset_id=asset.id, version_number=1, storage_mode='managed',
        storage_location='unused.fits', byte_size=1, content_hash='blake3:' + 'a' * 64, availability='available',
        frame_type=frame_type, calibration_level='master' if master else 'individual',
        capture_snapshot={'classification': {'frame_class': asset.frame_class, 'frame_type': frame_type},
            'parameters': {'exposure_seconds': 60}})
    session.add(version)
    session.flush()
    asset.current_version_id = version.id
    return asset, version


def group(session, name, versions, defaults=None, overrides=None):
    dataset = Dataset(id=str(uuid4()), name=name)
    session.add(dataset)
    session.flush()
    version = DatasetVersion(id=str(uuid4()), dataset_id=dataset.id, version_number=1)
    session.add(version)
    session.flush()
    dataset.current_version_id = version.id
    set_default_bindings(version, defaults or {})
    members = []
    for position, item in enumerate(versions):
        member = DatasetMember(id=str(uuid4()), dataset_version_id=version.id,
            asset_version_id=item.id, position=position)
        set_member_bindings(member, (overrides or {}).get(position, {}))
        session.add(member)
        members.append(member)
    session.flush()
    return dataset, version, members


def target(version):
    return {'kind': 'asset_version', 'id': version.id}


def test_change_state_tracks_records_and_thumbnails_without_reading_large_json(database):
    with database.write_session() as session:
        asset, version = image(session, 'changing')
        asset_id, version_id = asset.id, version.id
    statements = []
    def record(_connection, _cursor, statement, *_):
        statements.append(statement)
    event.listen(database.engine, 'before_cursor_execute', record)
    try:
        with database.read_session() as session:
            before = get_library_change_state(session)
            assert before == get_library_change_state(session)
        assert not any('capture_snapshot' in statement or 'header_cards' in statement or 'asset_task.sources' in statement for statement in statements)
        with database.write_session() as session:
            asset = session.get(Asset, asset_id)
            asset.gain = 0
            asset.revision += 1
        with database.read_session() as session:
            changed = get_library_change_state(session)
            assert changed.revision_token != before.revision_token
            assert changed.thumbnail_token == before.thumbnail_token
        with database.write_session() as session:
            session.add(Preview(id=str(uuid4()), asset_version_id=version_id, hdu_index=0, size='thumbnail',
                algorithm_version='library-thumb-1', width=100, height=100, storage_path='unused.jpg',
                mime_type='image/jpeg', display_parameters={}, status='available'))
        with database.read_session() as session:
            ready = get_library_change_state(session)
            assert ready.revision_token == changed.revision_token
            assert ready.thumbnail_token != changed.thumbnail_token
    finally:
        event.remove(database.engine, 'before_cursor_execute', record)


def test_member_summaries_keep_fixed_identity_without_loading_capture_json(database):
    with database.write_session() as session:
        asset, first = image(session, 'first')
        asset.gain, asset.offset, asset.sensor_temperature_c = 0, 0, -16
        first.capture_snapshot = {'large_frozen_payload': 'never-list-this' * 10000}
        first.scientific_metadata = {'large_science_payload': 'never-list-this' * 10000}
        _, second = image(session, 'second')
        dataset, version, _ = group(session, 'summary', [first, second])
        ids = dataset.id, version.id, first.id, asset.id
    statements = []
    def record(_connection, _cursor, statement, *_):
        statements.append(statement)
    event.listen(database.engine, 'before_cursor_execute', record)
    try:
        with database.read_session() as session:
            page = list_dataset_members(session, UUID(ids[0]), UUID(ids[1]), DatasetMemberQuery(limit=1), summaries=True)
            row = page.items[0]
            assert page.total == 2 and row.member_position == 0
            assert str(row.version_id) == ids[2] and str(row.id) == ids[3]
            assert row.summary.parameters.gain.value == row.summary.parameters.offset.value == 0
            assert row.summary.parameters.sensor_temperature_c.value == -16
            assert row.calibration_projection.slots['dark'].status == 'unconfigured'
            assert 'capture_snapshot' not in row.model_dump_json()
        assert not any('asset_version.capture_snapshot' in statement or 'asset_version.scientific_metadata' in statement for statement in statements)
    finally:
        event.remove(database.engine, 'before_cursor_execute', record)


def test_root_and_member_columns_resolve_group_context_without_science(database, monkeypatch):
    with database.write_session() as session:
        _, first = image(session, 'night-one')
        _, second = image(session, 'night-two')
        _, flat_a = image(session, 'Master Flat A', 'flat', True)
        _, flat_b = image(session, 'Master Flat B', 'flat', True)
        dataset, version, _ = group(session, 'Two nights', [first, second], {'flat': target(flat_a)},
            {1: {'flat': target(flat_b), 'bias': None}})
        group(session, 'Different context', [first], {'flat': target(flat_b)})
        configuration = ImageCalibrationConfiguration(id=str(uuid4()), asset_version_id=first.id,
            version_number=1, bindings={'flat': target(flat_b)})
        session.add(configuration)
        session.flush()
        monkeypatch.setattr('astrophotoflow.modules.data.calibration.checks.inspect_calibration_bindings',
            lambda *args, **kwargs: pytest.fail('Library browsing must not check science'))
        root = search_library(session, LibraryQuery(q='Two nights'))
        slots = root.items[0].calibration_projection.slots
        assert slots['flat'].status == 'mixed'
        assert slots['flat'].choice is None
        assert slots['dark'].status == 'unconfigured'
        assert slots['dark_flat'].status == 'not_applicable'
        page = list_dataset_members(session, UUID(dataset.id), UUID(version.id), DatasetMemberQuery(limit=1))
        flat = page.items[0].calibration_projection.slots['flat']
        assert flat.target_detail.name == 'Master Flat A'
        assert str(flat.target_detail.target.id) == flat_a.id
        assert flat.source == 'dataset_default'
        next_page = list_image_dataset_members(session, dataset.id, version.id, DatasetMemberSearch(limit=1, offset=1))
        flat = next_page['items'][0]['member']['calibration_projection']['slots']['flat']
        assert flat['source'] == 'member_override'
        assert flat['target_detail']['target']['id'] == flat_b.id
        assert next_page['items'][0]['member']['calibration_projection']['slots']['bias']['status'] == 'disabled'


def test_standalone_columns_return_binding_revision_and_flat_appropriate_slots(database):
    with database.write_session() as session:
        asset, flat = image(session, 'Standalone flat', 'flat')
        _, dark_flat = image(session, 'Master dark-flat', 'dark_flat', True)
        config = ImageCalibrationConfiguration(id=str(uuid4()), asset_version_id=flat.id,
            version_number=1, bindings={'dark_flat': target(dark_flat)})
        session.add(config)
        session.flush()
        row = search_library(session, LibraryQuery(q='Standalone')).items[0]
        assert str(row.id) == asset.id
        projection = row.calibration_projection
        assert str(projection.binding_version_id) == config.id
        assert projection.slots['dark_flat'].target_detail.name == 'Master dark-flat'
        assert projection.slots['dark_flat'].source == 'standalone'
        assert projection.slots['bias'].status == 'unconfigured'
        assert projection.slots['flat'].status == 'not_applicable'


def test_uniform_target_with_different_sources_does_not_become_mixed(database):
    with database.write_session() as session:
        _, one = image(session, 'one')
        _, two = image(session, 'two')
        _, flat = image(session, 'Flat', 'flat', True)
        group(session, 'Uniform', [one, two], {'flat': target(flat)}, {1: {'flat': target(flat)}})
        row = search_library(session, LibraryQuery(q='Uniform')).items[0]
        assert row.calibration_projection.slots['flat'].status == 'target'
        assert row.calibration_projection.slots['flat'].source == 'mixed'


def test_group_projection_queries_are_bounded_as_members_grow(database):
    with database.write_session() as session:
        _, flat = image(session, 'Flat', 'flat', True)
        versions = [image(session, f'light-{index}')[1] for index in range(100)]
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
        # Main page and exposure queries plus grouped relationships/target lookup;
        # no standalone configuration or per-member query is issued for the group.
        assert len(statements) <= 8
        assert any('GROUP BY' in statement and 'member_calibration' in statement for statement in statements)
    finally:
        event.remove(database.engine, 'before_cursor_execute', record)
