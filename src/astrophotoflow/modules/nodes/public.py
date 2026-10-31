import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

from filelock import FileLock, Timeout
from pydantic import JsonValue

from astrophotoflow.contracts.nodes import DefinitionChange, DefinitionWriteResult, NodeDefinition, NodePort, PortRemap, SavedDefinition, definition_content_token
from astrophotoflow.contracts.software import SoftwareOperation
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import exception_error, workspace_locale


def _saved(definition: NodeDefinition) -> SavedDefinition:
    return SavedDefinition(
        definition=definition,
        content_token=definition_content_token(definition),
        native_type=f"APF_{definition.definition_id.hex}",
    )


def _directory(workspace: Path) -> Path:
    return workspace / "nodes"


def _path(workspace: Path, definition_id: UUID) -> Path:
    return _directory(workspace) / f"{definition_id}.json"


def _read(path: Path) -> SavedDefinition:
    definition = NodeDefinition.model_validate_json(path.read_text(encoding="utf-8"))
    if path.stem != str(definition.definition_id):
        raise ValueError(f"节点定义文件名与内容ID不匹配：{path}")
    return _saved(definition)


def _write(path: Path, definition: NodeDefinition, *, exclusive: bool) -> SavedDefinition:
    content = json.dumps(definition.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    if exclusive:
        created = False
        try:
            stream = path.open("x", encoding="utf-8", newline="\n")
            created = True
            with stream:
                stream.write(content)
        except BaseException:
            if created:
                path.unlink(missing_ok=True)
            raise
    else:
        temporary = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(content)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return _saved(definition)


def _lock(workspace: Path) -> FileLock:
    return FileLock(str(workspace / ".nodes.lock"), timeout=0)


def _binding_error(message: str, *, message_key: str, message_params: dict | None = None) -> ApiError:
    return ApiError(422, "INVALID_NODE_BINDING", message, message_key=message_key, message_params=message_params or {})


def _check_binding(definition: NodeDefinition, operation: SoftwareOperation) -> None:
    binding = definition.execution
    if binding.package_id != operation.package_id or binding.operation_id != operation.operation_id:
        raise _binding_error("节点执行绑定与提供的软件操作不匹配。", message_key='binding_operation_mismatch')

    operation_inputs = {item.name: item for item in operation.inputs}
    node_inputs = {item.name: item for item in definition.inputs}
    missing_required = {name for name, item in operation_inputs.items() if item.required} - set(binding.inputs)
    if not set(binding.inputs).issubset(operation_inputs) or missing_required or {target for target in binding.inputs.values()} != set(node_inputs):
        raise _binding_error("节点输入映射与操作输入或定义端口不匹配。", message_key='binding_input_mapping')
    for operation_name, node_name in binding.inputs.items():
        if node_inputs[node_name].type != operation_inputs[operation_name].type:
            raise _binding_error("节点输入类型与软件操作不匹配。", message_key='binding_input_type')

    operation_outputs = {item.name: item for item in operation.outputs}
    node_outputs = {item.name: item for item in definition.outputs}
    if set(binding.outputs) != set(node_outputs) or {target for target in binding.outputs.values()} != set(operation_outputs):
        raise _binding_error("节点输出映射与操作输出或定义端口不匹配。", message_key='binding_output_mapping')
    for node_name, operation_name in binding.outputs.items():
        if node_outputs[node_name].type != operation_outputs[operation_name].type:
            raise _binding_error("节点输出类型与软件操作不匹配。", message_key='binding_output_type')

    operation_parameters = {item.name: item for item in operation.parameters}
    node_parameters = {item.name: item for item in definition.parameters}
    if set(binding.parameters) != set(operation_parameters):
        raise _binding_error("节点参数映射与软件操作参数不匹配。", message_key='binding_parameter_mapping')
    for operation_name, source in binding.parameters.items():
        operation_parameter = operation_parameters[operation_name]
        if source.kind == "parameter":
            parameter = node_parameters.get(source.name)
            if parameter is None or parameter.kind != operation_parameter.kind:
                raise _binding_error("节点参数与软件操作参数类型不匹配。", message_key='binding_parameter_type')
            if parameter.nullable != operation_parameter.nullable:
                raise _binding_error("节点参数nullable标记必须与软件操作定义一致。", message_key='binding_nullable')
            if operation_parameter.minimum is not None and \
                    (parameter.minimum is None or parameter.minimum < operation_parameter.minimum):
                raise _binding_error("节点参数minimum不能扩大软件操作范围。", message_key='binding_minimum')
            if operation_parameter.maximum is not None and \
                    (parameter.maximum is None or parameter.maximum > operation_parameter.maximum):
                raise _binding_error("节点参数maximum不能扩大软件操作范围。", message_key='binding_maximum')
            if operation_parameter.choices is not None and parameter.choices != operation_parameter.choices:
                raise _binding_error("节点choice参数必须保留软件操作选项。", message_key='binding_choices')
            try:
                type(operation_parameter).model_validate({**operation_parameter.model_dump(), "default": parameter.default})
            except ValueError as exc:
                raise _binding_error(f"节点参数超出软件操作定义：{parameter.name}", message_key='binding_parameter_range', message_params={'name': parameter.name}) from exc
        else:
            try:
                type(operation_parameter).model_validate({**operation_parameter.model_dump(), "default": source.value})
            except ValueError as exc:
                raise _binding_error(f"固定参数不符合软件操作定义：{operation_name}", message_key='binding_constant_invalid', message_params={'name': operation_name}) from exc


def list_definitions(workspace: Path) -> list[SavedDefinition]:
    directory = _directory(workspace)
    if not directory.exists():
        return []
    return [_read(path) for path in sorted(directory.glob("*.json"))]


def get_definition(workspace: Path, definition_id: UUID) -> SavedDefinition:
    path = _path(workspace, definition_id)
    if not path.is_file():
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到请求的节点定义。", message_key='the_requested_node_definition_was_not_found')
    return _read(path)


def create_definition(workspace: Path, definition: NodeDefinition, operation: SoftwareOperation) -> SavedDefinition:
    if definition.source != "custom":
        raise ApiError(422, "UNSUPPORTED_NODE_DEFINITION", "首次自定义节点保存只接受source=custom。", message_key='a_new_custom_node_must_use_source_custom')
    _check_binding(definition, operation)
    directory = _directory(workspace)
    directory.mkdir(parents=True, exist_ok=True)
    path = _path(workspace, definition.definition_id)
    try:
        with _lock(workspace):
            try:
                return _write(path, definition, exclusive=True)
            except FileExistsError as exc:
                raise ApiError(409, "NODE_CONTENT_CONFLICT", "节点定义ID已存在。", message_key='the_node_definition_id_already_exists') from exc
    except Timeout as exc:
        raise ApiError(409, "NODE_CONTENT_CONFLICT", "节点定义正在被其他操作修改。", message_key='another_operation_is_modifying_the_node_definition') from exc


def _remap(before: list[NodePort], after: list[NodePort]) -> tuple[list[PortRemap], list[str]]:
    new_indexes = {port.name: (index, port.type) for index, port in enumerate(after)}
    remap = []
    disconnected = []
    for index, port in enumerate(before):
        target = new_indexes.get(port.name)
        if target is not None and target[1] == port.type:
            remap.append(PortRemap(name=port.name, type=port.type, before_index=index, after_index=target[0]))
        else:
            disconnected.append(port.name)
    return remap, disconnected


def preview_definition_update(workspace: Path, definition: NodeDefinition, expected_content_token: str,
                              operation: SoftwareOperation) -> DefinitionChange:
    before = get_definition(workspace, definition.definition_id)
    if before.content_token != expected_content_token:
        raise ApiError(409, "NODE_CONTENT_CONFLICT", "节点定义已改变，请重新读取后预览。", message_key='the_node_definition_has_changed_read_it_again_before_previewing')
    if definition.source != before.definition.source or definition.execution.package_id != before.definition.execution.package_id:
        raise ApiError(422, "UNSUPPORTED_NODE_DEFINITION", "节点更新不能改变定义来源或软件包归属。", message_key='a_node_update_cannot_change_its_source_or_package_ownership')
    _check_binding(definition, operation)
    after = _saved(definition)
    input_remap, disconnected_inputs = _remap(before.definition.inputs, definition.inputs)
    output_remap, disconnected_outputs = _remap(before.definition.outputs, definition.outputs)
    defaults = {parameter.name: parameter.default for parameter in definition.parameters}
    return DefinitionChange(
        before=before,
        after=after,
        input_remap=input_remap,
        output_remap=output_remap,
        disconnected_inputs=disconnected_inputs,
        disconnected_outputs=disconnected_outputs,
        parameter_defaults=defaults,
    )


def update_definition(workspace: Path, change: DefinitionChange) -> SavedDefinition:
    if change.before.definition.source != "custom" or change.after.definition.source != "custom":
        raise ApiError(422, "UNSUPPORTED_NODE_DEFINITION", "单定义更新只接受自定义节点。", message_key='single_definition_updates_accept_custom_nodes_only')
    if change.before.definition.definition_id != change.after.definition.definition_id or \
            change.before.definition.execution.package_id != change.after.definition.execution.package_id:
        raise ApiError(422, "UNSUPPORTED_NODE_DEFINITION", "节点更新不能改变定义ID或软件包归属。", message_key='a_node_update_cannot_change_its_definition_id_or_package_ownership')
    path = _path(workspace, change.before.definition.definition_id)
    try:
        with _lock(workspace):
            current = get_definition(workspace, change.before.definition.definition_id)
            if current.content_token != change.before.content_token:
                raise ApiError(409, "NODE_CONTENT_CONFLICT", "节点定义已改变，请重新预览。", message_key='the_node_definition_has_changed_preview_it_again')
            return _write(path, change.after.definition, exclusive=False)
    except Timeout as exc:
        raise ApiError(409, "NODE_CONTENT_CONFLICT", "节点定义正在被其他操作修改。", message_key='another_operation_is_modifying_the_node_definition') from exc


def replace_package_definitions(workspace: Path, package_id: str, definitions: list[NodeDefinition],
                                expected_tokens: dict[UUID, str]) -> list[DefinitionWriteResult]:
    incoming: dict[UUID, NodeDefinition] = {}
    for definition in definitions:
        if definition.source != "package" or definition.execution.package_id != package_id:
            raise ApiError(422, "UNSUPPORTED_NODE_DEFINITION", "软件包定义必须标记为package并匹配目标包。", message_key='bundled_definitions_must_use_source_package_and_match_the_target_package')
        if definition.definition_id in incoming:
            raise _binding_error("软件包定义列表包含重复ID。", message_key='binding_duplicate_id')
        incoming[definition.definition_id] = definition
    directory = _directory(workspace)
    try:
        with _lock(workspace):
            current = {item.definition.definition_id: item for item in list_definitions(workspace)
                       if item.definition.source == "package" and item.definition.execution.package_id == package_id}
            actual_tokens = {definition_id: item.content_token for definition_id, item in current.items()}
            if actual_tokens != expected_tokens:
                raise ApiError(409, "NODE_CONTENT_CONFLICT", "软件包节点定义集合已改变，请重新读取后替换。", message_key='the_bundled_node_definition_set_has_changed_read_it_again_before_replacemen')
            for definition_id, definition in incoming.items():
                existing = get_definition(workspace, definition_id) if _path(workspace, definition_id).is_file() else None
                if existing is not None and (existing.definition.source != "package" or existing.definition.execution.package_id != package_id):
                    raise ApiError(409, "NODE_CONTENT_CONFLICT", "节点定义ID已属于其他来源或软件包。", message_key='the_node_definition_id_belongs_to_another_source_or_package')
            if incoming:
                directory.mkdir(parents=True, exist_ok=True)
            results = []
            upserts = sorted(incoming.items(), key=lambda item: str(item[0]))
            for definition_id, definition in upserts:
                previous = current.get(definition_id)
                action = "create" if previous is None else "update"
                try:
                    saved = _write(_path(workspace, definition_id), definition, exclusive=previous is None)
                except OSError as exc:
                    results.append(DefinitionWriteResult(
                        definition_id=definition_id, action=action, applied=False, content=None,
                        error=exception_error(workspace_locale(workspace), exc, code='FILE_WRITE_FAILED', message_key='node_file_write_failed'),
                    ))
                    return results
                results.append(DefinitionWriteResult(
                    definition_id=definition_id, action=action, applied=True, content=saved, error=None,
                ))
            for definition_id in sorted(set(current) - set(incoming), key=str):
                try:
                    _path(workspace, definition_id).unlink()
                except OSError as exc:
                    results.append(DefinitionWriteResult(
                        definition_id=definition_id, action="remove", applied=False, content=None,
                        error=exception_error(workspace_locale(workspace), exc, code='FILE_REMOVE_FAILED', message_key='node_file_remove_failed'),
                    ))
                    return results
                results.append(DefinitionWriteResult(
                    definition_id=definition_id, action="remove", applied=True, content=None, error=None,
                ))
            return results
    except Timeout as exc:
        raise ApiError(409, "NODE_CONTENT_CONFLICT", "节点定义正在被其他操作修改。", message_key='another_operation_is_modifying_the_node_definition') from exc
