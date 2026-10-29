from astrophotoflow.contracts.nodes import NodeCapability
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.nodes.public import list_definitions, get_definition
from astrophotoflow.modules.software.public import get_package, get_operation, get_bundle_metadata


def describe_node(settings, definition_id):
    node = get_definition(settings.workspace, definition_id)
    binding = node.definition.execution
    manifest, entries, _ = get_bundle_metadata(settings, binding.package_id)
    operation = get_operation(settings, binding.package_id, manifest.software_version, binding.operation_id)
    entry = next(value for value in entries if value['operation']['operation_id'] == binding.operation_id)
    package = get_package(settings, binding.package_id)
    return NodeCapability(node=node, operation=operation, available=package.availability == 'ready',
        reason=package.reason, preview=entry.get('preview'), help=entry.get('help', operation.description),
        examples=entry.get('examples', []))


def list_nodes(settings, query=None):
    values = [describe_node(settings, value.definition.definition_id) for value in list_definitions(settings.workspace)]
    if query:
        text = query.casefold()
        values = [value for value in values if text in (value.node.definition.name + ' ' + value.node.definition.description).casefold()]
    return values
