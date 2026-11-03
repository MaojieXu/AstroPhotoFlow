import json
from uuid import UUID, uuid4

import numpy as np
import pytest
from astropy.io import fits
from sqlalchemy import func, select

from astrophotoflow.contracts.datasets import DatasetPatch
from astrophotoflow.contracts.equipment import CameraCreate, CameraPatch
from astrophotoflow.contracts.image_imports import ExplicitImportRequest, ImageImportReceipt, ImageInspectionRequest, ImagePublicationRetry
from astrophotoflow.contracts.imports import RetryCreate
from astrophotoflow.core.config import ImportRoot, Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import upgrade_database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion, ImageMetadataState
from astrophotoflow.modules.data.datasets.bindings import default_bindings, member_bindings
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion
from astrophotoflow.modules.data.datasets.service import update_dataset
from astrophotoflow.modules.data.equipment.service import create_equipment, update_equipment
from astrophotoflow.modules.data.imports.explicit import (
    get_image_import,
    inspect_image_files,
    list_image_inspection_files,
    retry_image_publication,
    submit_image_import,
)
from astrophotoflow.modules.data.imports.runner import run_import_task
from astrophotoflow.modules.data.imports.tasks import retry_asset_task
from astrophotoflow.modules.data.imports.history import compact_completed_imports


@pytest.fixture
def environment(tmp_path):
    source = tmp_path / 'night'
    source.mkdir()
    settings = Settings('127.0.0.1', 8190, tmp_path / 'workspace' / 'data', (),
                        import_roots=(ImportRoot('night', source),), workspace=tmp_path / 'workspace')
    upgrade_database(settings)
    database = Database(settings.database_path)
    yield source, settings, database
    database.close()


def photo(path, frame='Light Frame', gain=12):
    hdu = fits.PrimaryHDU(np.arange(256, dtype=np.float32).reshape(16, 16))
    hdu.header['OBJECT'] = 'M31'
    hdu.header['IMAGETYP'] = frame
    hdu.header['GAIN'] = gain
    hdu.header['EXPTIME'] = 30
    hdu.header['DATE-OBS'] = '2026-11-01T22:00:00Z'
    hdu.writeto(path)


def scan(environment, paths=None):
    source, settings, _ = environment
    observed = inspect_image_files(settings, ImageInspectionRequest(paths=[str(path) for path in (paths or [source])]))
    entries = list_image_inspection_files(settings, observed['scan_id'])['items']
    return observed, entries


def request(observed, entries, destination=None, **changes):
    return ExplicitImportRequest.model_validate_json(json.dumps({
        'request_id': str(uuid4()), 'scan_id': observed['scan_id'],
        'files': [{'file_id': item['file_id']} for item in entries],
        'destination': destination or {'mode': 'new_dataset', 'name': 'M31'}, **changes,
    }))


def submit(environment, body, *, execute=True):
    _, settings, database = environment
    with database.write_session() as session:
        accepted = submit_image_import(session, settings, body)
    if execute and accepted.scheduled:
        run_import_task(database, settings, accepted.receipt['task_id'])
    with database.read_session() as session:
        result = get_image_import(session, body.request_id)
    ImageImportReceipt.model_validate_json(json.dumps(result))
    return result


def test_completed_import_compaction_keeps_receipts_and_request_idempotency(environment):
    source, settings, database = environment
    photo(source / 'completed.fits')
    observed, entries = scan(environment)
    body = request(observed, entries)
    receipt = submit(environment, body)
    assert receipt['status'] == 'completed'
    original = (source / 'completed.fits').read_bytes()
    result = compact_completed_imports(database, settings)
    assert receipt['task_id'] in result['task_ids']
    assert result['payload_bytes_removed'] > 0
    assert not (settings.data_dir / 'import-inspections' / (observed['scan_id'] + '.json')).exists()
    with database.write_session() as session:
        replay = submit_image_import(session, settings, body)
        assert replay.scheduled is False
        assert replay.receipt == receipt
    assert (source / 'completed.fits').read_bytes() == original
    assert compact_completed_imports(database, settings)['task_ids'] == []


def test_pending_import_keeps_its_frozen_plan_and_inspection(environment):
    source, settings, database = environment
    photo(source / 'pending.fits')
    observed, entries = scan(environment)
    body = request(observed, entries)
    receipt = submit(environment, body, execute=False)
    result = compact_completed_imports(database, settings)
    assert receipt['task_id'] not in result['task_ids']
    assert (settings.data_dir / 'import-inspections' / (observed['scan_id'] + '.json')).is_file()


def test_file_facts_are_unclassified_by_filename_and_do_not_suggest_groups(environment):
    source, _, database = environment
    photo(source / 'M42_Dark_R_120s.fits')
    observed, entries = scan(environment)
    assert 'groups' not in observed
    assert entries[0]['observed']['target_name'] == 'M31'
    assert not {'hints', 'suggested', 'group_id'} & entries[0].keys()
    assert entries[0]['issues'] == []
    with database.read_session() as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 0


def test_order_per_file_metadata_null_zero_and_request_identity(environment):
    source, settings, database = environment
    photo(source / 'a.fits')
    photo(source / 'b.fits')
    observed, entries = scan(environment)
    body = request(observed, list(reversed(entries)), defaults={'metadata': {'parameters': {'gain': 0, 'offset': 0}}})
    body.files[0].metadata = body.files[0].__class__.model_validate_json(json.dumps({
        'file_id': str(body.files[0].file_id), 'metadata': {'target_name': None, 'parameters': {'gain': None}},
    })).metadata
    result = submit(environment, body)
    assert result['status'] == 'completed'
    assert [item['file_id'] for item in result['items']] == [str(item.file_id) for item in body.files]
    publication = result['stages']['publication']
    with database.write_session() as session:
        replay = submit_image_import(session, settings, body)
        assert not replay.scheduled and replay.receipt['task_id'] == result['task_id']
        assert session.scalar(select(func.count()).select_from(Asset)) == 2
        members = list(session.scalars(select(DatasetMember).where(DatasetMember.dataset_version_id == publication['dataset_version_id']).order_by(DatasetMember.position)))
        first = session.get(AssetVersion, members[0].asset_version_id)
        asset = session.get(Asset, first.asset_id)
        assert asset.gain is None and asset.offset == 0
        assert session.get(ImageMetadataState, asset.id).target_name is None
        assert session.get(ImageMetadataState, asset.id).capture_start_utc is not None
        assert asset.value_sources['target_name'] == 'manual'
        assert asset.value_sources['times.capture_start'] == 'file'
        assert first.capture_snapshot['image_metadata']['target_name'] is None
        assert first.capture_snapshot['image_metadata']['times']['capture_start']['raw_value'] == '2026-11-01T22:00:00Z'
    changed = body.model_copy(update={'destination': body.destination.model_copy(update={'name': 'another'})})
    with database.write_session() as session, pytest.raises(ApiError, match='different import'):
        submit_image_import(session, settings, changed)


def test_source_stamp_change_is_rejected_at_acceptance_and_during_copy(environment):
    source, _, _ = environment
    path = source / 'a.fits'
    photo(path)
    observed, entries = scan(environment)
    body = request(observed, entries, {'mode': 'standalone'})
    path.write_bytes(path.read_bytes() + b'changed')
    with pytest.raises(ApiError) as changed:
        submit(environment, body)
    assert changed.value.code == 'SOURCE_CHANGED'
    observed, entries = scan(environment)
    body = request(observed, entries, {'mode': 'standalone'})
    accepted = submit(environment, body, execute=False)
    path.write_bytes(path.read_bytes() + b'changed again')
    _, settings, database = environment
    run_import_task(database, settings, accepted['task_id'])
    with database.read_session() as session:
        result = get_image_import(session, body.request_id)
    assert result['status'] == 'failed' and result['items'][0]['asset_version_id'] is None


def test_append_preserves_old_default_and_gives_new_members_explicit_unconfigured(environment):
    source, _, database = environment
    photo(source / 'a.fits')
    observed, entries = scan(environment)
    first = submit(environment, request(observed, entries, calibration_defaults={'flat': {'mode': 'disabled'}}))
    first_publication = first['stages']['publication']
    photo(source / 'b.fits')
    observed, entries = scan(environment, [source / 'b.fits'])
    append = request(observed, entries, {'mode': 'append_dataset', 'dataset_id': first_publication['dataset_id'],
                                       'expected_revision': first_publication['dataset_revision'],
                                       'base_version_id': first_publication['dataset_version_id']})
    second = submit(environment, append)
    assert second['status'] == 'completed'
    with database.read_session() as session:
        version = session.get(DatasetVersion, second['stages']['publication']['dataset_version_id'])
        members = list(session.scalars(select(DatasetMember).where(DatasetMember.dataset_version_id == version.id).order_by(DatasetMember.position)))
        assert default_bindings(version) == {'flat': None}
        assert member_bindings(members[0]) == {}
        assert member_bindings(members[1])['flat'] == {'mode': 'unconfigured'}
        assert members[0].asset_version_id == first['items'][0]['asset_version_id']
        assert len(list(session.scalars(select(DatasetMember).where(DatasetMember.dataset_version_id == first_publication['dataset_version_id'])))) == 1


def test_conflicting_append_retains_originals_and_retry_only_publishes(environment):
    source, settings, database = environment
    photo(source / 'a.fits')
    observed, entries = scan(environment)
    first = submit(environment, request(observed, entries))
    fixed = first['stages']['publication']
    photo(source / 'b.fits')
    observed, entries = scan(environment, [source / 'b.fits'])
    body = request(observed, entries, {'mode': 'append_dataset', 'dataset_id': fixed['dataset_id'],
                                      'expected_revision': fixed['dataset_revision'], 'base_version_id': fixed['dataset_version_id']})
    accepted = submit(environment, body, execute=False)
    with database.write_session() as session:
        update_dataset(session, UUID(fixed['dataset_id']), DatasetPatch(base_revision=fixed['dataset_revision'], notes='changed concurrently'))
    run_import_task(database, settings, accepted['task_id'])
    with database.write_session() as session:
        result = get_image_import(session, body.request_id)
        assert result['items'][0]['originals'] == 'available'
        assert result['stages']['publication']['state'] == 'conflict'
        dataset = session.get(Dataset, fixed['dataset_id'])
        retry = ImagePublicationRetry(request_id=uuid4(), task_id=UUID(accepted['task_id']), expected_revision=dataset.revision,
                                       base_version_id=UUID(dataset.current_version_id))
        repaired = retry_image_publication(session, accepted['task_id'], retry)
        version = repaired['stages']['publication']['dataset_version_id']
        assert repaired['status'] == 'completed'
        assert repaired['items'][0]['asset_version_id'] == result['items'][0]['asset_version_id']
        assert retry_image_publication(session, accepted['task_id'], retry)['stages']['publication']['dataset_version_id'] == version
        assert session.scalar(select(func.count()).select_from(Asset)) == 2


def test_reference_mode_requires_configured_root_and_keeps_original(environment):
    source, _, database = environment
    photo(source / 'a.fits')
    observed, entries = scan(environment)
    result = submit(environment, request(observed, entries, {'mode': 'standalone'}, storage_mode='reference'))
    assert result['status'] == 'completed'
    with database.read_session() as session:
        version = session.get(AssetVersion, result['items'][0]['asset_version_id'])
        assert version.storage_mode == 'reference' and version.storage_location == 'roots/night/a.fits'
    assert (source / 'a.fits').is_file()


def test_failed_original_retry_preserves_identity_and_publishes_missing_member(environment, monkeypatch):
    from astrophotoflow.modules.data.imports import stages
    source, settings, database = environment
    photo(source / 'a.fits')
    photo(source / 'b.fits')
    observed, entries = scan(environment)
    body = request(observed, entries)
    original = stages.read_hash_and_copy
    failed = False
    def fail_once(path, *args, **kwargs):
        nonlocal failed
        if path.name == 'b.fits' and not failed:
            failed = True
            raise OSError('controlled copy failure')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(stages, 'read_hash_and_copy', fail_once)
    first = submit(environment, body)
    assert first['status'] == 'completed_with_errors'
    broken = next(item for item in first['items'] if item['originals'] == 'failed')
    with database.write_session() as session:
        retry = retry_asset_task(session, UUID(first['task_id']), RetryCreate(item_ids=[UUID(broken['task_item_id'])]))
    run_import_task(database, settings, str(retry.task_id))
    with database.read_session() as session:
        result = get_image_import(session, body.request_id)
        assert result['status'] == 'completed'
        repaired = next(item for item in result['items'] if item['file_id'] == broken['file_id'])
        assert repaired['asset_id'] == broken['asset_id'] and repaired['asset_version_id'] == broken['asset_version_id']
        assert repaired['originals'] == 'available' and repaired['member_position'] == 1
        assert session.scalar(select(func.count()).select_from(Asset)) == 2


def test_equipment_choice_is_frozen_before_registry_changes_and_defaults_normalized(environment):
    source, settings, database = environment
    photo(source / 'a.fits')
    with database.write_session() as session:
        camera = create_equipment(session, CameraCreate(kind='camera', name='At acceptance'))
    observed, entries = scan(environment)
    body = request(observed, entries, {'mode': 'standalone'}, defaults={
        'equipment': {'choice': {'source': 'devices', 'camera': {'equipment_id': str(camera.id), 'expected_revision': camera.revision}},
                      'fields': ['camera']},
    })
    accepted = submit(environment, body, execute=False)
    with database.write_session() as session:
        update_equipment(session, camera.id, CameraPatch(kind='camera', base_revision=camera.revision, name='After acceptance'))
        replay = submit_image_import(session, settings, body.model_copy(update={'storage_mode': 'managed', 'accept_unknown': False}))
        assert replay.scheduled is False
    run_import_task(database, settings, accepted['task_id'])
    with database.read_session() as session:
        result = get_image_import(session, body.request_id)
        assert result['status'] == 'completed'
        asset = session.get(Asset, result['items'][0]['asset_id'])
        assert asset.camera_id == str(camera.id)
        assert asset.equipment_snapshot['camera_id']['name'] == 'At acceptance'
        assert asset.gain == 12


def test_known_scientific_conflict_excludes_only_affected_incoming_file(environment):
    source, _, database = environment
    photo(source / 'master.fits', frame='Dark Frame')
    observed, entries = scan(environment)
    master = submit(environment, request(observed, entries, {'mode': 'standalone'}, defaults={
        'metadata': {'classification': {'frame_class': 'masterframe', 'frame_type': 'dark'},
                     'parameters': {'parameter_mode': 'gain'}},
    }))
    photo(source / 'light-a.fits')
    photo(source / 'light-b.fits')
    observed, entries = scan(environment, [source / 'light-a.fits', source / 'light-b.fits'])
    body = request(observed, entries, calibration_defaults={'dark': {
        'mode': 'target', 'target': {'kind': 'asset_version', 'id': master['items'][0]['asset_version_id']},
    }}, defaults={'metadata': {'parameters': {'parameter_mode': 'gain'}}}, accept_unknown=True)
    raw = body.model_dump(mode='json', exclude_unset=True)
    raw['files'][1]['metadata'] = {'parameters': {'gain': 999}}
    body = ExplicitImportRequest.model_validate_json(json.dumps(raw))
    result = submit(environment, body)
    assert result['status'] == 'completed_with_errors'
    publication = result['stages']['publication']
    assert publication['state'] == 'published'
    assert len(publication['errors']) == 1 and publication['errors'][0]['code'] == 'CALIBRATION_CONFLICT'
    assert all(item['originals'] == 'available' for item in result['items'])
    assert result['items'][0]['publication_status'] == 'published'
    assert result['items'][0]['calibration_status'] == 'saved'
    assert result['items'][1]['publication_status'] == 'excluded'
    assert result['items'][1]['calibration_status'] == 'blocked'
    assert result['items'][1]['error'] is None
    assert result['items'][1]['errors'][0]['code'] == 'CALIBRATION_CONFLICT'
    with database.read_session() as session:
        members = list(session.scalars(select(DatasetMember).where(DatasetMember.dataset_version_id == publication['dataset_version_id'])))
        assert len(members) == 1 and members[0].asset_version_id == result['items'][0]['asset_version_id']


class DeferredPreviews:
    """Keep rendering blocked while the real registration/publication completes."""
    def __init__(self):
        self.jobs = []

    def prioritize(self, _keys):
        pass

    def submit(self, fn, *args):
        from concurrent.futures import Future
        future = Future()
        self.jobs.append((fn, args, future))
        return future

    def render(self):
        while self.jobs:
            fn, args, future = self.jobs.pop(0)
            future.set_result(fn(*args))


def test_light_import_reuses_inspected_fits_and_finishes_before_only_cover_preview(environment, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from astrophotoflow.modules.data.imports import stages
    from astrophotoflow.modules.data.media.models import Preview
    from astrophotoflow.modules.data.media.display import DisplayPreviews
    source, settings, database = environment
    for name in ['a.fits', 'b.fits', 'c.fits']:
        photo(source / name)
    observed, entries = scan(environment)
    assert all('metadata_snapshot' not in entry for entry in entries)
    # No second header parse is permitted, including CFA override interpretation.
    def unexpected_parse(*_args, **_kwargs):
        raise AssertionError('Import repeated the inspected FITS header read')
    monkeypatch.setattr(stages, 'inspect_fits', unexpected_parse)
    body = request(observed, entries, defaults={'metadata': {'parameters': {'cfa_pattern': 'RGGB'}}})
    accepted = submit(environment, body, execute=False)
    previews = DeferredPreviews()
    with ThreadPoolExecutor(max_workers=1) as files:
        run_import_task(database, settings, accepted['task_id'], (files, previews))
    with database.read_session() as session:
        result = get_image_import(session, body.request_id)
        assert result['status'] == 'completed'
        assert result['stages']['originals']['available'] == 3
        assert result['stages']['publication']['state'] == 'published'
        assert all(item['previews'] == 'not_requested' for item in result['items'])
        assert session.scalar(select(func.count()).select_from(Preview)) == 1  # claimed cover, not rendered
        versions = [item['asset_version_id'] for item in result['items']]
        from astrophotoflow.modules.data.assets.models import FitsHduMetadata
        assert all(row.supported_kind == 'bayer' for row in session.scalars(select(FitsHduMetadata)))
    assert len(previews.jobs) == 1
    previews.render()
    with database.read_session() as session:
        assert list(session.scalars(select(Preview.asset_version_id).where(Preview.size == 'thumbnail'))) == versions[:1]
    # First opening a non-cover member creates both derivatives. Duplicate opens
    # coalesce under the existing display-preview ownership row.
    display = DisplayPreviews(database, settings, previews, recover=False)
    assert display.schedule(versions[1])['status'] == 'generating'
    assert display.schedule(versions[1])['status'] == 'generating'
    assert len(previews.jobs) == 1
    previews.render()
    assert display.status(versions[1])['status'] == 'available'
    assert display.schedule(versions[1])['status'] == 'available'
    assert not previews.jobs
    with database.read_session() as session:
        thumbnail = session.scalar(select(Preview).where(Preview.asset_version_id == versions[1], Preview.size == 'thumbnail'))
        assert thumbnail.status == 'available' and (settings.data_dir / thumbnail.storage_path).is_file()


def test_append_does_not_generate_a_new_cover_and_preview_failure_does_not_fail_import(environment, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from astrophotoflow.modules.data.media.display import DisplayPreviews
    source, settings, database = environment
    photo(source / 'a.fits')
    observed, entries = scan(environment)
    first_body = request(observed, entries)
    first = submit(environment, first_body, execute=False)
    previews = DeferredPreviews()
    with ThreadPoolExecutor(max_workers=1) as files:
        run_import_task(database, settings, first['task_id'], (files, previews))
    def failed_render(*_args):
        raise ValueError('preview deliberately unavailable')
    monkeypatch.setattr(DisplayPreviews, '_render', failed_render)
    previews.render()
    with database.read_session() as session:
        first = get_image_import(session, first_body.request_id)
        assert first['status'] == 'completed' and first['items'][0]['originals'] == 'available'
        assert first['items'][0]['previews'] == 'not_requested'
        assert DisplayPreviews(database, settings, previews, recover=False).status(first['items'][0]['asset_version_id'])['status'] == 'failed'
        publication = first['stages']['publication']
    photo(source / 'b.fits')
    observed, entries = scan(environment, [source / 'b.fits'])
    body = request(observed, entries, {'mode': 'append_dataset', 'dataset_id': publication['dataset_id'],
        'expected_revision': 1, 'base_version_id': publication['dataset_version_id']})
    accepted = submit(environment, body, execute=False)
    with ThreadPoolExecutor(max_workers=1) as files:
        run_import_task(database, settings, accepted['task_id'], (files, previews))
    assert not previews.jobs
    with database.read_session() as session:
        assert get_image_import(session, body.request_id)['status'] == 'completed'


def test_standalone_import_is_deferred_and_preserves_actual_and_set_temperature(environment):
    from concurrent.futures import ThreadPoolExecutor
    from astrophotoflow.modules.data.media.models import Preview
    source, settings, database = environment
    path = source / 'a.fits'
    photo(path)
    with fits.open(path, mode='update') as hdus:
        hdus[0].header['CCD-TEMP'] = -16.5
        hdus[0].header['SET-TEMP'] = -20
    observed, entries = scan(environment)
    assert entries[0]['observed']['sensor_temperature_c'] == -16.5
    assert entries[0]['observed']['sensor_temperature_setpoint_c'] == -20
    body = request(observed, entries, {'mode': 'standalone'})
    accepted = submit(environment, body, execute=False)
    previews = DeferredPreviews()
    with ThreadPoolExecutor(max_workers=1) as files:
        run_import_task(database, settings, accepted['task_id'], (files, previews))
    assert not previews.jobs
    with database.read_session() as session:
        result = get_image_import(session, body.request_id)
        assert result['status'] == 'completed' and result['items'][0]['previews'] == 'not_requested'
        asset = session.get(Asset, result['items'][0]['asset_id'])
        assert asset.sensor_temperature_c == -16.5
        version = session.get(AssetVersion, result['items'][0]['asset_version_id'])
        assert version.scientific_metadata['observed_parameters']['sensor_temperature_setpoint_c'] == -20
        assert session.scalar(select(func.count()).select_from(Preview)) == 0


def test_legacy_directory_import_also_schedules_only_one_cover(environment):
    from concurrent.futures import ThreadPoolExecutor
    from astrophotoflow.contracts.imports import ImportCreate
    from astrophotoflow.modules.data.imports.models import AssetTask
    from astrophotoflow.modules.data.imports.submission import create_import
    source, settings, database = environment
    photo(source / 'a.fits')
    photo(source / 'b.fits')
    with database.write_session() as session:
        accepted = create_import(session, settings, ImportCreate.model_validate_json(json.dumps({
            'sources': [{'path': str(source)}], 'storage_mode': 'managed'})))
    previews = DeferredPreviews()
    with ThreadPoolExecutor(max_workers=1) as files:
        run_import_task(database, settings, str(accepted.task_id), (files, previews))
    with database.read_session() as session:
        task = session.get(AssetTask, str(accepted.task_id))
        assert task.status == 'completed'
        assert task.dataset_id is not None
        assert session.scalar(select(func.count()).select_from(AssetVersion)) == 2
    assert len(previews.jobs) == 1
    previews.render()
