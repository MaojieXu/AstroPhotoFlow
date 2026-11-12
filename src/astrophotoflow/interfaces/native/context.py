"""Adopted local service configuration for the native HTTP and page bridges."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from astrophotoflow.core.config import ConfigurationError, Settings, load_running_settings, load_settings
from astrophotoflow.core.localization import workspace_locale


@dataclass(frozen=True, slots=True)
class NativeServiceContext:
    settings: Settings
    token: str | None = field(repr=False)


def native_locale():
    workspace = os.environ.get('APF_WORKSPACE')
    return workspace_locale(Path(workspace)) if workspace else 'en'


def service_context(*, allow_missing_token: bool = False) -> NativeServiceContext:
    settings = load_running_settings(Path(os.environ['APF_WORKSPACE'])) if 'APF_WORKSPACE' in os.environ else load_settings()
    try:
        token = settings.token_path.read_text(encoding='utf-8').strip()
    except FileNotFoundError:
        if not allow_missing_token:
            raise
        token = None
    if token is not None and not token:
        if not allow_missing_token:
            raise ConfigurationError('服务令牌为空')
        token = None
    return NativeServiceContext(settings=settings, token=token)
