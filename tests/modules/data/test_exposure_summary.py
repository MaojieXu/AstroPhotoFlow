"""Whole-group exposure is derived from subframes, never per-page metadata."""

from uuid import UUID, uuid4

import pytest

from astrophotoflow.contracts.assets import LibraryQuery
from astrophotoflow.contracts.datasets import DatasetCreate
from astrophotoflow.contracts.image_management import DatasetSearch
from astrophotoflow.core.database.db import Database
from astrophotoflow.modules.data.assets.exposure import summarize_dataset_exposures
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.datasets.image_queries import get_image_dataset, search_image_datasets
from astrophotoflow.modules.data.datasets.models import Dataset
from astrophotoflow.modules.data.datasets.queries import get_dataset, list_dataset_versions
from astrophotoflow.modules.data.datasets.service import create_dataset, publish_dataset_members
from astrophotoflow.modules.data.library.queries import search_library
from astrophotoflow.modules.data.persistence import schema_metadata


@pytest.fixture
def database(tmp_path):
    database = Database(tmp_path / 'exposure.sqlite3')
    schema_metadata().create_all(database.engine)
    yield database
    database.close()


def add_frame(session, exposure, *, frame_class='subframe', integration=99999):
    asset_id, version_id = str(uuid4()), str(uuid4())
    asset = Asset(id=asset_id, name='Authored exposure frame', scope='shared', role='raw',
        frame_class=frame_class, frame_type='light', exposure_seconds=exposure, integration_seconds=integration)
    session.add(asset)
    session.flush()
    version = AssetVersion(id=version_id, asset_id=asset_id, version_number=1, storage_mode='managed',
        storage_location='unused.fits', content_hash='blake3:' + 'a' * 64, byte_size=1, availability='available',
        frame_type='light', calibration_level='master' if frame_class == 'masterframe' else 'individual',
        capture_snapshot={'classification': {'frame_class': frame_class, 'frame_type': 'light'},
                          'parameters': {'exposure_seconds': exposure, 'integration_seconds': integration}})
    session.add(version)
    session.flush()
    asset.current_version_id = version_id
    return asset, version


def create_group(session, values, *, name='Exposure group'):
    frames = [add_frame(session, value) for value in values]
    dataset = create_dataset(session, DatasetCreate(name=name, asset_version_ids=[UUID(version.id) for _, version in frames]))
    return session.get(Dataset, str(dataset.id)), frames


def test_total_uses_all_members_despite_filters_and_ignores_master_integration(database):
    with database.write_session() as session:
        dataset, frames = create_group(session, [300, 180, None, 0])
        _, master = add_frame(session, 10000, frame_class='masterframe')
        publish_dataset_members(session, dataset, [version.id for _, version in frames] + [master.id])
        dataset_id, version_id = dataset.id, dataset.current_version_id
    with database.read_session() as session:
        rows = search_library(session, LibraryQuery(limit=1, exposure_min=200))
        assert rows.total == 1
        group = rows.items[0]
        assert group.member_count == 5 and group.matching_member_count == 2
        assert group.exposure_summary.model_dump() == {'subframe_count': 4, 'known_count': 3,
            'unknown_count': 1, 'total_seconds': 480.0, 'complete': False}
        assert get_dataset(session, UUID(dataset_id)).exposure_summary == group.exposure_summary
        assert summarize_dataset_exposures(session, [version_id], frozen=True)[version_id] == group.exposure_summary
        modern = search_image_datasets(session, DatasetSearch(exposure_min=200, limit=1))
        assert modern['items'][0]['dataset']['exposure_summary'] == group.exposure_summary.model_dump()


def test_correction_updates_current_total_without_changing_fixed_capture_total(database):
    with database.write_session() as session:
        dataset, frames = create_group(session, [300, 180])
        dataset_id, version_id, asset_id = dataset.id, dataset.current_version_id, frames[0][0].id
    with database.write_session() as session:
        session.get(Asset, asset_id).exposure_seconds = 600
    with database.read_session() as session:
        detail = get_image_dataset(session, dataset_id, version_id)
        assert detail['dataset']['exposure_summary']['total_seconds'] == 780
        assert detail['version']['exposure_summary']['total_seconds'] == 480
        assert search_library(session, LibraryQuery()).items[0].exposure_summary.total_seconds == 780
        assert list_dataset_versions(session, UUID(dataset_id)).items[0].exposure_summary.total_seconds == 480


def test_append_remove_and_historical_totals_follow_fixed_member_lists(database):
    with database.write_session() as session:
        dataset, frames = create_group(session, [300, 180])
        dataset_id, old_version = dataset.id, dataset.current_version_id
        _, incoming = add_frame(session, 60)
        publish_dataset_members(session, dataset, [version.id for _, version in frames] + [incoming.id])
        appended_version = dataset.current_version_id
        assert get_dataset(session, UUID(dataset_id)).exposure_summary.total_seconds == 540
        publish_dataset_members(session, dataset, [frames[1][1].id, incoming.id])
        assert get_dataset(session, UUID(dataset_id)).exposure_summary.total_seconds == 240
    with database.read_session() as session:
        old = get_image_dataset(session, dataset_id, old_version)
        appended = get_image_dataset(session, dataset_id, appended_version)
        assert old['version']['exposure_summary']['total_seconds'] == 480
        assert appended['version']['exposure_summary']['total_seconds'] == 540


@pytest.mark.parametrize(('values', 'expected'), [
    ([None, None], {'subframe_count': 2, 'known_count': 0, 'unknown_count': 2, 'total_seconds': None, 'complete': False}),
    ([0, 0], {'subframe_count': 2, 'known_count': 2, 'unknown_count': 0, 'total_seconds': 0, 'complete': True}),
])
def test_unknown_and_zero_are_distinct(database, values, expected):
    with database.write_session() as session:
        dataset, _ = create_group(session, values)
        assert get_dataset(session, UUID(dataset.id)).exposure_summary.model_dump() == expected


def test_standalone_subframe_exposure_and_master_exclusion(database):
    with database.write_session() as session:
        add_frame(session, 30)
        add_frame(session, 500, frame_class='masterframe')
    with database.read_session() as session:
        items = search_library(session, LibraryQuery()).items
        assert sorted(item.exposure_summary.subframe_count for item in items) == [0, 1]
        assert sorted(item.exposure_summary.total_seconds for item in items if item.exposure_summary.total_seconds is not None) == [30]
