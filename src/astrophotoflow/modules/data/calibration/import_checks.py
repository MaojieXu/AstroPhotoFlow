"""Check explicitly selected scan files before registration or copying originals."""
from copy import deepcopy
from astrophotoflow.core.errors import ApiError, invalid_reference
from astrophotoflow.modules.data.datasets.bindings import dataset_bindings
from astrophotoflow.modules.data.datasets.models import Dataset
from astrophotoflow.contracts.image_management import EquipmentApplication
from astrophotoflow.contracts.metadata import AssetParametersPatch
from astrophotoflow.modules.data.assets.image_metadata import freeze_import_equipment
from astrophotoflow.modules.data.calibration.checks import inspect_calibration_bindings
from astrophotoflow.modules.data.calibration.choices import patch_bindings
from astrophotoflow.modules.data.equipment.snapshots import capture_defaults_snapshot
from astrophotoflow.modules.data.formats.layout import apply_cfa_override
from astrophotoflow.modules.data.imports.explicit import _merge_metadata, _selected_entries
from astrophotoflow.modules.data.imports.metadata import current_asset_parameters, current_classification

def check_import_calibration(session, settings, body):
    request = body.model_dump(mode='json', exclude_unset=True)
    entries = _selected_entries(settings, request)
    defaults = request.get('defaults') or {}
    destination = request.get('destination')
    mode = destination['mode'] if destination else None
    grouped = mode in {'new_dataset', 'append_dataset'} or request.get('calibration') is not None
    bindings = patch_bindings({}, request.get('calibration') or {})
    if mode == 'append_dataset':
        dataset = session.get(Dataset, destination['dataset_id'])
        if dataset is None or dataset.status != 'active':
            raise invalid_reference('The destination dataset must exist and be active.', message_key='the_destination_dataset_must_exist_and_be_active')
        if dataset.revision != destination['expected_revision']:
            raise ApiError(409, 'REVISION_CONFLICT', 'Read the destination dataset again before appending.', message_key='read_the_destination_dataset_again_before_appending')
        bindings = dataset_bindings(dataset)
    rows = []
    for item, entry in zip(request['files'], entries, strict=True):
        observed = entry.get('observed', {})
        metadata = _merge_metadata(defaults.get('metadata'), item.get('metadata'))
        equipment = item.get('equipment', defaults.get('equipment'))
        explicit_parameters = metadata.get('parameters', {})
        snapshot = {}
        if equipment is not None:
            frozen = freeze_import_equipment(session, EquipmentApplication.model_validate(equipment), explicit_parameters)
            snapshot = frozen.get('selected_equipment', {})
        else:
            frozen = capture_defaults_snapshot(session, AssetParametersPatch.model_validate(explicit_parameters)).model_dump(mode='json', exclude_unset=True)
        scientific = entry.get('metadata_snapshot') or {}
        parsed = scientific.get('parsed_parameters', observed)
        hdus = deepcopy(scientific.get('hdus', []))
        classification, _ = current_classification(metadata.get('classification', {}), parsed.get('classification') or {}, {})
        parameters, _ = current_asset_parameters(explicit_parameters, parsed, frozen, classification=classification, hdus=hdus)
        if entry.get('format') == 'fits':
            apply_cfa_override(hdus, parameters.get('cfa_pattern'))
        selected = next((hdu for hdu in hdus if hdu.get('is_selected')), {})
        shape = selected.get('shape')
        dimensions = list(shape) if shape is not None else None
        facts = {'asset_id': item['file_id'], 'missing': False, 'availability': 'available', 'classification': classification, 'parameters': parameters, 'dimensions': dimensions, 'pixel_layout': selected.get('supported_kind'), 'equipment_snapshot': snapshot}
        if grouped and classification.get('frame_class') != 'subframe':
            raise invalid_reference('Only fixed subframes can be dataset members.', message_key='dataset_member_requires_subframe')
        choices = bindings if grouped else patch_bindings({}, item.get('calibration', {}))
        checked = inspect_calibration_bindings(session, [item['file_id']], choices, source_facts=facts)
        for row in checked:
            diagnostics = []
            for diagnostic in row['diagnostics']:
                diagnostic = dict(diagnostic)
                if diagnostic.get('source_asset_id') == item['file_id']:
                    diagnostic['source_file_id'] = diagnostic.pop('source_asset_id')
                diagnostics.append(diagnostic)
            rows.append({'file_id': item['file_id'], 'dependency_asset_id': row['asset_id'] if row['asset_id'] != item['file_id'] else None, **{key: row[key] for key in ('slot', 'target', 'state', 'master_required', 'dependency_path')}, 'diagnostics': diagnostics})
    conflicts = sum((row['state'] == 'conflict' for row in rows))
    unknowns = sum((row['state'] == 'unknown' for row in rows))
    warnings = sum(any(item['severity'] == 'warning' for item in row['diagnostics']) for row in rows)
    return {'state': 'conflict' if conflicts else 'unknown' if unknowns else 'warning' if warnings else 'compatible', 'checked_files': len(entries), 'checked_bindings': len(rows), 'conflict_count': conflicts, 'unknown_count': unknowns, 'warning_count': warnings, 'master_required_count': sum((row['master_required'] for row in rows)), 'items': rows[body.offset:body.offset + body.limit], 'total': len(rows), 'limit': body.limit, 'offset': body.offset}
