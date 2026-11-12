import json
import os
from importlib.resources import files
from pathlib import Path

from astrophotoflow.contracts.bundles import BundleManifest, BundlePreview
from astrophotoflow.contracts.localization import CapabilityDisplay
from astrophotoflow.contracts.nodes import NodeDefinition
from astrophotoflow.contracts.software import SoftwareOperation


def read_bundle_locales(root: Path, manifest: BundleManifest, operations: list) -> dict:
    result = {}
    identities = {entry['operation']['operation_id']: entry['operation'] for entry in operations}
    for locale, filename in manifest.locales.items():
        raw = json.loads(contained(root, filename).read_text(encoding='utf-8'))
        if set(raw) != set(identities):
            raise ValueError('Bundle translations must cover exactly the declared operations.')
        result[locale] = {}
        for identity, value in raw.items():
            display = CapabilityDisplay.model_validate(value)
            operation = identities[identity]
            for section in ('parameters', 'inputs', 'outputs'):
                if set(getattr(display, section)) != {item['name'] for item in operation[section]}:
                    raise ValueError('Bundle display labels must match the declared ' + section + ': ' + identity)
            result[locale][identity] = display.model_dump(mode='json')
    return result


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
        if type(entry.get('automatic_result_preview', False)) is not bool:
            raise ValueError('Automatic result preview policy must be a boolean.')
        operation = SoftwareOperation.model_validate(dict(entry['operation'], content_token='', ready=False, reason=None))
        if operation.package_id != manifest.package_id or operation.version != manifest.software_version:
            raise ValueError('Bundle operation identity mismatch.')
        if entry.get('preview') is not None:
            preview = BundlePreview.model_validate(entry['preview'])
            if not any(item.name == preview.input and item.data_kind == 'image' for item in operation.inputs):
                raise ValueError('Bundle preview input is not a declared image input.')
            if preview.output is not None and not any(item.name == preview.output and item.type == 'APF_SCIENCE' and 'fits' in item.formats for item in operation.outputs):
                raise ValueError('Bundle preview output is not a declared FITS image output.')
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
    read_bundle_locales(root, manifest, operations)
    return manifest, operations, nodes
