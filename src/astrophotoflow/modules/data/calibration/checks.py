"""Validate fixed calibration dependencies without running image processing."""
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.calibration.choices import UNCONFIGURED
from astrophotoflow.modules.data.datasets.scientific_checks import compare_facts, asset_facts
ALLOWED_SLOTS = {'light': {'bias', 'dark', 'flat'}, 'flat': {'bias', 'dark_flat'}, 'dark': {'bias'}, 'dark_flat': {'bias'}, 'bias': set()}

def _diagnostic(code, field, severity='conflict'):
    return {'code': code, 'field': field, 'severity': severity}

def target_members(session, target: dict, slot: str) -> tuple[list[str], list[dict], bool]:
    """Only an existing, same-purpose Master asset version is a target."""
    if target.get('kind') != 'asset':
        return ([], [_diagnostic('INVALID_TARGET_KIND', 'target.kind')], False)
    from astrophotoflow.modules.data.assets.visibility import not_removed
    from sqlalchemy import select
    usable = session.scalar(select(Asset.id).where(Asset.id == str(target['id']), Asset.status == 'active', not_removed('asset', Asset.id)))
    if usable is None:
        return ([], [_diagnostic('REFERENCE_UNAVAILABLE', 'target')], False)
    facts = asset_facts(session, str(target['id']))
    classification = facts.get('classification', {})
    valid = not facts.get('missing') and classification.get('frame_type') == slot and (classification.get('frame_class') == 'masterframe')
    asset = session.get(Asset, facts.get('asset_id')) if not facts.get('missing') else None
    if not valid or asset is None or asset.scope != 'shared':
        return ([], [_diagnostic('INVALID_MASTER_TARGET', 'target')], False)
    if asset.availability != 'available':
        return ([], [_diagnostic('CONTENT_UNAVAILABLE', 'target')], False)
    return ([str(target['id'])], [], False)

def validate_target_structure(session, bindings: dict) -> None:
    """Even an unused group default must identify a valid calibration source."""
    for slot, target in bindings.items():
        if target is None or target == UNCONFIGURED:
            continue
        _, issues, _ = target_members(session, target, slot)
        if issues:
            raise ApiError(409, 'CALIBRATION_CONFLICT', 'The calibration target is structurally invalid.', [{'path': slot, 'message': ', '.join((issue['code'] for issue in issues))}], message_key='the_calibration_target_is_structurally_invalid')

def _walk(session, source_id: str, bindings: dict, stack: tuple[str, ...], rows: list[dict], binding_sources: dict | None=None, context_bindings: dict | None=None, source_facts: dict | None=None) -> None:
    source = source_facts if source_facts is not None else asset_facts(session, source_id)
    source_type = source.get('classification', {}).get('frame_type')
    context_bindings = bindings if context_bindings is None else context_bindings
    for slot, target in bindings.items():
        if target is None or target == UNCONFIGURED:
            continue
        issues = []
        if source_type not in ALLOWED_SLOTS or slot not in ALLOWED_SLOTS[source_type]:
            issues.append(_diagnostic('INVALID_CONSUMER_SLOT', slot))
        ids, target_issues, master_required = target_members(session, target, slot)
        issues.extend(target_issues)
        identity = f"{target.get('kind')}:{target.get('id')}"
        if identity in stack or source_id in ids:
            issues.append(_diagnostic('CALIBRATION_CYCLE', 'target'))
        target_facts = [asset_facts(session, target_id) for target_id in ids]
        for facts in target_facts:
            issues.extend(compare_facts(source, facts, slot))
        if ids and (not master_required):
            from astrophotoflow.modules.data.assets.image_metadata import get_master_declaration
            declaration = get_master_declaration(session, ids[0])
            if declaration.get('bias_state', 'unknown') == 'unknown':
                issues.append(_diagnostic('MASTER_HISTORY_UNKNOWN', 'bias_state', 'unknown'))
            if slot == 'flat' and declaration.get('normalized') is None:
                issues.append(_diagnostic('MASTER_HISTORY_UNKNOWN', 'normalized', 'unknown'))
            if declaration.get('debayered') is True and source.get('parameters', {}).get('cfa_pattern') not in (None, 'MONO'):
                issues.append(_diagnostic('MASTER_ALREADY_DEBAYERED', 'debayered'))
        if slot == 'flat':
            issues.append(_diagnostic('OPTICAL_STATE_UNVERIFIED', 'optical_state', 'unknown'))
        if context_bindings.get('bias') not in (None, UNCONFIGURED) and slot in {'dark', 'dark_flat'} and ids and (not master_required):
            from astrophotoflow.modules.data.assets.image_metadata import get_master_declaration
            if get_master_declaration(session, ids[0]).get('bias_state') == 'included':
                issues.append(_diagnostic('BIAS_SUBTRACTION_DUPLICATED', 'bias'))
        if slot == 'bias':
            from astrophotoflow.modules.data.assets.image_metadata import get_master_declaration
            for dark_slot in ('dark', 'dark_flat'):
                dark = context_bindings.get(dark_slot)
                if dark and dark.get('kind') == 'asset' and (get_master_declaration(session, str(dark['id'])).get('bias_state') == 'included'):
                    issues.append(_diagnostic('BIAS_SUBTRACTION_DUPLICATED', dark_slot))
        status = 'conflict' if any((item['severity'] == 'conflict' for item in issues)) else 'unknown' if any((item['severity'] == 'unknown' for item in issues)) else 'warning' if any(item['severity'] == 'warning' for item in issues) else 'compatible'
        availabilities = {facts.get('availability', 'unknown') for facts in target_facts}
        dependency_path = [{'kind': parent.split(':', 1)[0], 'id': parent.split(':', 1)[1]} for parent in (*stack, identity)]
        rows.append({'asset_id': source_id, 'slot': slot, 'target': target, 'state': status, 'master_required': master_required, 'diagnostics': issues, 'binding_source': (binding_sources or {}).get(slot, 'dependency' if stack else 'proposal'), 'dependency_path': dependency_path, 'source_asset_revision': source.get('asset_revision'), 'source_metadata_basis': source.get('metadata_basis'), 'source_availability': source.get('availability'), 'target_asset_revision': target_facts[0].get('asset_revision') if not master_required and target_facts else None, 'target_availability': next(iter(availabilities)) if len(availabilities) == 1 else 'mixed' if availabilities else 'unknown', 'applicable': status in {'compatible', 'warning'} and (not master_required)})

def inspect_calibration_bindings(session, source_asset_ids: list[str], bindings: dict, *, binding_sources: dict | None=None, context_bindings: dict | None=None, source_facts: dict | None=None) -> list[dict]:
    rows = []
    for source_id in source_asset_ids:
        _walk(session, str(source_id), bindings, (), rows, binding_sources, context_bindings, source_facts)
    return rows

def validate_calibration_bindings(session, source_asset_ids: list[str], bindings: dict, *, accept_unknown: bool=False, context_bindings: dict | None=None) -> dict:
    rows = inspect_calibration_bindings(session, source_asset_ids, bindings, context_bindings=context_bindings)
    conflicts = sum((row['state'] == 'conflict' for row in rows))
    unknowns = sum((row['state'] == 'unknown' for row in rows))
    if conflicts:
        raise ApiError(409, 'CALIBRATION_CONFLICT', 'Known scientific conflicts prevent this calibration assignment.', [{'path': f"{row['asset_id']}.{row['slot']}", 'message': ', '.join((item['code'] for item in row['diagnostics'] if item['severity'] == 'conflict'))} for row in rows if row['state'] == 'conflict'], message_key='known_scientific_conflicts_prevent_this_calibration_assignment')
    if unknowns and (not accept_unknown):
        raise ApiError(409, 'CALIBRATION_UNKNOWN', 'Unknown scientific metadata requires accept_unknown=true.', [{'path': f"{row['asset_id']}.{row['slot']}", 'message': ', '.join((item['code'] for item in row['diagnostics'] if item['severity'] == 'unknown'))} for row in rows if row['state'] == 'unknown'], message_key='unknown_scientific_metadata_requires_accept_unknown')
    return {'checked_bindings': len(rows), 'conflict_count': conflicts, 'unknown_count': unknowns, 'warning_count': sum(any(item['severity'] == 'warning' for item in row['diagnostics']) for row in rows), 'master_required_count': sum((row['master_required'] for row in rows)), 'items': rows}
