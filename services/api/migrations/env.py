"""Alembic environment. Migrations run as the schema owner, never as the app role."""

from alembic import context
from sqlalchemy import create_engine, pool

from nexus.config import settings

config = context.config


def run_migrations_offline() -> None:
    context.configure(url=settings().database_owner_url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(settings().database_owner_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
