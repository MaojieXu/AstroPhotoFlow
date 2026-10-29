import asyncio
from io import BytesIO
import json
import os
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software import public


def archive_bytes(entries):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def download(monkeypatch, content):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def raise_for_status(self):
            pass

        def iter_bytes(self, _size):
            yield content

    class Client(Response):
        def __init__(self, **_kwargs):
            pass

        def stream(self, *_args):
            return Response()

    monkeypatch.setattr(public.httpx, "Client", Client)


def test_installer_extracts_into_final_path_before_version_check(tmp_path, monkeypatch):
    download(monkeypatch, archive_bytes({"siril/bin/siril-cli.exe": b"fixture", "siril/share/file.txt": b"resource"}))
    app = tmp_path / "app"
    stage = tmp_path / "stage"
    stage.mkdir()
    phases = []

    def verify(command, **kwargs):
        assert command == [str(app / "bin/siril-cli.exe"), "--version"]
        assert Path(kwargs["cwd"]) == app / "bin"
        assert (app / "share/file.txt").read_bytes() == b"resource"
        assert phases == ["installing", "verifying"]
        return SimpleNamespace(returncode=0, stdout="siril 1.4.4\n")

    monkeypatch.setattr(public.subprocess, "run", verify)
    result = public._download_and_verify_archive("https://fixed.invalid/siril.zip", stage, app, phases.append)
    assert result == app
    assert not (stage / "extract").exists()


@pytest.mark.parametrize("entry", ["siril/../escape.txt", "/siril/escape.txt", "siril/../../escape.txt"])
def test_archive_escape_is_rejected_before_creating_program(tmp_path, monkeypatch, entry):
    download(monkeypatch, archive_bytes({entry: b"invalid"}))
    stage = tmp_path / "stage"
    stage.mkdir()
    with pytest.raises(ValueError, match="不安全"):
        public._download_and_verify_archive("https://fixed.invalid/siril.zip", stage, tmp_path / "app", lambda _phase: None)
    assert not (tmp_path / "app").exists()


@pytest.mark.skipif(os.name != "nt", reason="Fixed package installation supports Windows")
@pytest.mark.parametrize("partial", [False, True])
def test_failed_install_records_original_error_instead_of_staying_running(tmp_path, monkeypatch, partial):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    package = public.get_package(settings, "siril")

    def fail(_url, _stage, app, phase):
        if partial:
            app.mkdir()
        phase("installing")
        raise PermissionError("[WinError 5] original directory failure")

    monkeypatch.setattr(public, "_download_and_verify_archive", fail)
    with pytest.raises(ApiError) as failure:
        asyncio.run(public.install_package(settings, "siril", "1.4.4", package.package_token))
    assert "WinError 5" in failure.value.message
    state = json.loads((tmp_path / "software/siril/state.json").read_text(encoding="utf-8"))
    assert state["operation_state"] == "failed" and state["phase"] is None
    assert state["last_error"]["code"] == "INSTALL_FAILED"
    assert "original directory failure" in state["last_error"]["message"]
    assert state["installed_version"] is None
    assert state["availability"] == ("not_ready" if partial else "not_installed")
    assert (state["install_path"] is not None) is partial
