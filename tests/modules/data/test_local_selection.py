import json
import subprocess
import sys
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from astrophotoflow.modules.data import local_selection, windows_picker

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

@pytest.mark.parametrize('mode', ['files', 'folder', 'save'])
def test_native_chooser_binds_owner_and_runs_in_its_own_process(tmp_path, chooser, mode):
    selected, process, desktop, launch = chooser
    assert local_selection.select_local_paths(mode, tmp_path, suggested_name='target.fits') == [selected.resolve()]
    args = launch.call_args.args[0]
    worker = Path(local_selection.__file__).with_name('windows_picker.py')
    assert args[:6] == [sys._base_executable, '-I', str(worker), mode, str(tmp_path), '4242']
    assert '*.fits' in args[6].split(';')
    assert args[7] == 'target.fits'
    assert launch.call_args.kwargs['stdin'] == subprocess.DEVNULL
    process.terminate.assert_not_called()
    desktop.close.assert_not_called()

@pytest.mark.parametrize('result,owners', [(0, [4242]), (-2147023673, [4242]), (-2147467259, [4242, None])])
def test_retries_without_owner_only_when_windows_rejects_the_owned_dialog(monkeypatch, result, owners):
    dialog = object()
    show = Mock(side_effect=[result, 0])
    monkeypatch.setattr(windows_picker, '_method', Mock(return_value=show))
    assert windows_picker._show_dialog(dialog, 4242) == (0 if len(owners) == 2 else result)
    assert [call.args for call in show.call_args_list] == [(dialog, owner) for owner in owners]

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
