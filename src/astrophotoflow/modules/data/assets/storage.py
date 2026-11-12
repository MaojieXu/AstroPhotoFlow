from __future__ import annotations
from pathlib import Path
from astrophotoflow.core.config import Settings
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.science.files import resolve_storage_path

def asset_path(settings: Settings, version: Asset) -> Path:
    return resolve_storage_path(settings, version.storage_mode, version.storage_location)
