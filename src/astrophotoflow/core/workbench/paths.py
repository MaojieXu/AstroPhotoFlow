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
    checkout = checkout_root()
    if checkout is not None:
        return checkout / ".artifacts" / "runtime"
    return app_data() / "runtime" / "native-web-0.1.0"


def workspace_for_config(path: Path) -> Path:
    if path.name != "config.toml":
        raise WorkbenchError("workspace 配置文件必须命名为 config.toml。")
    return path.parent


def package_directory() -> Path:
    return Path(__file__).resolve().parents[2]


def checkout_root() -> Path | None:
    package = package_directory()
    if package.parent.name != "src":
        return None
    root = package.parents[1]
    if (root / "pyproject.toml").is_file() and (root / "frontend/package.json").is_file():
        return root
    return None
