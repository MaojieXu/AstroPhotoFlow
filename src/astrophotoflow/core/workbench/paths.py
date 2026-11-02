from __future__ import annotations

import os
from pathlib import Path

from .errors import WorkbenchError


def app_data() -> Path:
    if os.name == "nt":
        return Path(os.environ["LOCALAPPDATA"]) / "AstroPhotoFlow"
    return Path.home() / ".local" / "share" / "astrophotoflow"


def runtime_dir() -> Path:
    configured = os.environ.get("ASTROPHOTOFLOW_RUNTIME")
    if configured:
        return Path(configured).expanduser().resolve()
    return app_data() / "runtime" / "native-web-0.1.0"


def workspace_for_config(path: Path) -> Path:
    if path.name != "config.toml":
        raise WorkbenchError("workspace 配置文件必须命名为 config.toml。")
    return path.parent


def package_directory() -> Path:
    return Path(__file__).resolve().parents[2]
