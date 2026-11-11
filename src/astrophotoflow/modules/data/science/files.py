from __future__ import annotations
import os
from errno import ENOSYS, EOPNOTSUPP, EXDEV
from pathlib import Path
import blake3
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.files import find_root, resolve_relative

def hash_file(path: Path) -> tuple[str, int, int]:
    try:
        before = path.stat()
        hasher = blake3.blake3()
        size = 0
        with path.open('rb') as stream:
            while (chunk := stream.read(8 * 1024 * 1024)):
                hasher.update(chunk)
                size += len(chunk)
        after = path.stat()
    except OSError as exc:
        raise ApiError(422, 'SOURCE_UNAVAILABLE', '素材文件当前无法完整读取。', message_key='the_asset_file_cannot_be_read_completely') from exc
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or size != after.st_size:
        raise ApiError(409, 'SOURCE_CHANGED', '素材文件在读取期间发生变化，请重新检查。', message_key='the_asset_file_changed_while_it_was_being_read_check_it_again')
    return (f'blake3:{hasher.hexdigest()}', size, after.st_mtime_ns)

def resolve_storage_path(settings: Settings, storage_mode: str, storage_location: str) -> Path:
    if storage_mode == 'managed':
        try:
            root = settings.data_dir.resolve()
            candidate = (root / storage_location).resolve(strict=True)
            candidate.relative_to(root)
        except OSError as exc:
            raise ApiError(422, 'SOURCE_UNAVAILABLE', '素材文件当前无法读取。', message_key='the_asset_file_cannot_be_read') from exc
        except ValueError as exc:
            raise ApiError(422, 'SOURCE_UNAVAILABLE', '素材存储位置无效。', message_key='invalid_asset_storage_location') from exc
        return candidate
    try:
        _, root_id, relative = storage_location.split('/', 2)
        _, root = find_root(settings, root_id)
        return resolve_relative(root, relative)
    except ApiError as exc:
        raise ApiError(422, 'SOURCE_UNAVAILABLE', '素材来源当前不可访问。', message_key='the_asset_source_is_currently_inaccessible') from exc
    except (ValueError, OSError) as exc:
        raise ApiError(422, 'SOURCE_UNAVAILABLE', '素材来源当前不可访问。', message_key='the_asset_source_is_currently_inaccessible') from exc

def read_hash_and_copy(path: Path, stage_path: Path | None, cancelled, progress=None) -> tuple[str, int]:
    try:
        import blake3
    except ImportError as exc:
        raise ApiError(503, 'SERVICE_NOT_CONFIGURED', '资产服务缺少 BLAKE3 依赖。', message_key='import_blake3_missing') from exc
    hasher = blake3.blake3()
    total = 0
    destination = stage_path.open('xb') if stage_path is not None else None
    try:
        with path.open('rb') as source:
            while (chunk := source.read(8 * 1024 * 1024)):
                if cancelled():
                    raise ApiError(409, 'CANCELLED', '文件处理已取消。', message_key='import_cancelled')
                hasher.update(chunk)
                total += len(chunk)
                if destination is not None:
                    destination.write(chunk)
                if progress is not None:
                    progress(total)
            if destination is not None:
                destination.flush()
                os.fsync(destination.fileno())
    finally:
        if destination is not None:
            destination.close()
    return (f'blake3:{hasher.hexdigest()}', total)

def source_stamp(path: Path) -> dict:
    stat = path.stat()
    return {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}


def try_hardlink(source: Path, destination: Path) -> bool:
    try:
        os.link(source, destination)
        return True
    except OSError as exc:
        if exc.errno in {EXDEV, EOPNOTSUPP, ENOSYS} or getattr(exc, 'winerror', None) in {1, 17, 50}:
            return False
        raise


def materialize_input(source: Path, destination: Path, content_hash: str, byte_size: int, *, prefer_link: bool = False) -> Path:
    """Retain an invocation-owned file entry without changing the registered original."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if hash_file(destination)[:2] != (content_hash, byte_size):
            raise ApiError(409, 'SOURCE_CHANGED', 'A fixed input file already exists with different content.', message_key='a_fixed_input_file_already_exists_with_different_content')
        return destination
    if prefer_link and try_hardlink(source, destination):
        return destination
    part = destination.with_name(destination.name + '.part')
    part.unlink(missing_ok=True)
    try:
        copied_hash, copied_size = read_hash_and_copy(source, part, lambda: False)
        if (copied_hash, copied_size) != (content_hash, byte_size):
            raise ApiError(409, 'SOURCE_CHANGED', 'The asset changed while its input was being fixed.', message_key='the_asset_changed_while_its_input_was_being_fixed')
        os.replace(part, destination)
    finally:
        part.unlink(missing_ok=True)
    return destination
