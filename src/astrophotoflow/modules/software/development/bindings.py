import json
from pathlib import Path

from astrophotoflow.contracts.software import BundleDevelopmentSource
from astrophotoflow.core.errors import ApiError

from .fingerprints import build_inputs, content_fingerprint


def bindings_path(workspace):
    return Path(workspace) / 'run/bundle-sources.json'


def bindings(workspace):
    path = bindings_path(workspace)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def receipt_path(workspace, package_id):
    return Path(workspace) / 'run/bundle-development' / (package_id + '.json')


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and json.loads(path.read_text(encoding='utf-8')) == value:
        return
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    pending.replace(path)


def source_state(workspace, package_id):
    binding = bindings(workspace).get(package_id)
    if binding is None:
        return None
    root = Path(binding['root'])
    path = receipt_path(workspace, package_id)
    raw = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    if raw.get('root') != str(root):
        return BundleDevelopmentSource(root=root, error='Waiting for development source generation.')
    value = BundleDevelopmentSource.model_validate_json(json.dumps({key: raw[key] for key in BundleDevelopmentSource.model_fields if key in raw}))
    try:
        _, inputs = build_inputs(root)
        if value.state == 'ready' and (inputs != raw.get('input_fingerprint') or content_fingerprint(root) != raw.get('output_fingerprint')):
            return value.model_copy(update={'state': 'building', 'error': 'Development source changed; waiting for regeneration.'})
    except (OSError, KeyError, ValueError) as exc:
        return value.model_copy(update={'state': 'failed', 'error': str(exc)})
    return value


def source_root(workspace, package_id, *, require_ready=True):
    source = source_state(workspace, package_id)
    if source is None:
        return Path(workspace) / 'software' / package_id / 'bundle'
    if require_ready and source.state != 'ready':
        raise ApiError(503, 'BUNDLE_DEVELOPMENT_NOT_READY', source.error or 'Development Bundle is not ready.', message_key='bundle_development_not_ready', fields=[{'path': 'diagnostic', 'message': source.error or 'Development Bundle is not ready.'}])
    return source.root


def observation_path(workspace, package_id):
    name = 'native-load-development.json' if package_id in bindings(workspace) else 'native-load.json'
    return Path(workspace) / 'software' / package_id / name


def identity(workspace, package_id):
    source = source_state(workspace, package_id)
    if source is not None:
        return {'commit': source.head, 'fingerprint': source.fingerprint, 'bundle_version': source.bundle_version}
    path = Path(workspace) / 'software' / package_id / 'bundle-lock.json'
    return json.loads(path.read_text(encoding='utf-8'))
