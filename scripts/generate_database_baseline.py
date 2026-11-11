"""Generate the sole pre-release baseline from an empty in-memory database.

This development command never opens a workspace database. Review the generated
constraints and validate against ORM metadata before accepting a schema change.
"""

from pathlib import Path

from alembic.autogenerate import produce_migrations, render_python_code
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from astrophotoflow.core.database.schema import SCHEMA_REVISION
from astrophotoflow.modules.data.persistence import schema_metadata


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    destination = root / "src/astrophotoflow/core/database/alembic/versions" / f"{SCHEMA_REVISION}.py"
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as connection:
            migration = produce_migrations(MigrationContext.configure(connection), schema_metadata())
            upgrade = render_python_code(migration.upgrade_ops)
            downgrade = render_python_code(migration.downgrade_ops)
    finally:
        engine.dispose()
    destination.write_text(
        '"""Fresh workspace baseline; historical database upgrades are unsupported."""\n\n'
        'from alembic import op\nimport sqlalchemy as sa\n\n'
        f'revision = "{SCHEMA_REVISION}"\ndown_revision = None\nbranch_labels = None\ndepends_on = None\n\n\n'
        f'def upgrade() -> None:\n{upgrade}\n\n\ndef downgrade() -> None:\n{downgrade}\n',
        encoding="utf-8",
    )
    print(f"Generated {destination.relative_to(root)} ({len(schema_metadata().tables)} tables)")


if __name__ == "__main__":
    main()
