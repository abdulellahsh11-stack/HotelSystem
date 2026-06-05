#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_integration_postgres.py — Real PostgreSQL integration tests.

All tests are marked @pytest.mark.integration and require a live
PostgreSQL instance reachable via the DATABASE_URL environment variable.
They are automatically skipped when DATABASE_URL is absent.
"""

import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _unique_client_id() -> str:
    """Generate a unique client ID so tests don't collide with each other."""
    return f"test-{uuid.uuid4().hex[:12]}"


def _insert_test_client(db, client_id: str) -> dict:
    """Insert a minimal client row and return the stored record."""
    db.execute(
        """
        INSERT INTO clients (id, name, type, city)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (client_id, f"Test Hotel {client_id}", "hotel", "Riyadh"),
    )
    return db.execute(
        "SELECT * FROM clients WHERE id = %s",
        (client_id,),
        fetch="one",
    )


def _delete_test_client(db, client_id: str) -> None:
    """Remove test data — CASCADE handles child rows."""
    db.execute("DELETE FROM clients WHERE id = %s", (client_id,))


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestMigrationsIdempotent:
    """Migrations must be safe to run multiple times without error."""

    def test_run_migrations_idempotent(self, db_pool):
        """
        Calling run_all_migrations() twice must not raise any exception.
        All CREATE TABLE / CREATE INDEX statements use IF NOT EXISTS, and
        trigger creation is guarded by an existence check, so the second run
        should be a no-op.
        """
        from db.migrations import run_all_migrations

        # First run already executed by the db_pool fixture.
        # Run again — must not raise.
        run_all_migrations(db_pool)

        # Verify the schema is still intact after the second run.
        row = db_pool.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN (
                'clients', 'bookings', 'guests', 'rooms',
                'invoices', 'guest_sessions', 'revoked_sessions'
              )
            """,
            fetch="one",
        )
        assert int(row["cnt"]) == 7, (
            f"Expected 7 core tables, found {row['cnt']}"
        )


@pytest.mark.integration
class TestClientCRUD:
    """Insert a client, read it back, verify row-level isolation."""

    def test_client_crud(self, db_pool):
        """
        Insert a client row, fetch it back by primary key, confirm all
        inserted fields are preserved, then clean up.
        """
        client_id = _unique_client_id()
        try:
            # INSERT
            db_pool.execute(
                """
                INSERT INTO clients (id, name, type, city, region, email)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    client_id,
                    "فندق الاختبار",
                    "hotel",
                    "Riyadh",
                    "Riyadh Region",
                    f"{client_id}@test.invalid",
                ),
            )

            # READ BACK
            row = db_pool.execute(
                "SELECT * FROM clients WHERE id = %s",
                (client_id,),
                fetch="one",
            )
            assert row is not None, "Inserted client row not found"
            assert row["id"] == client_id
            assert row["name"] == "فندق الاختبار"
            assert row["type"] == "hotel"
            assert row["city"] == "Riyadh"
            assert row["email"] == f"{client_id}@test.invalid"
            assert row["settings_locked"] is False  # default

        finally:
            _delete_test_client(db_pool, client_id)

    def test_client_isolation_between_tests(self, db_pool):
        """
        Two clients inserted with distinct IDs must not share data.
        Deleting one must not affect the other.
        """
        id_a = _unique_client_id()
        id_b = _unique_client_id()

        try:
            _insert_test_client(db_pool, id_a)
            _insert_test_client(db_pool, id_b)

            # Both must exist.
            row_a = db_pool.execute(
                "SELECT id FROM clients WHERE id = %s", (id_a,), fetch="one"
            )
            row_b = db_pool.execute(
                "SELECT id FROM clients WHERE id = %s", (id_b,), fetch="one"
            )
            assert row_a is not None and row_a["id"] == id_a
            assert row_b is not None and row_b["id"] == id_b

            # Delete A — B must still exist.
            _delete_test_client(db_pool, id_a)
            row_a_after = db_pool.execute(
                "SELECT id FROM clients WHERE id = %s", (id_a,), fetch="one"
            )
            row_b_after = db_pool.execute(
                "SELECT id FROM clients WHERE id = %s", (id_b,), fetch="one"
            )
            assert row_a_after is None, "Client A should have been deleted"
            assert row_b_after is not None, "Client B should still exist"

        finally:
            # Best-effort cleanup; A may already be gone.
            try:
                _delete_test_client(db_pool, id_a)
            except Exception:
                pass
            _delete_test_client(db_pool, id_b)

    def test_unique_constraint_on_client_id(self, db_pool):
        """INSERT of a duplicate client_id must raise an IntegrityError."""
        import psycopg2

        client_id = _unique_client_id()
        try:
            _insert_test_client(db_pool, client_id)

            with pytest.raises(psycopg2.errors.UniqueViolation):
                db_pool.execute(
                    "INSERT INTO clients (id, name) VALUES (%s, %s)",
                    (client_id, "Duplicate"),
                )
        finally:
            _delete_test_client(db_pool, client_id)


@pytest.mark.integration
class TestSessionExpiry:
    """Verify the guest_sessions expiry logic at the database level."""

    def test_session_expiry(self, db_pool):
        """
        A guest_session row created with an expires_at in the past must be
        identifiable as expired via a simple SQL WHERE clause.
        An active session (expires_at in the future) must NOT appear expired.
        """
        client_id = _unique_client_id()
        token_expired = f"expired_{uuid.uuid4().hex}"
        token_active = f"active_{uuid.uuid4().hex}"

        import hashlib
        hash_expired = hashlib.sha256(token_expired.encode()).hexdigest()
        hash_active = hashlib.sha256(token_active.encode()).hexdigest()

        try:
            # Set up: client row required for FK
            _insert_test_client(db_pool, client_id)

            now_utc = datetime.now(timezone.utc)
            past = now_utc - timedelta(hours=1)
            future = now_utc + timedelta(hours=48)

            # Insert an already-expired session.
            db_pool.execute(
                """
                INSERT INTO guest_sessions
                    (token_hash, client_id, actor_type, created_at, expires_at)
                VALUES (%s, %s, 'guest', %s, %s)
                """,
                (hash_expired, client_id, now_utc - timedelta(hours=2), past),
            )

            # Insert an active session.
            db_pool.execute(
                """
                INSERT INTO guest_sessions
                    (token_hash, client_id, actor_type, created_at, expires_at)
                VALUES (%s, %s, 'guest', %s, %s)
                """,
                (hash_active, client_id, now_utc, future),
            )

            # Query for expired sessions.
            expired_row = db_pool.execute(
                """
                SELECT token_hash FROM guest_sessions
                WHERE token_hash = %s
                  AND expires_at < NOW()
                """,
                (hash_expired,),
                fetch="one",
            )
            assert expired_row is not None, (
                "Expired session should appear in expiry query"
            )

            # Active session must not appear in the expiry query.
            active_expired_row = db_pool.execute(
                """
                SELECT token_hash FROM guest_sessions
                WHERE token_hash = %s
                  AND expires_at < NOW()
                """,
                (hash_active,),
                fetch="one",
            )
            assert active_expired_row is None, (
                "Active session must not appear in expiry query"
            )

            # The active session must appear in a valid-sessions query.
            active_valid_row = db_pool.execute(
                """
                SELECT token_hash FROM guest_sessions
                WHERE token_hash = %s
                  AND expires_at > NOW()
                """,
                (hash_active,),
                fetch="one",
            )
            assert active_valid_row is not None, (
                "Active session should appear in valid-session query"
            )

        finally:
            # Clean up sessions first (FK), then the client.
            db_pool.execute(
                "DELETE FROM guest_sessions WHERE client_id = %s",
                (client_id,),
            )
            _delete_test_client(db_pool, client_id)


@pytest.mark.integration
class TestConcurrentConnections:
    """Exercise the connection pool under concurrent load."""

    def test_concurrent_connections(self, db_pool):
        """
        Fire 10 concurrent db.execute() calls from separate threads.
        All must succeed without pool exhaustion, deadlock, or data race.
        """
        num_threads = 10
        results = []
        errors = []
        barrier = threading.Barrier(num_threads)

        def worker(thread_id: int):
            try:
                # Synchronise all threads to start simultaneously.
                barrier.wait(timeout=10)
                row = db_pool.execute(
                    "SELECT %s::int AS thread_id, pg_backend_pid() AS pid",
                    (thread_id,),
                    fetch="one",
                )
                results.append(row)
            except Exception as exc:
                errors.append((thread_id, exc))

        threads = [
            threading.Thread(target=worker, args=(i,), daemon=True)
            for i in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, (
            f"Concurrent db.execute() calls raised errors: {errors}"
        )
        assert len(results) == num_threads, (
            f"Expected {num_threads} results, got {len(results)}"
        )

        # Each thread must have received its own thread_id back.
        returned_ids = {int(r["thread_id"]) for r in results}
        assert returned_ids == set(range(num_threads)), (
            f"Thread IDs mismatch: expected 0-{num_threads - 1}, got {returned_ids}"
        )

    def test_concurrent_inserts_and_reads(self, db_pool):
        """
        Insert rows from multiple threads and verify count afterwards.
        Tests that the pool handles interleaved commits correctly.
        """
        client_id = _unique_client_id()
        num_threads = 5
        errors = []

        try:
            _insert_test_client(db_pool, client_id)

            # Insert rooms from multiple threads simultaneously.
            def insert_room(thread_id: int):
                try:
                    db_pool.execute(
                        """
                        INSERT INTO rooms (client_id, room_number, room_type, base_price)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            client_id,
                            f"T{thread_id:03d}",
                            "standard",
                            100.0 + thread_id,
                        ),
                    )
                except Exception as exc:
                    errors.append((thread_id, exc))

            threads = [
                threading.Thread(target=insert_room, args=(i,), daemon=True)
                for i in range(num_threads)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)

            assert not errors, f"Concurrent inserts failed: {errors}"

            # All rows must be visible after threads complete.
            count_row = db_pool.execute(
                "SELECT COUNT(*) AS cnt FROM rooms WHERE client_id = %s",
                (client_id,),
                fetch="one",
            )
            assert int(count_row["cnt"]) == num_threads, (
                f"Expected {num_threads} rooms, found {count_row['cnt']}"
            )

        finally:
            # Cascade delete handles rooms.
            _delete_test_client(db_pool, client_id)
