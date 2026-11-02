from pathlib import Path

from astrophotoflow.contracts.metadata import AssetParametersPatch
from astrophotoflow.core.config import load_settings


def test_parameters_patch_keeps_omitted_null_and_zero_distinct():
    assert AssetParametersPatch.model_validate({}).model_dump(mode="json", exclude_unset=True) == {}
    assert AssetParametersPatch.model_validate({"gain": None, "exposure_seconds": 0}).model_dump(
        mode="json", exclude_unset=True
    ) == {"gain": None, "exposure_seconds": 0.0}


def test_relative_data_root_is_resolved_from_workspace_config(tmp_path: Path):
    config = tmp_path / "config.toml"
    config.write_text(
        '[server]\nhost = "127.0.0.1"\nport = 8190\n'
        '[storage]\ndata_dir = "data"\n'
        '[comfyui]\nallowed_origins = ["http://127.0.0.1:8188"]\n',
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.database_path == tmp_path / "data" / "astrophotoflow.sqlite3"
