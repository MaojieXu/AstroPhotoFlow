from pathlib import Path
import json
import tomllib

import pytest
from filelock import FileLock
from pydantic import ValidationError

from astrophotoflow.core import config
from astrophotoflow.contracts.workbench import ConfigSave, ConfigValues, ImportRootValue
from astrophotoflow.core.errors import ApiError
from astrophotoflow.client import AssetClient
from astrophotoflow.comfyui import proxy
from astrophotoflow.core.workbench import _load_config


@pytest.fixture(autouse=True)
def isolated_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "user/config.toml")
    monkeypatch.delenv("ASTROPHOTOFLOW_CONFIG", raising=False)


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
    config._set_default_workspace(default.parent)
    assert config.load_settings().port == 31001
    (config.CONFIG_PATH.parent / "active-workspace").write_text(str(active), encoding="utf-8")
    assert config.load_settings().port == 31001
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
    assert settings.workspace == path.parent
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


def write_running_configuration(path, values):
    record = {
        "workspace": str(path.parent), "config_path": str(path),
        "effective_settings": values.model_dump(), "processes": [{"role": "asset-service"}, {"role": "comfyui"}],
    }
    run_path = path.parent / "run/processes.json"
    run_path.parent.mkdir()
    run_path.write_text(json.dumps(record), encoding="utf-8")
    return run_path


def test_no_default_does_not_read_old_pointer_or_create_workspace(tmp_path):
    config.CONFIG_PATH.parent.mkdir()
    old = config.CONFIG_PATH.parent / "active-workspace"
    old.write_text(str(tmp_path / "old/config.toml"), encoding="utf-8")
    with pytest.raises(config.ConfigurationError, match="未设置默认 workspace"):
        config.load_settings()
    assert not config.CONFIG_PATH.exists()
    assert not (tmp_path / "old").exists()


def test_configuration_read_has_no_side_effects_and_workspace_is_not_data_dir(tmp_path):
    path = write_config(tmp_path / "workspace/config.toml")
    state = config.get_configuration(path)
    assert state.default_workspace is None
    assert state.effective is None and not state.restart_required
    assert state.saved.data_dir == "data"
    assert config.load_settings(path).workspace == path.parent
    assert config.load_settings(path).data_dir == path.parent / "data"
    assert not config.CONFIG_PATH.parent.exists()
    assert not (path.parent / "run").exists()
    # Data may be external; this must not change workspace ownership.
    path.write_text(path.read_text(encoding="utf-8").replace('data_dir = "data"', 'data_dir = "../external-data"'), encoding="utf-8")
    assert config.load_settings(path).data_dir == tmp_path / "external-data"
    assert config.load_settings(path).workspace == path.parent


def test_saved_configuration_waits_for_next_start_and_preserves_running_record(tmp_path):
    path = write_config(tmp_path / "workspace/config.toml")
    initial = config.get_configuration(path)
    run_path = write_running_configuration(path, initial.saved)
    before = run_path.read_bytes()
    values = initial.saved.model_copy(update={"file_workers": 4, "service_port": 31490})
    saved = config.save_configuration(path, values, initial.config_token)
    assert saved.saved.file_workers == 4 and saved.saved.service_port == 31490
    assert saved.effective.file_workers == 2 and saved.effective.service_port == 31390
    assert saved.restart_required
    assert run_path.read_bytes() == before
    assert config.load_running_settings(path.parent).port == 31390
    assert config.load_running_settings(path.parent).file_workers == 2
    # B12 writes the values actually adopted by the next start.
    record = json.loads(before)
    record["effective_settings"] = values.model_dump()
    run_path.write_text(json.dumps(record), encoding="utf-8")
    assert not config.get_configuration(path).restart_required


def test_startup_can_read_adopted_values_before_child_processes_are_recorded(tmp_path):
    path = write_config(tmp_path / "workspace/config.toml")
    state = config.get_configuration(path)
    run_path = write_running_configuration(path, state.saved)
    record = json.loads(run_path.read_text(encoding="utf-8"))
    record["processes"] = []
    run_path.write_text(json.dumps(record), encoding="utf-8")
    assert config.load_running_settings(path.parent).port == 31390
    assert config.get_configuration(path).effective is None


def test_saving_default_does_not_retarget_current_workspace_or_move_data(tmp_path):
    path = write_config(tmp_path / "one/config.toml")
    second = write_config(tmp_path / "two/config.toml", 31490)
    config._set_default_workspace(path.parent)
    initial = config.get_configuration(path)
    run_path = write_running_configuration(path, initial.saved)
    before = run_path.read_bytes()
    saved = config.save_configuration(path, initial.saved, initial.config_token, default_workspace=second.parent)
    assert saved.default_workspace == str(second.parent)
    assert saved.config_path == str(path)
    assert not saved.restart_required
    assert config.load_settings().workspace == second.parent
    assert config.load_running_settings(path.parent).workspace == path.parent
    assert run_path.read_bytes() == before
    assert not (second.parent / "data").exists()
    assert tomllib.loads(config.CONFIG_PATH.read_text(encoding="utf-8")) == {"workspace": {"default": str(second.parent)}}


def test_stale_configuration_token_never_overwrites_new_configuration(tmp_path):
    path = write_config(tmp_path / "workspace/config.toml")
    initial = config.get_configuration(path)
    config.save_configuration(path, initial.saved.model_copy(update={"file_workers": 3}), initial.config_token)
    before = path.read_bytes()
    with pytest.raises(ApiError) as error:
        config.save_configuration(path, initial.saved.model_copy(update={"file_workers": 4}), initial.config_token)
    assert error.value.status_code == 409
    assert path.read_bytes() == before


def test_token_includes_default_location_and_target_workspace(tmp_path):
    first = write_config(tmp_path / "one/config.toml")
    second = write_config(tmp_path / "two/config.toml")
    state = config.get_configuration(first)
    assert state.config_token != config.get_configuration(second).config_token
    config._set_default_workspace(second.parent)
    with pytest.raises(ApiError) as error:
        config.save_configuration(first, state.saved, state.config_token)
    assert error.value.status_code == 409


def test_configuration_save_is_mutually_exclusive(tmp_path):
    path = write_config(tmp_path / "workspace/config.toml")
    state = config.get_configuration(path)
    config.CONFIG_PATH.parent.mkdir()
    before = path.read_bytes()
    with FileLock(str(config.CONFIG_PATH) + ".lock"):
        with pytest.raises(ApiError) as error:
            config.save_configuration(path, state.saved, state.config_token)
    assert error.value.code == "CONFIGURATION_BUSY"
    assert path.read_bytes() == before


def test_configuration_roundtrip_keeps_import_roots_and_special_path_characters(tmp_path):
    path = write_config(tmp_path / "workspace/config.toml")
    state = config.get_configuration(path)
    root = tmp_path / 'science "引号" \\目录'
    values = state.saved.model_dump()
    values["import_roots"] = [{"id": "science", "path": str(root)}]
    values["preview_workers"] = 3
    saved = config.save_configuration(path, ConfigValues(**values), state.config_token)
    loaded = config.load_settings(path)
    assert saved.saved.import_roots[0].path == str(root)
    assert loaded.import_roots == (config.ImportRoot("science", root),)
    assert loaded.preview_workers == 3


@pytest.mark.parametrize("change", [
    {"service_port": 0}, {"host": "0.0.0.0"}, {"allowed_origins": []},
    {"import_roots": [ImportRootValue(id="root", path="relative")]}, {"file_workers": 0},
])
def test_invalid_saved_values_leave_configuration_unchanged(tmp_path, change):
    path = write_config(tmp_path / "workspace/config.toml")
    state = config.get_configuration(path)
    before = path.read_bytes()
    with pytest.raises(ApiError) as error:
        config.save_configuration(path, state.saved.model_copy(update=change), state.config_token)
    assert error.value.status_code == 422
    assert path.read_bytes() == before


def test_explicit_null_or_empty_default_rejected_and_omission_keeps_default(tmp_path):
    path = write_config(tmp_path / "workspace/config.toml")
    config._set_default_workspace(path.parent)
    state = config.get_configuration(path)
    body = {"config_token": state.config_token, "values": state.saved.model_dump()}
    assert ConfigSave(**body).model_fields_set == {"config_token", "values"}
    for value in (None, "", " "):
        with pytest.raises(ValidationError):
            ConfigSave(**body, default_workspace=value)
    config.save_configuration(path, state.saved, state.config_token)
    assert config.get_configuration(path).default_workspace == str(path.parent)


def test_default_save_failure_reports_actual_partial_result(tmp_path, monkeypatch):
    path = write_config(tmp_path / "workspace/config.toml")
    state = config.get_configuration(path)
    def fail(workspace):
        raise OSError("test default write failed")
    monkeypatch.setattr(config, "_write_default_workspace", fail)
    with pytest.raises(ApiError) as error:
        config.save_configuration(path, state.saved.model_copy(update={"file_workers": 5}), state.config_token,
                                  default_workspace=tmp_path / "other")
    assert error.value.code == "CONFIGURATION_PARTIALLY_SAVED"
    assert config.load_settings(path).file_workers == 5
    assert config.get_configuration(path).default_workspace is None


def test_missing_or_wrong_running_record_is_not_replaced_with_saved_values(tmp_path):
    path = write_config(tmp_path / "workspace/config.toml")
    with pytest.raises(config.ConfigurationError, match="运行采用配置"):
        config.load_running_settings(path.parent)
    state = config.get_configuration(path)
    run_path = write_running_configuration(path, state.saved)
    record = json.loads(run_path.read_text(encoding="utf-8"))
    record["workspace"] = str(tmp_path / "wrong")
    run_path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ApiError) as error:
        config.get_configuration(path)
    assert error.value.status_code == 503
    record["processes"] = []
    run_path.write_text(json.dumps(record), encoding="utf-8")
    assert config.get_configuration(path).effective is None


def test_client_uses_adopted_values_while_running_and_saved_values_after_stop(tmp_path):
    path = write_config(tmp_path / "workspace/config.toml")
    state = config.get_configuration(path)
    run_path = write_running_configuration(path, state.saved)
    token = path.parent / "data/service.token"
    token.parent.mkdir()
    token.write_text("test-token", encoding="utf-8")
    config.save_configuration(path, state.saved.model_copy(update={"service_port": 31490}), state.config_token)
    with AssetClient(path) as client:
        assert client.base_url == "http://127.0.0.1:31390/api/v1"
    record = json.loads(run_path.read_text(encoding="utf-8"))
    record["processes"] = []
    run_path.write_text(json.dumps(record), encoding="utf-8")
    with AssetClient(path) as client:
        assert client.base_url == "http://127.0.0.1:31490/api/v1"
