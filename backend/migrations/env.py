import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure workspace root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.core.config import settings
from backend.models import Base

config = getattr(context, "config", None)

if config is not None and getattr(config, "config_file_name", None) is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_url():
    alembic_cfg_url = config.get_main_option("sqlalchemy.url") if config is not None else None
    url = (
        os.getenv("MIGRATION_DATABASE_URL")
        or settings.MIGRATION_DATABASE_URL
        or alembic_cfg_url
        or settings.DATABASE_URL
    )
    if not url:
        return "sqlite:///:memory:"
    return url

def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()

if config is not None:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
