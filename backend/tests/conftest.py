"""Shared test fixtures.

Seeds an isolated, file-based SQLite database with the deterministic synthetic
dataset, overrides the app's `get_session` dependency to use it, and exposes
both a `TestClient` and a direct `Session` (for server-side / ground-truth
assertions the API deliberately never exposes).
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine

from app.core.db import get_session
from app.core.seed import seed_database
from app.main import app


@pytest.fixture(scope="session")
def engine(tmp_path_factory: pytest.TempPathFactory):
    """A seeded, isolated SQLite engine shared across the test session."""
    db_path = tmp_path_factory.mktemp("db") / "test_prohoripay.db"
    eng = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    seed_database(eng, reset=True)
    return eng


@pytest.fixture()
def db_session(engine) -> Generator[Session, None, None]:
    """A direct session for asserting on stored state, including ground truth."""
    with Session(engine) as session:
        yield session


@pytest.fixture()
def client(engine) -> Generator[TestClient, None, None]:
    """A TestClient whose endpoints read from the seeded test engine."""

    def _get_session_override() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
