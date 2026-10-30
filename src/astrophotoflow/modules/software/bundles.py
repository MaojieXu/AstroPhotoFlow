"""Pinned, project-maintained bundles. Python is loaded only after activation."""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile
import httpx
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from importlib.resources import files
from pathlib import Path

from astrophotoflow.contracts.bundles import (
    BundleCollectedResult, BundleFile, BundleManifest, BundleProgress, NamedProcessPlan, ProcessPlan,
)
from astrophotoflow.contracts.software import SoftwareOperation
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software.metadata import catalog, contained, read_bundle
from astrophotoflow.modules.software.environment import bundle_environment


def release(package_id):
    value = catalog().get(package_id)
    if value is None:
        raise ApiError(404, 'RESOURCE_NOT_FOUND', '未找到项目维护的软件包。')
    manifest = BundleManifest.model_validate(value['manifest'])
    if value['tag'] != 'v' + manifest.bundle_version:
        raise ValueError('Catalog tag does not match its version and release channel.')
    return value


def remove_checkout(path: Path, parent: Path):
    resolved = path.resolve()
    if path.is_symlink() or resolved == parent.resolve() or not resolved.is_relative_to(parent.resolve()):
        raise ValueError('Refusing to remove a checkout outside its managed parent.')
    def writable(function, filename, error):
        target = Path(filename)
        if not isinstance(error, PermissionError) or not target.resolve().is_relative_to(resolved):
            raise error
        target.chmod(stat.S_IWRITE | stat.S_IREAD)
        function(filename)
    shutil.rmtree(path, onexc=writable)


def metadata(workspace: Path, package_id: str):
    root = workspace / 'software' / package_id / 'bundle'
    if root.is_dir():
        return read_bundle(root)
    item = release(package_id)
    return BundleManifest.model_validate(item['manifest']), item['operations'], item['nodes']


def ensure_git(tool_root: Path | None):
    executable = shutil.which('git')
    if executable:
        return executable
    if tool_root is None or os.name != 'nt':
        raise ApiError(503, 'GIT_NOT_READY', '未找到平台 Git 运行工具。')
    destination = tool_root / 'git-2.56.0.4'
    executable = destination / 'cmd/git.exe'
    if executable.is_file():
        return str(executable)
    tool_root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.git-', dir=tool_root))
    try:
        archive = stage / 'git.zip'
        digest = hashlib.sha256()
        url = 'https://github.com/git-for-windows/git/releases/download/v2.56.0.windows.4/MinGit-2.56.0.4-64-bit.zip'
        with httpx.stream('GET', url, follow_redirects=True, timeout=120) as response:
            response.raise_for_status()
            with archive.open('wb') as stream:
                for chunk in response.iter_bytes(1024 * 1024):
                    digest.update(chunk)
                    stream.write(chunk)
        if digest.hexdigest() != 'e3bf78351fe777fba47ddee5950082f8a98bb0f02604fdc7ba3ee2cb68ffa877':
            raise ValueError('Managed Git archive checksum mismatch.')
        extracted = stage / 'git'
        with zipfile.ZipFile(archive) as source:
            for entry in source.infolist():
                contained(extracted, entry.filename)
            source.extractall(extracted)
        if not (extracted / 'cmd/git.exe').is_file():
            raise ValueError('Managed Git executable is missing.')
        extracted.rename(destination)
    finally:
        shutil.rmtree(stage)
    return str(executable)


def git(arguments, *, cwd=None, tool_root=None, on_progress=None):
    executable = ensure_git(tool_root)
    if executable is None:
        raise ApiError(503, 'GIT_NOT_READY', '未找到 Git；请安装 Git for Windows 并登录私有仓库。')
    options = dict(cwd=cwd, text=True, encoding='utf-8', errors='replace',
                   env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'LC_ALL': 'C'},
                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if on_progress is not None:
        with subprocess.Popen([executable, *arguments], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **options) as process:
            with ThreadPoolExecutor(max_workers=1) as reader:
                reading = reader.submit(_read_clone_progress, process.stderr, on_progress)
                try:
                    process.wait(timeout=600)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raise
                reading.result()
            if process.returncode:
                raise ApiError(503, 'BUNDLE_FETCH_FAILED', 'Git 获取失败。请检查网络及系统 Git 凭据中的私有仓库访问权限。')
        return ''
    result = subprocess.run([executable, *arguments], capture_output=True, timeout=600, **options)
    if result.returncode:
        raise ApiError(503, 'BUNDLE_FETCH_FAILED', 'Git 获取失败。请检查网络及系统 Git 凭据中的私有仓库访问权限。')
    return result.stdout.strip()


def _read_clone_progress(stream, on_progress):
    phases = {'Receiving objects': 'downloading', 'Resolving deltas': 'resolving', 'Updating files': 'checking_out'}
    previous = None
    for line in stream:
        match = re.search(r'(Receiving objects|Resolving deltas|Updating files):\s+(\d+)%', line)
        if match:
            current = (phases[match[1]], int(match[2]) / 100)
            if current != previous:
                on_progress(*current)
                previous = current


def checkout(package_id: str, destination: Path, *, tool_root=None, on_progress=None):
    item = release(package_id)
    if not item['commit']:
        raise ApiError(503, 'BUNDLE_NOT_RELEASED', '该 Bundle 尚未发布固定提交。')
    git(['clone', '--depth', '1', '--branch', item['tag'], '--progress', '--', item['repository'], str(destination)], tool_root=tool_root, on_progress=on_progress)
    if on_progress is not None:
        on_progress('verifying', None)
    actual = git(['rev-parse', 'HEAD'], cwd=destination, tool_root=tool_root)
    if actual != item['commit']:
        raise ApiError(409, 'BUNDLE_VERSION_CHANGED', '远端 tag 与已确认的提交不一致，未安装。')
    manifest, operations, nodes = read_bundle(destination)
    if manifest.model_dump() != item['manifest'] or operations != item['operations'] or nodes != item['nodes']:
        raise ApiError(409, 'BUNDLE_VERSION_CHANGED', 'Bundle 内容与发布目录不一致，未安装。')
    if 'reference_files' in item and {
        name: contained(destination, name).read_bytes().decode('utf-8')
        for name in [manifest.commands, manifest.assessments] if name is not None
    } != item['reference_files']:
        raise ApiError(409, 'BUNDLE_VERSION_CHANGED', 'Bundle 参考目录与已确认快照不一致，未安装。')
    executable = contained(destination, manifest.executable)
    result = subprocess.run([str(executable), *manifest.version_args],
                            cwd=executable.parent, env=bundle_environment(executable),
                            capture_output=True, text=True, timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode or result.stdout.strip().casefold() != manifest.version_output.casefold():
        detail = (result.stderr.strip() or result.stdout.strip() or '程序没有输出。')[-2000:]
        raise ApiError(503, 'SOFTWARE_NOT_READY', f'Bundle 程序版本检查失败（退出码 {result.returncode}，预期 {manifest.version_output}）：{detail}')
    adapter_path = contained(destination, manifest.adapter)
    adapter = _adapter(str(adapter_path), actual, adapter_path.read_bytes())
    if not callable(getattr(adapter, 'build_plan', None)):
        raise ValueError('Bundle adapter does not implement SDK v1 build_plan.')
    if manifest.host_api == 2 and any(not callable(getattr(adapter, name, None)) for name in ('parse_result', 'parse_progress', 'parse_failure')):
        raise ValueError('Bundle SDK v2 requires result and progress parsers.')
    return manifest, actual


@lru_cache(maxsize=16)
def _adapter(path: str, commit: str, source: bytes):
    spec = importlib.util.spec_from_file_location('apf_bundle_' + hashlib.sha256(path.encode()).hexdigest(), path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(source, path, 'exec'), module.__dict__)
    return module


def adapter_plan(workspace: Path, package_id: str, operation_id: str, sources, parameters, directory, **options):
    root = workspace / 'software' / package_id / 'bundle'
    manifest, _, _ = metadata(workspace, package_id)
    lock = json.loads((root.parent / 'bundle-lock.json').read_text(encoding='utf-8'))
    adapter_path = contained(root, manifest.adapter)
    adapter = _adapter(str(adapter_path), lock['commit'], adapter_path.read_bytes())
    if manifest.host_api == 2:
        plan = NamedProcessPlan.model_validate(adapter.build_plan(operation_id, sources, parameters, directory, **options))
        paths = [plan.temporary_directory]
        for output in plan.outputs.values():
            paths.extend(file.path for file in output.files)
            for pattern in output.patterns + output.supporting_patterns:
                if Path(pattern.pattern).is_absolute() or '..' in Path(pattern.pattern).parts:
                    raise ValueError('Bundle output pattern escapes the invocation directory.')
                contained(directory, pattern.pattern)
    else:
        options.pop('supporting_sources', None)
        options.pop('source_groups', None)
        options.pop('supporting_groups', None)
        options.pop('source_metadata', None)
        legacy_sources = sources['image'] if isinstance(sources, dict) else sources
        plan = ProcessPlan.model_validate(adapter.build_plan(operation_id, legacy_sources, parameters, directory, **options))
        paths = list(plan.outputs)
    for output in [*paths, *([plan.linear_sample] if plan.linear_sample else [])]:
        if not output.resolve().is_relative_to(directory.resolve()):
            raise ValueError('Bundle output escapes the invocation directory.')
    return plan


def collect_result(workspace: Path, package_id: str, operation_id: str, plan, directory: Path, log_path: Path):
    if isinstance(plan, ProcessPlan):
        return BundleCollectedResult(outputs={'image': [
            BundleFile(path=path, format=plan.output_format) for path in plan.outputs
            if path.is_file() and path.stat().st_size > 0
        ]})
    root = workspace / 'software' / package_id / 'bundle'
    manifest, _, _ = metadata(workspace, package_id)
    lock = json.loads((root.parent / 'bundle-lock.json').read_text(encoding='utf-8'))
    adapter_path = contained(root, manifest.adapter)
    adapter = _adapter(str(adapter_path), lock['commit'], adapter_path.read_bytes())
    adapter.parse_result(operation_id, directory, plan, log_path)
    outputs, supporting = {}, {}

    def matches(pattern):
        paths = sorted(directory.glob(pattern.pattern))
        if len(paths) < pattern.minimum_count:
            raise ValueError('Bundle did not produce the required output: ' + pattern.pattern)
        return [BundleFile(path=path, format=pattern.format, allow_empty=pattern.allow_empty, frame_count=pattern.frame_count) for path in paths]

    for name, output in plan.outputs.items():
        outputs[name] = list(output.files)
        for pattern in output.patterns:
            outputs[name].extend(matches(pattern))
        supporting[name] = [file for pattern in output.supporting_patterns for file in matches(pattern)]
    result = BundleCollectedResult(outputs=outputs, supporting_outputs=supporting)
    for group in [*result.outputs.values(), *result.supporting_outputs.values()]:
        for file in group:
            contained(directory, str(file.path))
            if file.allow_empty and file.format != 'other':
                raise ValueError('Only declared non-scientific file outputs may be empty.')
            if not file.path.is_file() or (file.path.stat().st_size == 0 and not file.allow_empty):
                raise ValueError('Bundle output is missing or empty: ' + str(file.path))
    return result


def progress_reader(workspace: Path, package_id: str):
    root = workspace / 'software' / package_id / 'bundle'
    manifest = BundleManifest.model_validate_json((root / 'bundle.json').read_text(encoding='utf-8'))
    if manifest.host_api == 1:
        return None
    lock = json.loads((root.parent / 'bundle-lock.json').read_text(encoding='utf-8'))
    adapter_path = contained(root, manifest.adapter)
    adapter = _adapter(str(adapter_path), lock['commit'], adapter_path.read_bytes())
    return lambda text: BundleProgress.model_validate(adapter.parse_progress(text))


def failure_reason(workspace: Path, package_id: str, log_path: Path):
    root = workspace / 'software' / package_id / 'bundle'
    manifest, _, _ = metadata(workspace, package_id)
    if manifest.host_api == 1:
        return '程序没有完整完成操作，请查看本次调用日志。'
    lock = json.loads((root.parent / 'bundle-lock.json').read_text(encoding='utf-8'))
    adapter_path = contained(root, manifest.adapter)
    adapter = _adapter(str(adapter_path), lock['commit'], adapter_path.read_bytes())
    return str(adapter.parse_failure(log_path))


def operation(workspace: Path, package_id: str, operation_id: str, ready: bool, reason: str | None):
    _, entries, _ = metadata(workspace, package_id)
    entry = next((value for value in entries if value['operation']['operation_id'] == operation_id), None)
    if entry is None:
        raise ApiError(404, 'RESOURCE_NOT_FOUND', '未找到软件操作。')
    return operation_from_entry(entry, ready, reason)


def operation_from_entry(entry, ready: bool, reason: str | None):
    value = SoftwareOperation.model_validate(dict(entry['operation'], content_token='', ready=ready, reason=reason))
    encoded = json.dumps(value.model_dump(mode='json', exclude={'content_token', 'ready', 'reason'}), sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return value.model_copy(update={'content_token': hashlib.sha256(encoded.encode()).hexdigest()})
