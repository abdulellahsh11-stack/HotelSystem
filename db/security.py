#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/security.py — Security helpers for isolation hardening
Addresses all 10 findings from the Isolation Security Audit
"""
import hashlib
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger("dheuof.security")

# ── Constants ─────────────────────────────────────────────────
SESSION_TTL_HOURS = 8       # Finding #8: short session lifetime
GUEST_SESSION_TTL_HOURS = 48

# In-memory revocation set (PostgreSQL is authoritative; this is fast-path cache)
_revoked_cache: set = set()
_revoke_lock = threading.Lock()


# ── Finding #8: Session TTL Enforcement ───────────────────────

def session_is_expired(session: dict) -> bool:
    """Return True if the session has exceeded SESSION_TTL_HOURS."""
    created = session.get("created_at")
    if not created:
        return True
    try:
        ts = datetime.fromisoformat(created)
        return datetime.now() - ts > timedelta(hours=SESSION_TTL_HOURS)
    except (ValueError, TypeError):
        return True


def token_hash(token: str) -> str:
    """SHA-256 hash of a session token for safe storage in revoked_sessions."""
    return hashlib.sha256(token.encode()).hexdigest()


def revoke_token(db, token: str, client_id: str, reason: str = "logout") -> None:
    """Mark a token as revoked in PostgreSQL and local cache (Finding #8)."""
    h = token_hash(token)
    with _revoke_lock:
        _revoked_cache.add(h)
    if db and db.use_postgres:
        try:
            db.execute(
                """INSERT INTO revoked_sessions (token_hash, client_id, reason)
                   VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                (h, client_id, reason)
            )
        except Exception as e:
            log.warning(f"revoke_token DB write failed: {e}")


def is_token_revoked(db, token: str) -> bool:
    """
    Check revocation: fast-path local cache first, then PostgreSQL.
    Finding #8: every request must verify the token hasn't been revoked.
    """
    h = token_hash(token)
    with _revoke_lock:
        if h in _revoked_cache:
            return True
    if db and db.use_postgres:
        try:
            row = db.execute(
                "SELECT 1 FROM revoked_sessions WHERE token_hash = %s",
                (h,), fetch="one"
            )
            if row:
                with _revoke_lock:
                    _revoked_cache.add(h)
                return True
        except Exception as e:
            log.warning(f"is_token_revoked DB check failed: {e}")
    return False


# ── Finding #1: Branch Isolation ──────────────────────────────

def session_branches(session: dict) -> Optional[list]:
    """
    Returns list of branch_ids from session, or None for GM/owner (unrestricted).
    Finding #1: callers MUST pass this to queries that filter by branch_id.
    """
    return session.get("branch_ids")  # None = GM sees all


def branch_clause(session: dict, alias: str = "") -> tuple:
    """
    Returns (sql_fragment, params) for branch filtering.
    Finding #1: inject into WHERE clause of any operational query.

    Usage:
        frag, params = branch_clause(session, alias="r")
        sql = f"SELECT * FROM rooms r WHERE r.client_id = %s{frag}"
        db.execute(sql, [cid] + params)
    """
    prefix = f"{alias}." if alias else ""
    branches = session_branches(session)
    if branches is None:
        return "", []
    return f" AND ({prefix}branch_id IS NULL OR {prefix}branch_id = ANY(%s))", [branches]


# ── Finding #2: RBAC Guard ─────────────────────────────────────

# Map of endpoint patterns → required permission
_PERMISSION_MAP: dict = {
    "payroll":      "payroll",
    "hr":           "hr",
    "salary":       "payroll",
    "housekeeping": "housekeeping",
    "maintenance":  "maintenance",
    "invoices":     "invoices",
    "pos":          "pos",
    "reports":      "reports",
    "channels":     "channels",
}


def check_permission(session: dict, permission: str) -> bool:
    """
    Finding #2: verify the session actor has the required permission.
    owner / gm always pass. Staff checked against their role permissions.
    """
    role = session.get("role", "")
    perms = session.get("permissions", [])
    if "*" in perms or role in ("owner", "gm"):
        return True
    return permission in perms


def enforce_permission(session: dict, permission: str) -> None:
    """Raise ValueError if permission is missing (Finding #2)."""
    if not check_permission(session, permission):
        raise PermissionError(
            f"الصلاحية '{permission}' مطلوبة — الدور الحالي: {session.get('role', 'غير محدد')}"
        )


# ── Finding #3: NULL-safe tenant guard ────────────────────────

def require_client_id(session: dict) -> str:
    """
    Finding #3: fail loudly if client_id is missing or empty.
    Never return a falsy value that could cause 'no filter' queries.
    """
    cid = session.get("client_id", "")
    if not cid or not cid.strip():
        raise ValueError("client_id غير موجود في الجلسة — رفض الاستعلام")
    return cid.strip()


# ── Finding #4: Guest Session Isolation ───────────────────────

def validate_guest_session(db, token: str, guest_id: int) -> bool:
    """
    Finding #4: verify the guest token is bound to the specific guest_id only.
    Returns False if token expired, invalid, or belongs to different guest.
    """
    h = token_hash(token)
    if db and db.use_postgres:
        try:
            row = db.execute(
                """SELECT guest_id FROM guest_sessions
                   WHERE token_hash = %s
                     AND actor_type = 'guest'
                     AND expires_at > NOW()""",
                (h,), fetch="one"
            )
            return bool(row and row["guest_id"] == guest_id)
        except Exception as e:
            log.warning(f"validate_guest_session failed: {e}")
    return False


def create_guest_session(db, client_id: str, guest_id: int, booking_id: str, token: str) -> None:
    """Finding #4: insert a guest session token bound to one guest/booking."""
    h = token_hash(token)
    if db and db.use_postgres:
        try:
            db.execute(
                """INSERT INTO guest_sessions
                       (token_hash, client_id, guest_id, booking_id, actor_type)
                   VALUES (%s, %s, %s, %s, 'guest')
                   ON CONFLICT DO NOTHING""",
                (h, client_id, guest_id, booking_id)
            )
        except Exception as e:
            log.warning(f"create_guest_session failed: {e}")


# ── Finding #5: Cache Key Pattern ─────────────────────────────

def cache_key(tenant_id: str, resource: str, identifier: str = "") -> str:
    """
    Finding #5: enforce {tid}:{resource}:{id} key pattern for any cache store.
    Call this instead of building cache keys manually.
    """
    if not tenant_id or not resource:
        raise ValueError("tenant_id و resource مطلوبان في مفتاح الكاش")
    parts = [tenant_id, resource]
    if identifier:
        parts.append(identifier)
    return ":".join(parts)


# ── Finding #6: Event Context Guard ───────────────────────────

def set_event_context(db, tenant_id: str) -> None:
    """
    Finding #6: set app.tenant_id in PostgreSQL session before processing
    any event (NATS / background jobs). Must be called before any write.
    """
    if not tenant_id:
        raise ValueError("tenant_id مطلوب لضبط سياق الحدث")
    if db and db.use_postgres:
        try:
            # H4 fix: استخدم set_config المُمعلَّم بدل إقحام النص (يمنع حقن SQL)
            db.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))
        except Exception as e:
            log.warning(f"set_event_context failed: {e}")


# ── Finding #7: Secure File Links ─────────────────────────────

import secrets as _secrets  # noqa: E402


def create_secure_link(
    db, client_id: str, guest_id: int, file_path: str,
    created_by: str, ttl_minutes: int = 15, branch_id: Optional[int] = None
) -> str:
    """
    Finding #7: create a short-lived presigned-style link for a file.
    Path must follow tenant/branch/guest/filename structure.
    Returns the link token.
    """
    if not file_path.startswith(f"{client_id}/"):
        raise ValueError(
            f"مسار الملف يجب أن يبدأ بـ {client_id}/ — مسار خاطئ: {file_path}"
        )
    link_token = _secrets.token_urlsafe(32)
    if db and db.use_postgres:
        try:
            db.execute(
                """INSERT INTO secure_file_links
                       (client_id, branch_id, guest_id, file_path,
                        link_token, expires_at, created_by)
                   VALUES (%s, %s, %s, %s, %s,
                           NOW() + (%s || ' minutes')::interval, %s)""",
                (client_id, branch_id, guest_id, file_path, link_token, int(ttl_minutes), created_by)
            )
        except Exception as e:
            log.warning(f"create_secure_link failed: {e}")
    return link_token


# ── Finding #9: SECURITY DEFINER audit ────────────────────────

def audit_security_definer_functions(db) -> list:
    """
    Finding #9: return all SECURITY DEFINER functions for review.
    Call this on startup and log a warning if any are found.
    """
    if not (db and db.use_postgres):
        return []
    try:
        rows = db.execute(
            "SELECT * FROM v_security_definer_audit", fetch="all"
        )
        return [dict(r) for r in (rows or [])]
    except Exception as e:
        log.warning(f"audit_security_definer_functions: {e}")
        return []


# ── Finding #10: ID Masking ───────────────────────────────────

def mask_id(serial_id: int, salt: str = "dheuof") -> str:
    """
    Finding #10: convert a BIGSERIAL to a safe token before exposing in API.
    Never return raw sequential IDs in public-facing endpoints.
    """
    raw = f"{salt}::{serial_id}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]
