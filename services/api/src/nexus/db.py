"""Database access.

Every unit of work runs inside `tenant(firm_id)`, which opens a transaction
and sets `app.firm_id` for its duration. Row-level security uses that setting,
so code inside the block can only ever see the one firm's rows.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from uuid import UUID

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from nexus.config import settings


@lru_cache
def engine() -> Engine:
    return create_engine(settings().database_url, pool_pre_ping=True, pool_size=10)


@lru_cache
def _sessions() -> sessionmaker[Session]:
    return sessionmaker(engine(), expire_on_commit=False)


@contextmanager
def tenant(firm_id: UUID | str, user_id: UUID | str | None = None) -> Iterator[Session]:
    """A transaction scoped to one firm. Commits on success, rolls back on error."""
    with _sessions()() as session, session.begin():
        session.execute(
            text("SELECT set_config('app.firm_id', :f, true)"), {"f": str(firm_id)}
        )
        if user_id is not None:
            session.execute(
                text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user_id)}
            )
        yield session


def rows(session: Session, sql: str, **params: object) -> list[dict]:
    return [dict(r) for r in session.execute(text(sql), params).mappings()]


def row(session: Session, sql: str, **params: object) -> dict | None:
    found = session.execute(text(sql), params).mappings().first()
    return dict(found) if found else None


def scalar(session: Session, sql: str, **params: object) -> object:
    return session.execute(text(sql), params).scalar()


@contextmanager
def unscoped() -> Iterator[Session]:
    """A transaction with no firm set: tenant tables return nothing.

    Used only for the job queue and the login lookup function.
    """
    with _sessions()() as session, session.begin():
        yield session
