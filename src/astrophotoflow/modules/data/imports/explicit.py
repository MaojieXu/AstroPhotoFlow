"""Explicit, inspected file imports over the existing resumable import pipeline."""
from __future__ import annotations
import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from pydantic import ValidationError
from sqlalchemy import select
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember
from astrophotoflow.modules.data.datasets.service import publish_dataset_members
from astrophotoflow.modules.data.equipment.snapshots import capture_defaults_snapshot
from astrophotoflow.modules.data.imports.inspection import inspect_sources, read_manifest, source_stamp
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem

@dataclass(frozen=True)
class ImageImportAcceptance:
    receipt: dict
    scheduled: bool

def inspect_image_files(settings, body):
    """Observe files without inventing groups or metadata from their names."""
    manifest = inspect_sources(settings, body, include_groups=False)
    return image_inspection_summary(manifest)

def image_inspection_summary(manifest):
    issues = manifest['issues'] + [{'file_id': item['id'], 'path': item['path'], **issue} for item in manifest['files'] for issue in item['issues']]
    return {'scan_id': manifest['scan_id'], 'recursive': manifest['recursive'], 'roots': manifest['roots'], 'file_count': len(manifest['files']), 'excluded_count': len(manifest['excluded']), 'issues': issues[:20], 'issues_total': len(issues)}

def get_image_inspection(settings, scan_id):
    return image_inspection_summary(read_manifest(settings, scan_id))

def list_image_inspection_files(settings, scan_id, *, kind='files', query=None):
    manifest = read_manifest(settings, scan_id)
    values = query.model_dump(exclude_none=True) if hasattr(query, 'model_dump') else dict(query or {})
    limit, offset = (values.pop('limit', 50), values.pop('offset', 0))
    if kind not in {'files', 'excluded', 'issues'}:
        raise ApiError(422, 'VALIDATION_ERROR', 'Inspection entries must be files, excluded or issues.', message_key='inspection_entries_must_be_files_excluded_or_issues')
    if kind == 'issues':
        rows = manifest['issues'] + [{'file_id': item['id'], 'path': item['path'], **issue} for item in manifest['files'] for issue in item['issues']]
    elif kind == 'files':
        rows = [{key: deepcopy(value) for key, value in item.items() if key not in {'id', 'hints', 'suggested', 'group_id', 'metadata_snapshot'}} | {'file_id': item['id'], 'supported': True} for item in manifest['files']]
    else:
        rows = [{**item, 'supported': False} for item in manifest['excluded']]

    def matches(row):
        if values.get('text') and values['text'].casefold() not in row.get('path', '').casefold():
            return False
        if 'supported' in values and row.get('supported') != values['supported']:
            return False
        observed = row.get('observed', {})
        classification = observed.get('classification', {})
        return all((values.get(key) is None or (classification.get(key) if key in {'frame_class', 'frame_type'} else observed.get(key)) == values[key] for key in ('frame_class', 'frame_type', 'target_name')))
    rows = [row for row in rows if matches(row)]
    return {'items': rows[offset:offset + limit], 'total': len(rows), 'limit': limit, 'offset': offset}

def _dump(value):
    return value.model_dump(mode='json', exclude_unset=True) if hasattr(value, 'model_dump') else deepcopy(value)

def _merge_metadata(defaults, individual):
    result = deepcopy(defaults or {})
    for key, value in (individual or {}).items():
        if key in {'classification', 'parameters', 'times'}:
            result[key] = {**result.get(key, {}), **value}
        else:
            result[key] = value
    return result

def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
_FITS_DATETIME = re.compile('\\d{4}-\\d{2}-\\d{2}[T ]\\d{2}:\\d{2}:\\d{2}')

def _fits_time_cards(hdus):
    primary, selected = ({}, {})
    for hdu in hdus:
        if hdu['hdu_index'] == 0 or hdu['is_selected']:
            cards = {card['keyword']: card['value'] for card in hdu['header_cards'] if card['keyword'] in {'DATE-OBS', 'TIMESYS', 'INHERIT'}}
            if hdu['hdu_index'] == 0:
                primary = cards
            if hdu['is_selected']:
                selected = cards
    if not str(selected.get('DATE-OBS') or '').strip():
        return primary
    if selected.get('INHERIT') is True and 'TIMESYS' not in selected and ('TIMESYS' in primary):
        return {**selected, 'TIMESYS': primary['TIMESYS']}
    return selected

def _observed_image_metadata(entry):
    observed = entry.get('observed', {})
    result = {}
    if observed.get('target_name') is not None:
        result['target_name'] = observed['target_name']
    is_fits = entry.get('format') == 'fits'
    hdus = (entry.get('metadata_snapshot') or {}).get('hdus') if is_fits else None
    cards = _fits_time_cards(hdus) if hdus else observed
    raw_date = cards.get('DATE-OBS')
    if raw_date is None or not str(raw_date).strip():
        return result
    time = {'raw_value': str(raw_date)}
    has_timesys = 'TIMESYS' in cards
    if has_timesys:
        time['time_system'] = str(cards['TIMESYS']) if cards['TIMESYS'] is not None else None
    timestamp = time['raw_value'].strip()
    utc_scale = not is_fits or not has_timesys or str(cards['TIMESYS']).strip().upper() == 'UTC'
    if utc_scale and (not hdus or _FITS_DATETIME.match(timestamp)):
        try:
            parsed = datetime.fromisoformat(timestamp)
            if parsed.tzinfo is None and hdus and (has_timesys or parsed.year >= 1972):
                parsed = parsed.replace(tzinfo=UTC)
            if parsed.tzinfo is not None:
                time['utc'] = parsed.astimezone(UTC).isoformat().replace('+00:00', 'Z')
        except (ValueError, OverflowError):
            pass
    result['times'] = {'capture_start': time}
    return result

def context_for_image_item(task_data, item):
    """Reuse native metadata precedence with the accepted per-file frozen values."""
    if not task_data.image_import_plan:
        return task_data
    plan = task_data.image_import_plan['files'][item.root_item_id]
    return replace(task_data, classification=deepcopy(plan['metadata'].get('classification', {})), parameters=deepcopy(plan['metadata'].get('parameters', {})), import_defaults_snapshot=deepcopy(plan['defaults_snapshot']), notes=plan.get('notes'), calibration_status=plan.get('calibration_status', 'Unknown'), calibration_reason=plan.get('calibration_reason'))

def _selected_entries(settings, request):
    manifest = read_manifest(settings, request['scan_id'])
    entries = {item['id']: item for item in manifest['files']}
    selected = []
    for item in request['files']:
        entry = entries.get(item['file_id'])
        if entry is None:
            raise ApiError(422, 'INVALID_REFERENCE', 'Selected file is not part of this inspection.', message_key='selected_file_is_not_part_of_this_inspection')
        path = Path(entry['path'])
        try:
            unchanged = path.is_file() and source_stamp(path) == entry['source_stamp']
        except OSError:
            unchanged = False
        if not unchanged or any((issue['code'] == 'SOURCE_CHANGED' for issue in entry['issues'])):
            raise ApiError(409, 'SOURCE_CHANGED', 'An inspected source changed; inspect it again before importing.', message_key='an_inspected_source_changed_inspect_it_again_before_importing')
        selected.append(entry)
    return selected

def submit_image_import(session, settings, body):
    """Accept exact file identities once, freezing all manual and device choices."""
    request = _dump(body)
    request['destination']['mode'] = body.destination.mode
    request['storage_mode'] = body.storage_mode
    request['accept_unknown'] = body.accept_unknown
    if body.destination.mode == 'new_dataset':
        request['destination']['notes'] = body.destination.notes
    fingerprint = _fingerprint(request)
    previous = session.scalar(select(AssetTask).where(AssetTask.request_id == request['request_id']))
    if previous is not None:
        if previous.request_fingerprint != fingerprint:
            raise ApiError(409, 'IMPORT_REQUEST_CONFLICT', 'This request_id belongs to a different import.', message_key='this_request_id_belongs_to_a_different_import')
        return ImageImportAcceptance(image_import_receipt(session, previous), False)
    entries = _selected_entries(settings, request)
    destination = request['destination']
    target_id = None
    if destination['mode'] == 'new_dataset':
        target_id = str(uuid4())
    elif destination['mode'] == 'append_dataset':
        target_id = destination['dataset_id']
        dataset = session.get(Dataset, target_id)
        if dataset is None or dataset.status != 'active':
            raise ApiError(422, 'INVALID_REFERENCE', 'The destination dataset must exist and be active.', message_key='the_destination_dataset_must_exist_and_be_active')
        if dataset.revision != destination['expected_revision']:
            raise ApiError(409, 'REVISION_CONFLICT', 'Read the destination dataset again before appending.', message_key='read_the_destination_dataset_again_before_appending')
    from astrophotoflow.contracts.imports import ImportOptions
    from .project_links import import_destination
    _, destination_context = import_destination(session, ImportOptions(
        mode=destination['mode'], target_dataset_id=destination.get('dataset_id'),
        dataset_base_revision=destination.get('expected_revision'), project_id=request.get('project_id'),
        project_base_revision=request.get('project_base_revision')))
    defaults = request.get('defaults', {})
    files, sources = ({}, [])
    for item, entry in zip(request['files'], entries, strict=True):
        manual_metadata = _merge_metadata(defaults.get('metadata'), item.get('metadata'))
        metadata = _merge_metadata(_observed_image_metadata(entry), manual_metadata)
        image_value_sources = {}
        if 'target_name' in metadata:
            image_value_sources['target_name'] = 'manual' if 'target_name' in manual_metadata else 'file'
        for slot in metadata.get('times', {}):
            image_value_sources[f'times.{slot}'] = 'manual' if slot in manual_metadata.get('times', {}) else 'file'
        from astrophotoflow.contracts.image_management import ImageMetadata
        try:
            ImageMetadata.model_validate_json(json.dumps(metadata))
        except ValidationError as exc:
            raise ApiError(422, 'VALIDATION_ERROR', 'Combined per-file metadata is invalid.', [{'path': '.'.join(map(str, error['loc'])), 'message': error['msg']} for error in exc.errors()], message_key='combined_per_file_metadata_is_invalid') from exc
        from astrophotoflow.contracts.metadata import AssetParametersPatch
        frozen = capture_defaults_snapshot(session, AssetParametersPatch.model_validate(metadata.get('parameters', {})))
        equipment = item.get('equipment', defaults.get('equipment'))
        if equipment is not None:
            from astrophotoflow.contracts.image_management import EquipmentApplication
            from astrophotoflow.modules.data.assets.image_metadata import freeze_import_equipment
            if 'optical_accessory' in equipment['fields'] and 'telescope' not in equipment['fields']:
                raise ApiError(422, 'INVALID_REFERENCE', 'A new image needs an explicit telescope application together with its optical accessory.', message_key='a_new_image_needs_a_telescope_application_with_its_optical_accessory')
            frozen = freeze_import_equipment(session, EquipmentApplication.model_validate_json(json.dumps(equipment)), metadata.get('parameters', {}))
        files[item['file_id']] = {**item, 'calibration_status': item.get('calibration_status', defaults.get('calibration_status', 'Unknown')), 'calibration_reason': item.get('calibration_reason', defaults.get('calibration_reason')), 'metadata': metadata, 'image_value_sources': image_value_sources, 'defaults_snapshot': _dump(frozen), 'notes': item.get('notes', defaults.get('notes'))}
        root_id, source_path = ('', entry['path'])
        sources.append({'root_id': root_id, 'path': source_path, 'kind': 'file', 'enumeration_completed': True, 'error': None, 'entries': [{'root_id': root_id, 'path': source_path, 'identity': entry['path'], 'format': entry['format'], 'source_stamp': entry['source_stamp'], 'metadata_snapshot': entry.get('metadata_snapshot')}]})
    now = datetime.now(UTC)
    task_id = str(uuid4())
    task = AssetTask(id=task_id, request_id=request['request_id'], request_fingerprint=fingerprint, image_import_plan={**request, 'files': files, 'publication': {'state': 'pending'}}, status='queued', sources=sources, storage_mode=request.get('storage_mode', 'managed'), classification={}, parameters={}, import_defaults_snapshot={}, notes=defaults.get('notes'), dataset_name=destination.get('name'), target_dataset_id=target_id, dataset_base_revision=destination.get('expected_revision'), dataset_id=None, enumeration_completed=True, retry_of_task_id=None, report={'destination': destination_context}, error=None, created_at=now, updated_at=now)
    session.add(task)
    task.image_import_plan = {**task.image_import_plan, 'root_task_id': task_id}
    session.flush()
    for position, (item, entry, source) in enumerate(zip(request['files'], entries, sources, strict=True)):
        session.add(AssetTaskItem(id=str(uuid4()), task_id=task.id, root_item_id=item['file_id'], retry_of_item_id=None, root_id=source['root_id'], source_path=source['path'], source_identity=entry['path'], position=position, status='queued', content_status='pending', metadata_status='pending', preview_status='pending', error=None, created_at=now, updated_at=now))
    session.flush()
    return ImageImportAcceptance(image_import_receipt(session, task), True)

def image_import_receipt(session, task, *, items_limit=50, items_offset=0):
    rows = _family_items(session, task)
    publication = deepcopy((task.image_import_plan or {}).get('publication', {'state': 'not_requested'}))
    positions = publication.pop('positions', {})
    published = set(publication.get('published_file_ids', []))
    states = {identity: (status, evidence) for identity, status, evidence in session.execute(select(Asset.id, Asset.calibration_status, Asset.calibration_evidence).where(Asset.id.in_([row.asset_id for row in rows if row.asset_id])))}
    items = []
    for row in rows:
        row_errors = ([deepcopy(row.error)] if row.error else []) + [deepcopy(error) for error in publication.get('errors', []) if error.get('file_id') == row.root_item_id or (not error.get('file_id') and row.root_item_id not in published and (row.content_status == 'available'))]
        if row.root_item_id in published:
            publication_status, calibration_binding_status = ('published', 'saved')
        elif publication.get('state') == 'conflict':
            publication_status, calibration_binding_status = ('conflict', 'pending')
        elif any((error.get('file_id') == row.root_item_id for error in publication.get('errors', []))):
            publication_status, calibration_binding_status = ('excluded', 'blocked')
        elif row.content_status != 'available' or row.metadata_status not in {'available', 'unsupported'}:
            publication_status, calibration_binding_status = ('not_ready', 'not_checked')
        else:
            publication_status, calibration_binding_status = ('pending', 'pending')
        declared = ((task.image_import_plan or {}).get('files') or {}).get(row.root_item_id, {})
        status, evidence = states.get(row.asset_id, (declared.get('calibration_status', 'Unknown'), {'source': 'user' if declared.get('calibration_reason') or declared.get('calibration_status', 'Unknown') != 'Unknown' else 'unknown', 'reason': declared.get('calibration_reason')}))
        items.append({'file_id': row.root_item_id, 'task_item_id': row.id, 'asset_id': row.asset_id, 'status': row.status, 'originals': row.content_status, 'metadata': row.metadata_status, 'previews': row.preview_status, 'member_position': positions.get(row.asset_id), 'error': row.error, 'publication_status': publication_status, 'calibration_binding_status': calibration_binding_status, 'calibration_status': status, 'calibration_evidence': evidence or {}, 'errors': row_errors})
    family = _task_family(session, task)
    active = any((member.status in {'queued', 'running', 'cancelling'} for member in family))
    return {'organization_recovery': (task.report or {}).get('organization_recovery'), 'destination': (task.report or {}).get('destination'), 'request_id': task.request_id, 'task_id': task.id, 'status': 'running' if active and task.status not in {'queued', 'running', 'cancelling'} else task.status, 'state': 'running' if active else 'needs_attention' if task.status != 'completed' else 'completed', 'stages': {'registration': {'total': len(rows), 'registered': sum((row.asset_id is not None for row in rows))}, 'originals': {'available': sum((row.content_status == 'available' for row in rows)), 'total': len(rows)}, 'metadata': {'available': sum((row.metadata_status == 'available' for row in rows)), 'total': len(rows)}, 'publication': publication, 'calibration': publication.get('calibration', {}), 'previews': {'available': sum((row.preview_status == 'available' for row in rows)), 'total': len(rows)}}, 'items': items[items_offset:items_offset + items_limit], 'items_total': len(rows), 'items_limit': items_limit, 'items_offset': items_offset, 'next_poll_seconds': 5 if active else None, 'error': task.error}

def get_image_import(session, request_id):
    task = session.scalar(select(AssetTask).where(AssetTask.request_id == str(request_id)))
    if task is None:
        raise not_found()
    return image_import_receipt(session, task)

def get_image_import_task(session, task_id, *, items_limit=50, items_offset=0):
    task = session.get(AssetTask, str(task_id))
    if task is None or not task.image_import_plan:
        from astrophotoflow.modules.data.imports.tasks import get_asset_task
        return get_asset_task(session, task_id, items_limit=items_limit, items_offset=items_offset)
    root = session.get(AssetTask, task.image_import_plan.get('root_task_id', task.id))
    return image_import_receipt(session, root, items_limit=items_limit, items_offset=items_offset)

def _task_family(session, root):
    return list(session.scalars(select(AssetTask).where((AssetTask.id == root.id) | (AssetTask.image_import_plan['root_task_id'].as_string() == root.id)).order_by(AssetTask.created_at, AssetTask.id)))

def _family_items(session, root):
    tasks = _task_family(session, root)
    latest = {}
    for item in session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id.in_([task.id for task in tasks])).order_by(AssetTaskItem.created_at, AssetTaskItem.id)):
        latest[item.root_item_id] = item
    order = {file_id: position for position, file_id in enumerate(root.image_import_plan['files'])}
    return sorted(latest.values(), key=lambda item: order[item.root_item_id])

def publish_image_import(session, task, *, expected_revision=None):
    """Publish only ready scientific members and their bindings in this transaction."""
    from astrophotoflow.modules.data.calibration.choices import patch_bindings
    from astrophotoflow.modules.data.calibration.service import apply_import_calibration, validate_calibration_bindings
    from astrophotoflow.modules.data.datasets.bindings import dataset_bindings
    from astrophotoflow.modules.data.datasets.calibration import require_subframe
    from astrophotoflow.modules.data.datasets.models import Dataset
    root_id = (task.image_import_plan or {}).get('root_task_id', task.id)
    root = session.get(AssetTask, root_id)
    plan = deepcopy(root.image_import_plan)
    destination = plan['destination']
    old_publication = plan.get('publication', {})
    published = set(old_publication.get('published_file_ids', []))
    candidates = [item for item in _family_items(session, root) if item.root_item_id not in published and item.content_status == 'available' and (item.metadata_status in {'available', 'unsupported'})]
    if not candidates:
        if old_publication.get('state') == 'pending':
            plan['publication'] = {**old_publication, 'state': 'blocked', 'errors': []}
            root.image_import_plan = plan
            return plan['publication']
        return old_publication
    dataset = None
    current_members = []
    defaults = {}
    if destination['mode'] != 'standalone':
        dataset = session.get(Dataset, root.target_dataset_id)
        if dataset is not None:
            required_revision = expected_revision if expected_revision is not None else old_publication.get('dataset_revision', destination.get('expected_revision'))
            if dataset.status != 'active' or dataset.revision != required_revision:
                raise ApiError(409, 'REVISION_CONFLICT', 'Imported originals are retained; reconcile the dataset before publication.', message_key='imported_originals_are_retained_reconcile_the_dataset_before_publication')
            current_members = list(session.scalars(select(DatasetMember).where(DatasetMember.dataset_id == dataset.id).order_by(DatasetMember.position)))
            defaults = dataset_bindings(dataset)
        elif destination['mode'] == 'append_dataset':
            raise ApiError(409, 'INVALID_REFERENCE', 'The destination dataset disappeared; imported originals are retained.', message_key='the_destination_dataset_disappeared_imported_originals_are_retained')
        else:
            defaults = patch_bindings({}, plan.get('calibration', {}))
    valid, diagnostics, errors = ([], {}, [])
    for item in candidates:
        file_plan = plan['files'][item.root_item_id]
        standalone = destination['mode'] == 'standalone'
        effective = patch_bindings({}, file_plan.get('calibration', {})) if standalone else defaults
        try:
            if not standalone:
                require_subframe(session.get(Asset, item.asset_id))
            check = validate_calibration_bindings(session, [item.asset_id], effective, accept_unknown=plan.get('accept_unknown', False))
        except ApiError as exc:
            errors.append({'file_id': item.root_item_id, 'asset_id': item.asset_id, 'code': exc.code, 'message': exc.message, 'fields': exc.fields})
            continue
        diagnostics[item.root_item_id] = check
        valid.append(item)
    publication = {**old_publication, 'state': 'blocked' if not valid else 'published', 'errors': errors, 'calibration': {'diagnostics': diagnostics, 'message': '关系已保存，尚未执行校准。'}}
    if valid and destination['mode'] == 'standalone':
        publication['bindings'] = [apply_import_calibration(session, item.asset_id, patch_bindings({}, plan['files'][item.root_item_id].get('calibration', {})), accept_unknown=plan.get('accept_unknown', False)) for item in valid]
        if len(publication['bindings']) == 1:
            publication['binding'] = publication['bindings'][0]
    elif valid:
        creating = dataset is None
        if dataset is None:
            dataset = Dataset(library_directory=(root.report or {}).get('library_directory'), id=root.target_dataset_id, name=destination['name'], notes=destination.get('notes'), revision=1, status='active')
            session.add(dataset)
            session.flush()
        ids = [member.asset_id for member in current_members]
        paths = {}
        for item in valid:
            if item.asset_id not in ids:
                ids.append(item.asset_id)
                paths[item.asset_id] = Path(item.source_path).name
        version = publish_dataset_members(session, dataset, ids, paths, calibration=defaults)
        if creating:
            dataset.revision = 1
        root.dataset_id = dataset.id
        publication.update(dataset_id=version.id, dataset_revision=dataset.revision, positions={member.asset_id: member.position for member in session.scalars(select(DatasetMember).where(DatasetMember.dataset_id == version.id))})
    publication['published_file_ids'] = list(dict.fromkeys([*old_publication.get('published_file_ids', []), *(item.root_item_id for item in valid)]))
    plan['publication'] = publication
    root.image_import_plan = plan
    if errors:
        root.report = {**(root.report or {}), 'dataset_publish_error': {'code': 'CALIBRATION_NOT_READY', 'files': errors}}
    else:
        root.report = {key: value for key, value in (root.report or {}).items() if key != 'dataset_publish_error'}
    session.flush()
    return publication

def settle_image_import(database, task_id):
    try:
        with database.write_session() as session:
            publish_image_import(session, session.get(AssetTask, task_id))
    except ApiError as exc:
        with database.write_session() as session:
            task = session.get(AssetTask, task_id)
            root = session.get(AssetTask, (task.image_import_plan or {}).get('root_task_id', task.id))
            plan = deepcopy(root.image_import_plan)
            plan['publication'] = {**plan.get('publication', {}), 'state': 'conflict', 'errors': [{'code': exc.code, 'message': exc.message, 'fields': exc.fields}]}
            root.image_import_plan = plan
            task.report = {**(task.report or {}), 'dataset_publish_error': {'code': exc.code, 'message': exc.message, 'fields': exc.fields}}

def finish_image_import(database, task_id):
    with database.write_session() as session:
        task = session.get(AssetTask, task_id)
        if task is None or not task.image_import_plan:
            return
        root = session.get(AssetTask, task.image_import_plan.get('root_task_id', task.id))
        if any((member.status in {'queued', 'running', 'cancelling'} for member in _task_family(session, root))):
            return
        rows = _family_items(session, root)
        failed = any((item.content_status != 'available' or item.metadata_status == 'failed' for item in rows))
        publication = root.image_import_plan.get('publication', {})
        failed |= publication.get('state') != 'published' or bool(publication.get('errors'))
        if root.status not in {'cancelled', 'interrupted'}:
            root.status = 'completed_with_errors' if failed and any((item.content_status == 'available' for item in rows)) else 'failed' if failed else 'completed'
        if not failed:
            root.report = {key: value for key, value in (root.report or {}).items() if key != 'dataset_publish_error'}

def retry_image_publication(session, task_id, body):
    task = session.get(AssetTask, str(task_id))
    if task is None or not task.image_import_plan:
        raise not_found()
    root = session.get(AssetTask, task.image_import_plan.get('root_task_id', task.id))
    request = _dump(body)
    if request['task_id'] != str(task_id):
        raise ApiError(422, 'INVALID_REFERENCE', 'Publication task_id does not match the requested import task.', message_key='publication_task_id_does_not_match_the_requested_import_task')
    fingerprint = _fingerprint(request)
    previous = (root.image_import_plan.get('publication_requests') or {}).get(request['request_id'])
    if previous:
        if previous['fingerprint'] != fingerprint:
            raise ApiError(409, 'IMPORT_REQUEST_CONFLICT', 'Publication request_id has different content.', message_key='publication_request_id_has_different_content')
        return image_import_receipt(session, root)
    if any((member.status in {'queued', 'running', 'cancelling'} for member in _task_family(session, root))):
        raise ApiError(409, 'TASK_STATE_CONFLICT', 'Wait for import originals before retrying publication.', message_key='wait_for_import_originals_before_retrying_publication')
    publish_image_import(session, root, expected_revision=request['expected_revision'])
    plan = deepcopy(root.image_import_plan)
    plan['publication_requests'] = {**plan.get('publication_requests', {}), request['request_id']: {'fingerprint': fingerprint}}
    root.image_import_plan = plan
    if not root.image_import_plan['publication'].get('errors'):
        root.report = {key: value for key, value in (root.report or {}).items() if key != 'dataset_publish_error'}
    rows = _family_items(session, root)
    publication = root.image_import_plan['publication']
    failed = publication.get('state') != 'published' or bool(publication.get('errors')) or any((item.content_status != 'available' or item.metadata_status not in {'available', 'unsupported'} for item in rows))
    if root.status not in {'cancelled', 'interrupted'}:
        root.status = 'completed_with_errors' if failed and any((item.content_status == 'available' for item in rows)) else 'failed' if failed else 'completed'
    session.flush()
    return image_import_receipt(session, root)
