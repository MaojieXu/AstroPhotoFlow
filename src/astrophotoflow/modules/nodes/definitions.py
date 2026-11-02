from pathlib import Path
from uuid import UUID

from filelock import Timeout

from astrophotoflow.contracts.nodes import DefinitionChange, DefinitionWriteResult, NodeDefinition, SavedDefinition
from astrophotoflow.contracts.software import SoftwareOperation
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import exception_error, workspace_locale

from .bindings import binding_error, validate_binding
from .changes import build_definition_change
from .storage import definition_directory, definition_lock, definition_path, get_definition, list_definitions, write_definition


def create_definition(workspace: Path, definition: NodeDefinition, operation: SoftwareOperation) -> SavedDefinition:
    if definition.source != "custom":
        raise ApiError(422, "UNSUPPORTED_NODE_DEFINITION", "首次自定义节点保存只接受source=custom。", message_key='a_new_custom_node_must_use_source_custom')
    validate_binding(definition, operation)
    directory = definition_directory(workspace)
    directory.mkdir(parents=True, exist_ok=True)
    path = definition_path(workspace, definition.definition_id)
    try:
        with definition_lock(workspace):
            try:
                return write_definition(path, definition, exclusive=True)
            except FileExistsError as exc:
                raise ApiError(409, "NODE_CONTENT_CONFLICT", "节点定义ID已存在。", message_key='the_node_definition_id_already_exists') from exc
    except Timeout as exc:
        raise ApiError(409, "NODE_CONTENT_CONFLICT", "节点定义正在被其他操作修改。", message_key='another_operation_is_modifying_the_node_definition') from exc

def preview_definition_update(workspace: Path, definition: NodeDefinition, expected_content_token: str,
                              operation: SoftwareOperation) -> DefinitionChange:
    before = get_definition(workspace, definition.definition_id)
    if before.content_token != expected_content_token:
        raise ApiError(409, "NODE_CONTENT_CONFLICT", "节点定义已改变，请重新读取后预览。", message_key='the_node_definition_has_changed_read_it_again_before_previewing')
    if definition.source != before.definition.source or definition.execution.package_id != before.definition.execution.package_id:
        raise ApiError(422, "UNSUPPORTED_NODE_DEFINITION", "节点更新不能改变定义来源或软件包归属。", message_key='a_node_update_cannot_change_its_source_or_package_ownership')
    validate_binding(definition, operation)
    return build_definition_change(before, definition)

def update_definition(workspace: Path, change: DefinitionChange) -> SavedDefinition:
    if change.before.definition.source != "custom" or change.after.definition.source != "custom":
        raise ApiError(422, "UNSUPPORTED_NODE_DEFINITION", "单定义更新只接受自定义节点。", message_key='single_definition_updates_accept_custom_nodes_only')
    if change.before.definition.definition_id != change.after.definition.definition_id or \
            change.before.definition.execution.package_id != change.after.definition.execution.package_id:
        raise ApiError(422, "UNSUPPORTED_NODE_DEFINITION", "节点更新不能改变定义ID或软件包归属。", message_key='a_node_update_cannot_change_its_definition_id_or_package_ownership')
    path = definition_path(workspace, change.before.definition.definition_id)
    try:
        with definition_lock(workspace):
            current = get_definition(workspace, change.before.definition.definition_id)
            if current.content_token != change.before.content_token:
                raise ApiError(409, "NODE_CONTENT_CONFLICT", "节点定义已改变，请重新预览。", message_key='the_node_definition_has_changed_preview_it_again')
            return write_definition(path, change.after.definition, exclusive=False)
    except Timeout as exc:
        raise ApiError(409, "NODE_CONTENT_CONFLICT", "节点定义正在被其他操作修改。", message_key='another_operation_is_modifying_the_node_definition') from exc

def replace_package_definitions(workspace: Path, package_id: str, definitions: list[NodeDefinition],
                                expected_tokens: dict[UUID, str]) -> list[DefinitionWriteResult]:
    incoming: dict[UUID, NodeDefinition] = {}
    for definition in definitions:
        if definition.source != "package" or definition.execution.package_id != package_id:
            raise ApiError(422, "UNSUPPORTED_NODE_DEFINITION", "软件包定义必须标记为package并匹配目标包。", message_key='bundled_definitions_must_use_source_package_and_match_the_target_package')
        if definition.definition_id in incoming:
            raise binding_error("软件包定义列表包含重复ID。", message_key='binding_duplicate_id')
        incoming[definition.definition_id] = definition
    directory = definition_directory(workspace)
    try:
        with definition_lock(workspace):
            current = {item.definition.definition_id: item for item in list_definitions(workspace)
                       if item.definition.source == "package" and item.definition.execution.package_id == package_id}
            actual_tokens = {definition_id: item.content_token for definition_id, item in current.items()}
            if actual_tokens != expected_tokens:
                raise ApiError(409, "NODE_CONTENT_CONFLICT", "软件包节点定义集合已改变，请重新读取后替换。", message_key='the_bundled_node_definition_set_has_changed_read_it_again_before_replacemen')
            for definition_id, definition in incoming.items():
                existing = get_definition(workspace, definition_id) if definition_path(workspace, definition_id).is_file() else None
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
                    saved = write_definition(definition_path(workspace, definition_id), definition, exclusive=previous is None)
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
                    definition_path(workspace, definition_id).unlink()
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
