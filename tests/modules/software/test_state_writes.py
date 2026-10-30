import os

import pytest

from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software import public


def busy_error(code=5):
    error = PermissionError('file is open for reading')
    error.winerror = code
    return error


@pytest.fixture
def state_write(tmp_path):
    settings = Settings('127.0.0.1', 8190, tmp_path/'data', (), workspace=tmp_path)
    state = public._state(public.get_package(settings, 'siril'))
    public._write_package_state(settings, 'siril', state)
    return settings, state, tmp_path/'software/siril/state.json'


@pytest.mark.skipif(os.name != 'nt', reason='Windows reader blocks atomic replacement')
def test_state_write_retries_after_real_reader_closes(state_write, monkeypatch):
    settings, state, path = state_write
    pauses = []
    with path.open(encoding='utf-8') as reader:
        def release(delay):
            pauses.append(delay)
            reader.close()
        monkeypatch.setattr(public.time, 'sleep', release)
        public._write_package_state(settings, 'siril', state.model_copy(update={'progress': 0.42}))
    assert pauses == [0.05]
    assert public.get_package(settings, 'siril').progress == 0.42


@pytest.mark.skipif(os.name != 'nt', reason='Windows sharing violation')
def test_progress_skips_busy_write_then_saves_latest_value(state_write, monkeypatch, caplog):
    settings, state, path = state_write
    previous = path.read_bytes()
    replace = public.os.replace
    attempts, pauses = [], []
    def blocked(*args):
        attempts.append(args)
        raise busy_error()
    monkeypatch.setattr(public.os, 'replace', blocked)
    monkeypatch.setattr(public.time, 'sleep', pauses.append)
    public._write_package_state(settings, 'siril', state.model_copy(update={'progress': 0.42}), progress_only=True)
    assert len(attempts) == 5 and pauses == [0.05] * 4
    assert path.read_bytes() == previous
    assert '保留上次进度' in caplog.text
    monkeypatch.setattr(public.os, 'replace', replace)
    public._write_package_state(settings, 'siril', state.model_copy(update={'progress': 0.75}), progress_only=True)
    assert public.get_package(settings, 'siril').progress == 0.75


@pytest.mark.skipif(os.name != 'nt', reason='Windows sharing violation')
def test_final_state_cannot_silently_skip_persistent_lock(state_write, monkeypatch):
    settings, state, path = state_write
    previous = path.read_bytes()
    attempts = []
    def blocked(*args):
        attempts.append(args)
        raise busy_error()
    monkeypatch.setattr(public.os, 'replace', blocked)
    monkeypatch.setattr(public.time, 'sleep', lambda _: None)
    with pytest.raises(ApiError, match='安装结果未能保存，需核对') as failed:
        public._write_package_state(settings, 'siril', state.model_copy(update={'operation_state': 'completed'}))
    assert failed.value.code == 'SOFTWARE_STATE_SAVE_FAILED'
    assert len(attempts) == 5 and path.read_bytes() == previous


@pytest.mark.parametrize('code', [32, None])
def test_other_permission_errors_are_not_retried_or_suppressed(state_write, monkeypatch, code):
    settings, state, _ = state_write
    pauses = []
    def blocked(*args):
        raise busy_error(code)
    monkeypatch.setattr(public.os, 'replace', blocked)
    monkeypatch.setattr(public.time, 'sleep', pauses.append)
    with pytest.raises(PermissionError):
        public._write_package_state(settings, 'siril', state, progress_only=True)
    assert pauses == []


def test_other_io_errors_are_not_suppressed(state_write, monkeypatch):
    settings, state, _ = state_write
    def full(*args):
        raise OSError('disk full')
    monkeypatch.setattr(public.os, 'replace', full)
    with pytest.raises(OSError, match='disk full'):
        public._write_package_state(settings, 'siril', state, progress_only=True)
