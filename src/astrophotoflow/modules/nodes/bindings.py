from astrophotoflow.contracts.nodes import NodeDefinition
from astrophotoflow.contracts.software import SoftwareOperation
from astrophotoflow.core.errors import ApiError


def binding_error(message: str, *, message_key: str, message_params: dict | None = None) -> ApiError:
    return ApiError(422, "INVALID_NODE_BINDING", message, message_key=message_key, message_params=message_params or {})

def validate_binding(definition: NodeDefinition, operation: SoftwareOperation) -> None:
    binding = definition.execution
    if binding.package_id != operation.package_id or binding.operation_id != operation.operation_id:
        raise binding_error("节点执行绑定与提供的软件操作不匹配。", message_key='binding_operation_mismatch')

    operation_inputs = {item.name: item for item in operation.inputs}
    node_inputs = {item.name: item for item in definition.inputs}
    missing_required = {name for name, item in operation_inputs.items() if item.required} - set(binding.inputs)
    if not set(binding.inputs).issubset(operation_inputs) or missing_required or {target for target in binding.inputs.values()} != set(node_inputs):
        raise binding_error("节点输入映射与操作输入或定义端口不匹配。", message_key='binding_input_mapping')
    for operation_name, node_name in binding.inputs.items():
        if node_inputs[node_name].type != operation_inputs[operation_name].type:
            raise binding_error("节点输入类型与软件操作不匹配。", message_key='binding_input_type')

    operation_outputs = {item.name: item for item in operation.outputs}
    node_outputs = {item.name: item for item in definition.outputs}
    if set(binding.outputs) != set(node_outputs) or {target for target in binding.outputs.values()} != set(operation_outputs):
        raise binding_error("节点输出映射与操作输出或定义端口不匹配。", message_key='binding_output_mapping')
    for node_name, operation_name in binding.outputs.items():
        if node_outputs[node_name].type != operation_outputs[operation_name].type:
            raise binding_error("节点输出类型与软件操作不匹配。", message_key='binding_output_type')

    operation_parameters = {item.name: item for item in operation.parameters}
    node_parameters = {item.name: item for item in definition.parameters}
    if set(binding.parameters) != set(operation_parameters):
        raise binding_error("节点参数映射与软件操作参数不匹配。", message_key='binding_parameter_mapping')
    for operation_name, source in binding.parameters.items():
        operation_parameter = operation_parameters[operation_name]
        if source.kind == "parameter":
            parameter = node_parameters.get(source.name)
            if parameter is None or parameter.kind != operation_parameter.kind:
                raise binding_error("节点参数与软件操作参数类型不匹配。", message_key='binding_parameter_type')
            if parameter.nullable != operation_parameter.nullable:
                raise binding_error("节点参数nullable标记必须与软件操作定义一致。", message_key='binding_nullable')
            if operation_parameter.minimum is not None and \
                    (parameter.minimum is None or parameter.minimum < operation_parameter.minimum):
                raise binding_error("节点参数minimum不能扩大软件操作范围。", message_key='binding_minimum')
            if operation_parameter.maximum is not None and \
                    (parameter.maximum is None or parameter.maximum > operation_parameter.maximum):
                raise binding_error("节点参数maximum不能扩大软件操作范围。", message_key='binding_maximum')
            if operation_parameter.choices is not None and parameter.choices != operation_parameter.choices:
                raise binding_error("节点choice参数必须保留软件操作选项。", message_key='binding_choices')
            try:
                type(operation_parameter).model_validate({**operation_parameter.model_dump(), "default": parameter.default})
            except ValueError as exc:
                raise binding_error(f"节点参数超出软件操作定义：{parameter.name}", message_key='binding_parameter_range', message_params={'name': parameter.name}) from exc
        else:
            try:
                type(operation_parameter).model_validate({**operation_parameter.model_dump(), "default": source.value})
            except ValueError as exc:
                raise binding_error(f"固定参数不符合软件操作定义：{operation_name}", message_key='binding_constant_invalid', message_params={'name': operation_name}) from exc
