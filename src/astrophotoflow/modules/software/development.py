"""Workspace-local Bundle source bindings and generation receipts."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from filelock import FileLock, Timeout

from astrophotoflow.contracts.software import BundleDevelopmentSource
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software.metadata import catalog, contained, read_bundle


def bindings_path(workspace):
    return Path(workspace) / 'run/bundle-sources.json'


def bindings(workspace):
    path = bindings_path(workspace)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def receipt_path(workspace, package_id):
    return Path(workspace) / 'run/bundle-development' / (package_id + '.json')


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and json.loads(path.read_text(encoding='utf-8')) == value:
        return
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    pending.replace(path)


def _digest(root, paths):
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes() if path.is_file() else b'missing')
    return digest.hexdigest()


def _inputs(root):
    config = json.loads((root / 'development.json').read_text(encoding='utf-8'))
    script = contained(root, config['build'])
    if script.suffix != '.py' or not script.is_file():
        raise ValueError('Development build must name a Bundle Python script.')
    paths = {root / 'development.json', script}
    for pattern in config['watch']:
        if Path(pattern).is_absolute() or '..' in Path(pattern).parts:
            raise ValueError('Development watch patterns must stay inside the Bundle.')
        for path in root.glob(pattern):
            if path.is_file():
                contained(root, path.relative_to(root).as_posix())
                paths.add(path)
    return script, _digest(root, paths)


def content_fingerprint(root):
    paths = {root / 'bundle.json'}
    try:
        manifest = json.loads((root / 'bundle.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return _digest(root, paths)
    for name in [*manifest['operations'], *manifest['nodes'], *manifest.get('locales', {}).values(), manifest['adapter']]:
        paths.add(contained(root, name))
    paths.update(path for path in contained(root, manifest['adapter']).parent.rglob('*.py') if path.is_file())
    return _digest(root, paths)


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
        _, inputs = _inputs(root)
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
        raise ApiError(503, 'BUNDLE_DEVELOPMENT_NOT_READY', source.error or 'Development Bundle is not ready.')
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


def configure(workspace, specifications, clear, python):
    previous = bindings(workspace)
    values = dict(previous)
    for package_id in clear:
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', package_id):
            raise ValueError('Invalid Bundle package identifier.')
        values.pop(package_id, None)
    for specification in specifications:
        package_id, path = specification.split('=', 1)
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', package_id):
            raise ValueError('Invalid Bundle package identifier.')
        root = Path(path).expanduser().resolve()
        if package_id not in catalog():
            raise ValueError('Unknown maintained Bundle: ' + package_id)
        if root == (Path(workspace) / 'software' / package_id / 'bundle').resolve():
            raise ValueError('Development source must be separate from the installed Bundle.')
        manifest = json.loads((root / 'bundle.json').read_text(encoding='utf-8'))
        if manifest['package_id'] != package_id:
            raise ValueError('Development Bundle package identity mismatch.')
        _inputs(root)
        values[package_id] = {'root': str(root), 'python': str(python)}
    for package_id in previous.keys() | values.keys():
        if previous.get(package_id) != values.get(package_id):
            name = 'native-load-development.json' if package_id in values else 'native-load.json'
            (Path(workspace) / 'software' / package_id / name).unlink(missing_ok=True)
    _write(bindings_path(workspace), values)
    refresh_sources(workspace, force=True)
    return {key: source_state(workspace, key).model_dump(mode='json') for key in values}


def refresh_sources(workspace, *, force=False):
    for package_id, binding in bindings(workspace).items():
        path = receipt_path(workspace, package_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with FileLock(str(path.with_suffix('.lock')), timeout=0):
                _refresh(workspace, package_id, binding, force=force)
        except Timeout:
            continue


def _refresh(workspace, package_id, binding, *, force):
    root = Path(binding['root'])
    path = receipt_path(workspace, package_id)
    old = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    value = dict(old) if old.get('root') == str(root) else {'root': str(root)}
    try:
        script, inputs = _inputs(root)
        output = content_fingerprint(root)
        git = ['git', '-c', 'safe.directory=' + root.as_posix(), '-C', str(root)]
        options = {'text': True, 'encoding': 'utf-8', 'stderr': subprocess.PIPE,
                   'creationflags': subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0}
        head = subprocess.check_output([*git, 'rev-parse', 'HEAD'], **options).strip()
        dirty = bool(subprocess.check_output([*git, 'status', '--porcelain'], **options).strip())
        value.update(head=head, dirty=dirty)
        if not force and inputs != value.get('input_fingerprint') and value.get('pending') != inputs:
            value.update(state='building', error='Development source changed; waiting for generation.', pending=inputs)
            _write(path, value)
            return
        if force or inputs != value.get('input_fingerprint'):
            value.pop('generation_failed', None)
            value.update(state='building', error='Generating development Bundle.', input_fingerprint=inputs)
            value.pop('pending', None)
            _write(path, value)
            log = Path(workspace) / 'logs' / ('bundle-development-' + package_id + '.log')
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open('w', encoding='utf-8') as stream:
                result = subprocess.run([binding['python'], str(script)], cwd=root, stdout=stream, stderr=subprocess.STDOUT,
                                        timeout=120, creationflags=options['creationflags'])
            if result.returncode:
                value['generation_failed'] = True
                raise ValueError(f'Development generation failed ({result.returncode}); see {log}')
            output = content_fingerprint(root)
            value['dirty'] = bool(subprocess.check_output([*git, 'status', '--porcelain'], **options).strip())
        elif value.get('generation_failed') and output == value.get('output_fingerprint'):
            _write(path, value)
            return
        elif output == value.get('output_fingerprint') and value.get('state') == 'ready':
            _write(path, value)
            return
        manifest, _, _ = read_bundle(root)
        if manifest.package_id != package_id:
            raise ValueError('Development Bundle package identity mismatch.')
        value.update(state='ready', error=None, output_fingerprint=output,
                     fingerprint=hashlib.sha256((inputs + output).encode()).hexdigest(),
                     software_version=manifest.software_version, bundle_version=manifest.bundle_version)
    except (OSError, KeyError, ValueError, subprocess.SubprocessError) as exc:
        value.update(state='failed', error=str(exc))
        try:
            value['output_fingerprint'] = content_fingerprint(root)
            value['fingerprint'] = hashlib.sha256((value.get('input_fingerprint', '') + value['output_fingerprint']).encode()).hexdigest()
        except (OSError, KeyError, ValueError):
            pass
    _write(path, value)
