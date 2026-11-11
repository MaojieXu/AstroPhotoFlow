from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def _compare_casefold(left: str, right: str) -> int:
    first, second = left.casefold(), right.casefold()
    return (first > second) - (first < second)


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
        event.listen(self.engine, "connect", self._configure_sqlite)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    @staticmethod
    def _configure_sqlite(dbapi_connection, _connection_record) -> None:
        dbapi_connection.create_collation("apf_casefold", _compare_casefold)
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    @contextmanager
    def read_session(self) -> Iterator[Session]:
        with self.engine.connect() as connection:
            # sqlite3's legacy transaction mode does not BEGIN for SELECT.
            # Explicitly fix one snapshot for members, metadata and calibration.
            connection.exec_driver_sql('BEGIN')
            with self.sessions(bind=connection) as session:
                yield session

    @contextmanager
    def write_session(self) -> Iterator[Session]:
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                with self.sessions(bind=connection) as session:
                    yield session
                    session.flush()
                    callbacks = list(session.info.get('after_commit_callbacks', ()))
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        for callback in callbacks:
            callback()

    def close(self) -> None:
        self.engine.dispose()
