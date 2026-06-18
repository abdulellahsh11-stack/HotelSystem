#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مدير مفاتيح API (API Key Manager)
==================================
يُصدر ويُدقّق مفاتيح API لكل مشترك — لربط البرامج الخارجية بمرونة.

الأمان:
- لا يُخزَّن المفتاح الخام أبداً — يُخزَّن SHA-256 hash + قناع (hint) فقط.
- كل مفتاح مرتبط بـ client_id (رقم المشترك) ونطاقات صلاحية (scopes).
- يتدهور بأمان عند غياب PostgreSQL.
"""
import hashlib
import secrets
import logging

log = logging.getLogger("dheuof.apikeys")

KEY_PREFIX = "dhk_"  # Dheuof Key

# النطاقات المتاحة — لكل برنامج نطاق
SCOPES = [
    "rooms:read", "rooms:write",
    "bookings:read", "bookings:write",
    "guests:read", "guests:write",
    "invoices:read", "invoices:write",
    "pos:read", "pos:write",
    "inventory:read", "inventory:write",
    "hr:read", "channels:read", "channels:write",
    "kpi:read", "accounting:read", "accounting:write",
]


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _hint(raw: str) -> str:
    if len(raw) <= 8:
        return "••••"
    return raw[:7] + "••••" + raw[-4:]


class APIKeyManager:
    """يُهيّأ مرة واحدة في lifespan عبر APIKeyManager(db)."""

    def __init__(self, db):
        self.db = db
        try:
            self.ensure_schema()
        except Exception as e:  # pragma: no cover
            log.warning(f"تعذّر تهيئة مخطط مفاتيح API: {e}")

    def ensure_schema(self) -> None:
        if not getattr(self.db, "use_postgres", False):
            return
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id         SERIAL PRIMARY KEY,
                client_id  VARCHAR(50) NOT NULL,
                name       VARCHAR(120) DEFAULT '',
                key_hash   VARCHAR(64) NOT NULL UNIQUE,
                key_hint   VARCHAR(40) DEFAULT '',
                scopes     TEXT DEFAULT '',
                active     BOOLEAN DEFAULT TRUE,
                last_used  TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_apikeys_client ON api_keys(client_id)")

    # ── إصدار مفتاح ───────────────────────────────────────────
    def issue_key(self, client_id: str, name: str = "", scopes=None) -> dict:
        """يُصدر مفتاحاً جديداً — يُعاد الخام مرة واحدة فقط."""
        raw = KEY_PREFIX + secrets.token_urlsafe(32)
        scope_str = ",".join(scopes) if scopes else "rooms:read,bookings:read,invoices:read"
        if getattr(self.db, "use_postgres", False):
            self.db.execute(
                """INSERT INTO api_keys (client_id, name, key_hash, key_hint, scopes)
                   VALUES (%s,%s,%s,%s,%s)""",
                (client_id, name, _hash(raw), _hint(raw), scope_str))
        return {
            "api_key": raw,                  # يظهر مرة واحدة فقط
            "key_hint": _hint(raw),
            "name": name,
            "scopes": scope_str.split(","),
            "warning": "احفظ هذا المفتاح الآن — لن يظهر مرة أخرى",
        }

    # ── تدقيق مفتاح ───────────────────────────────────────────
    def validate_key(self, raw: str) -> dict:
        """يُعيد {client_id, scopes} إذا كان المفتاح صالحاً، وإلا None."""
        if not raw or not raw.startswith(KEY_PREFIX):
            return None
        if not getattr(self.db, "use_postgres", False):
            return None
        row = self.db.execute(
            """SELECT client_id, scopes, active FROM api_keys
               WHERE key_hash=%s""", (_hash(raw),), fetch="one")
        if not row:
            return None
        row = dict(row)
        if not row.get("active"):
            return None
        # تحديث آخر استخدام (best-effort)
        try:
            self.db.execute(
                "UPDATE api_keys SET last_used=NOW() WHERE key_hash=%s", (_hash(raw),))
        except Exception:
            pass
        return {
            "client_id": row["client_id"],
            "scopes": (row.get("scopes") or "").split(","),
        }

    def has_scope(self, key_data: dict, scope: str) -> bool:
        scopes = key_data.get("scopes", []) if key_data else []
        return scope in scopes or "*" in scopes

    # ── إدارة ─────────────────────────────────────────────────
    def list_keys(self, client_id: str) -> list:
        if not getattr(self.db, "use_postgres", False):
            return []
        rows = self.db.execute(
            """SELECT id, name, key_hint, scopes, active, last_used, created_at
               FROM api_keys WHERE client_id=%s ORDER BY created_at DESC""",
            (client_id,), fetch="all") or []
        out = []
        for r in rows:
            d = dict(r)
            d["scopes"] = (d.get("scopes") or "").split(",")
            out.append(d)
        return out

    def revoke_key(self, client_id: str, key_id: int) -> bool:
        if not getattr(self.db, "use_postgres", False):
            return False
        n = self.db.execute(
            "UPDATE api_keys SET active=FALSE WHERE id=%s AND client_id=%s",
            (key_id, client_id))
        return bool(n)

    @staticmethod
    def available_scopes() -> list:
        return list(SCOPES)
