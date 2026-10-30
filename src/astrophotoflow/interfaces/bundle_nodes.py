import asyncio
import os
import json
import sys
from importlib.resources import files
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import aiohttp
import psutil
from comfy_api.latest import io
from comfy_execution.utils import get_executing_context
from comfy.model_management import processing_interrupted, throw_exception_if_processing_interrupted
from comfy.utils import ProgressBar

from astrophotoflow.core.config import load_running_settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.contracts.nodes import NodeDefinition, definition_content_token
from astrophotoflow.modules.nodes.public import list_definitions
from astrophotoflow.contracts.software import SoftwareOperation
from astrophotoflow.modules.software.public import get_bundle_metadata
import subprocess


async def _request(session: aiohttp.ClientSession, method: str, path: str, body=None):
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
    RELATIVE_PYTHON_MODULE = "custom_nodes.astrophotoflow"
    definition: NodeDefinition
    operation: SoftwareOperation
    output_node: bool = False

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
            options = {"default": parameter.default, 'advanced': parameter.advanced}
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
            category="AstroPhotoFlow/" + definition.execution.package_id,
            description=definition.description,
            inputs=inputs + controls,
            outputs=[io.Custom(port.type).Output(display_name=port.name) for port in definition.outputs],
            hidden=[io.Hidden.extra_pnginfo],
            is_output_node=cls.output_node, not_idempotent=True)

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
            path = f"/internal/native/bundles/calls/{context.prompt_id}/{call_id}"
            record = await _request(session, "POST", "/internal/native/bundles/calls", body)
            progress = ProgressBar(100)
            try:
                while record["state"] in {"starting", "running"}:
                    observed = record.get('observation') or {}
                    if observed.get('progress') is not None:
                        progress.update_absolute(round(observed['progress'] * 100), 100)
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
                message = (error or {}).get("message", f"软件操作状态为 {record['state']}，请检查本次运行日志。")
                raise RuntimeError(message + f'\n调用日志：/astrophotoflow/api/v1/runs/{context.prompt_id}/calls/{call_id}/log')
            ui = {'images': record['images'], 'apf_result': [{
                'prompt_id': context.prompt_id, 'call_id': call_id, 'node_id': str(context.node_id),
                'state': 'completed',
                'workflow_id': body['workflow_id'],
                'package_id': record['operation']['package_id'], 'software_version': record['operation']['version'],
                'bundle_version': record['bundle']['version'], 'bundle_commit': record['bundle']['commit'],
                'operation_id': record['operation']['operation_id'], 'definition_token': body['definition_token'],
                'ports': [{'name': port['name'], 'type': port['type'], 'members': len(port['files']),
                           'formats': [file['format'] for file in port['files']],
                           'names': [Path(file['path']).name for file in port['files']]} for port in record['ports']],
                'preview_error': record.get('preview_error'),
            }]}
            return io.NodeOutput(*record['outputs'], ui=ui)


def register_bundle_nodes(server, registry, display_names):
    workspace = os.environ.get("APF_WORKSPACE")
    if not workspace:
        return
    settings = load_running_settings(Path(workspace))
    catalog = json.loads(files('astrophotoflow').joinpath('vendor/bundle-catalog.json').read_text(encoding='utf-8'))
    packages = {}
    checked_packages = {}
    for saved in list_definitions(settings.workspace):
        package_id = saved.definition.execution.package_id
        observation = packages.setdefault(package_id, {"ready": True, "reason": None, "nodes": {}})
        try:
            if package_id not in catalog:
                raise ValueError('Package is not in the maintained bundle catalog.')
            if package_id not in checked_packages:
                root = settings.workspace / "software" / package_id / "bundle"
                manifest, entries, _ = get_bundle_metadata(settings, package_id)
                if manifest.package_id != package_id:
                    raise ValueError('Bundle package identity mismatch.')
                lock = json.loads((root.parent / "bundle-lock.json").read_text(encoding="utf-8"))
                executable = (root / manifest.executable).resolve()
                if not executable.is_relative_to(root.resolve()) or not (root / manifest.adapter).is_file():
                    raise ValueError("Bundle executable or adapter is unavailable.")
                checked = subprocess.run([str(executable), *manifest.version_args], cwd=executable.parent,
                    capture_output=True, text=True, timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                if checked.returncode or checked.stdout.strip().casefold() != manifest.version_output.casefold():
                    raise ValueError("Bundle program version check failed.")
                checked_packages[package_id] = manifest, lock, {entry['operation']['operation_id']: entry['operation'] for entry in entries}
            manifest, lock, operations = checked_packages[package_id]
            observation["commit"] = lock["commit"]
            definition = saved.definition
            if manifest.host_api == 1 and (len(definition.inputs) != 1 or len(definition.outputs) != 1 or any(port.type != "APF_SCIENCE" for port in definition.inputs + definition.outputs)):
                raise ValueError("Bundle SDK v1 requires one science input and output.")
            operation = SoftwareOperation.model_validate(dict(operations[definition.execution.operation_id],
                ready=True, reason=None, content_token=''))
            cls = type(saved.native_type, (BundleNode,), {"definition": definition,
                'operation': operation,
                "output_node": str(definition.definition_id) in manifest.output_nodes})
            schema = cls.GET_SCHEMA()
            registry[schema.node_id] = cls
            display_names[schema.node_id] = schema.display_name
            observation["nodes"][str(definition.definition_id)] = saved.content_token
        except (OSError, ValueError, ImportError, RuntimeError, ApiError, subprocess.SubprocessError) as exc:
            observation.update(ready=False, reason=str(exc))
    for package_id, observation in packages.items():
        observation.update(pid=os.getpid(), create_time=psutil.Process().create_time())
        path = settings.workspace / "software" / package_id / "native-load.json"
        if path.parent.is_dir():
            part = path.with_suffix(".part")
            part.write_text(json.dumps(observation, ensure_ascii=False), encoding="utf-8")
            os.replace(part, path)
