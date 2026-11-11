"""Native software use cases assembled from public business capabilities."""
import asyncio
import hashlib
import json
import logging
from contextlib import nullcontext

from astrophotoflow.contracts.bundles import AnalysisResult, MediaPosition
from astrophotoflow.contracts.inputs import OutputLocator
from astrophotoflow.contracts.results import CheckedResult, CheckedResultMember, CheckedResultPort
from astrophotoflow.contracts.software import (
    NativeBundleCall,
    RunOutputMember,
    RunOutputPort,
    SoftwareCallResult,
    SoftwareInvocation,
    bundle_data_kind,
)
from astrophotoflow.contracts.software_calls import NativeResultImage, SoftwareCallBundle, SoftwareCallRecord
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import error_message, exception_error, workspace_locale
from astrophotoflow.modules.data.public import (
    check_output,
    get_checked_result,
    checked_output_calibration,
    calibration_metadata,
    publish_checked_result,
    read_result_analysis,
    render_output_preview,
    resolve_canvas_input_groups,
    resolve_result_inputs,
    result_member_base,
)
from astrophotoflow.modules.nodes.public import get_definition
from astrophotoflow.modules.software.public import (
    cancel_operation,
    find_software_call,
    get_bundle_metadata,
    get_package,
    inspect_operation,
    invoke_operation,
    effective_calibration_effect,
    list_software_call_records,
    read_software_call,
    save_software_call,
    unfinished_software_calls,
    validate_parameters,
)


async def observe_software_call(settings, active, prompt_id, call_id):
    owned_before_read = call_id in active
    record = await asyncio.to_thread(read_software_call, settings, prompt_id, call_id)
    if owned_before_read and call_id not in active:
        # Completion can publish a terminal record while the threaded read returns
        # its earlier snapshot. Read the owner's final facts; never overwrite them.
        return await asyncio.to_thread(read_software_call, settings, prompt_id, call_id)
    if owned_before_read or call_id in active:
        return record
    orphan = record.state in {'starting', 'running'} and call_id not in active
    if orphan or record.state == 'unknown':
        record.state = 'unknown'
        if record.invocation is not None and record.observation is not None:
            observed = await inspect_operation(settings, record.invocation,
                                               record.observation)
            record.observation = observed
        save_software_call(settings,prompt_id,call_id,record)
    return record


def _fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _input_token(invocation: SoftwareInvocation | None, *, positions: bool = False) -> str | None:
    if invocation is None:
        return None
    groups = [
        {name: [((item.position_token if positions and item.kind == "run_output" else None) or item.content_hash,
                 item.selection.model_dump(mode="json"), item.reference_index) for item in members]
         for name, members in inputs.items()}
        for inputs in (invocation.inputs, invocation.supporting_inputs)
    ]
    return _fingerprint(groups)


def _run_output_port(record, port, prompt_id, call_id, index):
    output_name = record.definition.execution.outputs[port.name]
    definition = next(output for output in record.operation.outputs if output.name == output_name)
    members = []
    for position, member in enumerate(port.members):
        metadata = member.checked.scientific_metadata or {}
        width, height = metadata.get("width"), metadata.get("height")
        shape = metadata.get("shape") or []
        if len(shape) == 2:
            height, width = shape
        elif len(shape) == 3 and metadata.get("colour_layout") == "planar":
            _, height, width = shape
        elif len(shape) == 3 and metadata.get("colour_layout") == "interleaved":
            height, width, _ = shape
        base = result_member_base(prompt_id, call_id, index, position)
        members.append(RunOutputMember(
            name=member.name, format=member.checked.format, view_base=base, file_url=base + '/file',
            width=width, height=height,
            frame_count=metadata.get("frame_count"), hdu_index=metadata.get("selected_hdu"),
            content_hash=member.checked.content_hash, position_token=member.position_token,
        ))
    kind = definition.data_kind or bundle_data_kind(port.type, definition.formats)
    if definition.data_kind is None and kind == "image":
        if members and all(member.format == "video" for member in members):
            kind = "video"
        elif any((member.frame_count or 1) > 1 for member in members) or any(
            member.name.lower().endswith(".seq") for member in port.supporting
        ):
            kind = "sequence"
    return RunOutputPort(name=port.name, type=port.type, data_kind=kind,
                         role=definition.role, operation_output=output_name, members=members)


def _verify_analysis_positions(analyses: list[AnalysisResult], definition, ports: list[CheckedResultPort]) -> None:
    outputs = {definition.execution.outputs[port.name]: port.members for port in ports if port.type == "APF_SCIENCE"}
    for analysis in analyses:
        if analysis.output is None:
            continue
        members = outputs.get(analysis.output)
        if not members:
            raise ValueError(f"Analysis refers to an unavailable media output: {analysis.output}.")
        positions = list(analysis.row_positions or [])
        if analysis.member_index is not None or analysis.frame_index is not None:
            positions.append(MediaPosition(member_index=analysis.member_index or 0, frame_index=analysis.frame_index))
        for position in positions:
            if position.member_index >= len(members):
                raise ValueError("Analysis refers to an unavailable result member.")
            metadata = members[position.member_index].checked.scientific_metadata or {}
            frames = metadata.get("frame_count")
            if position.frame_index is not None and frames is not None and position.frame_index >= frames:
                raise ValueError("Analysis refers to an unavailable result frame.")


def _call_summary(settings, record: SoftwareCallRecord, prompt_id, call_id) -> SoftwareCallResult:
    base = f'/astrophotoflow/api/v1/runs/{prompt_id}/calls/{call_id}'
    result = get_checked_result(settings, prompt_id, call_id) if record.result_registered else None
    ports = [_run_output_port(record, port, prompt_id, call_id, index)
             for index, port in enumerate(result.ports)] if result else []
    editor_values = {
        parameter.name: value for parameter in record.operation.parameters
        if parameter.editor is not None and (value := parameter.editor_value(record.parameters.get(parameter.name))) is not None
    }
    return SoftwareCallResult(prompt_id=prompt_id, call_id=call_id, log_url=base + '/log',
        node_id=record.request.node_id, state=record.state,
        workflow_id=record.request.workflow_id, calculation_signature=record.request.calculation_signature,
        package_id=record.operation.package_id, software_version=record.operation.version,
        bundle_version=record.bundle.version, bundle_commit=record.bundle.commit,
        operation_id=record.operation.operation_id, definition_token=record.request.definition_token,
        development_source=record.bundle.development_source, ports=ports,
        preview_error=record.preview_error, observation=record.observation,
        error=record.error or (record.result.error if record.result else None),
        input_token=_input_token(record.invocation), editor_values=editor_values)


def _binding(settings, body):
    saved = get_definition(settings.workspace, body.definition_id)
    if saved.content_token != body.definition_token:
        raise ApiError(409, "NODE_CONTENT_CONFLICT", "节点定义已变化，请重新加载节点。", message_key='the_node_definition_has_changed_reload_the_node')
    binding = saved.definition.execution
    if set(body.parameters) != {p.name for p in saved.definition.parameters}:
        raise ApiError(422, "VALIDATION_ERROR", "节点参数与定义不一致。", message_key='node_parameters_do_not_match_the_definition')
    values = {name: body.parameters[source.name] if source.kind == "parameter" else source.value for name, source in binding.parameters.items()}
    operation = validate_parameters(settings, binding.package_id, binding.operation_id, values)
    return saved.definition, operation, values


def _references(definition, body, operation):
    references = body.inputs
    if not set(references).issubset({port.name for port in definition.inputs}):
        raise ApiError(422, 'INVALID_REFERENCE', '输入端口与节点定义不匹配。', message_key='input_ports_do_not_match_the_node_definition')
    result = {name: references[port] for name, port in definition.execution.inputs.items() if port in references}
    if any(item.required and item.name not in result for item in operation.inputs):
        raise ApiError(422, 'INVALID_REFERENCE', '节点缺少必要输入。', message_key='a_required_node_input_is_missing')
    for item in operation.inputs:
        if item.name in result and isinstance(result[item.name], list) != item.multiple_connections:
            raise ApiError(422, 'INVALID_REFERENCE', '输入连接数量形式与端口定义不匹配。', message_key='the_input_connection_cardinality_does_not_match_the_port_definition')
    return result


async def execute_native_call(database, settings, body: NativeBundleCall, *, admission_lock: asyncio.Lock | None = None):
    record = read_software_call(settings, body.prompt_id, body.call_id)
    work = settings.workspace / "runs" / str(body.prompt_id) / "work" / str(body.call_id)
    try:
        async with admission_lock if admission_lock is not None else nullcontext():
            definition = record.definition
            operation = record.operation
            parameters = record.parameters
            reference_groups = _references(definition, body, operation)
            current = {}
            for name, reference_value in reference_groups.items():
                expected = next(item for item in operation.inputs if item.name == name)
                for group_index, reference in enumerate(reference_value if isinstance(reference_value, list) else [reference_value]):
                    if reference.kind != 'run_output':
                        if expected.type not in {'APF_SCIENCE', 'APF_FILE'}:
                            raise ApiError(422, 'INVALID_REFERENCE', '该端口需要本次运行中已固定的文件输出。', message_key='this_port_requires_a_file_output_fixed_within_this_run')
                        current[f'{name}/{group_index}'] = (reference, expected.colour_layout)
            preparation = asyncio.create_task(asyncio.to_thread(resolve_canvas_input_groups, database, settings, current,
                                               run_directory=work.parent / (str(body.call_id) + '-inputs')))
            try:
                prepared = await asyncio.shield(preparation)
            except asyncio.CancelledError:
                # A cancelled coroutine must keep admission until its file reader stops.
                await asyncio.gather(preparation, return_exceptions=True)
                raise
            inputs, supporting = {}, {}
            for name, reference_value in reference_groups.items():
                expected = next(item for item in operation.inputs if item.name == name)
                inputs[name], supporting[name] = [], []
                for group_index, reference in enumerate(reference_value if isinstance(reference_value, list) else [reference_value]):
                    if reference.kind == 'run_output':
                        items, supporting_items = await asyncio.to_thread(resolve_result_inputs, settings, body.prompt_id, reference, expected.type)
                    else:
                        resolved = prepared[f'{name}/{group_index}']
                        items, supporting_items = resolved.items, []
                    inputs[name].extend(item.model_copy(update={'reference_index': group_index}) for item in items)
                    supporting[name].extend(item.model_copy(update={'reference_index': group_index}) for item in supporting_items)
            invocation = SoftwareInvocation(
                run_id=body.prompt_id, node_execution_id=body.node_id, call_id=body.call_id,
                package_id=operation.package_id, version=operation.version, operation_id=operation.operation_id, operation_content_token=operation.content_token,
                bundle_commit=record.bundle.commit,
                development_source=get_package(settings, operation.package_id).development_source,
                inputs=inputs, supporting_inputs=supporting, parameters=parameters,
                work_directory=work,
            )
            record.invocation = invocation
            if invocation.development_source is not None:
                record.bundle.development_source = invocation.development_source

            save_software_call(settings, body.prompt_id, body.call_id, record)

        async def observe(observation):
            record.state = 'running' if observation.state == 'completed' else observation.state
            record.observation = observation
            save_software_call(settings,body.prompt_id,body.call_id,record)

        result = await invoke_operation(settings, invocation, observe)
        record.result = result
        record.state = "running" if result.state == "completed" else result.state
        save_software_call(settings,body.prompt_id,body.call_id,record)
        if result.state == "completed":
            preview_directory = settings.workspace / "output" / "apf-siril" / str(body.prompt_id) / str(body.call_id)
            preview_directory.mkdir(parents=True, exist_ok=True)
            registered_ports=[]
            analyses = []
            # A program may rewrite FITS headers on each run. Bind coordinates
            # to the same producer, inputs, parameters and checked pixel layout.
            position_context = _fingerprint([
                body.workflow_id.hex if body.workflow_id else None, body.node_id,
                body.definition_token, operation.content_token, record.bundle.commit,
                invocation.development_source.fingerprint if invocation.development_source else None,
                _input_token(invocation, positions=True), parameters,
            ])
            for index, port in enumerate(definition.outputs):
                output_name = definition.execution.outputs[port.name]
                output_definition = next(item for item in operation.outputs if item.name == output_name)
                checked_files, checked_supporting = [], []
                for produced_files, checked_group in [(result.outputs[output_name], checked_files),
                                                      (result.supporting_outputs.get(output_name, []), checked_supporting)]:
                    for produced in produced_files:
                        checked = await asyncio.to_thread(check_output, settings, run_directory=work,
                                                          path=produced.path, expected_format=produced.format,
                                                          allow_empty=produced.allow_empty,
                                                          expected_frames=produced.frame_count,
                                                          colour_layout=output_definition.colour_layout if produced.format == 'fits' else None)
                        checked_group.append(checked)
                        if checked_group is checked_files and port.type == 'APF_ANALYSIS':
                            analyses.extend(await asyncio.to_thread(read_result_analysis, checked.path))
                effect = effective_calibration_effect(operation, parameters)
                for position, checked in enumerate(checked_files):
                    calibration, source = checked_output_calibration(
                        effect, invocation.inputs, output_name=output_name, position=position,
                        output_count=len(checked_files),
                        call={'run_id': str(body.prompt_id), 'call_id': str(body.call_id),
                              'package_id': operation.package_id, 'version': operation.version,
                              'operation_id': operation.operation_id, 'content_token': operation.content_token},
                        parameters=parameters,
                    )
                    checked_files[position] = checked.model_copy(update={'scientific_metadata': {
                        **(checked.scientific_metadata or {}), **calibration_metadata(calibration, source),
                    }})
                registered_ports.append(CheckedResultPort(name=port.name,type=port.type,
                    members=[CheckedResultMember(
                        checked=item, name=item.path.name, display=record.output_display,
                        position_token=_fingerprint([position_context, output_name, position,
                            [(item.scientific_metadata or {}).get(key)
                             for key in ("width", "height", "shape", "selected_hdu", "frame_hdus", "frame_count", "colour_layout")]])
                        if port.type == "APF_SCIENCE" else None,
                    ) for position, item in enumerate(checked_files)],
                    supporting=[CheckedResultMember(checked=item, name=item.path.name, display=record.output_display) for item in checked_supporting]))
                record.outputs.append(OutputLocator(kind='run_output', run_id=body.prompt_id,
                    execution_id=body.call_id, output_index=index))
                if port.type == 'APF_SCIENCE' and checked_files:
                    try:
                        filename = f'preview-{index}.jpg'
                        first = result.outputs[output_name][0]
                        checked = await asyncio.to_thread(check_output, settings, run_directory=work,
                                                          path=first.path, expected_format=first.format,
                                                          colour_layout=output_definition.colour_layout if first.format == 'fits' else None)
                        await asyncio.to_thread(render_output_preview, checked, preview_directory / filename,
                                                max_edge=1024, auto_stretch=record.output_display == 'auto')
                        record.images.append(NativeResultImage(filename=filename,
                            subfolder=f'apf-siril/{body.prompt_id}/{body.call_id}'))
                    except (ApiError, OSError, ValueError) as exc:
                        record.preview_error = error_message(workspace_locale(settings.workspace), '', 'preview_generation_diagnostic', {'diagnostic': str(exc)})
            _verify_analysis_positions(analyses, definition, registered_ports)
            await asyncio.to_thread(publish_checked_result,settings,CheckedResult(run_id=body.prompt_id,execution_id=body.call_id,source_kind='software',ports=registered_ports))
            record.result_registered=True
            record.state = "completed"
    except asyncio.CancelledError:
        record.state = "cancelled"
    except Exception as exc:
        logging.getLogger(__name__).exception("Native software call failed")
        record.state = "failed"
        record.error = exception_error(workspace_locale(settings.workspace), exc, code='SOFTWARE_EXECUTION_FAILED', message_key='software_execution_failed')
    finally:
        save_software_call(settings,body.prompt_id,body.call_id,record)



def prepare_native_call(settings,body:NativeBundleCall):
    previous=find_software_call(settings,body.prompt_id,body.call_id)
    if previous is not None:
        if previous.request != body:raise ApiError(409,'SOFTWARE_CONTENT_CONFLICT','Call ID already belongs to other inputs.', message_key='software_call_identity_conflict')
        return previous,False
    if body.calculation_signature is not None:
        definition=get_definition(settings.workspace,body.definition_id).definition
        _,entries,_=get_bundle_metadata(settings,definition.execution.package_id)
        if not any(entry['operation']['operation_id']==definition.execution.operation_id and entry.get('automatic_result_preview',False) for entry in entries):
            raise ApiError(409,'AUTOMATIC_RESULT_MANUAL_OPERATION','This operation requires manual execution.', message_key='software_manual_execution_required')
    definition,operation,parameters=_binding(settings,body);_references(definition,body,operation)
    if not operation.ready:raise ApiError(503,'SOFTWARE_NOT_READY',operation.reason or 'Software is not ready.', message_key='software_operation_not_ready', fields=[{'path': 'diagnostic', 'message': operation.reason or 'Software is not ready.'}])
    package=get_package(settings,operation.package_id)
    record = SoftwareCallRecord(request=body, state='starting', definition=definition,
        operation=operation, parameters=parameters,
        bundle=SoftwareCallBundle(version=package.effective_bundle_version, commit=package.effective_bundle_commit,
                                  development_source=package.development_source),
        output_display='direct')
    save_software_call(settings,body.prompt_id,body.call_id,record)
    return record,True


async def get_software_call(settings,active,prompt_id,call_id):
    return _call_summary(settings,await observe_software_call(settings,active,prompt_id,call_id),prompt_id,call_id)


async def list_software_calls(settings,active,prompt_id,node_id,limit,offset):
    matching=[(call,record) for call,record in list_software_call_records(settings,prompt_id) if node_id is None or record.request.node_id==node_id]
    return [await get_software_call(settings,active,prompt_id,call) for call,_ in matching[offset:offset+limit]]


async def recover_software_calls(settings):
    for prompt,call,record in unfinished_software_calls(settings):
        if record.invocation is not None and record.observation is not None:
            await inspect_operation(settings,record.invocation,record.observation)
        record.state='unknown';save_software_call(settings,prompt,call,record)


async def cancel_native_call(settings, active, prompt_id, call_id):
    record=read_software_call(settings,prompt_id,call_id)
    result=await cancel_operation(call_id)
    task=active.get(call_id)
    if task is not None and record.invocation is None:
        if not task.cancelling():
            task.cancel()
        await asyncio.shield(asyncio.gather(task, return_exceptions=True))
        record.state='cancelled';save_software_call(settings,prompt_id,call_id,record)
    return result
