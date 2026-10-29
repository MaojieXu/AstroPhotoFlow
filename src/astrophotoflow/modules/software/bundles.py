"""Pinned, project-maintained bundles. Python is loaded only after activation."""
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import tempfile
import zipfile
import httpx
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from astrophotoflow.contracts.bundles import BundleManifest, ProcessPlan
from astrophotoflow.contracts.nodes import NodeDefinition
from astrophotoflow.contracts.software import SoftwareOperation
from astrophotoflow.core.errors import ApiError


def catalog():
    return json.loads(files('astrophotoflow').joinpath('vendor/bundle-catalog.json').read_text(encoding='utf-8'))


def release(package_id):
    value = catalog().get(package_id)
    if value is None:
        raise ApiError(404, 'RESOURCE_NOT_FOUND', '未找到项目维护的软件包。')
    manifest = BundleManifest.model_validate(value['manifest'])
    if value['tag'] != 'v' + manifest.bundle_version:
        raise ValueError('Catalog tag does not match its version and release channel.')
    return value


def contained(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Bundle path escapes its checkout.')
    return path


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


def read_bundle(root: Path):
    manifest = BundleManifest.model_validate_json((root / 'bundle.json').read_text(encoding='utf-8'))
    operations = [json.loads(contained(root, name).read_text(encoding='utf-8')) for name in manifest.operations]
    for entry in operations:
        operation = SoftwareOperation.model_validate(dict(entry['operation'], content_token='', ready=False, reason=None))
        if operation.package_id != manifest.package_id or operation.version != manifest.software_version:
            raise ValueError('Bundle operation identity mismatch.')
    nodes = []
    for name in manifest.nodes:
        value = json.loads(contained(root, name).read_text(encoding='utf-8'))
        operation = next(entry['operation'] for entry in operations if entry['operation']['operation_id'] == value['execution']['operation_id'])
        # Parameters in the operation are authoritative; node bindings only name them.
        value['parameters'] = operation['parameters']
        node = NodeDefinition.model_validate(value)
        if node.execution.package_id != manifest.package_id:
            raise ValueError('Bundle node ownership mismatch.')
        nodes.append(node.model_dump(mode='json'))
    if not set(manifest.output_nodes).issubset({node['definition_id'] for node in nodes}):
        raise ValueError('Bundle output_nodes must name declared node definitions.')
    contained(root, manifest.executable)
    contained(root, manifest.adapter)
    return manifest, operations, nodes


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


def git(arguments, *, cwd=None, tool_root=None):
    executable = ensure_git(tool_root)
    if executable is None:
        raise ApiError(503, 'GIT_NOT_READY', '未找到 Git；请安装 Git for Windows 并登录私有仓库。')
    result = subprocess.run([executable, *arguments], cwd=cwd, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=600,
                            env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'},
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode:
        raise ApiError(503, 'BUNDLE_FETCH_FAILED', 'Git 获取失败。请检查网络及系统 Git 凭据中的私有仓库访问权限。')
    return result.stdout.strip()


def checkout(package_id: str, destination: Path, *, tool_root=None):
    item = release(package_id)
    if not item['commit']:
        raise ApiError(503, 'BUNDLE_NOT_RELEASED', '该 Bundle 尚未发布固定提交。')
    git(['clone', '--depth', '1', '--branch', item['tag'], '--', item['repository'], str(destination)], tool_root=tool_root)
    actual = git(['rev-parse', 'HEAD'], cwd=destination, tool_root=tool_root)
    if actual != item['commit']:
        raise ApiError(409, 'BUNDLE_VERSION_CHANGED', '远端 tag 与已确认的提交不一致，未安装。')
    manifest, operations, nodes = read_bundle(destination)
    if manifest.model_dump() != item['manifest'] or operations != item['operations'] or nodes != item['nodes']:
        raise ApiError(409, 'BUNDLE_VERSION_CHANGED', 'Bundle 内容与发布目录不一致，未安装。')
    result = subprocess.run([str(contained(destination, manifest.executable)), *manifest.version_args],
                            cwd=contained(destination, manifest.executable).parent,
                            capture_output=True, text=True, timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode or result.stdout.strip().casefold() != manifest.version_output.casefold():
        raise ApiError(503, 'SOFTWARE_NOT_READY', 'Bundle 程序未报告发布版本。')
    adapter = _adapter(str(contained(destination, manifest.adapter)), actual)
    if not callable(getattr(adapter, 'build_plan', None)):
        raise ValueError('Bundle adapter does not implement SDK v1 build_plan.')
    return manifest, actual


@lru_cache(maxsize=16)
def _adapter(path: str, commit: str):
    spec = importlib.util.spec_from_file_location('apf_bundle_' + hashlib.sha256(path.encode()).hexdigest(), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def adapter_plan(workspace: Path, package_id: str, operation_id: str, sources, parameters, directory, **options):
    root = workspace / 'software' / package_id / 'bundle'
    manifest, _, _ = read_bundle(root)
    lock = json.loads((root.parent / 'bundle-lock.json').read_text(encoding='utf-8'))
    adapter = _adapter(str(contained(root, manifest.adapter)), lock['commit'])
    plan = ProcessPlan.model_validate(adapter.build_plan(operation_id, sources, parameters, directory, **options))
    for output in [*plan.outputs, *([plan.linear_sample] if plan.linear_sample else [])]:
        if not output.resolve().is_relative_to(directory.resolve()):
            raise ValueError('Bundle output escapes the invocation directory.')
    return plan


def operation(workspace: Path, package_id: str, operation_id: str, ready: bool, reason: str | None):
    _, entries, _ = metadata(workspace, package_id)
    entry = next((value for value in entries if value['operation']['operation_id'] == operation_id), None)
    if entry is None:
        raise ApiError(404, 'RESOURCE_NOT_FOUND', '未找到软件操作。')
    value = SoftwareOperation.model_validate(dict(entry['operation'], content_token='', ready=ready, reason=reason))
    encoded = json.dumps(value.model_dump(mode='json', exclude={'content_token', 'ready', 'reason'}), sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return value.model_copy(update={'content_token': hashlib.sha256(encoded.encode()).hexdigest()})
