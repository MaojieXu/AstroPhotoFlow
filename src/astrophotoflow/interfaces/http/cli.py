from astrophotoflow.core.localization import workspace_locale
import argparse
from contextlib import contextmanager
import sys

import uvicorn

from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.core.database.schema import SCHEMA_REVISION, SchemaError, database_status, database_lock, ensure_schema_for_serve, upgrade_database
from astrophotoflow.core.database.db import Database
from astrophotoflow.modules.data.public import backfill_missing_previews, mark_interrupted_tasks
from astrophotoflow.core.config import ConfigurationError, ensure_service_token, load_settings, load_running_settings
import os
from pathlib import Path


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
    previews = commands.add_parser("previews")
    previews.add_subparsers(dest="preview_command", required=True).add_parser("backfill")
    args = parser.parse_args()
    try:
        settings = load_running_settings(Path(os.environ["APF_WORKSPACE"])) if "APF_WORKSPACE" in os.environ else load_settings()
        if args.command == "db" and args.db_command == "status":
            result = database_status(settings)
            for key, value in result.items():
                print(f"{key}: {value}")
            return
        if args.command == "db" and args.db_command == "upgrade":
            with hold_database_lock(settings):
                backup = upgrade_database(settings)
            print(f"schema_revision: {SCHEMA_REVISION}")
            if backup:
                print(f"backup: {backup}")
            else:
                print("backup: not needed (new database or already current)")
            return
        if args.command == "previews" and args.preview_command == "backfill":
            with hold_database_lock(settings):
                ensure_schema_for_serve(settings)
                database = Database(settings.database_path)
                try:
                    result = backfill_missing_previews(database, settings)
                finally:
                    database.close()
            print(f"generated: {result['generated']}")
            print(f"failed: {result['failed']}")
            return
        token = ensure_service_token(settings)
        with hold_database_lock(settings):
            ensure_schema_for_serve(settings)
            app = create_app(settings, token)
            interrupted = mark_interrupted_tasks(app.state.database, locale=workspace_locale(settings.workspace))
            if interrupted:
                print(f"interrupted_tasks: {interrupted}")
            server = uvicorn.Server(uvicorn.Config(app, host=settings.host, port=settings.port, log_level="info"))
            app.state.shutdown = lambda: setattr(server, "should_exit", True)
            server.run()
    except (ConfigurationError, SchemaError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
