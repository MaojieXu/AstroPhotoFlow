"""Validate scientific inputs and exact operation contracts."""
from astrophotoflow.contracts.software import ParameterDefinition, SoftwareInvocation
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software import bundles
from astrophotoflow.modules.software.execution.usage import get_usage
from astrophotoflow.modules.software.packages.catalog import get_operation, get_package


def validate_parameters(settings, package_id, operation_id, values):
    manifest, _, _ = bundles.metadata(settings.workspace, package_id)
    operation = get_operation(settings, package_id, manifest.software_version, operation_id)
    if set(values) != {item.name for item in operation.parameters}:
        raise ApiError(422, "VALIDATION_ERROR", "参数与 Bundle 操作定义不一致。", message_key='parameters_do_not_match_the_bundle_operation_definition')
    for parameter in operation.parameters:
        try:
            ParameterDefinition.model_validate({**parameter.model_dump(), "default": values[parameter.name]})
        except ValueError as exc:
            raise ApiError(422, "VALIDATION_ERROR", f"参数无效：{parameter.name}", message_key='invalid_parameters_p0', message_params={'p0': parameter.name}) from exc
    return operation


def validate_invocation(settings: Settings, invocation: SoftwareInvocation):
    if any(use.state == "unknown" for use in get_usage(invocation.package_id)):
        raise ApiError(409, "SOFTWARE_BUSY", "软件包仍有无法确认停止的调用。", message_key='some_package_invocations_could_not_be_confirmed_stopped')
    operation = get_operation(settings, invocation.package_id, invocation.version, invocation.operation_id)
    if not operation.ready:
        raise ApiError(503, "SOFTWARE_NOT_READY", operation.reason or "Siril 尚未就绪。", message_key='siril_not_ready', fields=[{'path': 'software', 'message': operation.reason}] if operation.reason else [])
    if invocation.operation_content_token != operation.content_token:
        raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "软件操作定义已变化，请重新提交。", message_key='the_software_operation_definition_has_changed_submit_it_again')
    package = get_package(settings, invocation.package_id)
    if invocation.bundle_commit != package.effective_bundle_commit:
        raise ApiError(409, 'SOFTWARE_CONTENT_CONFLICT', '调用受理后 Bundle 实现已变化，请查询本次状态，不得采用新版替换在途实现。', message_key='the_bundle_implementation_changed_after_acceptance_query_this_invocation_do')
    if set(invocation.parameters) != {item.name for item in operation.parameters}:
        raise ApiError(422, "VALIDATION_ERROR", "Siril 参数与准确操作定义不匹配。", message_key='siril_parameters_do_not_match_the_exact_operation_definition')
    for parameter in operation.parameters:
        try:
            value = invocation.parameters[parameter.name]
            ParameterDefinition.model_validate({**parameter.model_dump(), "default": value})
            if parameter.editor is not None and parameter.editor.input is not None:
                selection = parameter.editor_value(value)
                if selection is not None:
                    items = invocation.inputs.get(parameter.editor.input, [])
                    if selection.member_index >= len(items):
                        raise ValueError("The selected input member is missing.")
                    item = items[selection.member_index]
                    metadata = item.scientific_metadata or {}
                    hdu = item.selection.hdu_index if item.selection.kind == "fits_hdu" else metadata.get("selected_hdu")
                    frame_count = metadata.get("frame_count")
                    frame_hdus = metadata.get("frame_hdus", [])
                    if (item.selection.kind == "whole_file" and selection.frame_index is not None
                        and selection.frame_index < len(frame_hdus)):
                        hdu = frame_hdus[selection.frame_index]
                    source = (item.position_token if item.kind == "run_output" else None) or item.content_hash
                    if (selection.source_token != source or selection.hdu_index != hdu
                        or (frame_count is not None and selection.frame_index is not None and selection.frame_index >= frame_count)
                        or (hdu == metadata.get("selected_hdu") and (
                            metadata.get("width") not in (None, selection.width) or metadata.get("height") not in (None, selection.height)
                        ))):
                        raise ValueError("The selected coordinates belong to a different input image.")
        except ValueError as exc:
            raise ApiError(422, "VALIDATION_ERROR", f"参数无效：{parameter.name}", message_key='invalid_parameters_p0', message_params={'p0': parameter.name},
                           fields=[{"path": parameter.name, "message": str(exc)}]) from exc
    definitions = {item.name: item for item in operation.inputs}
    required = {name for name, item in definitions.items() if item.required}
    if not set(invocation.inputs).issubset(definitions) or not required.issubset(invocation.inputs):
        raise ApiError(422, "INVALID_REFERENCE", "具名输入与软件操作定义不匹配。", message_key='named_inputs_do_not_match_the_software_operation_definition')
    if not set(invocation.supporting_inputs).issubset(invocation.inputs):
        raise ApiError(422, "INVALID_REFERENCE", "序列附属文件没有对应的输入。", message_key='a_sequence_supporting_file_has_no_corresponding_input')
    root = settings.workspace.resolve() / "runs" / str(invocation.run_id) / "work"
    if root.resolve() != root:
        raise ApiError(422, "INVALID_WORK_DIRECTORY", "运行目录指向了工作区以外的位置。", message_key='the_run_directory_points_outside_the_workspace')
    work = invocation.work_directory.resolve()
    if work != root and not work.is_relative_to(root):
        raise ApiError(422, "INVALID_WORK_DIRECTORY", "软件只能写入本次运行的工作目录。", message_key='software_may_write_only_within_this_invocation_s_working_directory')
    for name, items in invocation.inputs.items():
        definition = definitions[name]
        if not items or (definition.cardinality == "one" and len(items) != 1):
            raise ApiError(422, "INVALID_REFERENCE", f"输入成员数量不符合操作定义：{name}", message_key='input_member_count_does_not_match_the_operation_definition_p0', message_params={'p0': name})
        for item in items:
            if item.format not in definition.formats:
                raise ApiError(422, "UNSUPPORTED_SELECTION", f"输入格式不符合操作定义：{name}", message_key='input_format_does_not_match_the_operation_definition_p0', message_params={'p0': name})
            metadata = item.scientific_metadata or {}
            if definition.colour_layout is not None and metadata.get('colour_layout') not in (None, definition.colour_layout):
                raise ApiError(422, 'UNSUPPORTED_SELECTION', f'输入颜色布局与操作要求不一致：{name}。', message_key='input_color_layout_does_not_match_the_operation_requirements_p0', message_params={'p0': name})
            default_hdu = definition.data_kind != 'file' and item.selection.kind == 'fits_hdu' and item.selection.hdu_index == 0 and metadata.get('selected_hdu') == 0
            if item.selection.kind != "whole_file" and not definition.supports_hdu and not default_hdu:
                raise ApiError(422, "UNSUPPORTED_SELECTION", f"操作不支持指定 HDU：{name}", message_key='the_operation_does_not_support_the_selected_hdu_p0', message_params={'p0': name})
            if definition.data_kind == 'image' and item.selection.kind == 'whole_file' and metadata.get('frame_count', 1) is not None and metadata.get('frame_count', 1) > 1:
                raise ApiError(422, 'UNSUPPORTED_SELECTION', f'该单图输入不能静默读取序列容器的首帧：{name}；请使用适用的序列操作或明确选择主HDU。', message_key='this_single_image_input_must_not_silently_use_the_first_frame_of_a_sequence', message_params={'p0': name})
            if definition.data_kind != 'file' and item.format == 'fits' and 'hdu_count' in metadata and (metadata.get('selected_hdu') is None or metadata.get('frame_count') is None and not default_hdu):
                raise ApiError(422, 'UNSUPPORTED_SELECTION', f'该输入没有已确认的二维灰度或RGB图像布局：{name}。', message_key='this_input_has_no_confirmed_2d_grayscale_or_rgb_layout_p0', message_params={'p0': name})
            whole_container = item.selection.kind == 'whole_file' and (
                definition.data_kind in {'sequence', 'file'} or
                any(file.read_path.suffix.lower() == '.seq' for file in invocation.supporting_inputs.get(name, [])) or
                item.read_path.name.lower().endswith(('.fit.fz', '.fits.fz', '.fts.fz')) and metadata.get('frame_count') == 1)
            if metadata.get("selected_hdu") not in (None, 0) and not definition.supports_hdu and not whole_container:
                raise ApiError(422, "UNSUPPORTED_SELECTION", f"操作不支持扩展 HDU：{name}", message_key='the_operation_does_not_support_extension_hdus_p0', message_params={'p0': name})
    for item in [item for group in [*invocation.inputs.values(), *invocation.supporting_inputs.values()] for item in group]:
        stat_result = item.read_path.stat()
        if (stat_result.st_size, stat_result.st_mtime_ns) != (item.byte_size, item.mtime_ns):
            raise ApiError(409, "SOURCE_CHANGED", "科学输入在准入后发生变化。", message_key='a_scientific_input_changed_after_admission')
        if item.read_path.resolve().is_relative_to(work):
            raise ApiError(422, "INVALID_REFERENCE", "科学输入不能位于即将创建的调用输出目录内。", message_key='scientific_inputs_must_not_be_inside_the_invocation_output_directory_that_w')
    return package, work, operation
