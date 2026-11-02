import asyncio
import hashlib
import json
import os
import subprocess
from pathlib import Path
from uuid import UUID

import psutil

from astrophotoflow.contracts.nodes import NodeDefinition, definition_content_token
from astrophotoflow.contracts.software import SoftwareOperation
from astrophotoflow.core.config import load_running_settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import error_message, workspace_locale
from astrophotoflow.modules.nodes.public import list_definitions, replace_package_definitions
from astrophotoflow.modules.software.environment import bundle_environment
from astrophotoflow.modules.software.public import (
    bundle_content_fingerprint,
    bundle_observation_path,
    bundle_source_identity,
    bundle_source_receipt_path,
    bundle_source_root,
    bundle_sources_path,
    get_bundle_display,
    get_bundle_metadata,
    list_package_ids,
)

from .node import BundleNode


def bundle_fingerprint(workspace):
    paths = {*((workspace / 'nodes').glob('*.json')), bundle_sources_path(workspace)}
    digest = hashlib.sha256()
    for package_id in list_package_ids():
        root = bundle_source_root(workspace, package_id, require_ready=False)
        paths.update((bundle_source_receipt_path(workspace, package_id), root / 'bundle.json',
                      workspace / 'software' / package_id / 'bundle-lock.json'))
        try:
            digest.update(bundle_content_fingerprint(root).encode())
        except (OSError, KeyError, TypeError, ValueError):
            # Raw manifest and generation receipt still identify the failed content.
            pass
    for path in sorted(paths):
        digest.update(str(path).encode())
        try:
            digest.update(path.read_bytes())
        except FileNotFoundError:
            digest.update(b'missing')
    return digest.hexdigest()


def collect_bundle_nodes():
    workspace = os.environ.get("APF_WORKSPACE")
    if not workspace:
        return {}, {}, []
    settings = load_running_settings(Path(workspace))
    catalog = list_package_ids()
    classes, names, observations = {}, {}, []
    for package_id in catalog:
        observation = {"ready": True, "reason": None, "nodes": {}}
        root = bundle_source_root(settings.workspace, package_id, require_ready=False)
        try:
            bundle_source_root(settings.workspace, package_id)
            if not root.is_dir():
                raise ValueError("尚未安装 Bundle。")
            manifest, operations, bundled = get_bundle_metadata(settings, package_id)
            displays = get_bundle_display(settings, package_id)
            if manifest.package_id != package_id:
                raise ValueError('Bundle package identity mismatch.')
            lock = bundle_source_identity(settings.workspace, package_id)
            observation.update(commit=lock['commit'], fingerprint=lock.get('fingerprint'), root=str(root))
            executable = (root / manifest.executable).resolve()
            if not executable.is_relative_to(root.resolve()) or not (root / manifest.adapter).is_file():
                raise ValueError("Bundle executable or adapter is unavailable.")
            checked = subprocess.run([str(executable), *manifest.version_args], cwd=executable.parent, env=bundle_environment(executable),
                check=False, capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if checked.returncode or checked.stdout.strip().casefold() != manifest.version_output.casefold():
                raise ValueError("Bundle program version check failed.")
            current = [item for item in list_definitions(settings.workspace)
                       if item.definition.source == "package" and item.definition.execution.package_id == package_id]
            incoming = {UUID(value["definition_id"]): NodeDefinition.model_validate(value) for value in bundled}
            declared = set(incoming)
            for saved in current:
                incoming.setdefault(saved.definition.definition_id, saved.definition)
            expected = {item.definition.definition_id: item.content_token for item in current}
            if expected != {key: definition_content_token(value) for key, value in incoming.items()}:
                results = replace_package_definitions(settings.workspace, package_id, list(incoming.values()), expected)
                if any(not result.applied for result in results):
                    raise ValueError("Bundle 节点定义同步失败。")
            operation_ids = {value["operation"]["operation_id"] for value in operations}
            package_classes, package_names = {}, {}
            for saved in list_definitions(settings.workspace):
                definition = saved.definition
                if definition.execution.package_id != package_id or definition.execution.operation_id not in operation_ids:
                    continue
                if definition.source == "package" and definition.definition_id not in declared:
                    continue
                operation_entry = next(value['operation'] for value in operations if value['operation']['operation_id'] == definition.execution.operation_id)
                operation = SoftwareOperation.model_validate(dict(operation_entry, ready=True, reason=None, content_token=''))
                cls = type(saved.native_type, (BundleNode,), {"definition": definition, 'operation': operation,
                    'APF_AUTOMATIC_RESULT': next(value.get('automatic_result_preview', False) for value in operations if value['operation']['operation_id'] == definition.execution.operation_id),
                    "search_aliases": tuple(sorted({definition.execution.operation_id, definition.name,
                        *(values[definition.execution.operation_id]['name'] for values in displays.values()
                          if definition.source == 'package' and definition.execution.operation_id in values)})),
                    "RELATIVE_PYTHON_MODULE": "custom_nodes." + package_id,
                    "output_node": str(definition.definition_id) in manifest.output_nodes})
                schema = cls.GET_SCHEMA()
                package_classes[schema.node_id] = cls
                package_names[schema.node_id] = schema.display_name
                observation["nodes"][str(definition.definition_id)] = saved.content_token
            classes.update(package_classes)
            names.update(package_names)
        except (OSError, KeyError, ValueError, ImportError, RuntimeError, ApiError, subprocess.SubprocessError) as exc:
            observation.update(ready=False, reason=error_message(workspace_locale(settings.workspace), '', 'bundle_load_diagnostic', {'diagnostic': str(exc)}))
        observation.update(pid=os.getpid(), create_time=psutil.Process().create_time())
        path = bundle_observation_path(settings.workspace, package_id)
        observations.append((path, observation))
    return classes, names, observations


def apply_bundle_nodes(server, registry, display_names, collected):
    classes, names, observations = collected
    for name in getattr(server, "apf_bundle_types", set()):
        registry.pop(name, None)
        display_names.pop(name, None)
    registry.update(classes)
    display_names.update(names)
    server.apf_bundle_types = set(classes)
    for path, observation in observations:
        if path.name == 'native-load-development.json':
            path.parent.mkdir(parents=True, exist_ok=True)
        if path.parent.is_dir():
            part = path.with_suffix(".part")
            part.write_text(json.dumps(observation, ensure_ascii=False), encoding="utf-8")
            os.replace(part, path)


def register_bundle_nodes(server, registry, display_names):
    apply_bundle_nodes(server, registry, display_names, collect_bundle_nodes())


async def reload_bundle_nodes(server):
    import nodes
    async with server.apf_bundle_lock:
        collected = await asyncio.to_thread(collect_bundle_nodes)
        apply_bundle_nodes(server, nodes.NODE_CLASS_MAPPINGS, nodes.NODE_DISPLAY_NAME_MAPPINGS, collected)
        await server.send_json("apf.bundles_changed", {})
