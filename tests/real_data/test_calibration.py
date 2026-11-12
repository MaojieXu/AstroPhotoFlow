"""Shared pending Masters, real missing facts and current-revision writes."""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from astrophotoflow.contracts.image_calibration import DatasetCalibrationUpdate
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.models import DatasetCalibration
from astrophotoflow.modules.data.public import get_dataset, update_image_dataset_calibration


def _binding(revision, master_id, *, accept_unknown=False):
    return DatasetCalibrationUpdate.model_validate({
        'request_id': uuid4(), 'expected_revision': revision, 'accept_unknown': accept_unknown,
        'changes': {'dark': {'mode': 'target', 'target': {'kind': 'asset', 'id': master_id}}},
    })


def test_unknown_master_metadata_requires_confirmation_and_binding_keeps_state(real_library, imported_group, master_dark):
    dataset_id = UUID(imported_group['stages']['publication']['dataset_id'])
    with real_library.database.read_session() as session:
        dataset = get_dataset(session, dataset_id)
    with pytest.raises(ApiError) as unknown, real_library.database.write_session() as session:
        update_image_dataset_calibration(session, dataset_id, _binding(dataset.revision, master_dark.id))
    assert unknown.value.code == 'CALIBRATION_UNKNOWN'
    body = _binding(dataset.revision, master_dark.id, accept_unknown=True)
    with real_library.database.write_session() as session:
        accepted = update_image_dataset_calibration(session, dataset_id, body)
    with real_library.database.write_session() as session:
        replay = update_image_dataset_calibration(session, dataset_id, body)
        assert replay == accepted
        assert session.scalar(select(func.count()).select_from(DatasetCalibration).where(DatasetCalibration.dataset_id == str(dataset_id))) == 1
        assert all(session.get(Asset, asset.id).calibration_status == 'Unknown' for asset in real_library.assets(imported_group))
        current = get_dataset(session, dataset_id)
    mirror = json.loads((real_library.settings.data_dir / 'library' / current.library_directory / 'dataset.json').read_text(encoding='utf-8'))
    assert mirror['pending_calibration']['dark']['asset_id'] == master_dark.id
    assert mirror['executed_processing'] == []
    with pytest.raises(ApiError) as wrong_purpose, real_library.database.write_session() as session:
        current = get_dataset(session, dataset_id)
        update_image_dataset_calibration(session, dataset_id, DatasetCalibrationUpdate.model_validate({
            'request_id': uuid4(), 'expected_revision': current.revision, 'accept_unknown': True,
            'changes': {'flat': {'mode': 'target', 'target': {'kind': 'asset', 'id': master_dark.id}}},
        }))
    assert wrong_purpose.value.code == 'CALIBRATION_CONFLICT'


def test_known_exposure_conflict_cannot_be_accepted_as_unknown(real_library, imported_group, real_data_catalog):
    master = next(item for item in real_data_catalog['masters'] if item['frame_type'] == 'dark' and item['header']['EXPTIME'] == 300)
    imported = real_library.import_files([real_library.root / master['path']], frame_class='masterframe', frame_type='dark')
    target = real_library.assets(imported)[0]
    dataset_id = UUID(imported_group['stages']['publication']['dataset_id'])
    with real_library.database.read_session() as session:
        revision = get_dataset(session, dataset_id).revision
    with pytest.raises(ApiError) as mismatch, real_library.database.write_session() as session:
        update_image_dataset_calibration(session, dataset_id, _binding(revision, target.id, accept_unknown=True))
    assert mismatch.value.code == 'CALIBRATION_CONFLICT'


def test_two_calibration_writers_share_one_revision_guard(real_library, imported_group, master_dark):
    dataset_id = UUID(imported_group['stages']['publication']['dataset_id'])
    with real_library.database.read_session() as session:
        revision = get_dataset(session, dataset_id).revision

    def save():
        try:
            with real_library.database.write_session() as session:
                return update_image_dataset_calibration(session, dataset_id, _binding(revision, master_dark.id, accept_unknown=True))['result']['revision']
        except ApiError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: save(), range(2)))
    assert sorted(map(str, results)) == [str(revision + 1), 'REVISION_CONFLICT']
