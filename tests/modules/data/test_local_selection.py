import base64
import json
import subprocess
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from astrophotoflow.modules.data import local_selection


@pytest.fixture
def chooser(tmp_path, monkeypatch):
    selected = tmp_path / "天文 素材" / "one.fits"
    process = Mock(pid=73, returncode=0)
    process.poll.return_value = 0
    process.communicate.return_value = (json.dumps([str(selected)]).encode("utf-8"), b"")
    desktop = Mock(owner=4242)
    launch = Mock(return_value=process)
    monkeypatch.setattr(local_selection, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(local_selection, "_Desktop", Mock(return_value=desktop))
    monkeypatch.setattr(local_selection.subprocess, "Popen", launch)
    monkeypatch.setattr(local_selection.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    return selected, process, desktop, launch


@pytest.mark.parametrize("mode", ["files", "folder"])
def test_file_and_folder_choosers_bind_owner_and_activate_only_their_own_dialog(tmp_path, chooser, mode):
    selected, process, desktop, launch = chooser
    assert local_selection.select_local_paths(mode, tmp_path) == [selected.resolve()]
    args = launch.call_args.args[0]
    script = base64.b64decode(args[-1]).decode("utf-16-le")
    assert "-STA" in args and launch.call_args.kwargs["stdin"] == subprocess.DEVNULL
    assert "$owner = New-Object SelectionOwner ([IntPtr]4242)" in script
    assert "$dialog.ShowDialog($owner)" in script
    assert "$timer.Stop()" in script and "$timer.Dispose()" in script
    assert "processId != GetCurrentProcessId()" in script
    assert "new IntPtr(-1)" in script and "new IntPtr(-2)" in script
    assert "[SelectionOwner]::RestoreFocus($owner.Handle)" in script
    assert ("$dialog = New-Object Windows.Forms.OpenFileDialog" if mode == "files" else "$dialog = New-Object ModernFolderDialog") in script
    assert base64.b64encode(str(tmp_path).encode("utf-8")).decode("ascii") in script
    process.terminate.assert_not_called()
    desktop.close.assert_not_called()


def test_cancel_before_launch_does_not_create_a_native_process(tmp_path, chooser):
    _, _, _, launch = chooser
    cancelled = Event()
    cancelled.set()
    assert local_selection.select_local_paths("files", tmp_path, cancelled) == []
    launch.assert_not_called()


@pytest.mark.parametrize("mode", ["files", "folder"])
def test_system_dialog_cancel_returns_no_paths(tmp_path, chooser, mode):
    _, process, desktop, _ = chooser
    process.communicate.return_value = (b"", b"")
    assert local_selection.select_local_paths(mode, tmp_path) == []
    process.terminate.assert_not_called()
    desktop.close.assert_not_called()


def test_cancel_closes_native_window_and_collects_the_child_process(tmp_path, chooser):
    _, process, desktop, _ = chooser
    cancelled = Event()

    def first_wait(**kwargs):
        cancelled.set()
        raise subprocess.TimeoutExpired("picker", kwargs["timeout"])

    process.communicate.side_effect = lambda **kwargs: first_wait(**kwargs) if not cancelled.is_set() else (b"", b"")
    assert local_selection.select_local_paths("files", tmp_path, cancelled) == []
    desktop.close.assert_called_once_with(process)
    process.terminate.assert_not_called()
    assert process.communicate.call_count == 2


def test_unresponsive_cancel_terminates_only_the_owned_child_and_restores_owner(tmp_path, chooser):
    _, process, desktop, _ = chooser
    cancelled = Event()
    calls = 0

    def wait(**kwargs):
        nonlocal calls
        calls += 1
        if calls <= 2:
            cancelled.set()
            raise subprocess.TimeoutExpired("picker", kwargs["timeout"])
        return b"", b""

    process.communicate.side_effect = wait
    assert local_selection.select_local_paths("folder", tmp_path, cancelled) == []
    desktop.close.assert_called_once_with(process)
    process.terminate.assert_called_once_with()
    desktop.restore_owner.assert_called_once_with()


def test_simultaneous_selection_is_rejected_without_creating_another_window(tmp_path, chooser):
    _, _, _, launch = chooser
    local_selection._selection_lock.acquire()
    try:
        with pytest.raises(local_selection.LocalSelectionBusy, match="已有本机选择窗口"):
            local_selection.select_local_paths("files", tmp_path)
    finally:
        local_selection._selection_lock.release()
    launch.assert_not_called()


def test_failed_native_process_releases_selection_for_the_next_request(tmp_path, chooser):
    selected, process, _, launch = chooser
    process.returncode = 1
    with pytest.raises(subprocess.CalledProcessError):
        local_selection.select_local_paths("files", tmp_path)
    process.returncode = 0
    assert local_selection.select_local_paths("files", tmp_path) == [selected.resolve()]
    assert launch.call_count == 2
