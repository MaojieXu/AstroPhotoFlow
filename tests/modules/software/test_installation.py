from astrophotoflow.core import files as core_files
from astrophotoflow.modules.software.bundles import install as bundle_installation, git as bundle_git, catalog as bundle_catalog
from astrophotoflow.modules.software import metadata as bundle_metadata
import astrophotoflow.modules.software.packages.install as software_packages_install
import astrophotoflow.modules.software.packages.state as software_package_state
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software import public, bundles
from astrophotoflow.modules.software.environment import bundle_environment


@pytest.mark.parametrize('exit_code', [0, 7])
def test_git_streams_transfer_progress_and_keeps_process_errors(monkeypatch, exit_code):
    monkeypatch.setattr(bundle_git, 'ensure_git', lambda _root: sys.executable)
    updates = []
    script = "import sys;sys.stderr.write('Receiving objects: 42% (42/100)\\rReceiving objects: 42% (42/100)\\rUpdating files: 75% (3/4)\\n');sys.stderr.flush();sys.exit(" + str(exit_code) + ")"
    def run():
        return bundles.run_git(['-c', script], on_progress=lambda phase, value: updates.append((phase, value)))
    if exit_code:
        with pytest.raises(ApiError) as failed:
            run()
        assert failed.value.code == 'BUNDLE_FETCH_FAILED'
    else:
        assert run() == ''
    assert updates == [('downloading', 0.42), ('checking_out', 0.75)]


@pytest.mark.skipif(os.name != 'nt', reason='Windows Bundle process environment')
def test_bundle_process_uses_its_own_program_search_path_without_changing_parent(tmp_path, monkeypatch):
    original = 'C:/host/conda/bin'
    monkeypatch.setenv('PATH', original)
    monkeypatch.setenv('APF_WORKSPACE', str(tmp_path))
    executable = tmp_path/'app/bin/siril-cli.exe'
    environment = bundle_environment(executable)
    windows = Path(os.environ['SystemRoot'])
    assert environment['PATH'].split(os.pathsep) == [str(executable.resolve().parent), str(windows/'System32'), str(windows)]
    assert environment['APF_WORKSPACE'] == str(tmp_path)
    assert os.environ['PATH'] == original


def test_checkout_rejects_tag_moving_before_loading_code(tmp_path, monkeypatch):
    release = bundles.release('siril')
    calls=[]
    def git(args, **kwargs):
        calls.append(args)
        return 'different-commit' if args[0]=='rev-parse' else ''
    monkeypatch.setattr(bundle_installation, 'run_git',git)
    with pytest.raises(ApiError, match='tag'):
        bundles.checkout('siril',tmp_path/'bundle')
    assert calls[0][:4]==['clone','--depth','1','--branch']
    assert release['tag'] in calls[0]


@pytest.mark.parametrize('changed', [False, True])
def test_reference_snapshot_allows_git_eol_conversion_but_rejects_content_changes(tmp_path, monkeypatch, changed):
    from copy import deepcopy
    from astrophotoflow.contracts.bundles import BundleManifest
    selected = deepcopy(bundles.release('siril'))
    manifest = BundleManifest.model_validate(selected['manifest'])
    selected['reference_files'] = {}
    for name in [manifest.commands, manifest.assessments]:
        if name is None:
            continue
        selected['reference_files'][name] = '{\r\n  "value": 1\r\n}\r\n'
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'{\n  "value": 2\n}\n' if changed else b'{\n  "value": 1\n}\n')
    adapter = tmp_path / manifest.adapter
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_bytes(b'fixture')
    monkeypatch.setattr(bundle_installation, 'run_git', lambda args, **kwargs: selected['commit'] if args[0] == 'rev-parse' else '')
    monkeypatch.setattr(bundle_installation, 'read_bundle', lambda root: (manifest, selected['operations'], selected['nodes']))
    monkeypatch.setattr(bundle_installation, 'read_bundle_locales', lambda *args: selected.get('localizations', {}))
    monkeypatch.setattr(bundle_installation.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=manifest.version_output))
    monkeypatch.setattr(bundle_installation, 'load_adapter', lambda *args: SimpleNamespace(**{name: lambda: None for name in ['build_plan', 'parse_result', 'parse_progress', 'parse_failure']}))
    if changed:
        with pytest.raises(ApiError) as failure:
            bundles.checkout('siril', tmp_path, release_record=selected)
        assert failure.value.code == 'BUNDLE_VERSION_CHANGED'
        assert failure.value.message_key == 'bundle_reference_data_does_not_match_the_confirmed_snapshot_nothing_was_ins'
    else:
        assert bundles.checkout('siril', tmp_path, release_record=selected) == (manifest, selected['commit'])


@pytest.mark.parametrize('locale', ['en', 'zh'])
def test_install_failure_saves_localized_reason_and_keeps_diagnostic_fields(tmp_path, monkeypatch, locale):
    from astrophotoflow.core.localization import error_message
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    path = tmp_path / 'comfyui-user/default/comfy.settings.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'Comfy.Locale': locale}), encoding='utf-8')
    error = ApiError(409, 'BUNDLE_VERSION_CHANGED', '原始中文错误', fields=[{'path': 'reference/assessments.json', 'message': 'original diagnostic'}],
                     message_key='bundle_reference_data_does_not_match_the_confirmed_snapshot_nothing_was_ins')
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(bundles, 'checkout', fail)
    package = public.get_package(settings, 'siril')
    with pytest.raises(ApiError) as failure:
        asyncio.run(public.install_package(settings, 'siril', '1.4.4', package.package_token))
    reason = error_message(locale, error.code, error.message_key)
    saved = public.get_package(settings, 'siril').last_error
    assert saved.message == reason and saved.fields == error.fields
    assert error_message(locale, failure.value.code, failure.value.message_key, failure.value.message_params) == error_message(locale, '', 'bundle_installation_failed_p0', {'p0': reason})


@pytest.mark.parametrize('partial',[False,True])
def test_failed_clone_keeps_previous_state_and_removes_staging(tmp_path,monkeypatch,partial):
    settings=Settings('127.0.0.1',8190,tmp_path/'data',(),workspace=tmp_path)
    package=public.get_package(settings,'siril')
    def fail(package_id,destination,**kwargs):
        if partial:
            destination.mkdir()
            (destination/'partial').write_text('incomplete')
        raise PermissionError('original directory failure')
    monkeypatch.setattr(bundles,'checkout',fail)
    with pytest.raises(ApiError,match='original directory failure'):
        asyncio.run(public.install_package(settings,'siril','1.4.4',package.package_token))
    state=public.get_package(settings,'siril')
    assert state.operation_state=='failed' and state.availability=='not_installed'
    assert not (tmp_path/'software/siril/bundle').exists()
    assert not list((tmp_path/'software/siril').glob('.bundle-install-*'))


def test_install_uses_verified_checkout_and_waits_for_native_load(tmp_path,monkeypatch,bundle_install):
    source_settings=Settings('127.0.0.1',8190,tmp_path/'source/data',(),workspace=tmp_path/'source')
    source=bundle_install(source_settings)
    settings=Settings('127.0.0.1',8190,tmp_path/'target/data',(),workspace=tmp_path/'target')
    def clone(package_id,destination,**kwargs):
        kwargs['on_progress']('downloading', 0.42)
        observed = public.get_package(settings, 'siril')
        assert observed.progress == 0.42 and observed.phase == 'downloading'
        shutil.copytree(source,destination)
        return bundle_metadata.read_bundle(destination)[0], 'pinned-commit'
    monkeypatch.setattr(bundles,'checkout',clone)
    before=public.get_package(settings,'siril')
    after=asyncio.run(public.install_package(settings,'siril','1.4.4',before.package_token))
    assert after.availability=='not_ready' and not after.restart_required
    assert after.progress is None
    assert after.bundle_commit=='pinned-commit' and after.bundle_version==bundles.release('siril')['manifest']['bundle_version']
    assert after.install_path==settings.workspace/'software/siril/bundle/app'


@pytest.mark.skipif(os.name != 'nt', reason='Windows reader blocks progress state replacement')
def test_install_continues_when_a_progress_write_is_blocked(tmp_path, monkeypatch, bundle_install, caplog):
    source_settings = Settings('127.0.0.1', 8190, tmp_path/'source/data', (), workspace=tmp_path/'source')
    source = bundle_install(source_settings)
    settings = Settings('127.0.0.1', 8190, tmp_path/'target/data', (), workspace=tmp_path/'target')
    def clone(package_id, destination, **kwargs):
        with (settings.workspace/'software/siril/state.json').open(encoding='utf-8'):
            kwargs['on_progress']('downloading', 0.42)
            assert public.get_package(settings, 'siril').progress == 0.0
        kwargs['on_progress']('downloading', 0.75)
        assert public.get_package(settings, 'siril').progress == 0.75
        shutil.copytree(source, destination)
        return bundle_metadata.read_bundle(destination)[0], 'pinned-commit'
    monkeypatch.setattr(bundles, 'checkout', clone)
    before = public.get_package(settings, 'siril')
    after = asyncio.run(public.install_package(settings, 'siril', '1.4.4', before.package_token))
    assert after.operation_state == 'completed' and after.progress is None
    assert '保留上次进度' in caplog.text


@pytest.mark.skipif(os.name != 'nt', reason='Windows final state sharing violation')
def test_install_final_save_failure_reports_need_to_verify(tmp_path, monkeypatch, bundle_install):
    source_settings = Settings('127.0.0.1', 8190, tmp_path/'source/data', (), workspace=tmp_path/'source')
    source = bundle_install(source_settings)
    settings = Settings('127.0.0.1', 8190, tmp_path/'target/data', (), workspace=tmp_path/'target')
    calls = []
    def clone(package_id, destination, **kwargs):
        calls.append(package_id)
        shutil.copytree(source, destination)
        return bundle_metadata.read_bundle(destination)[0], 'pinned-commit'
    replace = software_package_state.os.replace
    def blocked_final(part, path):
        if json.loads(Path(part).read_text(encoding='utf-8'))['operation_state'] == 'completed':
            error = PermissionError('final state is busy')
            error.winerror = 5
            raise error
        replace(part, path)
    monkeypatch.setattr(bundles, 'checkout', clone)
    monkeypatch.setattr(software_package_state.os, 'replace', blocked_final)
    monkeypatch.setattr(core_files.time, 'sleep', lambda _: None)
    before = public.get_package(settings, 'siril')
    with pytest.raises(ApiError, match='安装结果未能保存，需核对') as failed:
        asyncio.run(public.install_package(settings, 'siril', '1.4.4', before.package_token))
    after = public.get_package(settings, 'siril')
    assert failed.value.code == 'SOFTWARE_STATE_SAVE_FAILED'
    assert after.operation_state == 'failed' and after.last_error.code == 'SOFTWARE_STATE_SAVE_FAILED'
    assert after.installed_version is None and not (settings.workspace/'software/siril/bundle').exists()
    assert calls == ['siril']


def test_manifest_paths_cannot_escape_checkout(tmp_path):
    with pytest.raises(ValueError):
        bundle_metadata.contained(tmp_path,'../outside.py')


def test_adapter_changes_apply_without_commit_timestamp_or_size_changes(tmp_path, bundle_install):
    import os
    settings = Settings('127.0.0.1', 8190, tmp_path/'data', (), workspace=tmp_path)
    root = bundle_install(settings)
    path = root/'adapter/siril.py'
    source = "from astrophotoflow.contracts.bundles import NamedProcessPlan, ProcessOutput, BundleFile\ndef build_plan(operation_id,sources,parameters,directory,**options):\n return NamedProcessPlan(arguments=['A'],temporary_directory=directory/'tmp',outputs={'image':ProcessOutput(files=[BundleFile(path=directory/'result.fit',format='fits')])})\n"
    path.write_text(source, encoding='utf-8')
    timestamp = path.stat()
    first = bundles.adapter_plan(tmp_path, 'siril', 'autostretch', [], {}, tmp_path/'runs/first')
    path.write_text(source.replace("['A']", "['B']"), encoding='utf-8')
    os.utime(path, ns=(timestamp.st_atime_ns, timestamp.st_mtime_ns))
    second = bundles.adapter_plan(tmp_path, 'siril', 'autostretch', [], {}, tmp_path/'runs/second')
    assert first.arguments == ['A'] and second.arguments == ['B']


def test_remove_checkout_handles_git_readonly_pack_files_and_keeps_siblings(tmp_path):
    import stat
    root=tmp_path/'bundle'
    pack=root/'.git/objects/pack/data.pack'
    pack.parent.mkdir(parents=True)
    pack.write_bytes(b'git data')
    pack.chmod(stat.S_IREAD)
    protected=tmp_path/'science.fit'
    protected.write_bytes(b'original')
    bundles.remove_checkout(root,tmp_path)
    assert not root.exists() and protected.read_bytes()==b'original'
    with pytest.raises(ValueError):
        bundles.remove_checkout(tmp_path,tmp_path)


@pytest.mark.parametrize('transient_lock', [False, True])
def test_update_switches_installed_metadata_and_adapter_without_touching_user_files(tmp_path, monkeypatch, bundle_install, transient_lock):
    settings = Settings('127.0.0.1', 8190, tmp_path/'workspace/data', (), workspace=tmp_path/'workspace')
    root = bundle_install(settings)
    adapter = root/'adapter/siril.py'
    implementation = "from astrophotoflow.contracts.bundles import NamedProcessPlan, ProcessOutput, BundleFile\ndef build_plan(operation_id,sources,parameters,directory,**options):\n return NamedProcessPlan(arguments=['before'],temporary_directory=directory/'tmp',outputs={'image':ProcessOutput(files=[BundleFile(path=directory/'result.fit',format='fits')])})\n"
    adapter.write_text(implementation, encoding='utf-8')
    first = bundles.adapter_plan(settings.workspace, 'siril', 'autostretch', [], {}, tmp_path/'runs/before')
    upstream = tmp_path/'updated-bundle'
    shutil.copytree(root, upstream)
    manifest_path = upstream/'bundle.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['bundle_version'] = '0.3.0-dev.1'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    operation_path = upstream/manifest['operations'][0]
    operation = json.loads(operation_path.read_text(encoding='utf-8'))
    operation['operation']['parameters'][2]['default'] = 0.4
    operation_path.write_text(json.dumps(operation), encoding='utf-8')
    (upstream/'adapter/siril.py').write_text(implementation.replace("['before']", "['after']"), encoding='utf-8')
    release = json.loads(json.dumps(bundles.release('siril')))
    release.update(manifest=manifest, tag='v0.3.0-dev.1', commit='updated-fixture', operations=[operation, *release['operations'][1:]])
    monkeypatch.setattr(bundle_catalog, 'catalog', lambda: {'siril': release})
    def checkout(package_id, destination, **kwargs):
        shutil.copytree(upstream, destination)
        return bundle_metadata.read_bundle(destination)[0], release['commit']
    monkeypatch.setattr(bundles, 'checkout', checkout)
    original = settings.workspace/'science.fit'
    workflow = settings.workspace/'workflow.json'
    original.write_bytes(b'protected original')
    workflow.write_text('{}', encoding='utf-8')
    before = public.get_package(settings, 'siril')
    assert before.update_available
    rename = Path.rename
    locked_attempts = []
    if transient_lock:
        def briefly_locked(path, target):
            if path == root and Path(target).name == 'previous-bundle' and len(locked_attempts) < 2:
                locked_attempts.append(path)
                error = OSError(13, 'Bundle temporarily held by a Windows version probe')
                error.winerror = 5
                raise error
            return rename(path, target)
        monkeypatch.setattr(Path, 'rename', briefly_locked)
    after = asyncio.run(public.install_package(settings, 'siril', '1.4.4', before.package_token))
    second = bundles.adapter_plan(settings.workspace, 'siril', 'autostretch', [], {}, tmp_path/'runs/after')
    assert first.arguments == ['before'] and second.arguments == ['after']
    assert after.bundle_version == '0.3.0-dev.1' and after.bundle_commit == 'updated-fixture'
    assert after.availability == 'not_ready' and not after.update_available and not after.restart_required
    assert bundles.metadata(settings.workspace, 'siril')[1][0]['operation']['parameters'][2]['default'] == 0.4
    assert not (root.parent/'previous-bundle').exists() and not list(root.parent.glob('.bundle-install-*'))
    removed = asyncio.run(public.uninstall_package(settings, 'siril', after.package_token))
    assert removed.availability == 'not_installed' and not root.exists()
    assert original.read_bytes() == b'protected original' and workflow.read_text(encoding='utf-8') == '{}'


@pytest.mark.parametrize('winerror', [5, 32, 33, None])
def test_bundle_rename_persistent_lock_is_bounded_and_preserves_files(tmp_path, monkeypatch, winerror):
    source = tmp_path / 'bundle'
    source.mkdir()
    (source / 'original.fit').write_bytes(b'original')
    target = tmp_path / 'previous-bundle'
    attempts, waits = [], []
    failure = OSError(13, 'locked')
    if winerror is not None:
        failure.winerror = winerror
    def locked(path, destination):
        attempts.append((path, destination))
        raise failure
    monkeypatch.setattr(Path, 'rename', locked)
    monkeypatch.setattr(core_files.time, 'sleep', waits.append)
    with pytest.raises(OSError) as caught:
        software_packages_install.rename_bundle(source, target)
    assert caught.value is failure
    assert len(attempts) == (6 if winerror is not None else 1)
    assert sum(waits) <= 1.55 + 1e-9
    assert (source / 'original.fit').read_bytes() == b'original'
    assert not target.exists()


def test_failed_stage_activation_restores_original_bundle(tmp_path, monkeypatch, bundle_install):
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    root = bundle_install(settings)
    original_manifest = (root / 'bundle.json').read_bytes()
    original_lock = (root.parent / 'bundle-lock.json').read_bytes()
    def checkout(package_id, destination, **kwargs):
        shutil.copytree(root, destination)
        return bundle_metadata.read_bundle(destination)[0], 'staged'
    monkeypatch.setattr(bundles, 'checkout', checkout)
    rename = Path.rename
    def locked_stage(path, destination):
        if path.name == 'bundle' and path.parent.name.startswith('.bundle-install-'):
            failure = OSError(13, 'stage locked')
            failure.winerror = 32
            raise failure
        return rename(path, destination)
    monkeypatch.setattr(Path, 'rename', locked_stage)
    monkeypatch.setattr(core_files.time, 'sleep', lambda delay: None)
    package = public.get_package(settings, 'siril')
    with pytest.raises(ApiError) as failure:
        asyncio.run(public.install_package(settings, 'siril', '1.4.4', package.package_token))
    assert failure.value.code == 'SOFTWARE_NOT_READY'
    assert (root / 'bundle.json').read_bytes() == original_manifest
    assert (root.parent / 'bundle-lock.json').read_bytes() == original_lock
    assert not (root.parent / 'previous-bundle').exists()
    assert public.get_package(settings, 'siril').operation_state == 'failed'
