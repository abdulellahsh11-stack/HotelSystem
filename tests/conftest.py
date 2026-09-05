#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/conftest.py — Shared pytest fixtures for ضيوف test suite.

Requires a live PostgreSQL instance reachable via DATABASE_URL.
Tests that need the database are automatically skipped when DATABASE_URL
is absent so the suite stays green in environments without Postgres.
"""

import os
import pytest

from fastapi.testclient import TestClient

# ── Environment ───────────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Ensure mandatory env vars have at least stub values so Config.from_env()
# doesn't raise during import.  Real secrets are injected by CI.
os.environ.setdefault("ADMIN_PASS_HASH", "test_hash_for_ci")
os.environ.setdefault("SECRET_KEY", "ci_test_secret_key_32chars_minimum")

# ── Markers ───────────────────────────────────────────────────────────────────

def pytest_configure(config):
    """Register custom markers to avoid PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as requiring a live PostgreSQL database",
    )


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """Clear the in-process API rate-limit buckets before each test.

    The general limiter counts writes across the whole process; without a
    reset a test that issues many writes could exhaust the window and make an
    unrelated later test see a spurious 429. Reset keeps tests independent.
    """
    from services import rate_limit

    rate_limit.reset()
    yield
    rate_limit.reset()


# ── Helpers ───────────────────────────────────────────────────────────────────

_db_available = bool(DATABASE_URL)
skip_no_db = pytest.mark.skipif(
    not _db_available,
    reason="DATABASE_URL not set — skipping database tests",
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def db_pool():
    """
    Session-scoped DatabasePool connected to the test PostgreSQL instance.

    Runs all migrations once for the entire test session, then yields the
    pool.  The pool is closed after the last test in the session.

    Tests that use this fixture are automatically skipped when DATABASE_URL
    is not set.
    """
    if not _db_available:
        pytest.skip("DATABASE_URL not set — skipping database tests")

    # Break the singleton so each test-session gets a fresh pool.
    from db import connection as _conn_mod
    _conn_mod._db = None
    _conn_mod.DatabasePool._instance = None

    from db.connection import init_db
    from db.migrations import run_all_migrations

    db = init_db(DATABASE_URL)

    # Verify the pool is actually connected to PostgreSQL.
    assert db.use_postgres, (
        "DatabasePool did not connect to PostgreSQL — check DATABASE_URL"
    )

    run_all_migrations(db)

    yield db

    db.close()


@pytest.fixture(scope="session")
def test_client(db_pool):
    """
    Session-scoped FastAPI TestClient.

    Injects the already-initialised db_pool into app.state so the app
    doesn't attempt to re-connect or re-run migrations.
    """
    # Prevent the lifespan handler from reinitialising the pool.
    os.environ["DATABASE_URL"] = DATABASE_URL

    from main import app

    # Manually pre-populate app.state to bypass the lifespan startup.
    # TestClient runs the full lifespan by default; we override state after.
    with TestClient(app, raise_server_exceptions=True) as client:
        # Overwrite the pool reference so tests use the fixture-managed pool.
        client.app.state.db = db_pool
        yield client


@pytest.fixture()
def db(db_pool):
    """
    Function-scoped alias for db_pool — convenient for tests that only
    need a single execute() call without caring about the full pool object.
    """
    return db_pool
