"""Actual Data node execution records, independent of software invocation records."""
import hashlib
import json
from uuid import UUID

import numpy as np
from astropy.io import fits
from fastapi import APIRouter, Depends, Request
from filelock import FileLock

from astrophotoflow.contracts.data_nodes import NativeDataExecute, DataNodeResult
from astrophotoflow.contracts.inputs import CheckedOutput, OutputLocator
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.core.http import authenticate, TaskAdmission, ERROR_RESPONSES
from astrophotoflow.modules.data.public import check_output, resolve_canvas_inputs

router = APIRouter(dependencies=[Depends(authenticate)], responses=ERROR_RESPONSES)


def result_directory(settings, run_id, execution_id):
    return settings.workspace / 'runs' / str(UUID(str(run_id))) / 'data' / str(UUID(str(execution_id)))


def read_result(settings, run_id, execution_id):
    path = result_directory(settings, run_id, execution_id) / 'result.json'
    if not path.is_file(): raise not_found()
    return json.loads(path.read_text(encoding='utf-8'))


def _save(path, value):
    part = path.with_suffix('.part')
    part.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    part.replace(path)


def _source_members(database, settings, reference, directory):
    if reference.kind == 'run_output':
        if reference.node_execution_id.startswith('data:'):
            value = read_result(settings, reference.run_id, reference.node_execution_id.removeprefix('data:'))
            if value['state'] != 'completed':
                raise ApiError(409, 'OUTPUT_NOT_READY', 'Upstream Data result is not completed.')
            members = value['members']
            if reference.output_index != 0:
                raise ApiError(422, 'INVALID_REFERENCE', 'Data has only one science output.')
            if reference.member_index is not None:
                if reference.member_index >= len(members): raise not_found()
                members = [members[reference.member_index]]
            return members
        from .software_calls import _record_ports
        matches = []
        for path in (settings.workspace / 'runs' / str(reference.run_id) / 'siril').glob('*.json'):
            value = json.loads(path.read_text(encoding='utf-8'))
            if value['request']['node_id'] == reference.node_execution_id and value['state'] == 'completed':
                matches.append((path, value))
        if len(matches) != 1:
            raise ApiError(409, 'OUTPUT_NOT_READY', 'Upstream output must identify one completed execution.')
        path, value = matches[0]
        ports = _record_ports(value)
        if reference.output_index >= len(ports) or ports[reference.output_index]['type'] != 'APF_SCIENCE':
            raise ApiError(422, 'INVALID_REFERENCE', 'Upstream port is not a science output.')
        port = ports[reference.output_index]
        indexes = [reference.member_index] if reference.member_index is not None else list(range(len(port['files'])))
        if any(index >= len(port['files']) for index in indexes): raise not_found()
        from .software_calls import _checked_file
        members = []
        for index in indexes:
            checked, _, _ = _checked_file(settings, reference.run_id, UUID(path.stem), reference.output_index, index, full=True)
            base = f'/astrophotoflow/api/v1/runs/{reference.run_id}/calls/{path.stem}/outputs/{reference.output_index}/members/{index}'
            members.append({'checked': checked.model_dump(mode='json'), 'name': checked.path.name,
                            'view_base': base, 'selection': {}, 'display': value.get('output_display', 'direct')})
        return members
    resolved = resolve_canvas_inputs(database, settings, reference, run_directory=directory)
    members = []
    for item in resolved.items:
        checked = check_output(settings, run_directory=item.read_path.parent, path=item.read_path, expected_format=item.format,
                               colour_layout=(item.scientific_metadata or {}).get('colour_layout'))
        checked = checked.model_copy(update={'scientific_metadata': {
            **(checked.scientific_metadata or {}), 'parameters': item.parameters,
            'equipment_snapshot': item.equipment_snapshot, 'classification': item.classification.model_dump(mode='json'),
        }})
        base = f'/astrophotoflow/api/v1/library/assets/{item.asset_id}/versions/{item.asset_version_id}/previews'
        members.append({'checked': checked.model_dump(mode='json'), 'name': item.read_path.name,
                        'view_base': base, 'selection': {'hdu_index': item.selection.hdu_index} if item.selection.kind == 'fits_hdu' else {},
                        'display': 'auto'})
    return members


def checked_member(settings, record, index):
    if record['state'] != 'completed' or not 0 <= index < len(record['members']):
        raise ApiError(409, 'OUTPUT_NOT_READY', 'No completed full-resolution member is available.')
    member = record['members'][index]
    previous = CheckedOutput.model_validate_json(json.dumps(member['checked']))
    checked = check_output(settings, run_directory=previous.run_directory, path=previous.path, expected_format=previous.format,
                           colour_layout=(previous.scientific_metadata or {}).get('colour_layout'))
    if (checked.content_hash, checked.byte_size) != (previous.content_hash, previous.byte_size):
        raise ApiError(409, 'SOURCE_CHANGED', 'Data result changed after execution; it cannot be saved or exported.')
    return checked


def execute_data(database, settings, body):
    directory = result_directory(settings, body.run_id, body.execution_id)
    directory.mkdir(parents=True, exist_ok=True)
    payload = body.model_dump(mode='json')
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    with FileLock(str(directory / 'execution.lock')):
        path = directory / 'result.json'
        if path.exists():
            previous = read_result(settings, body.run_id, body.execution_id)
            if previous['fingerprint'] != fingerprint:
                raise ApiError(409, 'DATA_EXECUTION_CONFLICT', 'Execution ID already belongs to another Data input.')
            if previous['state'] != 'completed':
                raise ApiError(409, 'DATA_EXECUTION_UNKNOWN', 'Previous execution did not complete. Inspect its record instead of replaying it.')
            return public_result(previous)
        record = {**payload, 'fingerprint': fingerprint, 'state': 'preparing', 'members': [], 'error': None}
        _save(path, record)
        try:
            if body.reference is not None:
                if body.reference.kind == 'run_output' and body.reference.run_id != body.run_id:
                    raise ApiError(422, 'INVALID_REFERENCE', 'Upstream science result must belong to this native run.')
                record['members'] = _source_members(database, settings, body.reference, directory)
                record['output'] = body.reference.model_dump(mode='json')
            else:
                for index in range(body.image_count):
                    incoming = directory / f'input-{index:06}.npy'
                    pixels = np.load(incoming, mmap_mode='r', allow_pickle=False)
                    if pixels.dtype.name != body.input_dtype or pixels.ndim not in {2, 3} or pixels.ndim == 3 and pixels.shape[-1] != 3 or not all(pixels.shape):
                        raise ApiError(422, 'INVALID_IMAGE', 'IMAGE member must have the declared floating dtype and nonempty grayscale/RGB shape.')
                    dtype = 'float32' if body.input_dtype == 'float16' else body.input_dtype
                    header = fits.Header()
                    header['APFSRC'] = 'native IMAGE tensor'
                    header['APFDTYPE'] = body.input_dtype
                    array = np.asarray(pixels, dtype=dtype)
                    if array.ndim == 3:
                        array = np.moveaxis(array, -1, 0)
                        header['CTYPE3'] = 'RGB'
                    target = directory / f'image-{index + 1:06}.fits'
                    fits.PrimaryHDU(array, header).writeto(target, overwrite=False)
                    checked = check_output(settings, run_directory=directory, path=target, expected_format='fits',
                                           colour_layout='planar' if pixels.ndim == 3 else None)
                    base = f'/astrophotoflow/api/v1/runs/{body.run_id}/calls/{body.execution_id}/outputs/0/members/{index}'
                    record['members'].append({'checked': checked.model_dump(mode='json'), 'name': target.name,
                                              'view_base': base, 'selection': {'hdu_index': 0}, 'display': 'direct'})
                record['output'] = OutputLocator(kind='run_output', run_id=body.run_id,
                    node_execution_id='data:' + str(body.execution_id), output_index=0).model_dump(mode='json')
            if not record['members']:
                raise ApiError(422, 'EMPTY_SCIENCE_OUTPUT', 'Data requires at least one complete member.')
            for index in range(len(record['members'])):
                # Set completion only after every member is known, then validate the frozen bytes.
                record['state'] = 'completed'
                checked_member(settings, record, index)
            _save(path, record)
            return public_result(record)
        except Exception as exc:
            record['state'], record['error'] = 'failed', str(exc)
            _save(path, record)
            raise


def public_result(record):
    return {key: record[key] for key in ('run_id', 'execution_id', 'node_id', 'workflow_id', 'state', 'error', 'input_bindings')} | {
        'reference': record.get('output'),
        'members': [{'name': member['name'], 'view_base': member['view_base'], 'selection': member['selection'],
                     'format': member['checked']['format'], 'metadata': member['checked'].get('scientific_metadata'),
                     'byte_size': member['checked']['byte_size']} for member in record['members']]}


@router.post('/internal/native/data', response_model=DataNodeResult)
def native_data(body: NativeDataExecute, request: Request, admission: TaskAdmission):
    return execute_data(request.app.state.database, request.app.state.settings, body)


@router.get('/api/v1/data-nodes/{run_id}/{execution_id}', response_model=DataNodeResult)
def get_data(run_id: UUID, execution_id: UUID, request: Request):
    return public_result(read_result(request.app.state.settings, run_id, execution_id))
