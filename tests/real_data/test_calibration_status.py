"""Declarations and controlled successful-call facts propagate independently."""

import json
import shutil
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from astrophotoflow.contracts.assets import AssetPatch
from astrophotoflow.contracts.calibration_status import CalibrationEffect
from astrophotoflow.contracts.inputs import AssetInputReference, ScienceSelection
from astrophotoflow.contracts.library import LibraryOrganizeExecute, LibraryOrganizeRequest
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.public import (
    calibration_metadata,
    check_output,
    checked_output_calibration,
    get_dataset,
    get_output_registration,
    organize_library,
    plan_library_organization,
    register_output,
    resolve_canvas_inputs,
    run_import_task,
    update_asset,
)
from astrophotoflow.modules.software.bundles.catalog import operation_from_entry
from astrophotoflow.modules.software.metadata import catalog
from astrophotoflow.modules.software.packages.calibration import effective_calibration_effect


@pytest.mark.parametrize('status', ['Unknown', 'UnCalibrated', 'Calibrated'])
def test_explicit_status_has_evidence_snapshot_directory_and_counts(real_library, green_group, status):
    receipt = real_library.import_group(green_group, count=1, status=status)
    asset = real_library.assets(receipt)[0]
    assert asset.calibration_status == status
    assert asset.calibration_evidence['reason'] == 'Explicit acceptance fixture declaration.'
    assert asset.capture_snapshot['import_provenance']['calibration_status'] == status
    assert Path(asset.storage_location).parts[3] == status
    with real_library.database.read_session() as session:
        dataset = get_dataset(session, UUID(receipt['stages']['publication']['dataset_id']))
    assert dataset.calibration_status == status
    assert dataset.calibration_counts == {value: int(value == status) for value in ['UnCalibrated', 'Calibrated', 'Unknown']}


def test_mixed_current_member_states_publish_counts(real_library, imported_group):
    assets = real_library.assets(imported_group)
    original_positions = [asset.storage_location for asset in assets]
    with real_library.database.write_session() as session:
        update_asset(session, UUID(assets[0].id), AssetPatch(base_revision=assets[0].revision, calibration_status='UnCalibrated', calibration_reason='Confirmed raw subframe.'))
    with real_library.database.read_session() as session:
        dataset = get_dataset(session, UUID(imported_group['stages']['publication']['dataset_id']))
    assert dataset.calibration_status == 'Unknown'
    assert dataset.calibration_counts == {'UnCalibrated': 1, 'Calibrated': 0, 'Unknown': 1}
    assert [asset.storage_location for asset in real_library.assets(imported_group)] == original_positions
    mirror = json.loads((real_library.settings.data_dir / 'library' / dataset.library_directory / 'dataset.json').read_text(encoding='utf-8'))
    assert mirror['calibration_counts'] == dataset.calibration_counts


def _resolved(library, asset, directory):
    reference = AssetInputReference(kind='asset', asset_id=asset.id, selection=ScienceSelection(kind='whole_file'))
    return resolve_canvas_inputs(library.database, library.settings, reference, run_directory=directory).items[0]


def test_explicit_organization_aligns_the_uniform_dataset_status(real_library, imported_group):
    dataset_id = UUID(imported_group['stages']['publication']['dataset_id'])
    for asset in real_library.assets(imported_group):
        with real_library.database.write_session() as session:
            update_asset(session, UUID(asset.id), AssetPatch(base_revision=asset.revision,
                calibration_status='Calibrated', calibration_reason='Controlled explicit user declaration.'))
    with real_library.database.read_session() as session:
        dataset = get_dataset(session, dataset_id)
        plan = plan_library_organization(session, real_library.settings,
            LibraryOrganizeRequest(entry_type='dataset', id=dataset_id, base_revision=dataset.revision))
    result = organize_library(real_library.database, real_library.settings, LibraryOrganizeExecute(
        entry_type='dataset', id=dataset_id, base_revision=dataset.revision, request_id=uuid4(), plan_token=plan.token))
    assert result.state == 'completed'
    assert Path(result.plan.destination_directory).parts[:3] == ('Light', 'Subframe', 'Calibrated')
    assert all(move.state == 'completed' for move in result.plan.moves)


def test_declared_preservation_and_unknown_operation_semantics(real_library, green_group, tmp_path):
    imported = real_library.import_group(green_group, count=1, status='UnCalibrated')
    source = _resolved(real_library, real_library.assets(imported)[0], tmp_path / 'inputs')
    entry = next(entry for entry in catalog()['siril']['operations'] if entry['operation']['operation_id'] == 'autostretch')
    operation = operation_from_entry(entry, True, None)
    state, preserved = checked_output_calibration(operation.calibration_effect, {'image': [source]}, output_name='image',
        position=0, output_count=1, call={'call_id': str(uuid4()), 'operation_id': 'autostretch'}, parameters={})
    assert operation.calibration_effect.behavior == 'preserve'
    assert state.calibration_status == 'UnCalibrated' and preserved.asset_id == source.asset_id
    unknown, _ = checked_output_calibration(CalibrationEffect(), {'image': [source]}, output_name='image',
        position=0, output_count=1, call={'call_id': str(uuid4()), 'operation_id': 'undefined-semantics'}, parameters={})
    assert unknown.calibration_status == 'Unknown'


def test_controlled_calibration_receipt_registers_new_asset_and_keeps_actual_facts(real_library, imported_group, master_dark, tmp_path):
    source_asset = real_library.assets(imported_group)[0]
    source = _resolved(real_library, source_asset, tmp_path / 'science-input')
    master = _resolved(real_library, master_dark, tmp_path / 'master-input')
    call_id = str(uuid4())
    state, preserved = checked_output_calibration(
        CalibrationEffect(behavior='calibrate', input='image', outputs=['image'], masters={'dark': 'dark'}),
        {'image': [source], 'dark': [master]}, output_name='image', position=0, output_count=1,
        call={'call_id': call_id, 'operation_id': 'controlled-success-receipt'}, parameters={'fixture': True},
    )
    assert state.calibration_status == 'Calibrated'
    assert state.calibration_evidence['applied_masters']['dark'][0]['asset_id'] == master_dark.id
    # A controlled receipt tests registration semantics. Actual Siril execution
    # remains a separately reported acceptance activity.
    output_directory = tmp_path / 'controlled-output'
    output_directory.mkdir()
    output_path = output_directory / 'controlled-calibration.fits'
    shutil.copy2(source.read_path, output_path)
    checked = check_output(real_library.settings, run_directory=output_directory, path=output_path, expected_format='fits')
    checked = checked.model_copy(update={'scientific_metadata': {
        **checked.scientific_metadata, **calibration_metadata(state, preserved),
    }})
    task_id = uuid4()
    accepted = register_output(real_library.database, real_library.settings, task_id=task_id,
                               output=checked, name='Controlled calibrated output', provenance={'call_id': call_id})
    run_import_task(real_library.database, real_library.settings, str(accepted.task_id), real_library.workers)
    registered = get_output_registration(real_library.database, real_library.settings, task_id)
    assert str(registered.asset_id) != source_asset.id
    with real_library.database.write_session() as session:
        asset = session.get(Asset, str(registered.asset_id))
        assert asset.calibration_status == 'Calibrated'
        assert asset.scientific_metadata['processing_calibration']['call']['call_id'] == call_id
        changed = update_asset(session, registered.asset_id, AssetPatch(base_revision=asset.revision, calibration_status='Unknown', calibration_reason='Current manual review.'))
    assert changed.calibration_status == 'Unknown'
    assert changed.scientific_metadata['processing_calibration']['call']['call_id'] == call_id
    assert source_asset.calibration_status == 'Unknown'


def test_bias_expression_is_recorded_without_a_master_binding(real_library, imported_group, tmp_path):
    source = _resolved(real_library, real_library.assets(imported_group)[0], tmp_path / 'expression-input')
    entry = next(entry for entry in catalog()['siril']['operations'] if entry['operation']['operation_id'] == 'calibrate_single')
    operation = operation_from_entry(entry, True, None)
    effect = effective_calibration_effect(operation, {'bias_mode': 'expression', 'bias_expression': '=0'})
    state, _ = checked_output_calibration(effect, {'image': [source]}, output_name='image', position=0,
        output_count=1, call={'operation_id': 'controlled-bias-expression'}, parameters={'bias_mode': 'expression', 'bias_expression': '=0'})
    assert state.calibration_status == 'Calibrated'
    assert state.calibration_evidence['applied_parameters'] == {'bias_expression': '=0'}
    assert state.calibration_evidence['applied_masters'] == {}
