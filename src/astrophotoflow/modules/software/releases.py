"""Discover official tags and resolve immutable, display-independent install targets."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

from filelock import FileLock, Timeout

from astrophotoflow.contracts.bundles import BundleManifest
from astrophotoflow.contracts.software import SoftwareRelease, SoftwareReleaseListing
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import error_message, workspace_locale, localized_error
from astrophotoflow.modules.software import bundles
from astrophotoflow.modules.software.metadata import read_bundle, read_bundle_locales


VERSION = re.compile(r'^(\d+)\.(\d+)\.(\d+)(?:-dev\.(\d+))?$')


def version_key(version):
    match = VERSION.fullmatch(version)
    if match is None:
        raise ValueError('Unsupported Bundle version: ' + version)
    major, minor, patch, development = match.groups()
    return int(major), int(minor), int(patch), development is None, int(development or 0)


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    pending.replace(path)


def _root(settings, package_id, repository):
    return settings.workspace / 'software/.release-cache' / package_id / hashlib.sha256(repository.encode()).hexdigest()[:16]


def remote_tags(repository, *, tool_root=None):
    raw = bundles.git(['ls-remote', '--tags', '--', repository], tool_root=tool_root)
    tags, peeled = {}, {}
    for line in raw.splitlines():
        commit, ref = line.split(maxsplit=1)
        if not re.fullmatch(r'[0-9a-f]{40,64}', commit) or not ref.startswith('refs/tags/'):
            continue
        name = ref.removeprefix('refs/tags/')
        target = peeled if name.endswith('^{}') else tags
        target[name.removesuffix('^{}')] = commit
    tags.update(peeled)
    return {tag: commit for tag, commit in tags.items()
            if tag.startswith('v') and VERSION.fullmatch(tag[1:]) and tag not in {'v0.1.0', 'v0.1.1'}}


def _repository(root, repository, *, tool_root=None):
    path = root / 'repository.git'
    if not path.is_dir():
        bundles.git(['init', '--bare', str(path)], tool_root=tool_root)
        bundles.git(['--git-dir', str(path), 'config', 'remote.origin.url', repository], tool_root=tool_root)
        bundles.git(['--git-dir', str(path), 'config', 'remote.origin.promisor', 'true'], tool_root=tool_root)
        bundles.git(['--git-dir', str(path), 'config', 'remote.origin.partialclonefilter', 'blob:none'], tool_root=tool_root)
    return path


def _fetch(path, commit, *, tool_root=None):
    bundles.git(['--git-dir', str(path), 'fetch', '--no-tags', '--depth=1', '--filter=blob:none', 'origin', commit], tool_root=tool_root)


def _tree_objects(repo, commit, *, tool_root=None):
    raw = bundles.git(['--git-dir', str(repo), 'ls-tree', '-rz', '--format=%(objectname)%x09%(path)', commit], tool_root=tool_root)
    return {name: oid for record in raw.split('\0') if record for oid, name in [record.split('\t', 1)]}


def _paths(manifest):
    names = [manifest.executable, manifest.adapter, *manifest.operations, *manifest.nodes,
             *manifest.locales.values(), *[name for name in (manifest.commands, manifest.assessments) if name is not None]]
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or not name:
            raise ValueError('Bundle metadata path escapes the repository.')
    return names


def _header(root, repository, commit, *, tool_root=None):
    path = root / commit / 'header.json'
    if path.is_file():
        return json.loads(path.read_text(encoding='utf-8'))
    repo = _repository(root, repository, tool_root=tool_root)
    _fetch(repo, commit, tool_root=tool_root)
    objects = _tree_objects(repo, commit, tool_root=tool_root)
    raw = None
    if 'bundle.json' in objects:
        contents = bundles.git(['--git-dir', str(repo), 'show', commit + ':bundle.json'], tool_root=tool_root)
        try:
            raw = json.loads(contents)
        except json.JSONDecodeError:
            pass
    value = {'manifest': raw, 'paths': list(objects), 'objects': objects}
    _write(path, value)
    return value


def _token(repository, tag, commit, manifest):
    raw = json.dumps([repository, tag, commit, manifest], sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _describe(package_id, repository, tag, commit, header):
    version = tag[1:]
    channel = 'dev' if '-dev.' in version else 'stable'
    raw = header['manifest']
    reason, parameters = None, {}
    identity_valid = (isinstance(raw, dict) and raw.get('package_id') == package_id
                      and raw.get('bundle_version') == version and raw.get('release_channel', 'dev') == channel)
    software = raw.get('software_version') if isinstance(raw, dict) else None
    if not identity_valid or not isinstance(software, str):
        reason = 'invalid_metadata'
    elif raw.get('schema_version') != 1:
        reason, parameters = 'unsupported_schema', {'required': str(raw.get('schema_version'))}
    elif raw.get('host_api') not in (1, 2):
        reason, parameters = 'unsupported_sdk', {'required': str(raw.get('host_api'))}
    elif raw.get('platform') != 'windows-x86_64' or os.name != 'nt':
        reason, parameters = 'unsupported_platform', {'required': str(raw.get('platform'))}
    else:
        try:
            manifest = BundleManifest.model_validate(raw)
            if not set(_paths(manifest)).issubset(header['paths']):
                reason = 'missing_resources'
        except ValueError:
            reason = 'invalid_metadata'
    return SoftwareRelease(bundle_version=version, software_version=software if isinstance(software, str) else None,
        channel=channel, tag=tag, commit=commit, compatible=reason is None, reason_code=reason,
        reason_parameters=parameters, release_token=_token(repository, tag, commit, raw) if reason is None else None)


def _failure(settings, package_id, root, exc):
    previous = root / 'listing.json'
    listing = SoftwareReleaseListing.model_validate_json(previous.read_text(encoding='utf-8')) if previous.is_file() else SoftwareReleaseListing(
        package_id=package_id, releases=[], checked_at=None)
    key = 'release_check_busy' if isinstance(exc, Timeout) else 'release_check_failed'
    return listing.model_copy(update={'stale': True, 'error': localized_error(workspace_locale(settings.workspace), key.upper(), key, fields=exc.fields if isinstance(exc, ApiError) and exc.fields else [{'path': '', 'message': str(exc)}])})


def list_releases(settings, package_id):
    source = bundles.release(package_id)['repository']
    root = _root(settings, package_id, source)
    tool_root = settings.workspace / 'software/.tools'
    root.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(root / 'cache.lock'), timeout=0):
            values = [_describe(package_id, source, tag, commit, _header(root, source, commit, tool_root=tool_root))
                      for tag, commit in remote_tags(source, tool_root=tool_root).items()]
            values.sort(key=lambda value: version_key(value.bundle_version), reverse=True)
            channels = set()
            for value in values:
                if value.reason_code != 'invalid_metadata' and value.channel not in channels:
                    value.is_latest = True
                    channels.add(value.channel)
            listing = SoftwareReleaseListing(package_id=package_id, releases=values, checked_at=datetime.now(timezone.utc))
            _write(root / 'listing.json', listing.model_dump(mode='json'))
            return listing
    except (ApiError, OSError, ValueError, KeyError, TypeError, Timeout, subprocess.SubprocessError) as exc:
        return _failure(settings, package_id, root, exc)


def _snapshot(root, source, tag, commit, header, *, tool_root=None):
    path = root / commit / 'snapshot.json'
    if path.is_file():
        value = json.loads(path.read_text(encoding='utf-8'))
        if (value['repository'], value['tag'], value['commit']) != (source, tag, commit) or value['manifest'] != BundleManifest.model_validate(header['manifest']).model_dump():
            raise ValueError('Cached release identity does not match the selected commit.')
        return value
    manifest = BundleManifest.model_validate(header['manifest'])
    names = ['bundle.json', *manifest.operations, *manifest.nodes, *manifest.locales.values(),
             *[name for name in (manifest.commands, manifest.assessments) if name is not None]]
    if manifest.executable in names or manifest.adapter in names:
        raise ValueError('Executable paths cannot be used as declaration metadata.')
    repo = _repository(root, source, tool_root=tool_root)
    objects = header.get('objects') or _tree_objects(repo, commit, tool_root=tool_root)
    blobs = sorted({objects[name] for name in names})
    bundles.git(['--git-dir', str(repo), 'fetch', '--no-tags', '--filter=blob:none', 'origin', *blobs], tool_root=tool_root)
    destination = root / commit / 'metadata'
    destination.mkdir(parents=True, exist_ok=True)
    bundles.git(['--git-dir', str(repo), '--work-tree', str(destination), 'checkout', commit, '--', *names], tool_root=tool_root)
    actual, operations, nodes = read_bundle(destination)
    value = dict(repository=source, tag=tag, commit=commit, manifest=actual.model_dump(), operations=operations, nodes=nodes,
        localizations=read_bundle_locales(destination, actual, operations),
        reference_files={name: (destination / name).read_bytes().decode('utf-8').replace('\r\n', '\n')
                         for name in (actual.commands, actual.assessments) if name is not None})
    _write(path, value)
    return value


def resolve_release(settings, package_id, bundle_version, release_token):
    source = bundles.release(package_id)['repository']
    root = _root(settings, package_id, source)
    tool_root = settings.workspace / 'software/.tools'
    root.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(root / 'cache.lock'), timeout=0):
            tag = 'v' + bundle_version
            commit = remote_tags(source, tool_root=tool_root).get(tag)
            if commit is None:
                raise ValueError('The selected official tag is no longer available.')
            header = _header(root, source, commit, tool_root=tool_root)
            selected = _describe(package_id, source, tag, commit, header)
            if not selected.compatible or selected.release_token != release_token:
                raise ValueError('The selected release changed or is incompatible.')
            return _snapshot(root, source, tag, commit, header, tool_root=tool_root)
    except Timeout as exc:
        raise ApiError(409, 'BUNDLE_RELEASE_BUSY', str(exc), message_key='release_check_busy') from exc
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        raise ApiError(409, 'BUNDLE_RELEASE_CHANGED', str(exc), message_key='release_changed') from exc
