from pathlib import Path

import pytest

from astrophotoflow import config
from astrophotoflow.client import AssetClient
from astrophotoflow.comfyui import proxy
from astrophotoflow.workbench import _load_config


def write_config(path: Path, port: int = 31390) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'[server]\nhost = "127.0.0.1"\nport = {port}\n'
        '[storage]\ndata_dir = "data"\n'
        '[comfyui]\nallowed_origins = ["http://127.0.0.1:31388"]\n',
        encoding="utf-8",
    )
    return path


def test_config_path_precedence_and_selected_missing_file(tmp_path, monkeypatch):
    default = write_config(tmp_path / "defaults/config.toml", 31001)
    active = write_config(tmp_path / "active/config.toml", 31002)
    environment = write_config(tmp_path / "environment/config.toml", 31003)
    explicit = write_config(tmp_path / "explicit/config.toml", 31004)
    monkeypatch.setattr(config, "CONFIG_PATH", default)
    monkeypatch.delenv("ASTROPHOTOFLOW_CONFIG", raising=False)
    assert config.load_settings().port == 31001
    (default.parent / "active-workspace").write_text(str(active), encoding="utf-8")
    assert config.load_settings().port == 31002
    monkeypatch.setenv("ASTROPHOTOFLOW_CONFIG", str(environment))
    assert config.load_settings().port == 31003
    assert config.load_settings(explicit).port == 31004
    missing = tmp_path / "missing/config.toml"
    with pytest.raises(config.ConfigurationError, match="不存在"):
        config.load_settings(missing)
    monkeypatch.setenv("ASTROPHOTOFLOW_CONFIG", str(missing))
    with pytest.raises(config.ConfigurationError, match="不存在"):
        config.load_settings()


def test_all_entrypoints_share_resolved_settings(tmp_path, monkeypatch):
    path = write_config(tmp_path / "workspace/config.toml")
    monkeypatch.setenv("ASTROPHOTOFLOW_CONFIG", str(path))
    data = path.parent / "data"
    data.mkdir()
    (data / "service.token").write_text("test-token", encoding="utf-8")
    settings = config.load_settings()
    assert settings.data_dir == data.resolve()
    assert proxy._configuration() == (settings.service_url, set(settings.allowed_origins), "test-token")
    parsed, port, host, comfy_port = _load_config(path)
    assert parsed == settings
    assert (port, host, comfy_port) == (31390, "127.0.0.1", 31388)
    with AssetClient() as client:
        assert client.config_path == path.resolve()
        assert client.base_url == settings.service_url + "/api/v1"


def test_invalid_config_fails_consistently(tmp_path, monkeypatch):
    path = write_config(tmp_path / "config.toml")
    path.write_text(path.read_text(encoding="utf-8") + '\nunknown = true\n', encoding="utf-8")
    monkeypatch.setenv("ASTROPHOTOFLOW_CONFIG", str(path))
    with pytest.raises(config.ConfigurationError):
        config.load_settings()
    with pytest.raises(config.ConfigurationError):
        AssetClient()
    with pytest.raises(proxy.ProxyError) as error:
        proxy._configuration()
    assert error.value.code == "SERVICE_NOT_CONFIGURED"


def test_ingestion_concurrency_defaults_and_explicit_configuration(tmp_path):
    path = write_config(tmp_path / "config.toml")
    settings = config.load_settings(path)
    assert (settings.file_workers, settings.preview_workers) == (2, 1)
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n[ingestion]\nfile_workers = 4\npreview_workers = 2\n")
    settings = config.load_settings(path)
    assert (settings.file_workers, settings.preview_workers) == (4, 2)
    path.write_text(path.read_text(encoding="utf-8").replace("file_workers = 4", "file_workers = 0"), encoding="utf-8")
    with pytest.raises(config.ConfigurationError, match="正整数"):
        config.load_settings(path)
