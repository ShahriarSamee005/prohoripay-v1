"""Database engine and session management.

Exposes a SQLModel engine, an `init_db()` bootstrap, and a `get_session`
FastAPI dependency. Models are registered by later-phase modules; Phase 0 has
none, so `init_db()` simply creates the (currently empty) schema.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

# `check_same_thread` is required for SQLite when used across FastAPI's threads.
_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(settings.database_url, echo=False, connect_args=_connect_args)


def init_db() -> None:
    """Create tables for all imported SQLModel metadata.

    Later phases import their models before this runs so their tables register.
    """
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a scoped database session."""
    with Session(engine) as session:
        yield session
