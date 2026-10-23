import argparse
from contextlib import contextmanager
import sys

import uvicorn

from .api import create_app
from .schema import SchemaError, database_status, database_lock, ensure_schema_for_serve, upgrade_database
from .settings import ConfigurationError, ensure_service_token, load_settings


@contextmanager
def hold_database_lock(settings):
    lock = database_lock(settings)
    try:
        yield
    finally:
        lock.release()


def main() -> None:
    parser = argparse.ArgumentParser(prog="apf-service")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve")
    db = commands.add_parser("db")
    db_commands = db.add_subparsers(dest="db_command", required=True)
    db_commands.add_parser("status")
    db_commands.add_parser("upgrade")
    args = parser.parse_args()
    try:
        settings = load_settings()
        if args.command == "db" and args.db_command == "status":
            result = database_status(settings)
            for key, value in result.items():
                print(f"{key}: {value}")
            return
        if args.command == "db" and args.db_command == "upgrade":
            with hold_database_lock(settings):
                backup = upgrade_database(settings)
            print("schema_revision: 0001_foundation")
            if backup:
                print(f"backup: {backup}")
            else:
                print("backup: not needed (new database or already current)")
            return
        token = ensure_service_token(settings)
        with hold_database_lock(settings):
            ensure_schema_for_serve(settings)
            app = create_app(settings, token)
            uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
    except (ConfigurationError, SchemaError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
