import os
from pathlib import Path, PurePosixPath

from .errors import ApiError
from .settings import ImportRoot, Settings


SUPPORTED_EXTENSIONS = {
    ".fits": "fits", ".fit": "fits", ".fts": "fits", ".fits.fz": "fits", ".fit.fz": "fits",
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".tif": "image", ".tiff": "image", ".bmp": "image", ".webp": "image",
    ".heic": "image", ".heif": "image", ".hif": "image",
    ".cr2": "raw", ".cr3": "raw", ".nef": "raw", ".arw": "raw", ".dng": "raw", ".raf": "raw", ".orf": "raw", ".rw2": "raw", ".pef": "raw", ".srw": "raw",
    ".xisf": "xisf", ".npy": "numpy", ".npz": "numpy",
    ".ser": "video", ".mp4": "video", ".mov": "video", ".avi": "video", ".mkv": "video",
}

def format_for_path(path: Path) -> str | None:
    name = path.name.lower()
    for extension, kind in SUPPORTED_EXTENSIONS.items():
        if name.endswith(extension):
            return kind
    return None


def find_root(settings: Settings, root_id: str) -> tuple[ImportRoot, Path]:
    root = next((item for item in settings.import_roots if item.id == root_id), None)
    if root is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到配置的素材根目录。")
    try:
        resolved = root.path.resolve(strict=True)
    except OSError as exc:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "素材根目录当前不可访问。") from exc
    if not resolved.is_dir():
        raise ApiError(404, "RESOURCE_NOT_FOUND", "素材根目录当前不可访问。")
    return root, resolved


def resolve_relative(root: Path, relative_path: str, *, allow_empty: bool = False) -> Path:
    if not isinstance(relative_path, str) or "\\" in relative_path:
        raise ApiError(422, "VALIDATION_ERROR", "来源路径必须是根目录内的相对 POSIX 路径。")
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or ".." in pure.parts or (not allow_empty and not relative_path):
        raise ApiError(422, "VALIDATION_ERROR", "来源路径必须是根目录内的相对 POSIX 路径。")
    if relative_path in ("", ".") and allow_empty:
        return root
    candidate = root.joinpath(*pure.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "来源不存在或超出配置的素材根目录。") from exc
    return resolved


def relative_posix(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def entries_page(settings: Settings, root_id: str, relative_path: str, limit: int, offset: int, q: str | None = None) -> dict:
    _, root = find_root(settings, root_id)
    folder = resolve_relative(root, relative_path, allow_empty=True)
    if not folder.is_dir():
        raise ApiError(422, "VALIDATION_ERROR", "当前来源不是文件夹。")
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
        raise ApiError(404, "RESOURCE_NOT_FOUND", "当前文件夹无法读取。") from exc
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
                "error": {"code": "SOURCE_UNAVAILABLE", "message": "来源无法读取或超出素材根目录。"},
            }
            return
        if resolved.is_file():
            yield {
                "root_id": root_id, "path": relative_posix(root, path),
                "identity": str(resolved), "kind": "file",
                "format": format_for_path(path), "size": resolved.stat().st_size,
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
                "error": {"code": "SOURCE_UNAVAILABLE", "message": "文件夹无法读取。"},
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
                    "error": {"code": "SOURCE_UNAVAILABLE", "message": "来源无法读取或超出素材根目录。"},
                }
                continue
            if actual.is_dir():
                yield from visit(child)
            elif actual.is_file():
                yield {
                    "root_id": root_id, "path": relative_posix(root, child),
                    "identity": str(actual), "kind": "file",
                    "format": format_for_path(child), "size": actual.stat().st_size,
                }

    yield from visit(start)
