from uuid import UUID, uuid4
import pytest
from sqlalchemy import func, select
from astrophotoflow.contracts.image_calibration import CalibrationCheckPage, DatasetCalibrationUpdate, ImageCalibrationOut, ImageCalibrationUpdate, ImageDatasetCreate, ImageDatasetEditMembers, ImageOperationOut
from astrophotoflow.contracts.inputs import AssetInputReference, DatasetInputReference, ScienceSelection
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import initialize_database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.calibration.checks import validate_calibration_bindings
from astrophotoflow.modules.data.calibration.choices import UNCONFIGURED, patch_bindings
from astrophotoflow.modules.data.calibration.service import apply_import_calibration, calibration_references, check_calibration, create_image_dataset, edit_image_dataset_members, get_image_calibration, get_image_calibration_operation, get_image_dataset_calibration, search_calibrations, update_image_calibration, update_image_dataset_calibration
from astrophotoflow.modules.data.science.files import hash_file
from astrophotoflow.modules.data.science.inputs import resolve_canvas_inputs

@pytest.fixture
def library(tmp_path):
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    initialize_database(settings)
    database = Database(settings.database_path)
    yield (database, settings)
    database.close()
CAMERA = str(uuid4())
OPTICS = str(uuid4())
FILTER = str(uuid4())

def image(session, settings, frame_type='light', master=False, camera=CAMERA, exposure=60):
    identity, = (str(uuid4()),)
    path = settings.data_dir / 'objects' / identity / 'source.bin'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'synthetic scientific source')
    content_hash, size, _ = hash_file(path)
    parameters = {'camera_id': camera, 'optical_system_id': OPTICS, 'filter_id': FILTER, 'parameter_mode': 'gain', 'gain': 0, 'offset': 0, 'exposure_seconds': exposure, 'sensor_temperature_c': -10, 'binning_x': 1, 'binning_y': 1, 'cfa_pattern': 'MONO', 'readout_mode': 'test-mode'}
    asset = Asset(id=identity, name=f'{frame_type}-{identity[:8]}', scope='shared', role='raw' if frame_type == 'light' else 'calibration', frame_class='masterframe' if master else 'subframe', frame_type=frame_type, **parameters, storage_mode='managed', storage_location=path.relative_to(settings.data_dir).as_posix(), availability='available', content_hash=content_hash, byte_size=size, calibration_level='master' if master else 'individual', capture_snapshot={'parameters': parameters, 'classification': {'frame_class': 'masterframe' if master else 'subframe', 'frame_type': frame_type}}, scientific_metadata={'format': 'other', 'width': 8, 'height': 6, 'supported_kind': 'mono'})
    session.add(asset)
    session.flush()
    session.flush()
    return asset

def target(version):
    return {'kind': 'asset', 'id': version.id}

def choice(version):
    return {'mode': 'target', 'target': target(version)}

def create_group(session, name, versions, **extra):
    body = ImageDatasetCreate.model_validate({'request_id': uuid4(), 'name': name, 'members': [{'asset_id': version.id} for version in versions], **extra})
    return create_image_dataset(session, body)['result']

def test_scanned_calibration_check_is_read_only_and_reuses_actual_file_facts(library):
    import numpy as np
    from astropy.io import fits
    from astrophotoflow.contracts.image_imports import ImageInspectionRequest, ScannedCalibrationCheckPage, ScannedCalibrationCheckRequest
    from astrophotoflow.modules.data.calibration.import_checks import check_import_calibration
    from astrophotoflow.modules.data.imports.explicit import inspect_image_files, list_image_inspection_files
    from astrophotoflow.modules.data.imports.models import AssetTask
    database, settings = library
    path = settings.workspace / 'external' / 'light.fits'
    path.parent.mkdir(parents=True)
    hdu = fits.PrimaryHDU(np.zeros((6, 8), dtype=np.uint16))
    hdu.header['IMAGETYP'] = 'Light Frame'
    hdu.header['EXPTIME'] = 20
    hdu.header['GAIN'] = 0
    hdu.header['OFFSET'] = 0
    hdu.header['CCD-TEMP'] = -10
    hdu.header['XBINNING'] = 1
    hdu.header['YBINNING'] = 1
    hdu.writeto(path)
    scan = inspect_image_files(settings, ImageInspectionRequest(paths=[str(path)]))
    entries = list_image_inspection_files(settings, scan['scan_id'])
    file_id = entries['items'][0]['file_id']
    with database.write_session() as session:
        dark = image(session, settings, 'dark', master=True)
        request = {'scan_id': scan['scan_id'], 'files': [{'file_id': file_id}], 'defaults': {'metadata': {'parameters': {'parameter_mode': 'gain'}}}, 'calibration': {'dark': choice(dark)}}
        before = session.scalar(select(func.count()).select_from(Asset))
        result = check_import_calibration(session, settings, ScannedCalibrationCheckRequest.model_validate(request))
        ScannedCalibrationCheckPage.model_validate(result)
        assert result['state'] == 'conflict'
        assert result['items'][0]['file_id'] == file_id
        assert any((row['field'] == 'exposure_seconds' and row['code'] == 'METADATA_MISMATCH' for row in result['items'][0]['diagnostics']))
        request['files'][0]['metadata'] = {'parameters': {'exposure_seconds': 60}}
        unknown = check_import_calibration(session, settings, ScannedCalibrationCheckRequest.model_validate(request))
        assert unknown['state'] == 'unknown' and unknown['conflict_count'] == 0
        assert not any((row['field'] == 'dimensions' for row in unknown['items'][0]['diagnostics']))
        assert session.scalar(select(func.count()).select_from(Asset)) == before
        assert session.scalar(select(func.count()).select_from(AssetTask)) == 0
        path.write_bytes(b'changed after inspection')
        with pytest.raises(ApiError) as changed:
            check_import_calibration(session, settings, ScannedCalibrationCheckRequest.model_validate(request))
        assert changed.value.code == 'SOURCE_CHANGED'

@pytest.mark.parametrize(('header_pattern', 'changes'), [(None, {'parameters': {'gain': None}}), (None, {'classification': {'frame_type': None}}), (None, {'parameters': {'cfa_pattern': 'RGGB'}}), ('RGGB', {'parameters': {'cfa_pattern': 'MONO'}})])
def test_scan_precheck_matches_registered_facts_with_nulls_and_cfa_overrides(library, header_pattern, changes):
    import numpy as np
    from astropy.io import fits
    from astrophotoflow.contracts.image_imports import ExplicitImportRequest, ImageInspectionRequest, ScannedCalibrationCheckRequest
    from astrophotoflow.modules.data.calibration.import_checks import check_import_calibration
    from astrophotoflow.modules.data.imports.explicit import get_image_import, inspect_image_files, list_image_inspection_files, submit_image_import
    from astrophotoflow.modules.data.imports.runner import run_import_task
    database, settings = library
    path = settings.workspace / 'external' / 'explicit-values.fits'
    path.parent.mkdir(parents=True)
    hdu = fits.PrimaryHDU(np.zeros((6, 8), dtype=np.uint16))
    for key, value in {'IMAGETYP': 'Light Frame', 'GAIN': 0, 'OFFSET': 0, 'EXPTIME': 60, 'CCD-TEMP': -10, 'XBINNING': 1, 'YBINNING': 1}.items():
        hdu.header[key] = value
    if header_pattern:
        hdu.header['BAYERPAT'] = header_pattern
    hdu.writeto(path)
    scan = inspect_image_files(settings, ImageInspectionRequest(paths=[str(path)]))
    file_id = list_image_inspection_files(settings, scan['scan_id'])['items'][0]['file_id']
    metadata = {'parameters': {'parameter_mode': 'gain', 'readout_mode': 'test-mode', **changes.get('parameters', {})}, **{key: value for key, value in changes.items() if key != 'parameters'}}
    selected = {'file_id': file_id, 'metadata': metadata}
    request_id = uuid4()
    with database.write_session() as session:
        dark = image(session, settings, 'dark', master=True)
        binding = {'dark': choice(dark)}
        preflight = check_import_calibration(session, settings, ScannedCalibrationCheckRequest.model_validate({'scan_id': scan['scan_id'], 'files': [selected], 'calibration': binding}))
        accepted = submit_image_import(session, settings, ExplicitImportRequest.model_validate({'request_id': request_id, 'scan_id': scan['scan_id'], 'files': [selected], 'destination': {'mode': 'standalone'}}))
    run_import_task(database, settings, accepted.receipt['task_id'])
    with database.read_session() as session:
        outcome = get_image_import(session, request_id)['items'][0]
        assert outcome['publication_status'] == 'published'
        registered = check_calibration(session, {'kind': 'asset', 'asset_id': outcome['asset_id']}, {'changes': binding})
        assert registered['state'] == preflight['state']
        diagnostics = lambda result: [(row['code'], row['field'], row['severity'], row.get('source_value'), row.get('target_value')) for row in result['items'][0]['diagnostics']]
        assert diagnostics(registered) == diagnostics(preflight)
        if changes.get('parameters', {}).get('gain', 'not-provided') is None:
            assert any((row['field'] == 'gain' and row['severity'] == 'unknown' for row in preflight['items'][0]['diagnostics']))
        if changes.get('parameters', {}).get('cfa_pattern') == 'RGGB':
            assert any((row['field'] == 'pixel_layout' and row['source_value'] == 'bayer' for row in preflight['items'][0]['diagnostics']))

def test_standalone_binding_updates_current_state_and_request_replay_precedes_revision_check(library):
    database, settings = library
    with database.write_session() as session:
        light = image(session, settings)
        dark = image(session, settings, 'dark', master=True)
        request_id = uuid4()
        body = ImageCalibrationUpdate.model_validate({'request_id': request_id, 'expected_revision': 1, 'changes': {'dark': choice(dark)}, 'accept_unknown': True})
        receipt = update_image_calibration(session, light.id, body)
        assert update_image_calibration(session, light.id, body) == receipt
        assert get_image_calibration_operation(session, request_id) == receipt
        assert light.revision == 2
        assert session.scalar(select(func.count()).select_from(Asset).where(Asset.id == light.id)) == 1
        second = update_image_calibration(session, light.id, ImageCalibrationUpdate.model_validate({'request_id': uuid4(), 'expected_revision': 2, 'changes': {'dark': {'mode': 'disabled'}}}))
        assert second['result']['asset_id'] == light.id
        current = get_image_calibration(session, light.id)
        assert current['bindings']['dark'] == {'mode': 'disabled'}
        ImageCalibrationOut.model_validate(current)
        ImageOperationOut.model_validate(receipt)
        changed_request = body.model_copy(update={'expected_revision': 99})
        with pytest.raises(ApiError, match='different content') as conflict:
            update_image_calibration(session, light.id, changed_request)
        assert conflict.value.code == 'REQUEST_CONFLICT'

def test_known_camera_conflict_cannot_be_accepted_as_unknown(library):
    database, settings = library
    with database.write_session() as session:
        light = image(session, settings)
        dark = image(session, settings, 'dark', master=True, camera=str(uuid4()))
        with pytest.raises(ApiError) as error:
            validate_calibration_bindings(session, [light.id], {'dark': target(dark)}, accept_unknown=True)
        assert error.value.code == 'CALIBRATION_CONFLICT'

def test_unknown_master_history_requires_explicit_acceptance(library):
    database, settings = library
    with database.write_session() as session:
        light = image(session, settings)
        dark = image(session, settings, 'dark', master=True)
        with pytest.raises(ApiError) as error:
            validate_calibration_bindings(session, [light.id], {'dark': target(dark)})
        assert error.value.code == 'CALIBRATION_UNKNOWN'
        assert validate_calibration_bindings(session, [light.id], {'dark': target(dark)}, accept_unknown=True)['unknown_count'] == 1

def test_only_master_targets_are_accepted_and_raw_groups_remain_manageable(library):
    from pydantic import ValidationError
    from astrophotoflow.contracts.calibration import CalibrationTarget
    database, settings = library
    with database.write_session() as session:
        light = image(session, settings)
        dark = image(session, settings, 'dark')
        master = image(session, settings, 'dark', master=True)
        raw = create_group(session, 'raw darks', [dark])
        for candidate in ({'kind': 'dataset', 'id': raw['dataset_id']}, target(dark)):
            with pytest.raises(ApiError) as error:
                validate_calibration_bindings(session, [light.id], {'dark': candidate}, accept_unknown=True)
            assert error.value.code == 'CALIBRATION_CONFLICT'
        with pytest.raises(ValidationError):
            CalibrationTarget.model_validate({'kind': 'dataset', 'id': raw['dataset_id']})
        assert validate_calibration_bindings(session, [light.id], {}, accept_unknown=False)['checked_bindings'] == 0
        assert validate_calibration_bindings(session, [light.id], {'dark': target(master)}, accept_unknown=True)['master_required_count'] == 0
        page = search_calibrations(session, 'dark')
        assert [item['target']['id'] for item in page['items']] == [master.id]

def test_raw_flat_group_can_consume_master_darkflat_without_becoming_target(library):
    database, settings = library
    with database.write_session() as session:
        flat = image(session, settings, 'flat', exposure=1)
        dark_flat = image(session, settings, 'dark_flat', master=True, exposure=1)
        raw = create_group(session, 'flats', [flat], calibration={'dark_flat': choice(dark_flat)}, accept_unknown=True)
        checked = check_calibration(session, {'kind': 'dataset', 'dataset_id': raw['dataset_id']}, limit=1)
        assert checked['total'] == 1
        assert checked['items'][0]['asset_id'] == flat.id
        assert checked['items'][0]['slot'] == 'dark_flat'
        assert checked['items'][0]['master_required'] is False
        CalibrationCheckPage.model_validate(checked)

def test_science_inputs_freeze_actual_calibration_and_group_does_not_inherit_it(library, tmp_path):
    database, settings = library
    with database.write_session() as session:
        light = image(session, settings)
        dark = image(session, settings, 'dark', master=True)
        apply_import_calibration(session, light.id, {'dark': target(dark)}, accept_unknown=True)
        group = create_group(session, 'independent group', [light])
        light_id, dark_id = (light.id, dark.id)
        assert calibration_references(session, {dark_id}, set())
    standalone = resolve_canvas_inputs(database, settings, AssetInputReference(kind='asset', asset_id=UUID(light_id), selection=ScienceSelection(kind='whole_file')), run_directory=tmp_path / 'standalone')
    with database.write_session() as session:
        apply_import_calibration(session, light_id, {'dark': None})
        assert not calibration_references(session, {dark_id}, set())
    assert str(standalone.items[0].effective_calibration['dark'].id) == dark_id
    grouped = resolve_canvas_inputs(database, settings, DatasetInputReference(kind='dataset', dataset_id=UUID(group['dataset_id']), asset_ids=[UUID(light_id)]), run_directory=tmp_path / 'group')
    assert grouped.items[0].effective_calibration['dark'] is None
    with database.read_session() as session:
        assert get_image_calibration(session, light_id)['bindings']['dark'] == {'mode': 'disabled'}

def test_group_calibration_changes_update_current_dataset(library):
    database, settings = library
    with database.write_session() as session:
        first = image(session, settings)
        second = image(session, settings)
        dark_a = image(session, settings, 'dark', master=True)
        dark_b = image(session, settings, 'dark', master=True)
        group = create_image_dataset(session, ImageDatasetCreate.model_validate({'request_id': uuid4(), 'name': 'lights', 'members': [{'asset_id': first.id}, {'asset_id': second.id}], 'calibration': {'dark': choice(dark_a)}, 'accept_unknown': True}))['result']
        edited = update_image_dataset_calibration(session, group['dataset_id'], DatasetCalibrationUpdate.model_validate({'request_id': uuid4(), 'expected_revision': 1, 'changes': {'dark': choice(dark_b)}, 'accept_unknown': True}))['result']
        current = get_image_dataset_calibration(session, group['dataset_id'])
        assert current['calibration']['dark']['target'] == target(dark_b)
        assert edited['dataset_id'] == group['dataset_id']
        assert edited['revision'] == 2

@pytest.mark.parametrize('field,value', [('offset', 1), ('readout_mode', 'other-mode'), ('exposure_seconds', 120)])
def test_dark_electronic_and_exposure_mismatches_are_hard_conflicts(library, field, value):
    database, settings = library
    with database.write_session() as session:
        light = image(session, settings)
        dark_asset = image(session, settings, 'dark', master=True)
        setattr(dark_asset, field, value)
        with pytest.raises(ApiError) as error:
            validate_calibration_bindings(session, [light.id], {'dark': target(dark_asset)}, accept_unknown=True)
        assert error.value.code == 'CALIBRATION_CONFLICT'

def test_dark_temperature_difference_is_diagnostic_not_an_invented_tolerance(library):
    database, settings = library
    with database.write_session() as session:
        light = image(session, settings)
        dark_asset = image(session, settings, 'dark', master=True)
        dark_asset.sensor_temperature_c = -8
        checked = validate_calibration_bindings(session, [light.id], {'dark': target(dark_asset)}, accept_unknown=True)
        assert any((issue['code'] == 'TEMPERATURE_DIFFERENCE' and issue['severity'] == 'warning' for issue in checked['items'][0]['diagnostics']))

def test_flat_exposure_can_differ_but_selected_accessory_must_not(library):
    database, settings = library
    with database.write_session() as session:
        light_asset = image(session, settings, exposure=300)
        flat_asset = image(session, settings, 'flat', master=True, exposure=1)
        validate_calibration_bindings(session, [light_asset.id], {'flat': target(flat_asset)}, accept_unknown=True)
        light_asset.equipment_snapshot = {'optical_system_id': {'effective_focal_length_mm': 1645, 'optical_accessory': {'id': str(uuid4()), 'name': 'first reducer', 'factor': 0.7}}}
        flat_asset.equipment_snapshot = {'optical_system_id': {'effective_focal_length_mm': 1645, 'optical_accessory': {'id': str(uuid4()), 'name': 'different reducer', 'factor': 0.7}}}
        with pytest.raises(ApiError) as error:
            validate_calibration_bindings(session, [light_asset.id], {'flat': target(flat_asset)}, accept_unknown=True)
        assert error.value.code == 'CALIBRATION_CONFLICT'

def test_known_gain_conflict_is_not_hidden_by_unknown_parameter_mode(library):
    database, settings = library
    with database.write_session() as session:
        light_asset = image(session, settings)
        dark_asset = image(session, settings, 'dark', master=True)
        light_asset.parameter_mode = None
        dark_asset.parameter_mode = None
        dark_asset.gain = 99
        with pytest.raises(ApiError) as error:
            validate_calibration_bindings(session, [light_asset.id], {'dark': target(dark_asset)}, accept_unknown=True)
        assert error.value.code == 'CALIBRATION_CONFLICT'
        assert 'METADATA_MISMATCH' in error.value.fields[0]['message']

def test_unrelated_default_change_does_not_reject_previously_accepted_unknown_dark(library):
    database, settings = library
    with database.write_session() as session:
        light = image(session, settings)
        dark = image(session, settings, 'dark', master=True)
        group = create_group(session, 'lights', [light], calibration={'dark': choice(dark)}, accept_unknown=True)
        changed = update_image_dataset_calibration(session, group['dataset_id'], DatasetCalibrationUpdate.model_validate({'request_id': uuid4(), 'expected_revision': 1, 'changes': {'bias': {'mode': 'disabled'}}}))['result']
        assert changed['diagnostics']['checked_bindings'] == 0
        current = get_image_dataset_calibration(session, group['dataset_id'])
        assert current['calibration']['dark']['target'] == target(dark)

def test_standalone_unrelated_change_preserves_accepted_unknown_binding(library):
    database, settings = library
    with database.write_session() as session:
        light_asset = image(session, settings)
        dark = image(session, settings, 'dark', master=True)
        apply_import_calibration(session, light_asset.id, {'dark': target(dark)}, accept_unknown=True)
        receipt = update_image_calibration(session, light_asset.id, ImageCalibrationUpdate.model_validate({'request_id': uuid4(), 'expected_revision': light_asset.revision, 'changes': {'bias': {'mode': 'disabled'}}}))
        assert receipt['result']['bindings']['dark']['target'] == target(dark)

def test_master_target_check_explains_fixed_reference_without_reapplying_its_bindings(library):
    database, settings = library
    with database.write_session() as session:
        light_asset = image(session, settings)
        flat = image(session, settings, 'flat', master=True, exposure=1)
        dark_flat = image(session, settings, 'dark_flat', master=True, exposure=1)
        apply_import_calibration(session, flat.id, {'dark_flat': target(dark_flat)}, accept_unknown=True)
        apply_import_calibration(session, light_asset.id, {'flat': target(flat)}, accept_unknown=True)
        checked = check_calibration(session, {'kind': 'asset', 'asset_id': light_asset.id}, limit=1)
        assert checked['unknown_count'] == 1
        assert checked['checked_bindings'] == checked['total'] == 1
        first = checked['items'][0]
        assert first['binding_source'] == 'standalone'
        assert first['source_asset_revision'] == light_asset.revision
        assert first['source_metadata_basis'] == 'current_metadata'
        assert first['source_availability'] == first['target_availability'] == 'available'
        assert first['master_required'] is False
        assert first['dependency_path'] == [target(flat)]
        assert first['target_asset_revision'] == 1
        CalibrationCheckPage.model_validate(checked)

def test_unused_default_still_rejects_raw_subframe_target(library):
    database, settings = library
    with database.write_session() as session:
        light = image(session, settings)
        raw_dark = image(session, settings, 'dark')
        consumer = create_image_dataset(session, ImageDatasetCreate.model_validate({'request_id': uuid4(), 'name': 'lights', 'members': [{'asset_id': light.id}], 'calibration': {'dark': {'mode': 'disabled'}}}))['result']
        with pytest.raises(ApiError) as error:
            update_image_dataset_calibration(session, consumer['dataset_id'], DatasetCalibrationUpdate.model_validate({'request_id': uuid4(), 'expected_revision': 1, 'changes': {'dark': {'mode': 'target', 'target': target(raw_dark)}}, 'accept_unknown': True}))
        assert error.value.code == 'CALIBRATION_CONFLICT'

@pytest.mark.parametrize('frame_type', ['light', 'flat', 'dark', 'dark_flat'])
def test_bias_is_optional_for_all_supported_consumers_and_not_implicitly_disabled(library, frame_type):
    database, settings = library
    with database.write_session() as session:
        asset = image(session, settings, frame_type)
        bias = image(session, settings, 'bias', master=True, exposure=0)
        empty = get_image_calibration(session, asset.id)
        assert empty['bindings']['bias'] == {'mode': 'unconfigured'}
        saved = apply_import_calibration(session, asset.id, {'bias': target(bias)}, accept_unknown=True)
        assert saved['bindings']['bias'] == choice(bias)
        assert saved['slots']['bias']['status'] == 'target'

def test_candidate_search_paginates_before_optional_science_check(library, monkeypatch):
    database, settings = library
    with database.write_session() as session:
        masters = []
        for index in range(8):
            asset = image(session, settings, 'dark', master=True)
            asset.name = f'Master Dark {index}'
            masters.append(asset)
        for _ in range(12):
            image(session, settings, 'dark', master=False)
        session.flush()
        checks = []

        def checked(_session, consumer, proposal, limit):
            checks.append(proposal['changes']['dark']['target']['id'])
            return {'state': 'unknown'}
        monkeypatch.setattr('astrophotoflow.modules.data.calibration.service.check_calibration', checked)
        page = search_calibrations(session, 'dark', consumer={'kind': 'asset'}, query={'text': 'master dark', 'limit': 2, 'offset': 3})
        assert page['total'] == 8
        assert [item['target']['id'] for item in page['items']] == [masters[3].id, masters[4].id]
        assert checks == [masters[3].id, masters[4].id]
        checks.clear()
        no_consumer = search_calibrations(session, 'dark', query={'limit': 1, 'offset': 7})
        assert no_consumer['total'] == 8 and len(no_consumer['items']) == 1
        assert checks == []
        assert search_calibrations(session, 'dark', query={'text': '%'})['total'] == 0
