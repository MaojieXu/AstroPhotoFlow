from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from astrophotoflow.modules.data.persistence import schema_metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = schema_metadata()


def run_migrations_offline() -> None:
    context.configure(url=config.attributes["database_url"], target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is None:
        connectable = engine_from_config(
            {"sqlalchemy.url": config.attributes["database_url"]},
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
        with connectable.connect() as conn:
            context.configure(connection=conn, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
        connectable.dispose()
    else:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
