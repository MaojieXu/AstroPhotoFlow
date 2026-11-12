import os
import subprocess
from pathlib import Path

from astrophotoflow.contracts.bundles import BundleManifest
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software.environment import bundle_environment
from astrophotoflow.modules.software.metadata import contained, read_bundle, read_bundle_locales

from .catalog import release
from .git import run_git
from .loader import load_adapter


def checkout(package_id: str, destination: Path, *, tool_root=None, on_progress=None, release_record=None):
    official = release(package_id)
    item = release_record if release_record is not None else official
    if item['repository'] != official['repository'] or item['manifest']['package_id'] != package_id:
        raise ValueError('The selected release is outside the maintained official repository.')
    if not item['commit']:
        raise ApiError(503, 'BUNDLE_NOT_RELEASED', '该 Bundle 尚未发布固定提交。', message_key='this_bundle_has_no_published_pinned_commit_yet')
    run_git(['clone', '--depth', '1', '--branch', item['tag'], '--progress', '--', item['repository'], str(destination)], tool_root=tool_root, on_progress=on_progress)
    if on_progress is not None:
        on_progress('verifying', None)
    actual = run_git(['rev-parse', 'HEAD'], cwd=destination, tool_root=tool_root)
    if actual != item['commit']:
        raise ApiError(409, 'BUNDLE_VERSION_CHANGED', '远端 tag 与已确认的提交不一致，未安装。', message_key='the_remote_tag_does_not_match_the_confirmed_commit_nothing_was_installed')
    manifest, operations, nodes = read_bundle(destination)
    if manifest.model_dump() != BundleManifest.model_validate(item['manifest']).model_dump() or operations != item['operations'] or nodes != item['nodes']:
        raise ApiError(409, 'BUNDLE_VERSION_CHANGED', 'Bundle 内容与发布目录不一致，未安装。', message_key='bundle_content_does_not_match_the_release_catalog_nothing_was_installed')
    # Metadata-only and full Git checkouts can apply different Windows EOL rules.
    # Ignore only CRLF/LF conversion; all other reference content remains pinned.
    if 'reference_files' in item and {
        name: contained(destination, name).read_bytes().decode('utf-8').replace('\r\n', '\n')
        for name in [manifest.commands, manifest.assessments] if name is not None
    } != {name: content.replace('\r\n', '\n') for name, content in item['reference_files'].items()}:
        raise ApiError(409, 'BUNDLE_VERSION_CHANGED', 'Bundle 参考目录与已确认快照不一致，未安装。', message_key='bundle_reference_data_does_not_match_the_confirmed_snapshot_nothing_was_ins')
    if read_bundle_locales(destination, manifest, operations) != item.get('localizations', {}):
        raise ApiError(409, 'BUNDLE_VERSION_CHANGED', 'Bundle translation snapshot differs.', message_key='bundle_content_does_not_match_the_release_catalog_nothing_was_installed')
    executable = contained(destination, manifest.executable)
    result = subprocess.run([str(executable), *manifest.version_args],
                            cwd=executable.parent, env=bundle_environment(executable),
                            check=False, capture_output=True, text=True, timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode or result.stdout.strip().casefold() != manifest.version_output.casefold():
        detail = (result.stderr.strip() or result.stdout.strip() or '程序没有输出。')[-2000:]
        raise ApiError(503, 'SOFTWARE_NOT_READY', f'Bundle 程序版本检查失败（退出码 {result.returncode}，预期 {manifest.version_output}）：{detail}', message_key='bundle_executable_version_check_failed_exit_p0_expected_p1_p2', message_params={'p0': result.returncode, 'p1': manifest.version_output, 'p2': detail})
    adapter = load_adapter(destination, manifest.adapter, actual)
    if not callable(getattr(adapter, 'build_plan', None)):
        raise TypeError('Bundle adapter does not implement build_plan.')
    if any(not callable(getattr(adapter, name, None)) for name in ('parse_result', 'parse_progress', 'parse_failure')):
        raise ValueError('Bundle SDK v2 requires result and progress parsers.')
    return manifest, actual
