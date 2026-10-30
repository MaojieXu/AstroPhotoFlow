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
    monkeypatch.setattr(bundles, 'ensure_git', lambda _root: sys.executable)
    updates = []
    script = "import sys;sys.stderr.write('Receiving objects: 42% (42/100)\\rReceiving objects: 42% (42/100)\\rUpdating files: 75% (3/4)\\n');sys.stderr.flush();sys.exit(" + str(exit_code) + ")"
    def run():
        return bundles.git(['-c', script], on_progress=lambda phase, value: updates.append((phase, value)))
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
    monkeypatch.setattr(bundles,'git',git)
    with pytest.raises(ApiError, match='tag'):
        bundles.checkout('siril',tmp_path/'bundle')
    assert calls[0][:4]==['clone','--depth','1','--branch']
    assert release['tag'] in calls[0]


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
        return bundles.read_bundle(destination)[0], 'pinned-commit'
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
        return bundles.read_bundle(destination)[0], 'pinned-commit'
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
        return bundles.read_bundle(destination)[0], 'pinned-commit'
    replace = public.os.replace
    def blocked_final(part, path):
        if json.loads(Path(part).read_text(encoding='utf-8'))['operation_state'] == 'completed':
            error = PermissionError('final state is busy')
            error.winerror = 5
            raise error
        replace(part, path)
    monkeypatch.setattr(bundles, 'checkout', clone)
    monkeypatch.setattr(public.os, 'replace', blocked_final)
    monkeypatch.setattr(public.time, 'sleep', lambda _: None)
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
        bundles.contained(tmp_path,'../outside.py')


def test_adapter_changes_apply_without_commit_timestamp_or_size_changes(tmp_path, bundle_install):
    import os
    settings = Settings('127.0.0.1', 8190, tmp_path/'data', (), workspace=tmp_path)
    root = bundle_install(settings)
    path = root/'adapter/siril.py'
    source = "from astrophotoflow.contracts.bundles import ProcessPlan\ndef build_plan(operation_id,sources,parameters,directory,**options):\n return ProcessPlan(arguments=['A'],outputs=[directory/'result.fit'],output_format='fits')\n"
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
