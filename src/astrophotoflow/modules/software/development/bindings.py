import json
from pathlib import Path

from astrophotoflow.contracts.software import BundleDevelopmentSource
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.files import replace_file

from .fingerprints import build_inputs, content_fingerprint


REPOSITORY_BINDINGS = '_repo_bundles'


def bindings_path(workspace):
    return Path(workspace) / 'run/bundle-sources.json'


def read_bindings(workspace):
    path = bindings_path(workspace)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def resolve_bindings(values):
    sources = {key: value for key, value in values.items() if key != REPOSITORY_BINDINGS}
    repository = values.get(REPOSITORY_BINDINGS)
    if repository is None:
        return sources
    roots = {key: [Path(value['root'])] for key, value in sources.items()}
    for root, checkout in repository['checkouts'].items():
        package_id = checkout.get('package_id')
        if package_id is None:
            continue
        path = Path(root)
        paths = roots.setdefault(package_id, [])
        if path not in paths:
            paths.append(path)
        sources.setdefault(package_id, {**checkout, 'root': root, 'python': repository['python']})
    for package_id, paths in roots.items():
        if len(paths) > 1:
            sources[package_id] = {
                **sources[package_id], 'error': 'Conflicting Bundle sources: ' + ', '.join(map(str, paths)),
            }
    return sources


def bindings(workspace):
    return resolve_bindings(read_bindings(workspace))


def repository_roots(directory):
    roots = set()
    try:
        for path in directory.iterdir():
            if path.name.startswith('.') or not path.is_dir():
                continue
            root = path.resolve()
            if root.parent == directory:
                roots.add(root)
    except FileNotFoundError:
        pass
    return sorted(roots)


def receipt_path(workspace, package_id):
    return Path(workspace) / 'run/bundle-development' / (package_id + '.json')


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and json.loads(path.read_text(encoding='utf-8')) == value:
        return
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    replace_file(pending, path)


def write_bindings(workspace, values, previous):
    sources = resolve_bindings(values)
    for package_id in previous.keys() | sources.keys():
        before, after = previous.get(package_id), sources.get(package_id)
        if (before and before['root'], before and before.get('error')) != (after and after['root'], after and after.get('error')):
            name = 'native-load-development.json' if after else 'native-load.json'
            (Path(workspace) / 'software' / package_id / name).unlink(missing_ok=True)
    write_json(bindings_path(workspace), values)
    return sources


def source_state(workspace, package_id):
    binding = bindings(workspace).get(package_id)
    if binding is None:
        return None
    root = Path(binding['root'])
    if binding.get('error'):
        return BundleDevelopmentSource(root=root, state='failed', error=binding['error'])
    path = receipt_path(workspace, package_id)
    raw = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    if raw.get('root') != str(root):
        return BundleDevelopmentSource(root=root, error='Waiting for development source generation.')
    value = BundleDevelopmentSource.model_validate_json(json.dumps({key: raw[key] for key in BundleDevelopmentSource.model_fields if key in raw}))
    try:
        _, inputs = build_inputs(root)
        if value.state == 'ready' and (inputs != raw.get('input_fingerprint') or content_fingerprint(root) != raw.get('output_fingerprint')):
            return value.model_copy(update={'state': 'building', 'error': 'Development source changed; waiting for reload.'})
    except (OSError, KeyError, TypeError, ValueError) as exc:
        return value.model_copy(update={'state': 'failed', 'error': str(exc)})
    return value


def source_root(workspace, package_id, *, require_ready=True):
    if not require_ready:
        binding = bindings(workspace).get(package_id)
        if binding is not None:
            return Path(binding['root'])
        return Path(workspace) / 'software' / package_id / 'bundle'
    source = source_state(workspace, package_id)
    if source is None:
        return Path(workspace) / 'software' / package_id / 'bundle'
    if source.state != 'ready':
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
