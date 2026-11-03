"""Check explicitly selected scan files before registration or copying originals."""

from copy import deepcopy

from astrophotoflow.contracts.image_management import EquipmentApplication
from astrophotoflow.modules.data.assets.image_metadata import freeze_import_equipment
from astrophotoflow.modules.data.calibration.checks import inspect_calibration_bindings
from astrophotoflow.modules.data.calibration.choices import patch_bindings
from astrophotoflow.modules.data.formats.layout import apply_cfa_override
from astrophotoflow.modules.data.imports.explicit import _merge_metadata, _selected_entries
from astrophotoflow.modules.data.imports.metadata import current_asset_parameters, current_classification


def check_import_calibration(session, settings, body):
    request = body.model_dump(mode='json', exclude_unset=True)
    entries = _selected_entries(settings, request)
    defaults = request.get('defaults') or {}
    default_bindings = patch_bindings({}, request.get('calibration_defaults') or {})
    rows = []
    for item, entry in zip(request['files'], entries, strict=True):
        observed = entry.get('observed', {})
        metadata = _merge_metadata(defaults.get('metadata'), item.get('metadata'))
        equipment = item.get('equipment', defaults.get('equipment'))
        frozen = {}
        snapshot = {}
        if equipment is not None:
            frozen = freeze_import_equipment(session, EquipmentApplication.model_validate(equipment), metadata.get('parameters', {}))
            snapshot = frozen.get('selected_equipment', {})
        scientific = entry.get('metadata_snapshot') or {}
        parsed = scientific.get('parsed_parameters', observed)
        parameters, _ = current_asset_parameters(metadata.get('parameters', {}), parsed, frozen.get('parameters'))
        hdus = deepcopy(scientific.get('hdus', []))
        if entry.get('format') == 'fits':
            apply_cfa_override(hdus, parameters.get('cfa_pattern'))
        selected = next((hdu for hdu in hdus if hdu.get('is_selected')), {})
        shape = selected.get('shape')
        dimensions = list(shape) if shape is not None else None
        classification, _ = current_classification(metadata.get('classification', {}), parsed.get('classification') or {}, {})
        facts = {'asset_version_id': item['file_id'], 'missing': False, 'availability': 'available',
            'classification': classification, 'parameters': parameters, 'dimensions': dimensions,
            'pixel_layout': selected.get('supported_kind'), 'equipment_snapshot': snapshot}
        overrides = patch_bindings({}, item.get('calibration', {}), allow_inherit=True)
        bindings = {**default_bindings, **overrides}
        checked = inspect_calibration_bindings(session, [item['file_id']], bindings, source_facts=facts)
        for row in checked:
            diagnostics = []
            for diagnostic in row['diagnostics']:
                diagnostic = dict(diagnostic)
                if diagnostic.get('source_asset_version_id') == item['file_id']:
                    diagnostic['source_file_id'] = diagnostic.pop('source_asset_version_id')
                diagnostics.append(diagnostic)
            rows.append({'file_id': item['file_id'],
                'dependency_asset_version_id': row['asset_version_id'] if row['asset_version_id'] != item['file_id'] else None,
                **{key: row[key] for key in ('slot', 'target', 'state', 'master_required', 'dependency_path')},
                'diagnostics': diagnostics})
    conflicts = sum(row['state'] == 'conflict' for row in rows)
    unknowns = sum(row['state'] == 'unknown' for row in rows)
    return {'state': 'conflict' if conflicts else 'unknown' if unknowns else 'compatible',
        'checked_files': len(entries), 'checked_bindings': len(rows), 'conflict_count': conflicts,
        'unknown_count': unknowns, 'master_required_count': sum(row['master_required'] for row in rows),
        'items': rows[body.offset:body.offset + body.limit], 'total': len(rows), 'limit': body.limit, 'offset': body.offset}
