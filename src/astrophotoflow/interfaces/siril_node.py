import asyncio
import os
import json
import sys
from importlib.resources import files
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import aiohttp
from comfy_api.latest import io
from comfy_execution.utils import get_executing_context
from comfy.model_management import processing_interrupted, throw_exception_if_processing_interrupted

from astrophotoflow.core.config import load_running_settings
from astrophotoflow.contracts.nodes import NodeDefinition


NATIVE_TYPE = "APF_169de0837f814cdea3295541ecacf463"


def _definition():
    workspace = os.environ.get("APF_WORKSPACE")
    path = Path(workspace) / "nodes/169de083-7f81-4cde-a329-5541ecacf463.json" if workspace else None
    if path is not None and path.is_file():
        definition = NodeDefinition.model_validate_json(path.read_text(encoding="utf-8"))
    else:
        values = json.loads(files("astrophotoflow").joinpath("vendor", "siril-1.4.4-node-definitions.json").read_text(encoding="utf-8"))
        definition = NodeDefinition.model_validate(values[0])
    if str(definition.definition_id) != "169de083-7f81-4cde-a329-5541ecacf463" or definition.source != "package" or definition.execution.package_id != "siril" or definition.execution.operation_id != "autostretch" or \
            [port.name for port in definition.inputs] != ["image"] or [port.name for port in definition.outputs] != ["image"] or \
            {parameter.name for parameter in definition.parameters} != {"linked", "shadowsclip", "targetbg"} or \
            any(port.type != "APF_SCIENCE" for port in definition.inputs + definition.outputs) or \
            definition.execution.inputs != {"image": "image"} or definition.execution.outputs != {"image": "image"} or \
            set(definition.execution.parameters) != {"linked", "shadowsclip", "targetbg"} or \
            any(source.kind != "parameter" or source.name != name for name, source in definition.execution.parameters.items()):
        raise ValueError("首个 Siril 节点的执行绑定或端口已变化，需先完成节点更新接入。")
    return definition


async def _request(session: aiohttp.ClientSession, method: str, path: str, body=None):
    settings = load_running_settings(Path(os.environ["APF_WORKSPACE"]))
    token = settings.token_path.read_text(encoding="utf-8").strip()
    async with session.request(method, settings.service_url + path, json=body,
                               headers={"Authorization": f"Bearer {token}"},
                               timeout=aiohttp.ClientTimeout(total=10)) as response:
        value = await response.json()
        if response.status >= 400:
            raise RuntimeError(value.get("error", {}).get("message", "无法核对 Siril 操作结果。"))
        return value


class SirilAutostretchNode(io.ComfyNode):
    RELATIVE_PYTHON_MODULE = "custom_nodes.astrophotoflow"

    @classmethod
    def define_schema(cls):
        definition = _definition()
        science = io.Custom("APF_SCIENCE")
        controls = []
        for parameter in definition.parameters:
            if parameter.name == "linked" and parameter.kind == "boolean":
                controls.append(io.Boolean.Input(parameter.name, default=parameter.default))
            elif parameter.name != "linked" and parameter.kind == "float":
                options = {"default": parameter.default, "step": parameter.step or (0.1 if parameter.name == "shadowsclip" else 0.01)}
                if parameter.name == "shadowsclip":
                    # Missing bounds become 0..2048 in ComfyUI's float widget.
                    options.update(min=-sys.float_info.max, max=sys.float_info.max)
                if parameter.minimum is not None:
                    options["min"] = parameter.minimum
                if parameter.maximum is not None:
                    options["max"] = parameter.maximum
                controls.append(io.Float.Input(parameter.name, **options))
            else:
                raise ValueError("Siril 节点参数类型与准确操作不匹配。")
        return io.Schema(
            node_id=NATIVE_TYPE, display_name=definition.name, category="AstroPhotoFlow/Siril",
            description=definition.description,
            inputs=[science.Input("image"), *controls],
            outputs=[science.Output(display_name="image")], is_output_node=True, not_idempotent=True,
        )

    @classmethod
    async def execute(cls, image, linked: bool, shadowsclip: float, targetbg: float):
        context = get_executing_context()
        if context is None:
            raise RuntimeError("Siril 节点只能在原生执行上下文中运行。")
        async with aiohttp.ClientSession() as session:
            call_id = str(uuid5(NAMESPACE_URL, f"apf:siril:{context.prompt_id}:{context.node_id}:{context.list_index}"))
            body = {"call_id": call_id, "prompt_id": context.prompt_id, "node_id": str(context.node_id),
                    "reference": image, "linked": linked, "shadowsclip": shadowsclip, "targetbg": targetbg}
            path = f"/internal/native/siril/calls/{context.prompt_id}/{call_id}"
            record = await _request(session, "POST", "/internal/native/siril/calls", body)
            try:
                while record["state"] in {"starting", "running"}:
                    if processing_interrupted():
                        await _request(session, "POST", path + "/cancel")
                        throw_exception_if_processing_interrupted()
                    await asyncio.sleep(0.5)
                    record = await _request(session, "GET", path)
            except asyncio.CancelledError:
                await asyncio.shield(_request(session, "POST", path + "/cancel"))
                raise
            if record["state"] != "completed":
                error = record.get("error") or (record.get("result") or {}).get("error")
                raise RuntimeError((error or {}).get("message", f"Siril 操作状态为 {record['state']}，请检查本次运行日志。"))
            ui = {"images": record["images"]} if record["images"] else {"text": [record.get("preview_error") or "科学输出已完成。"]}
            return io.NodeOutput(record["output"], ui=ui)
