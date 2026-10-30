import json
import os
from importlib.resources import files
from pathlib import Path

from astrophotoflow.contracts.bundles import BundleManifest
from astrophotoflow.contracts.nodes import NodeDefinition
from astrophotoflow.contracts.software import SoftwareOperation


def catalog():
    source = os.environ.get('ASTROPHOTOFLOW_BUNDLE_CATALOG')
    raw = Path(source).read_bytes() if source is not None else files('astrophotoflow').joinpath('vendor/bundle-catalog.json').read_bytes()
    return json.loads(raw)


def contained(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Bundle path escapes its checkout.')
    return path


def read_bundle(root: Path):
    manifest = BundleManifest.model_validate_json((root / 'bundle.json').read_text(encoding='utf-8'))
    operations = [json.loads(contained(root, name).read_text(encoding='utf-8')) for name in manifest.operations]
    for entry in operations:
        operation = SoftwareOperation.model_validate(dict(entry['operation'], content_token='', ready=False, reason=None))
        if operation.package_id != manifest.package_id or operation.version != manifest.software_version:
            raise ValueError('Bundle operation identity mismatch.')
    nodes = []
    for name in manifest.nodes:
        value = json.loads(contained(root, name).read_text(encoding='utf-8'))
        operation = next((entry['operation'] for entry in operations if entry['operation']['operation_id'] == value['execution']['operation_id']), None)
        if operation is None:
            raise ValueError('Bundle node operation is unavailable.')
        value['parameters'] = operation['parameters']
        node = NodeDefinition.model_validate(value)
        if node.execution.package_id != manifest.package_id:
            raise ValueError('Bundle node ownership mismatch.')
        nodes.append(node.model_dump(mode='json'))
    if not set(manifest.output_nodes).issubset({node['definition_id'] for node in nodes}):
        raise ValueError('Bundle output_nodes must name declared node definitions.')
    contained(root, manifest.executable)
    contained(root, manifest.adapter)
    for name in [manifest.commands, manifest.assessments]:
        if name is not None:
            contained(root, name)
    return manifest, operations, nodes
