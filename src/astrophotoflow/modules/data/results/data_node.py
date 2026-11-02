"""Concrete Data node execution; fixed inputs and checked results belong to data."""
import hashlib
import json

import numpy as np
from astropy.io import fits
from filelock import FileLock

from astrophotoflow.contracts.data_nodes import DataNodeResult, NativeDataExecute
from astrophotoflow.contracts.inputs import OutputLocator
from astrophotoflow.contracts.results import CheckedResult, CheckedResultMember, CheckedResultPort
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.results.records import (
    data_execution_directory,
    get_checked_result,
    read_data_execution,
    save_data_execution,
)
from astrophotoflow.modules.data.results.service import get_result_member, publish_checked_result, result_member_base
from astrophotoflow.modules.data.science.inputs import resolve_canvas_inputs
from astrophotoflow.modules.data.science.outputs import check_output


def _source_members(database, settings, reference, directory):
    if reference.kind == 'run_output':
        result = get_checked_result(settings,reference.run_id,reference.execution_id)
        if not 0 <= reference.output_index < len(result.ports) or result.ports[reference.output_index].type != 'APF_SCIENCE':
            raise ApiError(422,'INVALID_REFERENCE','Upstream port is not a science output.', message_key='data_upstream_port_not_science')
        port=result.ports[reference.output_index]
        indexes=[reference.member_index] if reference.member_index is not None else list(range(len(port.members)))
        members=[]
        for index in indexes:
            checked,member,_=get_result_member(settings,reference.run_id,reference.execution_id,reference.output_index,index,full=True)
            members.append({**member.model_dump(mode='json'),'checked':checked.model_dump(mode='json')})
        return members
    resolved = resolve_canvas_inputs(database, settings, reference, run_directory=directory)
    members = []
    for item in resolved.items:
        checked = check_output(settings, run_directory=item.read_path.parent, path=item.read_path, expected_format=item.format,
                               colour_layout=(item.scientific_metadata or {}).get('colour_layout'))
        checked = checked.model_copy(update={'scientific_metadata': {
            **(checked.scientific_metadata or {}), 'parameters': item.parameters,
            'equipment_snapshot': item.equipment_snapshot, 'classification': item.classification.model_dump(mode='json') if item.classification is not None else None,
        }})
        members.append({'checked': checked.model_dump(mode='json'), 'source_input': item.model_dump(mode='json'), 'name': item.read_path.name,
                        'selection': {'hdu_index': item.selection.hdu_index} if item.selection.kind == 'fits_hdu' else {},
                        'display': 'auto'})
    return members


def result_members(settings,run_id,execution_id):
    result=get_checked_result(settings,run_id,execution_id)
    return [{**member.model_dump(mode='json'),'view_base':result_member_base(run_id,execution_id,0,index)} for index,member in enumerate(result.ports[0].members)]


def execute_data_node(database, settings, body:NativeDataExecute)->DataNodeResult:
    directory = data_execution_directory(settings, body.run_id, body.execution_id)
    directory.mkdir(parents=True, exist_ok=True)
    payload = body.model_dump(mode='json')
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    with FileLock(str(directory / 'execution.lock')):
        path = directory / 'result.json'
        if path.exists():
            previous = read_data_execution(settings, body.run_id, body.execution_id)
            if previous['fingerprint'] != fingerprint:
                raise ApiError(409, 'DATA_EXECUTION_CONFLICT', 'Execution ID already belongs to another Data input.', message_key='data_execution_identity_conflict')
            if previous['state'] != 'completed':
                raise ApiError(409, 'DATA_EXECUTION_UNKNOWN', 'Previous execution did not complete. Inspect its record instead of replaying it.', message_key='data_execution_not_completed')
            return public_result(settings,previous)
        record = {**payload, 'fingerprint': fingerprint, 'state': 'preparing', 'output':None, 'error': None}
        members=[]
        save_data_execution(path, record)
        try:
            if body.reference is not None:
                if body.reference.kind == 'run_output' and body.reference.run_id != body.run_id:
                    raise ApiError(422, 'INVALID_REFERENCE', 'Upstream science result must belong to this native run.', message_key='data_upstream_prompt_mismatch')
                members = _source_members(database, settings, body.reference, directory)
                record['reference'] = body.reference.model_dump(mode='json')
            else:
                for index in range(body.image_count):
                    incoming = directory / f'input-{index:06}.npy'
                    pixels = np.load(incoming, mmap_mode='r', allow_pickle=False)
                    if pixels.dtype.name != body.input_dtype or pixels.ndim not in {2, 3} or pixels.ndim == 3 and pixels.shape[-1] != 3 or not all(pixels.shape):
                        raise ApiError(422, 'INVALID_IMAGE', 'IMAGE member must have the declared floating dtype and nonempty grayscale/RGB shape.', message_key='data_image_shape_invalid')
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
                    members.append({'checked': checked.model_dump(mode='json'), 'name': target.name,
                                              'selection': {'hdu_index': 0}, 'display': 'direct'})
                record['output'] = OutputLocator(kind='run_output', run_id=body.run_id,
                    execution_id=body.execution_id, output_index=0).model_dump(mode='json')
            if not members:
                raise ApiError(422, 'EMPTY_SCIENCE_OUTPUT', 'Data requires at least one complete member.', message_key='data_complete_member_required')
            result=CheckedResult(run_id=body.run_id,execution_id=body.execution_id,source_kind='data',
                ports=[CheckedResultPort(name='science',type='APF_SCIENCE',members=[CheckedResultMember.model_validate_json(json.dumps({key:value for key,value in member.items() if key!='view_base'})) for member in members])])
            publish_checked_result(settings,result)
            record['output']=OutputLocator(kind='run_output',run_id=body.run_id,execution_id=body.execution_id,output_index=0).model_dump(mode='json')
            record['state']='completed'
            save_data_execution(path, record)
            return public_result(settings,record)
        except Exception as exc:
            record['state'], record['error'] = 'failed', str(exc)
            save_data_execution(path, record)
            raise


def public_result(settings, record):
    members=result_members(settings,record["run_id"],record["execution_id"]) if record["state"]=="completed" else []
    value = {key: record[key] for key in ('run_id', 'execution_id', 'node_id', 'workflow_id', 'state', 'error', 'input_bindings')} | {
        'reference': record.get('reference') or record.get('output'), 'output':record.get('output'),
        'members': [{'name': member['name'], 'view_base': member['view_base'], 'selection': member['selection'],
                     'format': member['checked']['format'], 'metadata': member['checked'].get('scientific_metadata'),
                     'byte_size': member['checked']['byte_size']} for member in members]}


    return DataNodeResult.model_validate_json(json.dumps(value))


def get_data_result(settings,run_id,execution_id)->DataNodeResult:
    return public_result(settings,read_data_execution(settings,run_id,execution_id))
