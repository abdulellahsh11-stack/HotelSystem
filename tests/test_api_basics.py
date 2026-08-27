#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Basic API smoke tests for the Dheuof Hotel SaaS platform.

These tests do not require a real database — db.execute() calls are mocked
wherever the route under test would touch the DB.

Run:
    cd /home/user/HotelSystem
    pytest tests/test_api_basics.py -v
"""

import sys
import os

import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Import the FastAPI app — skip every test gracefully if the import fails
# (e.g. missing optional dependencies in a CI environment)
# ---------------------------------------------------------------------------
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from main import app, _client_sessions
    from fastapi.testclient import TestClient
    HAS_APP = True
except Exception as _import_err:
    HAS_APP = False
    _import_err_msg = str(_import_err)

pytestmark = pytest.mark.skipif(not HAS_APP, reason="App not importable in test environment")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(*, session_token: str | None = None, session_data: dict | None = None):
    """
    Return a TestClient whose requests carry *session_token* as the
    ``client_token`` cookie.  If *session_data* is provided the token is
    pre-loaded into the in-memory session store so ``require_client`` will
    accept it.
    """
    client = TestClient(app, raise_server_exceptions=False)
    if session_token and session_data:
        _client_sessions[session_token] = session_data
    if session_token:
        client.cookies.set("client_token", session_token)
    return client


def _mock_db(*, use_postgres: bool = False):
    """Return a lightweight mock database object."""
    db = MagicMock()
    db.use_postgres = use_postgres
    db.health.return_value = {"ok": True}
    return db


# ---------------------------------------------------------------------------
# Test 1 — Auth is required: unauthenticated GET /api/m06/employees → 401
# ---------------------------------------------------------------------------

class TestAuthRequired:
    def test_employees_unauthenticated_returns_401(self):
        """Requests without a valid session cookie must be rejected with 401."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/m06/employees")
        assert response.status_code == 401, (
            f"Expected 401 for unauthenticated request, got {response.status_code}"
        )

    def test_employees_invalid_token_returns_401(self):
        """A made-up token that is not in the session store must be rejected."""
        client = TestClient(app, raise_server_exceptions=False)
        client.cookies.set("client_token", "totally-invalid-token-xyz")
        response = client.get("/api/m06/employees")
        assert response.status_code == 401, (
            f"Expected 401 for invalid token, got {response.status_code}"
        )


# ---------------------------------------------------------------------------
# Test 2 — Health endpoint: GET /api/health → 200 with {"ok": true}
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_returns_200(self):
        """/api/health must be publicly accessible and return HTTP 200."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/health")
        assert response.status_code == 200, (
            f"/api/health returned {response.status_code}"
        )

    def test_health_body_contains_ok(self):
        """/api/health body must contain {\"ok\": true}."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/health")
        body = response.json()
        assert body.get("ok") is True, (
            f"/api/health body missing 'ok: true', got: {body}"
        )


# ---------------------------------------------------------------------------
# Test 3 — Login / index page loads: GET / → 200 or redirect (3xx)
# ---------------------------------------------------------------------------

class TestIndexPage:
    def test_root_returns_200_or_redirect(self):
        """GET / must respond with 200 (HTML) or a redirect (3xx) — never 4xx/5xx."""
        # follow_redirects=False so we can also accept a 3xx directly
        client = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
        response = client.get("/")
        assert response.status_code in range(200, 400), (
            f"GET / returned unexpected status {response.status_code}"
        )


# ---------------------------------------------------------------------------
# Test 3b — Server-side auth gate: program pages are locked until login
# ---------------------------------------------------------------------------

class TestServerSideAuthGate:
    def test_module_page_unauthenticated_goes_to_the_home_page(self):
        """Direct navigation to a module page without a session → 302 /login."""
        client = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
        resp = client.get(
            "/static/dheuof/modules/07-pos/index.html",
            headers={"accept": "text/html"},
        )
        assert resp.status_code == 302, f"Expected 302 redirect, got {resp.status_code}"
        # إلى الصفحة الرئيسية لا صفحة الدخول: الزائر بلا جلسة قد يكون
        # عميلاً محتملاً، والرئيسية تُعرّفه بالمنصة وتحمل الدخول والتسجيل.
        assert resp.headers.get("location") == "/"

    def test_shortcut_route_unauthenticated_goes_to_the_home_page(self):
        """Pretty shortcut (/hr) without a session → 302 /login."""
        client = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
        resp = client.get("/hr", headers={"accept": "text/html"})
        assert resp.status_code == 302
        # إلى الصفحة الرئيسية لا صفحة الدخول: الزائر بلا جلسة قد يكون
        # عميلاً محتملاً، والرئيسية تُعرّفه بالمنصة وتحمل الدخول والتسجيل.
        assert resp.headers.get("location") == "/"

    def test_module_page_authenticated_serves_html(self):
        """With a valid session the module page is served (200)."""
        from datetime import datetime
        token = "gate-test-token"
        _client_sessions[token] = {"client_id": "gate_client", "created_at": datetime.now().isoformat()}
        try:
            client = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
            client.cookies.set("client_token", token)
            resp = client.get(
                "/static/dheuof/modules/07-pos/index.html",
                headers={"accept": "text/html"},
            )
            assert resp.status_code == 200, f"Expected 200 for authed user, got {resp.status_code}"
        finally:
            _client_sessions.pop(token, None)

    def test_root_html_content_type_or_redirect(self):
        """GET / that returns 200 must serve HTML."""
        client = TestClient(app, raise_server_exceptions=False, follow_redirects=True)
        response = client.get("/")
        if response.status_code == 200:
            ct = response.headers.get("content-type", "")
            assert "text/html" in ct, (
                f"GET / returned 200 but Content-Type was '{ct}', expected text/html"
            )


# ---------------------------------------------------------------------------
# Test 4 — Multi-tenant isolation
#
# Two clients with different client_ids must NOT see each other's data.
# We mock db.execute() so no real database is needed.
# ---------------------------------------------------------------------------

class TestMultiTenantIsolation:
    """
    Verifies that data returned for client_A does not bleed into client_B.

    Strategy:
      1. Register two fake sessions in _client_sessions (client_a / client_b).
      2. Patch app.state.db.execute to return different row sets depending on
         which client_id appears in the SQL arguments.
      3. Assert each client only sees its own rows.
    """

    # Stable fake tokens / client IDs used across all subtests
    TOKEN_A = "test-token-client-aaa"
    TOKEN_B = "test-token-client-bbb"
    CID_A = "client_aaa"
    CID_B = "client_bbb"

    # Fake employee rows per tenant
    EMPLOYEES_A = [
        {"id": 1, "client_id": CID_A, "full_name_ar": "موظف ألفا", "status": "active"},
    ]
    EMPLOYEES_B = [
        {"id": 2, "client_id": CID_B, "full_name_ar": "موظف بيتا", "status": "active"},
        {"id": 3, "client_id": CID_B, "full_name_ar": "موظف غاما", "status": "active"},
    ]

    @pytest.fixture(autouse=True)
    def _setup_sessions(self):
        """Pre-load both fake sessions before each test, clean up after.

        ``created_at`` must be *now* — the app enforces an 8-hour session TTL
        (db.security.SESSION_TTL_HOURS), so a stale timestamp would be rejected
        with 401 before the isolation logic is ever reached.
        """
        from datetime import datetime
        now_iso = datetime.now().isoformat()
        _client_sessions[self.TOKEN_A] = {"client_id": self.CID_A, "created_at": now_iso}
        _client_sessions[self.TOKEN_B] = {"client_id": self.CID_B, "created_at": now_iso}
        yield
        _client_sessions.pop(self.TOKEN_A, None)
        _client_sessions.pop(self.TOKEN_B, None)

    def _employee_execute(self, sql, params=(), fetch=None):
        """
        Minimal mock for db.execute: return tenant-specific employee rows
        when the SELECT employees query is detected.
        """
        sql_lower = sql.lower().strip()
        if "from employees" in sql_lower and fetch == "all":
            # params[0] is client_id
            cid = params[0] if params else None
            if cid == self.CID_A:
                # Return MagicMock rows that behave like mappings
                rows = []
                for e in self.EMPLOYEES_A:
                    m = MagicMock()
                    m.__iter__ = lambda s, _e=e: iter(_e.items())
                    m.keys = lambda _e=e: _e.keys()
                    m.__getitem__ = lambda s, k, _e=e: _e[k]
                    m.get = lambda k, d=None, _e=e: _e.get(k, d)
                    rows.append(m)
                return rows
            elif cid == self.CID_B:
                rows = []
                for e in self.EMPLOYEES_B:
                    m = MagicMock()
                    m.__iter__ = lambda s, _e=e: iter(_e.items())
                    m.keys = lambda _e=e: _e.keys()
                    m.__getitem__ = lambda s, k, _e=e: _e[k]
                    m.get = lambda k, d=None, _e=e: _e.get(k, d)
                    rows.append(m)
                return rows
        return []

    def test_client_a_sees_only_own_employees(self):
        """Client A's session must not return Client B's employees."""
        db_mock = _mock_db(use_postgres=True)
        db_mock.execute.side_effect = self._employee_execute

        with patch.object(app.state, "db", db_mock, create=True):
            client_a = _make_client(session_token=self.TOKEN_A)
            resp = client_a.get("/api/m06/employees")

        # Must succeed for authenticated client
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        body = resp.json()
        employees = body if isinstance(body, list) else body.get("employees", body.get("data", []))

        # None of the returned employees should belong to client B
        for emp in employees:
            cid = emp.get("client_id")
            assert cid != self.CID_B, (
                f"Client A response contains a Client B employee: {emp}"
            )

    def test_client_b_sees_only_own_employees(self):
        """Client B's session must not return Client A's employees."""
        db_mock = _mock_db(use_postgres=True)
        db_mock.execute.side_effect = self._employee_execute

        with patch.object(app.state, "db", db_mock, create=True):
            client_b = _make_client(session_token=self.TOKEN_B)
            resp = client_b.get("/api/m06/employees")

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        body = resp.json()
        employees = body if isinstance(body, list) else body.get("employees", body.get("data", []))

        for emp in employees:
            cid = emp.get("client_id")
            assert cid != self.CID_A, (
                f"Client B response contains a Client A employee: {emp}"
            )

    def test_different_clients_get_different_counts(self):
        """The two tenants must receive different employee counts (A:1, B:2)."""
        db_mock = _mock_db(use_postgres=True)
        db_mock.execute.side_effect = self._employee_execute

        with patch.object(app.state, "db", db_mock, create=True):
            resp_a = _make_client(session_token=self.TOKEN_A).get("/api/m06/employees")
            resp_b = _make_client(session_token=self.TOKEN_B).get("/api/m06/employees")

        assert resp_a.status_code == 200
        assert resp_b.status_code == 200

        body_a = resp_a.json()
        body_b = resp_b.json()
        emps_a = body_a if isinstance(body_a, list) else body_a.get("employees", body_a.get("data", []))
        emps_b = body_b if isinstance(body_b, list) else body_b.get("employees", body_b.get("data", []))

        assert len(emps_a) != len(emps_b), (
            f"Both clients returned the same number of employees ({len(emps_a)}); "
            "isolation may be broken"
        )


class TestNoClientSideAuthWall:
    """
    الجدار الذي كان يحجب المنصة عن مستخدميها.

    كان `sidebar.js` يُنزل `<div id="dh-auth-wall">` بـ`z-index:99999`
    فوق كل صفحة، ويقرّر ظهوره من `localStorage` — **لا من جلسة الخادم**.
    ومن يدخل من صفحة الدخول الحقيقية تُضبط جلسته في كوكي HttpOnly ويبقى
    `localStorage` فارغاً، فينزل الجدار فوق مستخدمٍ مسجَّل الدخول فعلاً.

    والنتيجة أن كل نقرة تُعترض: لا حفظ نزيل، ولا تخصيص، ولا فاتورة —
    بينما البيانات تُقرأ من الخادم بنجاح خلفه. فتبدو المنصة معطّلة وهي
    تعمل. (أثبته Playwright حرفياً: «dh-auth-wall intercepts pointer
    events».)

    الحجب الآن مسؤولية الخادم وحده: هو يعرف الجلسة الحقيقية.
    """

    def test_the_auth_wall_is_gone_from_the_shared_sidebar(self):
        src = open("static/dheuof/shared/sidebar.js", encoding="utf-8").read()
        for marker in ("dh-auth-wall", "showAuthWall", "injectAuthStyles"):
            assert marker not in src, f"عاد جدار المصادقة إلى الواجهة: {marker}"

    def test_no_page_ships_a_blocking_overlay(self):
        import glob

        offenders = []
        for path in glob.glob("static/**/*.js", recursive=True) + \
                glob.glob("static/**/*.html", recursive=True):
            try:
                body = open(path, encoding="utf-8").read()
            except OSError:
                continue
            if "dh-auth-wall" in body:
                offenders.append(path)
        assert not offenders, "ملفات تحمل جدار الحجب: " + " · ".join(offenders)

    def test_the_browser_never_decides_auth_from_local_storage(self):
        """
        `getSession()` يقرأ `localStorage` — وهو حالة عرضٍ لا هوية. لا
        بأس ببقائه لتزيين الشريط، لكن لا يجوز أن يحجب شيئاً.
        """
        src = open("static/dheuof/shared/sidebar.js", encoding="utf-8").read()
        assert "if (!session)" not in src or "showAuthWall" not in src, (
            "قرار الحجب عاد يعتمد على localStorage"
        )
