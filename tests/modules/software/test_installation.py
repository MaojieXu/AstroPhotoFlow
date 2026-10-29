import asyncio
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software import public, bundles


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
        shutil.copytree(source,destination)
        return bundles.read_bundle(destination)[0], 'pinned-commit'
    monkeypatch.setattr(bundles,'checkout',clone)
    before=public.get_package(settings,'siril')
    after=asyncio.run(public.install_package(settings,'siril','1.4.4',before.package_token))
    assert after.availability=='not_ready' and after.restart_required
    assert after.bundle_commit=='pinned-commit' and after.bundle_version==bundles.release('siril')['manifest']['bundle_version']
    assert after.install_path==settings.workspace/'software/siril/bundle/app'


def test_manifest_paths_cannot_escape_checkout(tmp_path):
    with pytest.raises(ValueError):
        bundles.contained(tmp_path,'../outside.py')


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
