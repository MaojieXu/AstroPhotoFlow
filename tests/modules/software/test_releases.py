import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from astrophotoflow.contracts.software import SoftwareInstallRequest
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software import releases


def header(version, *, api=2, platform='windows-x86_64'):
    manifest = dict(schema_version=1, package_id='siril', name='Siril', bundle_version=version,
        release_channel='dev' if '-dev.' in version else 'stable', software_version='1.4.4',
        platform=platform, host_api=api, executable='app/bin/siril.exe', version_args=['--version'],
        version_output='siril 1.4.4', adapter='adapter/siril.py', operations=['operations/test.json'], nodes=['nodes/test.json'])
    return {'manifest': manifest, 'paths': ['app/bin/siril.exe', 'adapter/siril.py', 'operations/test.json', 'nodes/test.json']}


@pytest.fixture
def discovery(tmp_path, monkeypatch):
    source = 'https://official.example/siril.git'
    monkeypatch.setattr(releases.bundles, 'release', lambda package: {'repository': source})
    monkeypatch.setattr(releases, 'os', SimpleNamespace(name='nt'))
    tags, headers = {}, {}
    monkeypatch.setattr(releases, 'remote_tags', lambda repository: tags.copy())
    monkeypatch.setattr(releases, '_header', lambda root, repository, commit: copy.deepcopy(headers[commit]))
    settings = SimpleNamespace(workspace=tmp_path)

    def add(version, **kwargs):
        commit = f'{len(tags) + 1:040x}'
        tags['v' + version] = commit
        headers[commit] = header(version, **kwargs)
        return commit

    return settings, source, tags, headers, add


def test_numeric_sort_and_independent_latest_badges(discovery):
    settings, _, _, _, add = discovery
    for version in ['0.2.0-dev.9', '0.2.0-dev.10', '0.9.0', '0.10.0']:
        add(version)
    add('1.0.0', api=3)
    result = releases.list_releases(settings, 'siril')
    assert not result.stale and result.error is None
    assert [value.bundle_version for value in result.releases] == ['1.0.0', '0.10.0', '0.9.0', '0.2.0-dev.10', '0.2.0-dev.9']
    latest = {value.channel: value for value in result.releases if value.is_latest}
    assert latest['stable'].bundle_version == '1.0.0'
    assert not latest['stable'].compatible and latest['stable'].reason_code == 'unsupported_sdk'
    assert latest['dev'].bundle_version == '0.2.0-dev.10'


def test_remote_tags_use_peeled_commits_and_exclude_historical_experiments(monkeypatch):
    monkeypatch.setattr(releases.bundles, 'git', lambda args: '\n'.join([
        '1' * 40 + '\trefs/tags/v0.1.0', '2' * 40 + '\trefs/tags/v0.1.1',
        '3' * 40 + '\trefs/tags/v0.2.0-dev.1', '4' * 40 + '\trefs/tags/v0.2.0-dev.1^{}',
        '5' * 40 + '\trefs/tags/unreleased-work']))
    assert releases.remote_tags('official') == {'v0.2.0-dev.1': '4' * 40}


def test_stable_requires_explicit_channel_and_missing_files_are_disabled(discovery):
    settings, _, _, headers, add = discovery
    stable = add('1.0.0')
    headers[stable]['manifest'].pop('release_channel')
    missing = add('0.2.0-dev.1')
    headers[missing]['paths'].remove('adapter/siril.py')
    result = releases.list_releases(settings, 'siril')
    assert result.releases[0].reason_code == 'invalid_metadata'
    assert not result.releases[0].is_latest
    assert result.releases[1].reason_code == 'missing_resources'
    assert result.releases[1].is_latest


def test_network_failure_retains_last_successful_list_and_time(discovery, monkeypatch):
    settings, _, _, _, add = discovery
    add('0.2.0-dev.1')
    first = releases.list_releases(settings, 'siril')

    def fail(repository):
        raise OSError('network unavailable')

    monkeypatch.setattr(releases, 'remote_tags', fail)
    failed = releases.list_releases(settings, 'siril')
    assert failed.stale and failed.error.code == 'RELEASE_CHECK_FAILED'
    assert failed.checked_at == first.checked_at
    assert failed.releases == first.releases
    assert 'network unavailable' in failed.error.fields[0]['message']


def test_selected_release_does_not_follow_new_tags_and_rejects_moved_tag(discovery, monkeypatch):
    settings, _, tags, headers, add = discovery
    original = add('0.2.0-dev.1')
    selected = releases.list_releases(settings, 'siril').releases[0]
    add('0.3.0-dev.1')
    seen = []

    def snapshot(root, source, tag, commit, value):
        seen.append((tag, commit))
        return {'tag': tag, 'commit': commit, 'manifest': value['manifest']}

    monkeypatch.setattr(releases, '_snapshot', snapshot)
    result = releases.resolve_release(settings, 'siril', selected.bundle_version, selected.release_token)
    assert result['commit'] == original and seen == [(selected.tag, original)]
    replacement = 'f' * 40
    tags[selected.tag] = replacement
    headers[replacement] = header(selected.bundle_version)
    with pytest.raises(ApiError) as failure:
        releases.resolve_release(settings, 'siril', selected.bundle_version, selected.release_token)
    assert failure.value.code == 'BUNDLE_RELEASE_CHANGED'


def test_language_does_not_change_selection_token(discovery):
    settings, _, _, _, add = discovery
    add('0.2.0-dev.1')
    first = releases.list_releases(settings, 'siril')
    path = settings.workspace / 'comfyui-user/default/comfy.settings.json'
    path.parent.mkdir(parents=True)
    path.write_text('{"Comfy.Locale":"zh"}', encoding='utf-8')
    assert releases.list_releases(settings, 'siril').releases == first.releases


def test_batch_metadata_fetch_requests_only_declared_blobs(tmp_path, monkeypatch):
    manifest = header('0.2.0-dev.1')['manifest']
    objects = {'bundle.json': 'a' * 40, 'operations/test.json': 'b' * 40,
               'nodes/test.json': 'c' * 40, 'app/bin/siril.exe': 'd' * 40, 'adapter/siril.py': 'e' * 40}
    commands = []
    monkeypatch.setattr(releases, '_repository', lambda root, source: root / 'repository.git')
    monkeypatch.setattr(releases.bundles, 'git', lambda args: commands.append(args) or '')
    from astrophotoflow.contracts.bundles import BundleManifest
    monkeypatch.setattr(releases, 'read_bundle', lambda root: (BundleManifest.model_validate(manifest), [], []))
    monkeypatch.setattr(releases, 'read_bundle_locales', lambda *args: {})
    releases._snapshot(tmp_path, 'official', 'v0.2.0-dev.1', '1' * 40, {'manifest': manifest, 'objects': objects})
    fetch = next(command for command in commands if 'fetch' in command)
    assert all(value in fetch for value in ['a' * 40, 'b' * 40, 'c' * 40])
    assert 'd' * 40 not in fetch and 'e' * 40 not in fetch
    checkout = next(command for command in commands if 'checkout' in command)
    assert 'app/bin/siril.exe' not in checkout and 'adapter/siril.py' not in checkout


@pytest.mark.parametrize('extra', [{'bundle_version': '0.2.0-dev.1'}, {'release_token': 'token'},
                                  {'bundle_version': None, 'release_token': None}])
def test_selected_version_requires_a_complete_non_null_pair(extra):
    with pytest.raises(ValidationError):
        SoftwareInstallRequest(version='1.4.4', package_token='package', **extra)


def test_legacy_request_retains_program_version_meaning():
    value = SoftwareInstallRequest(version='1.4.4', package_token='package')
    assert value.version == '1.4.4' and value.bundle_version is None and value.release_token is None
