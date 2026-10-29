import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
from threading import Event, Lock

from astrophotoflow.core.config import ConfigurationError
from astrophotoflow.modules.data.files import SUPPORTED_EXTENSIONS


class LocalSelectionBusy(ConfigurationError):
    pass


_selection_lock = Lock()


class _Desktop:
    def __init__(self):
        self.native = ctypes.WinDLL("user32", use_last_error=True)
        self.native.GetForegroundWindow.restype = wintypes.HWND
        self.native.IsWindow.argtypes = [wintypes.HWND]
        self.native.IsWindowEnabled.argtypes = [wintypes.HWND]
        self.native.EnableWindow.argtypes = [wintypes.HWND, wintypes.BOOL]
        self.native.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.native.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.native.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.owner = self.native.GetForegroundWindow()
        self.owner_enabled = bool(self.native.IsWindowEnabled(self.owner))
        if not self.owner:
            raise ConfigurationError("无法定位当前桌面窗口，请激活网页后重新选择。")

    def close(self, process):
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        @callback_type
        def close_window(window, _):
            pid = wintypes.DWORD()
            self.native.GetWindowThreadProcessId(window, ctypes.byref(pid))
            if pid.value == process.pid:
                self.native.PostMessageW(window, 0x0010, 0, 0)
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


def select_local_paths(mode: str, initial_path: Path, cancelled: Event | None = None) -> list[Path]:
    if os.name != "nt":
        raise ConfigurationError("系统文件选择窗口目前仅支持Windows。")
    if not _selection_lock.acquire(blocking=False):
        raise LocalSelectionBusy("已有本机选择窗口打开，请先完成或取消当前选择。")
    try:
        if cancelled is not None and cancelled.is_set():
            return []
        desktop = _Desktop()
        return _choose(mode, initial_path, desktop, cancelled)
    finally:
        _selection_lock.release()


def _selection_script(mode, initial_path, owner):
    encoded = base64.b64encode(str(initial_path).encode("utf-8")).decode("ascii")
    patterns = ";".join("*" + extension for extension in SUPPORTED_EXTENSIONS)
    script = """
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
[Windows.Forms.Application]::EnableVisualStyles()
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Windows.Forms;
public sealed class SelectionOwner : IWin32Window {
    public IntPtr Handle { get; private set; }
    public SelectionOwner(IntPtr handle) { Handle = handle; }
    [DllImport("user32.dll")] public static extern IntPtr GetActiveWindow();
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr handle, out uint processId);
    [DllImport("kernel32.dll")] public static extern uint GetCurrentProcessId();
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr handle);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr handle, IntPtr after, int x, int y, int cx, int cy, uint flags);
    public static bool ActivateDialog() {
        IntPtr handle = GetActiveWindow();
        uint processId;
        GetWindowThreadProcessId(handle, out processId);
        if (handle == IntPtr.Zero || processId != GetCurrentProcessId()) return false;
        SetWindowPos(handle, new IntPtr(-1), 0, 0, 0, 0, 0x0003);
        SetForegroundWindow(handle);
        SetWindowPos(handle, new IntPtr(-2), 0, 0, 0, 0, 0x0013);
        return true;
    }
    public static void RestoreFocus(IntPtr owner) {
        uint processId;
        GetWindowThreadProcessId(GetForegroundWindow(), out processId);
        if (processId == GetCurrentProcessId()) SetForegroundWindow(owner);
    }
}
'@ -ReferencedAssemblies System.Windows.Forms
$owner = New-Object SelectionOwner ([IntPtr]""" + str(owner) + """)
$timer = New-Object Windows.Forms.Timer
$timer.Interval = 50
$timer.add_Tick({ if ([SelectionOwner]::ActivateDialog()) { $timer.Stop() } })
"""
    if mode == "folder":
        script += """
$dialog = New-Object Windows.Forms.FolderBrowserDialog
$dialog.Description = '选择本机素材文件夹'
$dialog.SelectedPath = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('""" + encoded + """'))
"""
        selected = "@($dialog.SelectedPath)"
    else:
        script += """
$dialog = New-Object Windows.Forms.OpenFileDialog
$dialog.Title = '选择本机素材文件'
$dialog.Multiselect = $true
$dialog.CheckFileExists = $true
$dialog.Filter = '支持的素材|""" + patterns + """'
$dialog.InitialDirectory = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('""" + encoded + """'))
"""
        selected = "@($dialog.FileNames)"
    script += """
try {
    $timer.Start()
    if ($dialog.ShowDialog($owner) -eq [Windows.Forms.DialogResult]::OK) {
        [Console]::Write((ConvertTo-Json -InputObject """ + selected + """ -Compress))
    }
} finally {
    $timer.Stop()
    $timer.Dispose()
    [SelectionOwner]::RestoreFocus($owner.Handle)
    $dialog.Dispose()
}
"""
    return script


def _choose(mode, initial_path, desktop, cancelled):
    script = _selection_script(mode, initial_path, desktop.owner)
    command = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    args = ["powershell.exe", "-NoProfile", "-STA", "-EncodedCommand", command]
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
    value = stdout.decode("utf-8-sig").strip()
    return [Path(path).resolve() for path in json.loads(value)] if value else []
