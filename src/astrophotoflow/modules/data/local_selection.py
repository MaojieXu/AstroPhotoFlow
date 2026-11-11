import ctypes
import json
import os
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path
from threading import Event, Lock
from astrophotoflow.core.config import ConfigurationError
from astrophotoflow.modules.data.files import SUPPORTED_EXTENSIONS

class LocalSelectionBusy(ConfigurationError):
    pass
_selection_lock = Lock()

class _Desktop:

    def __init__(self):
        self.native = ctypes.WinDLL('user32', use_last_error=True)
        self.native.GetForegroundWindow.restype = wintypes.HWND
        self.native.IsWindow.argtypes = [wintypes.HWND]
        self.native.IsWindowEnabled.argtypes = [wintypes.HWND]
        self.native.EnableWindow.argtypes = [wintypes.HWND, wintypes.BOOL]
        self.native.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.native.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.owner = self.native.GetForegroundWindow()
        self.owner_enabled = bool(self.native.IsWindowEnabled(self.owner))
        if not self.owner:
            raise ConfigurationError('无法定位当前桌面窗口，请激活网页后重新选择。')

    def close(self, process):
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        @callback_type
        def close_window(window, _):
            pid = wintypes.DWORD()
            self.native.GetWindowThreadProcessId(window, ctypes.byref(pid))
            if pid.value == process.pid:
                self.native.PostMessageW(window, 16, 0, 0)
            return True
        self.native.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        self.native.EnumWindows(close_window, 0)

    def restore_owner(self):
        if self.owner_enabled and self.native.IsWindow(self.owner):
            self.native.EnableWindow(self.owner, True)

def _cancel(process, desktop):
    desktop.close(process)
    try:
        process.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.communicate(timeout=5)
        finally:
            desktop.restore_owner()

def select_local_paths(mode: str, initial_path: Path, cancelled: Event | None=None, suggested_name: str | None=None) -> list[Path]:
    if os.name != 'nt':
        raise ConfigurationError('系统文件选择窗口目前仅支持Windows。')
    if not _selection_lock.acquire(blocking=False):
        raise LocalSelectionBusy('已有本机选择窗口打开，请先完成或取消当前选择。')
    try:
        if cancelled is not None and cancelled.is_set():
            return []
        desktop = _Desktop()
        return _choose(mode, initial_path, desktop, cancelled, suggested_name) if suggested_name is not None else _choose(mode, initial_path, desktop, cancelled)
    finally:
        _selection_lock.release()

def _choose(mode, initial_path, desktop, cancelled, suggested_name=None):
    patterns = ';'.join(('*' + extension for extension in SUPPORTED_EXTENSIONS))
    args = [sys._base_executable, '-I', str(Path(__file__).with_name('windows_picker.py')), mode, str(initial_path), str(desktop.owner), patterns, suggested_name or 'image.fits']
    process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        while True:
            if cancelled is not None and cancelled.is_set():
                _cancel(process, desktop)
                return []
            try:
                stdout, stderr = process.communicate(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, args, output=stdout, stderr=stderr)
    finally:
        if process.poll() is None:
            _cancel(process, desktop)
    value = stdout.decode('utf-8-sig').strip()
    return [Path(path).resolve() for path in json.loads(value)] if value else []
