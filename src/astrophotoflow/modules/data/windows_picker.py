"""Run the Windows common item dialog in the picker process."""
import ctypes
import json
import sys
from contextlib import contextmanager
from ctypes import wintypes
from uuid import UUID
_HRESULT = ctypes.c_long
_POINTER = ctypes.c_void_p
_GUID = ctypes.c_ubyte * 16
_CANCELLED = 2147943623
_E_FAIL = 2147500037
_SIGDN_FILESYSPATH = 2147844096
_FOS_OVERWRITEPROMPT = 2
_FOS_PICKFOLDERS = 32
_FOS_FORCEFILESYSTEM = 64
_FOS_ALLOWMULTISELECT = 512
_FOS_PATHMUSTEXIST = 2048
_FOS_FILEMUSTEXIST = 4096
_FILE_OPEN = ('dc1c5a9c-e88a-4dde-a5a1-60f82a20aef7', 'd57c7288-d4ad-4768-be02-9d969532d960')
_FILE_SAVE = ('c0b4e2f3-ba21-4773-8dba-335ec946eb8b', '84bccd23-5fde-4cdb-aea4-af64b83d78ab')
_SHELL_ITEM = '43826d1e-e718-42ee-bc55-a1e261c37bfe'

class _FilterSpec(ctypes.Structure):
    _fields_ = [('name', wintypes.LPCWSTR), ('patterns', wintypes.LPCWSTR)]

def _guid(value: str):
    return _GUID.from_buffer_copy(UUID(value).bytes_le)

def _check(result: int) -> None:
    if result < 0:
        raise ctypes.WinError(result)

def _method(interface, index, result_type, *argument_types):
    table = ctypes.cast(interface, ctypes.POINTER(ctypes.POINTER(_POINTER))).contents
    return ctypes.WINFUNCTYPE(result_type, _POINTER, *argument_types)(table[index])

def _invoke(interface, index, argument_types, *arguments):
    _check(_method(interface, index, _HRESULT, *argument_types)(interface, *arguments))

@contextmanager
def _interface():
    interface = _POINTER()
    try:
        yield interface
    finally:
        if interface:
            _method(interface, 2, wintypes.ULONG)(interface)

def _path(shell_item, free) -> str:
    name = _POINTER()
    _invoke(shell_item, 5, (wintypes.UINT, ctypes.POINTER(_POINTER)), _SIGDN_FILESYSPATH, ctypes.byref(name))
    try:
        return ctypes.wstring_at(name)
    finally:
        free(name)

def _results(dialog, multiple, free) -> list[str]:
    if not multiple:
        with _interface() as item:
            _invoke(dialog, 20, (ctypes.POINTER(_POINTER),), ctypes.byref(item))
            return [_path(item, free)]
    with _interface() as items:
        _invoke(dialog, 27, (ctypes.POINTER(_POINTER),), ctypes.byref(items))
        count = wintypes.DWORD()
        _invoke(items, 7, (ctypes.POINTER(wintypes.DWORD),), ctypes.byref(count))
        paths = []
        for index in range(count.value):
            with _interface() as item:
                _invoke(items, 8, (wintypes.DWORD, ctypes.POINTER(_POINTER)), index, ctypes.byref(item))
                paths.append(_path(item, free))
        return paths

def _show_dialog(dialog, owner: int) -> int:
    show = _method(dialog, 3, _HRESULT, wintypes.HWND)
    result = show(dialog, owner)
    if owner and result & 4294967295 == _E_FAIL:
        result = show(dialog, None)
    return result

def choose_paths(mode: str, initial_path: str, owner: int, patterns: str, suggested_name: str) -> list[str]:
    ole = ctypes.WinDLL('ole32')
    ole.CoInitializeEx.argtypes = [_POINTER, wintypes.DWORD]
    ole.CoInitializeEx.restype = _HRESULT
    ole.CoUninitialize.restype = None
    ole.CoCreateInstance.argtypes = [ctypes.POINTER(_GUID), _POINTER, wintypes.DWORD, ctypes.POINTER(_GUID), ctypes.POINTER(_POINTER)]
    ole.CoCreateInstance.restype = _HRESULT
    ole.CoTaskMemFree.argtypes = [_POINTER]
    ole.CoTaskMemFree.restype = None
    shell = ctypes.WinDLL('shell32')
    shell.SHCreateItemFromParsingName.argtypes = [wintypes.LPCWSTR, _POINTER, ctypes.POINTER(_GUID), ctypes.POINTER(_POINTER)]
    shell.SHCreateItemFromParsingName.restype = _HRESULT
    _check(ole.CoInitializeEx(None, 6))
    try:
        with _interface() as dialog:
            clsid, iid = _FILE_SAVE if mode == 'save' else _FILE_OPEN
            _check(ole.CoCreateInstance(ctypes.byref(_guid(clsid)), None, 1, ctypes.byref(_guid(iid)), ctypes.byref(dialog)))
            options = wintypes.DWORD()
            _invoke(dialog, 10, (ctypes.POINTER(wintypes.DWORD),), ctypes.byref(options))
            flags = options.value | _FOS_FORCEFILESYSTEM | _FOS_PATHMUSTEXIST
            if mode == 'folder':
                flags |= _FOS_PICKFOLDERS
            elif mode == 'files':
                flags |= _FOS_FILEMUSTEXIST | _FOS_ALLOWMULTISELECT
                file_types = _FilterSpec('支持的素材', patterns)
                _invoke(dialog, 4, (wintypes.UINT, ctypes.POINTER(_FilterSpec)), 1, ctypes.byref(file_types))
            else:
                flags &= ~_FOS_OVERWRITEPROMPT
                _invoke(dialog, 15, (wintypes.LPCWSTR,), suggested_name)
            _invoke(dialog, 9, (wintypes.DWORD,), flags)
            title = {'files': '选择本机素材文件', 'folder': '选择本机素材文件夹', 'save': '导出完整图像'}[mode]
            _invoke(dialog, 17, (wintypes.LPCWSTR,), title)
            with _interface() as folder:
                _check(shell.SHCreateItemFromParsingName(initial_path, None, ctypes.byref(_guid(_SHELL_ITEM)), ctypes.byref(folder)))
                _invoke(dialog, 12, (_POINTER,), folder)
            result = _show_dialog(dialog, owner)
            if result & 4294967295 == _CANCELLED:
                return []
            _check(result)
            return _results(dialog, mode == 'files', ole.CoTaskMemFree)
    finally:
        ole.CoUninitialize()
if __name__ == '__main__':
    mode, initial_path, owner, patterns, suggested_name = sys.argv[1:]
    print(json.dumps(choose_paths(mode, initial_path, int(owner), patterns, suggested_name)))
