import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from filelock import FileLock, Timeout

from astrophotoflow.modules.software.metadata import catalog, read_bundle

from .bindings import bindings, bindings_path, receipt_path, source_state, write_json
from .fingerprints import build_inputs, content_fingerprint


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
        build_inputs(root)
        values[package_id] = {'root': str(root), 'python': str(python)}
    for package_id in previous.keys() | values.keys():
        if previous.get(package_id) != values.get(package_id):
            name = 'native-load-development.json' if package_id in values else 'native-load.json'
            (Path(workspace) / 'software' / package_id / name).unlink(missing_ok=True)
    write_json(bindings_path(workspace), values)
    refresh_sources(workspace, force=True)
    return {key: source_state(workspace, key).model_dump(mode='json') for key in values}


def refresh_sources(workspace, *, force=False):
    for package_id, binding in bindings(workspace).items():
        path = receipt_path(workspace, package_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with FileLock(str(path.with_suffix('.lock')), timeout=0):
                refresh_source(workspace, package_id, binding, force=force)
        except Timeout:
            continue


def refresh_source(workspace, package_id, binding, *, force):
    root = Path(binding['root'])
    path = receipt_path(workspace, package_id)
    old = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    value = dict(old) if old.get('root') == str(root) else {'root': str(root)}
    try:
        module, inputs = build_inputs(root)
        output = content_fingerprint(root)
        git = ['git', '-c', 'safe.directory=' + root.as_posix(), '-C', str(root)]
        options = {'text': True, 'encoding': 'utf-8', 'stderr': subprocess.PIPE,
                   'creationflags': subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0}
        head = subprocess.check_output([*git, 'rev-parse', 'HEAD'], **options).strip()
        dirty = bool(subprocess.check_output([*git, 'status', '--porcelain'], **options).strip())
        value.update(head=head, dirty=dirty)
        if not force and inputs != value.get('input_fingerprint') and value.get('pending') != inputs:
            value.update(state='building', error='Development source changed; waiting for generation.', pending=inputs)
            write_json(path, value)
            return
        if force or inputs != value.get('input_fingerprint'):
            value['generation_failed'] = True
            value.update(state='building', error='Generating development Bundle.', input_fingerprint=inputs)
            value.pop('pending', None)
            write_json(path, value)
            log = Path(workspace) / 'logs' / ('bundle-development-' + package_id + '.log')
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open('w', encoding='utf-8') as stream:
                result = subprocess.run([binding['python'], '-m', module], cwd=root, stdout=stream, stderr=subprocess.STDOUT, check=False,
                                        timeout=120, creationflags=options['creationflags'])
            if result.returncode:
                value['generation_failed'] = True
                raise ValueError(f'Development generation failed ({result.returncode}); see {log}')
            value.pop('generation_failed', None)
            output = content_fingerprint(root)
            value['dirty'] = bool(subprocess.check_output([*git, 'status', '--porcelain'], **options).strip())
        elif value.get('generation_failed') and output == value.get('output_fingerprint') or output == value.get('output_fingerprint') and value.get('state') == 'ready':
            write_json(path, value)
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
    write_json(path, value)
