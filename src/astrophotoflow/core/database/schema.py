import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from filelock import FileLock, Timeout
from sqlalchemy.engine import URL

from astrophotoflow.core.config import Settings, ensure_data_dir

SCHEMA_REVISION = "0001_baseline"
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


def upgrade_database(settings: Settings) -> None:
    ensure_data_dir(settings)
    if settings.database_path.exists():
        revision = current_revision(settings.database_path)
        if revision == SCHEMA_REVISION:
            return
        raise SchemaError(f"Database revision {revision!r} does not match {SCHEMA_REVISION!r}; create a new workspace or rebuild this database. Historical upgrades are unsupported.")
    try:
        command.upgrade(_alembic_config(settings), "head")
    except Exception as exc:
        raise SchemaError(f"New database initialization failed: {exc}") from exc
    if current_revision(settings.database_path) != SCHEMA_REVISION:
        raise SchemaError("Database initialization ended with an unexpected revision.")


def ensure_schema_for_serve(settings: Settings) -> None:
    if not settings.database_path.exists():
        upgrade_database(settings)
        return
    revision = current_revision(settings.database_path)
    if revision != SCHEMA_REVISION:
        raise SchemaError(
            f"Database revision {revision!r} does not match {SCHEMA_REVISION!r}; create a new workspace or rebuild this database. Historical upgrades are unsupported."
        )
