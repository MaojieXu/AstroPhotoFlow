"""Local source observation and selection, without request or response objects."""
import subprocess
from pathlib import Path
from threading import Event
from astrophotoflow.contracts.imports import ImportRootEntryPage, ImportRootOut, LocalSelectionOut, LocalSelectionRequest
from astrophotoflow.core.config import ConfigurationError, Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.files import entries_page, enumerate_local
from astrophotoflow.modules.data.local_selection import LocalSelectionBusy, select_local_paths

def list_import_roots(settings: Settings) -> list[ImportRootOut]:
    result = []
    for root in settings.import_roots:
        try:
            available = root.path.resolve(strict=True).is_dir()
        except OSError:
            available = False
        result.append(ImportRootOut(id=root.id, label=root.path.name or root.id, available=available))
    return result

def list_import_root_entries(settings: Settings, root_id: str, path: str, limit: int, offset: int, q: str | None) -> ImportRootEntryPage:
    return ImportRootEntryPage.model_validate(entries_page(settings, root_id, path, limit, offset, q))

def select_local_import(settings: Settings, body: LocalSelectionRequest, cancelled: Event) -> LocalSelectionOut:
    try:
        paths = select_local_paths(body.mode, settings.workspace, cancelled)
    except LocalSelectionBusy as exc:
        raise ApiError(409, 'LOCAL_PICKER_BUSY', str(exc), message_key='local_picker_busy', fields=[{'path': 'diagnostic', 'message': str(exc)}]) from exc
    except (OSError, ConfigurationError, subprocess.SubprocessError) as exc:
        raise ApiError(503, 'LOCAL_PICKER_UNAVAILABLE', 'The desktop file picker is unavailable.', message_key='cannot_open_the_local_file_picker_check_the_local_desktop_session') from exc
    if not paths:
        return LocalSelectionOut(cancelled=True, files=[], name=None, folder=body.mode == 'folder')
    entries = [entry for path in paths for entry in enumerate_local(path)]
    return LocalSelectionOut(cancelled=False, files=[{'path': entry['path'], 'name': Path(entry['path']).name, 'size': entry['size']} for entry in entries], name=paths[0].name or '素材集', folder=body.mode == 'folder')
