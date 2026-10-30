from astrophotoflow.contracts.nodes import NodeCapability
from astrophotoflow.modules.nodes.public import list_definitions, get_definition
from astrophotoflow.modules.software.public import get_package, list_operations, get_bundle_metadata


def _package_context(settings, package_id):
    _, entries, definitions = get_bundle_metadata(settings, package_id)
    return {
        'entries': {entry['operation']['operation_id']: entry for entry in entries},
        'declared': {value['definition_id'] for value in definitions},
        'package': get_package(settings, package_id),
        'operations': {operation.operation_id: operation for operation in list_operations(settings, package_id)},
    }


def _describe_node(node, context):
    binding = node.definition.execution
    entry = context['entries'].get(binding.operation_id)
    operation = context['operations'].get(binding.operation_id)
    if entry is None or operation is None:
        return NodeCapability(node=node, operation=None, available=False, reason="Bundle 中的软件操作已缺失。",
            preview=None, help=node.definition.description, examples=[])
    package = context['package']
    missing = node.definition.source == 'package' and str(node.definition.definition_id) not in context['declared']
    return NodeCapability(node=node, operation=operation, available=package.availability == 'ready' and not missing,
        reason="Bundle 中的节点已缺失。" if missing else package.reason, preview=entry.get('preview'), help=entry.get('help', operation.description),
        examples=entry.get('examples', []))


def describe_node(settings, definition_id):
    node = get_definition(settings.workspace, definition_id)
    return _describe_node(node, _package_context(settings, node.definition.execution.package_id))


def list_nodes(settings, query=None):
    contexts = {}
    values = []
    for node in list_definitions(settings.workspace):
        package_id = node.definition.execution.package_id
        if package_id not in contexts:
            contexts[package_id] = _package_context(settings, package_id)
        values.append(_describe_node(node, contexts[package_id]))
    if query:
        text = query.casefold()
        values = [value for value in values if text in (value.node.definition.name + ' ' + value.node.definition.description).casefold()]
    return values
