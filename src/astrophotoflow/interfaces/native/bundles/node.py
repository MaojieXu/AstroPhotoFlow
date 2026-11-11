import asyncio
import os
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import aiohttp
from comfy.model_management import processing_interrupted, throw_exception_if_processing_interrupted
from comfy.utils import ProgressBar
from comfy_api.latest import io
from comfy_execution.utils import get_executing_context

from astrophotoflow.contracts.nodes import NodeDefinition, definition_content_token
from astrophotoflow.contracts.software import SoftwareOperation
from astrophotoflow.core.config import load_running_settings
from astrophotoflow.interfaces.native.replies import software_call_error, software_call_reply


async def request_service(session: aiohttp.ClientSession, method: str, path: str, body=None):
    settings = load_running_settings(Path(os.environ["APF_WORKSPACE"]))
    token = settings.token_path.read_text(encoding="utf-8").strip()
    async with session.request(method, settings.service_url + path, json=body,
                               headers={"Authorization": f"Bearer {token}"},
                               timeout=aiohttp.ClientTimeout(total=10)) as response:
        value = await response.json()
        if response.status >= 400:
            raise RuntimeError(value.get("error", {}).get("message", "无法核对软件操作结果。"))
        return value


class BundleNode(io.ComfyNode):
    APF_AUTOMATIC_RESULT = False
    RELATIVE_PYTHON_MODULE = "custom_nodes.astrophotoflow"
    definition: NodeDefinition
    operation: SoftwareOperation
    output_node: bool = False
    search_aliases: tuple[str, ...] = ()

    @classmethod
    def define_schema(cls):
        definition = cls.definition
        inputs = []
        for port in definition.inputs:
            operation_input = next(item for item in cls.operation.inputs if definition.execution.inputs.get(item.name) == port.name)
            socket = io.Custom(port.type).Input(port.name, optional=not operation_input.required)
            if operation_input.multiple_connections:
                socket = io.Autogrow.Input(port.name, io.Autogrow.TemplatePrefix(
                    io.Custom(port.type).Input('value'), prefix='item', min=1 if operation_input.required else 0,
                    max=100), optional=not operation_input.required)
            inputs.append(socket)
        controls = []
        for parameter in definition.parameters:
            options = {"default": parameter.default}
            if parameter.kind in {"float", "int"}:
                options.update(min=parameter.minimum if parameter.minimum is not None else (-sys.float_info.max if parameter.kind == "float" else -(2**53-1)),
                               max=parameter.maximum if parameter.maximum is not None else (sys.float_info.max if parameter.kind == "float" else 2**53-1))
                if parameter.step is not None:
                    options["step"] = parameter.step
                factory = io.Float if parameter.kind == "float" else io.Int
            elif parameter.kind == "boolean":
                factory = io.Boolean
            elif parameter.kind == "string":
                factory = io.String
                if any(source.kind == 'parameter' and source.name == parameter.name and
                       cls.operation.parameter_widgets.get(name) == 'multiline'
                       for name, source in definition.execution.parameters.items()):
                    options['multiline'] = True
            else:
                factory = io.Combo
                options["options"] = parameter.choices
            controls.append(factory.Input(parameter.name, **options))
        return io.Schema(node_id=f"APF_{definition.definition_id.hex}", display_name=definition.name,
            category="/".join([definition.execution.package_id, *definition.category]),
            search_aliases=list(cls.search_aliases),
            description=definition.description,
            inputs=inputs + controls,
            outputs=[io.Custom(port.type).Output(display_name=port.name) for port in definition.outputs],
            hidden=[io.Hidden.extra_pnginfo],
            is_output_node=cls.output_node, not_idempotent=True)

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return float('nan')

    @classmethod
    async def execute(cls, **kwargs):
        context = get_executing_context()
        if context is None:
            raise RuntimeError("软件节点只能在原生执行上下文中运行。")
        async with aiohttp.ClientSession() as session:
            call_id = str(uuid5(NAMESPACE_URL, f"apf:siril:{context.prompt_id}:{context.node_id}:{context.list_index}"))
            inputs = {}
            for port in cls.definition.inputs:
                if port.name not in kwargs:
                    continue
                operation_input = next(item for item in cls.operation.inputs if cls.definition.execution.inputs.get(item.name) == port.name)
                value = kwargs[port.name]
                if operation_input.multiple_connections:
                    value = [value[name] for name in sorted(value, key=lambda name: int(name.removeprefix('item')))]
                inputs[port.name] = value
            body = {"call_id": call_id, "prompt_id": context.prompt_id, "node_id": str(context.node_id),
                    "inputs": inputs,
                    'workflow_id': ((cls.hidden.extra_pnginfo or {}).get('workflow') or {}).get('id'),
                    "definition_id": str(cls.definition.definition_id), "definition_token": definition_content_token(cls.definition),
                    "parameters": {parameter.name: kwargs[parameter.name] for parameter in cls.definition.parameters}}
            workflow = (cls.hidden.extra_pnginfo or {}).get('workflow') or {}
            automatic = (workflow.get('extra') or {}).get('apfAutomaticResult')
            if automatic is not None:
                if not cls.APF_AUTOMATIC_RESULT:
                    raise RuntimeError('This operation requires manual execution.')
                body['calculation_signature'] = automatic['signatures'][str(context.node_id)]
            path = f"/internal/native/bundles/calls/{context.prompt_id}/{call_id}"
            record = await request_service(session, "POST", "/internal/native/bundles/calls", body)
            progress = ProgressBar(100)
            try:
                while record["state"] in {"starting", "running"}:
                    observed = record.get('observation') or {}
                    if observed.get('progress') is not None:
                        progress.update_absolute(round(observed['progress'] * 100), 100)
                    if processing_interrupted():
                        await request_service(session, "POST", path + "/cancel")
                        throw_exception_if_processing_interrupted()
                    await asyncio.sleep(0.5)
                    record = await request_service(session, "GET", path)
            except asyncio.CancelledError:
                await asyncio.shield(request_service(session, "POST", path + "/cancel"))
                raise
            if record["state"] != "completed":
                raise software_call_error(record, str(context.prompt_id), call_id)
            summary = await request_service(session, 'GET', f'/api/v1/runs/{context.prompt_id}/calls/{call_id}')
            result = software_call_reply(summary, context.prompt_id, call_id)
            ui = {'images': record['images'], 'apf_result': [result.model_dump(mode='json')]}
            return io.NodeOutput(*record['outputs'], ui=ui)
