"""Non-ingesting source inspection. Manifests are local workspace data, not assets."""
import json
import logging
import os
import re
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4

from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.core.localization import localized_error, workspace_locale
from astrophotoflow.modules.data.formats.fits import PARSER_VERSION, inspect_fits
from astrophotoflow.modules.data.formats.xisf import inspect_xisf

from ..files import format_for_path

GROUP_KEYS = ('target_name', 'frame_type', 'frame_class', 'filter_name', 'exposure_seconds',
              'INSTRUME', 'TELESCOP', 'gain', 'offset', 'iso', 'binning_x', 'binning_y',
              'cfa_pattern', 'sensor_temperature_c', 'sensor_temperature_setpoint_c')


def source_stamp(path):
    stat = path.stat()
    return {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}


def read_manifest(settings, scan_id):
    path = settings.data_dir / 'import-inspections' / (str(UUID(str(scan_id))) + '.json')
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise not_found() from exc


def _hints(path):
    text = path.as_posix().casefold()
    result = {}
    target = re.search(r'(?<![a-z0-9])((?:m|ngc|ic)[ _-]?\d+)(?!\d)', text)
    if target:
        result['target_name'] = re.sub(r'[ _-]', '', target[1]).upper()
    frame = re.search(r'(?<![a-z])(dark[ _-]?flat|flat[ _-]?dark|light|dark|bias|flat)(?![a-z])', text)
    if frame:
        result['frame_type'] = 'dark_flat' if 'flat' in frame[1] and 'dark' in frame[1] else frame[1]
    if re.search(r'(?<![a-z])master(?![a-z])', text):
        result['frame_class'] = 'masterframe'
    exposure = re.search(r'(?<![\d.])(\d+(?:\.\d+)?)\s*(?:s|sec)(?![a-z])', text)
    if exposure:
        result['exposure_seconds'] = float(exposure[1])
    filt = re.search(r'(?<![a-z])(ha|oiii|sii|l|r|g|b)(?![a-z])', text)
    if filt:
        result['filter_name'] = filt[1].upper()
    return result


def _metadata(path, category, snapshots=None):
    if category == 'xisf':
        parsed = inspect_xisf(path)
        if snapshots is not None:
            snapshots.update({'parser_version': 'xisf-1', 'parsed_parameters': deepcopy(parsed), 'hdus': []})
        return {key: value for key, value in parsed.items() if key not in {'xisf_fits_keywords', 'preview_layout'}}
    if category != 'fits':
        return {}
    inspected = inspect_fits(path)
    if snapshots is not None:
        snapshots.update({'parser_version': PARSER_VERSION, **deepcopy(inspected)})
    parsed = inspected['parsed_parameters']
    for hdu in inspected['hdus']:
        if hdu['hdu_index'] == 0 or hdu['is_selected']:
            cards = {card['keyword']: card['value'] for card in hdu['header_cards']}
            for key in ('DATE-OBS', 'TIMESYS', 'INSTRUME', 'TELESCOP'):
                if cards.get(key) is not None:
                    parsed[key] = cards[key]
    return parsed


def inspect_sources(settings, body, *, include_groups=True):
    files, excluded, issues, roots = [], [], [], []
    seen_dirs, seen_files = set(), set()
    data_root = settings.data_dir.resolve()

    def visit(path, boundary, relative):
        try:
            # Never follow symlinks/junctions out of the explicitly selected source.
            actual = path.resolve(strict=True)
            if actual == data_root or data_root in actual.parents:
                raise ValueError('Workspace managed data cannot be an inspection source.')
            if actual != boundary and boundary not in actual.parents:
                raise ValueError('Source link leaves the selected folder.')
            if actual.is_dir():
                if actual in seen_dirs:
                    return
                seen_dirs.add(actual)
                with os.scandir(actual) as iterator:
                    children = sorted((Path(entry.path) for entry in iterator), key=lambda item: (item.name.casefold(), item.name))
                for child in children:
                    if child.is_dir() and not body.recursive:
                        excluded.append({'path': str(child), 'reason': 'SUBDIRECTORY_NOT_SELECTED'})
                    else:
                        visit(child, boundary, relative / child.name)
                return
            if actual in seen_files:
                return
            seen_files.add(actual)
            category = format_for_path(actual)
            if not actual.is_file() or category is None:
                excluded.append({'path': str(path), 'reason': 'UNSUPPORTED_FORMAT'})
                return
            before = source_stamp(actual)
            entry = {'id': str(uuid4()), 'path': str(actual), 'relative_path': relative.as_posix(),
                     'format': category, 'source_stamp': before, 'observed': {}, 'hints': _hints(relative),
                     'issues': [], 'metadata_status': 'unsupported'}
            try:
                snapshot = {}
                entry['observed'] = _metadata(actual, category, snapshot)
                if snapshot:
                    entry['metadata_snapshot'] = snapshot
                if category in {'fits', 'xisf'}:
                    entry['metadata_status'] = 'available'
            except Exception as exc:
                logging.getLogger(__name__).exception('Metadata inspection failed path=%s', path)
                entry['metadata_status'] = 'failed'
                entry['issues'].append({'code': 'METADATA_UNREADABLE', 'message': str(exc)})
            if source_stamp(actual) != before:
                entry['issues'].append(localized_error(workspace_locale(settings.workspace), 'SOURCE_CHANGED', 'inspection_source_changed_reading').model_dump(exclude={'fields'}))
            observed = {**entry['observed'], **entry['observed'].get('classification', {})}
            suggested = {}
            for key in (*GROUP_KEYS, 'DATE-OBS'):
                value = observed.get(key)
                hint = entry['hints'].get(key)
                suggested[key] = {'value': value if value is not None else hint,
                                  'source': 'header' if value is not None else 'name' if hint is not None else 'unknown'}
                if include_groups and value is not None and hint is not None and str(value).casefold().replace(' ', '') != str(hint).casefold().replace(' ', ''):
                    entry['issues'].append({'code': 'HEADER_NAME_CONFLICT', 'field': key, 'header': value, 'name': hint})
            if include_groups:
                entry['suggested'] = suggested
            else:
                # File discovery reports observations; grouping belongs to the caller.
                entry.pop('hints')
            files.append(entry)
        except (OSError, ValueError) as exc:
            issues.append({'path': str(path), 'code': 'SOURCE_UNAVAILABLE', 'message': str(exc)})

    for text in body.paths:
        path = Path(text)
        if not path.is_absolute():
            raise ApiError(422, 'VALIDATION_ERROR', 'Inspection requires absolute local paths.', message_key='inspection_absolute_paths_required')
        roots.append(str(path))
        visit(path, path.resolve(), Path(path.name))
    groups = {}
    group_keys = GROUP_KEYS
    for entry in files if include_groups else ():
        key = json.dumps({name: entry['suggested'][name]['value'] for name in group_keys}, sort_keys=True)
        if key not in groups:
            values = json.loads(key)
            groups[key] = {'id': str(uuid4()), 'name': ' · '.join(str(value) for value in values.values() if value is not None) or 'Unknown',
                           'suggested': {name: entry['suggested'][name] for name in group_keys}, 'member_ids': [], 'issue_count': 0,
                           'capture_dates': {'earliest': None, 'latest': None, 'unknown_count': 0,
                                             'basis': 'raw DATE-OBS header values, not a timezone-normalized observing night', 'time_systems': []},
                           'metadata_status_counts': {}}
        group = groups[key]
        entry['group_id'] = group['id']
        group['member_ids'].append(entry['id'])
        group['issue_count'] += len(entry['issues'])
        counts = group['metadata_status_counts']
        counts[entry['metadata_status']] = counts.get(entry['metadata_status'], 0) + 1
        captured = entry['observed'].get('DATE-OBS')
        dates = group['capture_dates']
        system = str(entry['observed'].get('TIMESYS', 'unspecified'))
        if system not in dates['time_systems']:
            dates['time_systems'].append(system)
        if captured is None:
            dates['unknown_count'] += 1
        else:
            # Preserve header strings/timezone uncertainty instead of guessing a local observing night.
            captured = str(captured)
            dates['earliest'] = min(dates['earliest'], captured) if dates['earliest'] else captured
            dates['latest'] = max(dates['latest'], captured) if dates['latest'] else captured
    manifest = {'scan_id': str(uuid4()), 'recursive': body.recursive, 'roots': roots,
                'files': files, 'groups': list(groups.values()), 'excluded': excluded, 'issues': issues}
    directory = settings.data_dir / 'import-inspections'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / (manifest['scan_id'] + '.json')).open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, ensure_ascii=False, allow_nan=False)
    return manifest


def inspection_summary(manifest):
    groups = [{**{key: value for key, value in group.items() if key != 'member_ids'}, 'count': len(group['member_ids'])}
              for group in manifest['groups']]
    issues = manifest['issues'] + [{'member_id': item['id'], **issue} for item in manifest['files'] for issue in item['issues']]
    return {'scan_id': manifest['scan_id'], 'recursive': manifest['recursive'], 'roots': manifest['roots'],
            'file_count': len(manifest['files']), 'excluded_count': len(manifest['excluded']),
            'groups': groups[:10], 'groups_total': len(groups), 'issues': issues[:20], 'issues_total': len(issues)}




def get_source_inspection(settings, scan_id):
    return inspection_summary(read_manifest(settings, scan_id))


def list_inspection_entries(settings, scan_id, *, limit=50, offset=0, group_id=None, kind='files'):
    if kind not in {'files', 'groups', 'excluded', 'issues'}:
        raise ApiError(422, 'VALIDATION_ERROR', 'kind must be files, groups, excluded or issues.', message_key='inspection_entry_kind_invalid')
    manifest = read_manifest(settings, scan_id)
    items = manifest[kind]
    if kind == 'issues':
        items = items + [{'member_id': item['id'], 'group_id': item.get('group_id'), 'path': item['path'], **issue}
                         for item in manifest['files'] for issue in item['issues']]
    if kind == 'groups':
        items = [{**{key: value for key, value in group.items() if key != 'member_ids'}, 'count': len(group['member_ids'])} for group in items]
    if group_id is not None:
        items = [item for item in items if item.get('group_id', item.get('id')) == str(group_id)]
    items = [{key: value for key, value in item.items() if key != 'metadata_snapshot'} for item in items]
    return {'items': items[offset:offset + limit], 'total': len(items), 'limit': limit, 'offset': offset}
