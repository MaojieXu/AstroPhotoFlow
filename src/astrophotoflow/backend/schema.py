from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from alembic import command
from alembic.config import Config
from filelock import FileLock, Timeout
from sqlalchemy.engine import URL

from .settings import Settings, ensure_data_dir


SCHEMA_REVISION = "0006_library_trash_cleanup_state"
_PACKAGE_ALEMBIC_INI = Path(__file__).resolve().parent / "alembic.ini"
ALEMBIC_INI = _PACKAGE_ALEMBIC_INI


class SchemaError(RuntimeError):
    pass


def database_lock(settings: Settings) -> FileLock:
    ensure_data_dir(settings)
    lock = FileLock(str(settings.lock_path), timeout=0)
    try:
        lock.acquire()
    except Timeout as exc:
        raise SchemaError("该数据目录已被其他服务或迁移进程使用。") from exc
    return lock


def _alembic_config(settings: Settings) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.attributes["database_url"] = URL.create("sqlite", database=str(settings.database_path)).render_as_string(hide_password=False)
    return config


def current_revision(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            found = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'").fetchone()
            if not found:
                return None
            row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
            return row[0] if row else None
    except sqlite3.Error as exc:
        raise SchemaError(f"无法读取数据库迁移版本：{exc}") from exc


def database_status(settings: Settings) -> dict[str, str | bool | None]:
    exists = settings.database_path.is_file()
    revision = current_revision(settings.database_path) if exists else None
    return {"database_path": str(settings.database_path), "exists": exists, "current_revision": revision, "expected_revision": SCHEMA_REVISION}


def _backup_before_upgrade(settings: Settings) -> Path:
    settings.data_dir.joinpath("backups").mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = settings.data_dir / "backups" / f"astrophotoflow-{stamp}-to-{SCHEMA_REVISION}.sqlite3"
    with sqlite3.connect(f"file:{settings.database_path}?mode=ro", uri=True) as source, sqlite3.connect(destination) as target:
        source.backup(target)
    return destination


def upgrade_database(settings: Settings) -> Path | None:
    ensure_data_dir(settings)
    exists = settings.database_path.exists()
    if exists:
        revision = current_revision(settings.database_path)
        if revision == SCHEMA_REVISION:
            return None
        if revision is None:
            raise SchemaError("数据库没有可识别的 Alembic revision；不会对未知数据库执行迁移。")
    backup = _backup_before_upgrade(settings) if exists else None
    try:
        command.upgrade(_alembic_config(settings), "head")
    except Exception as exc:
        raise SchemaError(f"数据库迁移失败；数据库及备份均已保留。诊断：{exc}") from exc
    if current_revision(settings.database_path) != SCHEMA_REVISION:
        raise SchemaError("迁移命令结束，但数据库 revision 与预期不符。")
    return backup


def ensure_schema_for_serve(settings: Settings) -> None:
    if not settings.database_path.exists():
        upgrade_database(settings)
        return
    revision = current_revision(settings.database_path)
    if revision != SCHEMA_REVISION:
        raise SchemaError(
            f"数据库 revision 为 {revision!r}，服务要求 {SCHEMA_REVISION!r}。请检查后显式运行："
            "uv run --project . apf-service db upgrade"
        )
