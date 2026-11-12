from astrophotoflow.contracts.nodes import DefinitionChange, NodeDefinition, NodePort, PortRemap, SavedDefinition, definition_content_token


def saved_definition(definition: NodeDefinition) -> SavedDefinition:
    return SavedDefinition(
        definition=definition,
        content_token=definition_content_token(definition),
        native_type=f"APF_{definition.definition_id.hex}",
    )

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

def build_definition_change(before: SavedDefinition, definition: NodeDefinition) -> DefinitionChange:
    after = saved_definition(definition)
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
