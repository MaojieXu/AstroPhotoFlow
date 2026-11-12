import hashlib
import json
import logging
import os
import re
import subprocess
from pathlib import Path, PureWindowsPath

from filelock import FileLock, Timeout

from astrophotoflow.modules.software.metadata import read_bundle

from .bindings import (
    REPOSITORY_BINDINGS, bindings_path, read_bindings, receipt_path, repository_roots,
    resolve_bindings, source_state, write_bindings, write_json,
)
from .fingerprints import adapter_paths, build_inputs, content_fingerprint


logger = logging.getLogger(__name__)


def checkout_identity(root):
    manifest = json.loads((root / 'bundle.json').read_text(encoding='utf-8'))
    package_id = manifest['package_id']
    if not isinstance(package_id, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', package_id) or PureWindowsPath(package_id).is_reserved():
        raise ValueError('Invalid Bundle package identifier.')
    name = manifest.get('name')
    return {'package_id': package_id, 'name': name if isinstance(name, str) and name.strip() else package_id}


def scan_repository(repository):
    previous = repository['checkouts']
    checkouts = {}
    for root in repository_roots(Path(repository['root'])):
        key = str(root)
        try:
            checkouts[key] = checkout_identity(root)
        except (OSError, KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, FileNotFoundError) and key not in previous:
                continue
            error = {**previous.get(key, {}), 'error': str(exc)}
            if 'package_id' not in error and previous.get(key) != error:
                logger.warning('Cannot identify development Bundle at %s: %s', root, exc)
            checkouts[key] = error
    return {**repository, 'checkouts': checkouts}


def configure(workspace, specifications, clear, python, *, repository=None, clear_repository=False):
    workspace = Path(workspace).resolve()
    path = bindings_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(path.with_suffix('.lock')), timeout=5):
        values = read_bindings(workspace)
        previous = resolve_bindings(values)
        for package_id in clear:
            if not re.fullmatch(r'[a-z][a-z0-9-]*', package_id):
                raise ValueError('Invalid Bundle package identifier.')
            values.pop(package_id, None)
        for specification in specifications:
            package_id, source = specification.split('=', 1)
            root = Path(source).expanduser().resolve()
            identity = checkout_identity(root)
            if identity['package_id'] != package_id:
                raise ValueError('Development Bundle package identity mismatch.')
            if root == (workspace / 'software' / package_id / 'bundle').resolve():
                raise ValueError('Development source must be separate from the installed Bundle.')
            values[package_id] = {**identity, 'root': str(root), 'python': str(python)}
        if clear_repository:
            values.pop(REPOSITORY_BINDINGS, None)
        if repository is not None:
            directory = Path(repository).resolve()
            directory.mkdir(parents=True, exist_ok=True)
            selected = values.get(REPOSITORY_BINDINGS)
            checkouts = selected['checkouts'] if selected and selected['root'] == str(directory) else {}
            values[REPOSITORY_BINDINGS] = scan_repository({'root': str(directory), 'python': str(python), 'checkouts': checkouts})
        write_bindings(workspace, values, previous)
    refresh_sources(workspace, force=bool(specifications))
    return {key: source_state(workspace, key).model_dump(mode='json') for key in resolve_bindings(read_bindings(workspace))}


def refresh_sources(workspace, *, force=False):
    values = read_bindings(workspace)
    if REPOSITORY_BINDINGS in values:
        path = bindings_path(workspace)
        with FileLock(str(path.with_suffix('.lock')), timeout=5):
            values = read_bindings(workspace)
            repository = values.get(REPOSITORY_BINDINGS)
            if repository is not None:
                previous = resolve_bindings(values)
                values[REPOSITORY_BINDINGS] = scan_repository(repository)
                write_bindings(workspace, values, previous)
    for package_id, binding in resolve_bindings(values).items():
        if binding.get('error'):
            continue
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
        git = ['git', '--no-optional-locks', '-c', 'safe.directory=' + root.as_posix(), '-C', str(root)]
        options = {'text': True, 'encoding': 'utf-8', 'stderr': subprocess.PIPE,
                   'creationflags': subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0}
        is_checkout = (root / '.git').exists()
        if is_checkout:
            value.update(head=subprocess.check_output([*git, 'rev-parse', 'HEAD'], **options).strip(),
                         dirty=bool(subprocess.check_output([*git, 'status', '--porcelain'], **options).strip()))
        else:
            value.update(head=None, dirty=True)
        if module and not force and 'input_fingerprint' in value and inputs != value['input_fingerprint'] and value.get('pending') != inputs:
            value.update(state='building', error='Development source changed; waiting for generation.', pending=inputs)
            write_json(path, value)
            return
        if module and (force or inputs != value.get('input_fingerprint')):
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
            if is_checkout:
                value['dirty'] = bool(subprocess.check_output([*git, 'status', '--porcelain'], **options).strip())
        elif module and value.get('generation_failed') or output == value.get('output_fingerprint') and value.get('state') == 'ready' and inputs == value.get('input_fingerprint'):
            write_json(path, value)
            return
        value.pop('generation_failed', None)
        value.pop('pending', None)
        manifest, _, _ = read_bundle(root)
        if manifest.package_id != package_id:
            raise ValueError('Development Bundle package identity mismatch.')
        for source in sorted(adapter_paths(root, manifest.adapter)):
            compile(source.read_bytes(), str(source), 'exec')
        value.update(state='ready', error=None, input_fingerprint=inputs, output_fingerprint=output,
                     fingerprint=hashlib.sha256((inputs + output).encode()).hexdigest(),
                     software_version=manifest.software_version, bundle_version=manifest.bundle_version)
    except (OSError, KeyError, TypeError, ValueError, SyntaxError, subprocess.SubprocessError) as exc:
        value.update(state='failed', error=str(exc))
        try:
            value['output_fingerprint'] = content_fingerprint(root)
            value['fingerprint'] = hashlib.sha256((value.get('input_fingerprint', '') + value['output_fingerprint']).encode()).hexdigest()
        except (OSError, KeyError, TypeError, ValueError):
            pass
    write_json(path, value)
