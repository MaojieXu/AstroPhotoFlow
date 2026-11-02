from __future__ import annotations

import logging

from astrophotoflow.core.localization import exception_error, localized_error, workspace_locale

logger = logging.getLogger(__name__)

class IngestionError(Exception):
    def __init__(self, code: str, message: str, *, message_key: str):
        self.code = code
        self.message = message
        self.message_key = message_key
        super().__init__(message)


def import_error(settings, exc, *, code, message_key):
    locale = workspace_locale(settings.workspace)
    if isinstance(exc, IngestionError):
        return localized_error(locale, exc.code, exc.message_key).model_dump()
    return exception_error(locale, exc, code=code, message_key=message_key).model_dump()
