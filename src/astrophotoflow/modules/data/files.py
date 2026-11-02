import os
from pathlib import Path, PurePosixPath

from astrophotoflow.core.config import ImportRoot, Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import localized_error, workspace_locale

SUPPORTED_EXTENSIONS = {
    ".fits": "fits", ".fit": "fits", ".fts": "fits", ".fits.fz": "fits", ".fit.fz": "fits", '.fts.fz': 'fits',
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".tif": "image", ".tiff": "image", ".bmp": "image", ".webp": "image",
    ".heic": "image", ".heif": "image", ".hif": "image",
    '.pic': 'image', '.ppm': 'image', '.pgm': 'image', '.pnm': 'image', '.jxl': 'image', '.avif': 'image',
    ".cr2": "raw", ".cr3": "raw", ".nef": "raw", ".arw": "raw", ".dng": "raw", ".raf": "raw", ".orf": "raw", ".rw2": "raw", ".pef": "raw", ".srw": "raw",
    '.mos': 'raw', '.crw': 'raw', '.bay': 'raw', '.erf': 'raw', '.3fr': 'raw', '.kdc': 'raw', '.dcr': 'raw',
    '.mef': 'raw', '.mrw': 'raw', '.nrw': 'raw', '.raw': 'raw', '.ptx': 'raw', '.x3f': 'raw',
    ".xisf": "xisf", ".npy": "numpy", ".npz": "numpy",
    ".ser": "video", ".mp4": "video", ".mov": "video", ".avi": "video", ".mkv": "video",
    '.mpg': 'video', '.mpeg': 'video', '.webm': 'video',
    '.lst': 'other', '.csv': 'other', '.icc': 'other', '.icm': 'other', '.py': 'other', '.wcs': 'other',
}

def format_for_path(path: Path) -> str | None:
    name = path.name.lower()
    for extension, kind in SUPPORTED_EXTENSIONS.items():
        if name.endswith(extension):
            return kind
    return None


def enumerate_local(path: Path) -> list[dict]:
    if not path.is_absolute():
        raise ApiError(422, "VALIDATION_ERROR", "请选择本机绝对路径。", message_key='select_an_absolute_local_path')
    try:
        selected = path.resolve(strict=True)
        candidates = sorted(selected.iterdir(), key=lambda child: (child.name.casefold(), child.name)) if selected.is_dir() else [selected]
        entries = []
        for candidate in candidates:
            actual = candidate.resolve(strict=True)
            if not actual.is_file() or format_for_path(actual) is None:
                continue
            stamp = actual.stat()
            entries.append({
                "root_id": "", "path": str(actual), "identity": str(actual), "kind": "file",
                "format": format_for_path(actual), "size": stamp.st_size,
                "source_stamp": {"size": stamp.st_size, "mtime_ns": stamp.st_mtime_ns},
            })
        return entries
    except OSError as exc:
        raise ApiError(404, "SOURCE_UNAVAILABLE", "所选本机路径当前无法读取。", message_key='the_selected_local_path_cannot_be_read') from exc


def find_root(settings: Settings, root_id: str) -> tuple[ImportRoot, Path]:
    root = next((item for item in settings.import_roots if item.id == root_id), None)
    if root is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到配置的素材根目录。", message_key='the_configured_asset_root_was_not_found')
    try:
        resolved = root.path.resolve(strict=True)
    except OSError as exc:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "素材根目录当前不可访问。", message_key='the_asset_root_is_currently_inaccessible') from exc
    if not resolved.is_dir():
        raise ApiError(404, "RESOURCE_NOT_FOUND", "素材根目录当前不可访问。", message_key='the_asset_root_is_currently_inaccessible')
    return root, resolved


def resolve_relative(root: Path, relative_path: str, *, allow_empty: bool = False) -> Path:
    if not isinstance(relative_path, str) or "\\" in relative_path:
        raise ApiError(422, "VALIDATION_ERROR", "来源路径必须是根目录内的相对 POSIX 路径。", message_key='the_source_must_be_a_relative_posix_path_within_the_root_directory')
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or ".." in pure.parts or (not allow_empty and not relative_path):
        raise ApiError(422, "VALIDATION_ERROR", "来源路径必须是根目录内的相对 POSIX 路径。", message_key='the_source_must_be_a_relative_posix_path_within_the_root_directory')
    if relative_path in ("", ".") and allow_empty:
        return root
    candidate = root.joinpath(*pure.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "来源不存在或超出配置的素材根目录。", message_key='the_source_is_missing_or_outside_the_configured_asset_root') from exc
    return resolved


def relative_posix(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def entries_page(settings: Settings, root_id: str, relative_path: str, limit: int, offset: int, q: str | None = None) -> dict:
    _, root = find_root(settings, root_id)
    folder = resolve_relative(root, relative_path, allow_empty=True)
    if not folder.is_dir():
        raise ApiError(422, "VALIDATION_ERROR", "当前来源不是文件夹。", message_key='the_selected_source_is_not_a_folder')
    entries = []
    try:
        with os.scandir(folder) as iterator:
            for entry in iterator:
                candidate = Path(entry.path)
                try:
                    resolved = candidate.resolve(strict=True)
                    resolved.relative_to(root)
                    is_directory = resolved.is_dir()
                    is_file = resolved.is_file()
                except (OSError, ValueError):
                    continue
                if not is_directory and not is_file:
                    continue
                kind = None if is_directory else format_for_path(candidate)
                entries.append({
                    "name": entry.name,
                    "path": relative_posix(root, candidate),
                    "kind": "directory" if is_directory else "file",
                    "format": kind,
                    "supported": is_directory or kind is not None,
                    "size": None if is_directory else resolved.stat().st_size,
                })
    except OSError as exc:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "当前文件夹无法读取。", message_key='this_folder_cannot_be_read') from exc
    entries.sort(key=lambda item: (item["kind"] != "directory", item["name"].casefold(), item["name"]))
    if q:
        entries = [item for item in entries if q.casefold() in item["name"].casefold()]
    return {"items": entries[offset:offset + limit], "total": len(entries), "limit": limit, "offset": offset}


def enumerate_source(settings: Settings, root_id: str, relative_path: str, stopped, mark_stopped):
    _, root = find_root(settings, root_id)
    start = resolve_relative(root, relative_path, allow_empty=True)
    seen_directories = set()

    def visit(path: Path):
        if stopped():
            mark_stopped()
            return
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError):
            yield {
                "root_id": root_id, "path": relative_posix(root, path),
                "identity": f"{root_id}:{relative_posix(root, path)}",
                "kind": "file", "format": format_for_path(path),
                "error": localized_error(workspace_locale(settings.workspace), 'SOURCE_UNAVAILABLE', 'source_outside_root').model_dump(),
            }
            return
        if resolved.is_file():
            stamp = resolved.stat()
            yield {
                "root_id": root_id, "path": relative_posix(root, path),
                "identity": str(resolved), "kind": "file",
                "format": format_for_path(path), "size": stamp.st_size,
                "source_stamp": {"size": stamp.st_size, "mtime_ns": stamp.st_mtime_ns},
            }
            return
        if not resolved.is_dir():
            return
        identity = str(resolved)
        if identity in seen_directories:
            return
        seen_directories.add(identity)
        try:
            with os.scandir(resolved) as iterator:
                children = sorted((Path(entry.path) for entry in iterator), key=lambda item: (item.name.casefold(), item.name))
        except OSError:
            relative = relative_posix(root, path)
            yield {
                "root_id": root_id, "path": relative, "identity": f"{root_id}:{relative}",
                "kind": "file", "format": None,
                "error": localized_error(workspace_locale(settings.workspace), 'SOURCE_UNAVAILABLE', 'source_folder_unreadable').model_dump(),
            }
            return
        for child in children:
            if stopped():
                mark_stopped()
                return
            try:
                actual = child.resolve(strict=True)
                actual.relative_to(root)
            except (OSError, ValueError):
                child_relative = relative_posix(root, child)
                yield {
                    "root_id": root_id, "path": child_relative, "identity": f"{root_id}:{child_relative}",
                    "kind": "file", "format": format_for_path(child),
                    "error": localized_error(workspace_locale(settings.workspace), 'SOURCE_UNAVAILABLE', 'source_outside_root').model_dump(),
                }
                continue
            if actual.is_dir():
                yield from visit(child)
            elif actual.is_file():
                stamp = actual.stat()
                yield {
                    "root_id": root_id, "path": relative_posix(root, child),
                    "identity": str(actual), "kind": "file",
                    "format": format_for_path(child), "size": stamp.st_size,
                    "source_stamp": {"size": stamp.st_size, "mtime_ns": stamp.st_mtime_ns},
                }

    yield from visit(start)
