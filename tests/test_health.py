#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_health.py — Basic smoke tests for the /api/health endpoint
and DatabasePool.health().

These tests use the TestClient and db_pool fixtures from conftest.py.
"""



# ── /api/health ───────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    """Tests for GET /api/health."""

    def test_health_ok(self, test_client):
        """GET /api/health must return HTTP 200 with {"ok": true}."""
        response = test_client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body.get("ok") is True

    def test_health_content_type(self, test_client):
        """The health endpoint must respond with JSON."""
        response = test_client.get("/api/health")
        assert "application/json" in response.headers.get("content-type", "")


# ── Database health ───────────────────────────────────────────────────────────

class TestDatabaseConnection:
    """Tests for DatabasePool.health() — requires a live PostgreSQL instance."""

    def test_database_connection(self, db_pool):
        """
        db_pool.health() must report status='ok' and type='postgresql'
        when connected to a real PostgreSQL database.
        """
        result = db_pool.health()
        assert result["status"] == "ok", (
            f"Expected db health status 'ok', got: {result}"
        )
        assert result["type"] == "postgresql", (
            f"Expected db type 'postgresql', got: {result}"
        )

    def test_database_execute_select_one(self, db_pool):
        """db_pool.execute() must be able to run a trivial SELECT 1 query."""
        row = db_pool.execute("SELECT 1 AS val", fetch="one")
        assert row is not None
        assert int(row["val"]) == 1

    def test_database_tables_exist(self, db_pool):
        """Core tables created by migrations must be present."""
        expected_tables = [
            "clients",
            "subscriptions",
            "rooms",
            "guests",
            "bookings",
            "invoices",
            "guest_sessions",
            "revoked_sessions",
        ]
        for table in expected_tables:
            row = db_pool.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = %s
                """,
                (table,),
                fetch="one",
            )
            assert row is not None, (
                f"Table '{table}' is missing — migrations may not have run"
            )
