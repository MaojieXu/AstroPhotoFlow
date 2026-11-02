from uuid import UUID

from astrophotoflow.contracts.nodes import NodeCapability
from astrophotoflow.core.config import Settings
from astrophotoflow.core.localization import error_message, workspace_locale
from astrophotoflow.modules.nodes.storage import get_definition, list_definitions
from astrophotoflow.modules.software.public import get_bundle_display, get_bundle_metadata, get_package, list_operations


def _package_context(settings, package_id):
    package = get_package(settings, package_id)
    if package.development_source is not None and package.effective_availability != 'ready':
        return {'entries': {}, 'declared': set(), 'package': package, 'operations': {}, 'display': {},
                'locale': workspace_locale(settings.workspace)}
    _, entries, definitions = get_bundle_metadata(settings, package_id)
    return {
        'entries': {entry['operation']['operation_id']: entry for entry in entries},
        'declared': {value['definition_id'] for value in definitions},
        'package': package,
        'operations': {operation.operation_id: operation for operation in list_operations(settings, package_id)},
        'display': get_bundle_display(settings, package_id),
        'locale': workspace_locale(settings.workspace),
    }


def _describe_node(node, context):
    binding = node.definition.execution
    entry = context['entries'].get(binding.operation_id)
    operation = context['operations'].get(binding.operation_id)
    if entry is None or operation is None:
        return NodeCapability(node=node, development_source=context['package'].development_source, operation=None, available=False,
            reason=context['package'].effective_reason if context['package'].development_source else error_message(context['locale'], '', 'bundle_operation_missing'),
            preview=None, help=node.definition.description, examples=[])
    package = context['package']
    missing = node.definition.source == 'package' and str(node.definition.definition_id) not in context['declared']
    return NodeCapability(node=node, operation=operation, automatic_result_preview=entry.get('automatic_result_preview', False), implementation_token=package.development_source.fingerprint if package.development_source else package.effective_bundle_commit, development_source=package.development_source, available=package.effective_availability == 'ready' and not missing,
        reason=error_message(context['locale'], '', 'bundle_node_missing') if missing else package.effective_reason, preview=entry.get('preview'), help=entry.get('help', operation.description),
        examples=entry.get('examples', []), display={locale: values[binding.operation_id]
            for locale, values in context['display'].items() if binding.operation_id in values}
            if node.definition.source == 'package' else {})


def describe_node(settings: Settings, definition_id: UUID) -> NodeCapability:
    node = get_definition(settings.workspace, definition_id)
    return _describe_node(node, _package_context(settings, node.definition.execution.package_id))


def list_nodes(settings: Settings, query: str | None = None) -> list[NodeCapability]:
    contexts = {}
    values = []
    for node in list_definitions(settings.workspace):
        package_id = node.definition.execution.package_id
        if package_id not in contexts:
            contexts[package_id] = _package_context(settings, package_id)
        values.append(_describe_node(node, contexts[package_id]))
    if query:
        text = query.casefold()
        values = [value for value in values if text in (' '.join([
            value.node.definition.name, value.node.definition.description, value.node.definition.execution.operation_id,
            *(display.name + ' ' + display.description for display in value.display.values())])).casefold()]
    return values
