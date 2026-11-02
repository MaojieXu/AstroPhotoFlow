import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software.metadata import contained


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


def ensure_git(tool_root: Path | None):
    executable = shutil.which('git')
    if executable:
        return executable
    if tool_root is None or os.name != 'nt':
        raise ApiError(503, 'GIT_NOT_READY', '未找到平台 Git 运行工具。', message_key='the_platform_git_tool_was_not_found')
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


def run_git(arguments, *, cwd=None, tool_root=None, on_progress=None):
    executable = ensure_git(tool_root)
    if executable is None:
        raise ApiError(503, 'GIT_NOT_READY', '未找到 Git；请安装 Git for Windows 并登录私有仓库。', message_key='git_was_not_found_install_git_for_windows_and_authenticate_with_the_private')
    options = {'cwd': cwd, 'text': True, 'encoding': 'utf-8', 'errors': 'replace',
               'env': {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'LC_ALL': 'C'},
               'creationflags': subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0}
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
                raise ApiError(503, 'BUNDLE_FETCH_FAILED', 'Git 获取失败。请检查网络及系统 Git 凭据中的私有仓库访问权限。', message_key='git_fetch_failed_check_the_network_and_private_repository_access_in_the_sys')
        return ''
    result = subprocess.run([executable, *arguments], check=False, capture_output=True, timeout=600, **options)
    if result.returncode:
        raise ApiError(503, 'BUNDLE_FETCH_FAILED', 'Git 获取失败。请检查网络及系统 Git 凭据中的私有仓库访问权限。',
            fields=[{'path': 'git', 'message': re.sub(r'(https?://)[^\s/]+@', r'\1[redacted]@', result.stderr)[-4000:]}],
            message_key='git_fetch_failed_check_the_network_and_private_repository_access_in_the_sys')
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
