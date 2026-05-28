"""
services/api_keys.py
يُدير مفاتيح API للتكامل الخارجي.

الأمان:
- مفتاح بـ 64 حرف (secrets.token_urlsafe(48))
- يُحفظ SHA256 hash فقط في DB — لا plain text أبداً
- rate limiting: sliding window (1 ساعة)
- tenant isolation صارم
- كل استخدام مُسجَّل مع IP والـ endpoint
"""

import hashlib
import secrets
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("api_keys")

# Rate limits افتراضية
RATE_LIMITS = {
    "read_only": 1000,      # 1000 request/hour
    "booking": 200,
    "full": 500,
}

PERMISSIONS = {
    "read_only": ["read"],
    "booking": ["read", "booking:create", "booking:cancel"],
    "full": ["read", "booking:create", "booking:cancel", "pricing:read", "channels:read"],
}


class APIKeyManager:
    """
    يُدير مفاتيح API للتكامل الخارجي.
    """

    def __init__(self, db):
        self.db = db

    # ─── Create / Revoke ──────────────────────────────────────

    def create_key(
        self,
        client_id: str,
        name: str,
        permissions: list,
        expires_days: int = 365
    ) -> dict:
        """
        يُنشئ مفتاح API جديد.
        يُعيد المفتاح مرة واحدة فقط — لا يُخزَّن plain text.
        """
        # التحقق من الصلاحيات المطلوبة
        valid_perms = {"read", "booking:create", "booking:cancel", "pricing:read", "channels:read"}
        invalid = [p for p in permissions if p not in valid_perms]
        if invalid:
            return {
                "success": False,
                "error": f"صلاحيات غير صالحة: {invalid}. المتاح: {list(valid_perms)}"
            }

        # توليد المفتاح
        raw_key = "dheuof_" + secrets.token_urlsafe(48)  # ~64 حرف
        key_hash = self._hash_key(raw_key)
        key_prefix = raw_key[:12]  # أول 12 حرف للتعريف

        # حساب rate limit
        perm_type = self._classify_permissions(permissions)
        rate_limit = RATE_LIMITS.get(perm_type, 100)

        expires_at = datetime.now() + timedelta(days=expires_days) if expires_days > 0 else None

        try:
            result = self.db.execute(
                """INSERT INTO api_keys
                   (client_id, key_hash, key_prefix, name, permissions,
                    rate_limit_rpm, expires_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    client_id, key_hash, key_prefix, name,
                    permissions,  # PostgreSQL TEXT[]
                    rate_limit,
                    expires_at,
                )
            )

            key_id = result[0]["id"] if result else None

            logger.info(f"API key created: prefix={key_prefix}, client={client_id}, name={name}")

            return {
                "success": True,
                "key": raw_key,            # يُعرض للمستخدم مرة واحدة فقط
                "key_id": key_id,
                "key_prefix": key_prefix,
                "name": name,
                "permissions": permissions,
                "rate_limit_rpm": rate_limit,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "warning": "احفظ المفتاح الآن — لن يُعرض مرة أخرى",
            }

        except Exception as e:
            logger.error(f"create_key failed: {e}")
            return {"success": False, "error": str(e)}

    def revoke_key(self, key_id: int, client_id: str) -> bool:
        """
        يُلغي مفتاحاً فوراً.
        يتحقق من أن المفتاح يعود لنفس العميل (tenant isolation).
        """
        try:
            result = self.db.execute(
                """UPDATE api_keys SET is_active = false
                   WHERE id = %s AND client_id = %s
                   RETURNING id""",
                (key_id, client_id)
            )
            success = bool(result)
            if success:
                logger.info(f"API key revoked: id={key_id}, client={client_id}")
            return success
        except Exception as e:
            logger.error(f"revoke_key failed: {e}")
            return False

    # ─── Validate ─────────────────────────────────────────────

    def validate_key(self, raw_key: str) -> dict:
        """
        يتحقق من المفتاح ويُعيد:
        {
          success, client_id, permissions, rate_limit_remaining,
          key_id, error (إذا فشل)
        }
        """
        if not raw_key or len(raw_key) < 20:
            return {"success": False, "error": "API key غير صالح", "code": "INVALID_KEY"}

        key_hash = self._hash_key(raw_key)

        try:
            rows = self.db.execute(
                """SELECT id, client_id, permissions, is_active,
                          rate_limit_rpm, expires_at, name
                   FROM api_keys
                   WHERE key_hash = %s LIMIT 1""",
                (key_hash,)
            )
        except Exception as e:
            return {"success": False, "error": "خطأ في قاعدة البيانات", "code": "DB_ERROR"}

        if not rows:
            return {"success": False, "error": "API key غير موجود", "code": "KEY_NOT_FOUND"}

        row = rows[0]

        # تحقق من التفعيل
        if not row.get("is_active"):
            return {"success": False, "error": "API key موقوف", "code": "KEY_REVOKED"}

        # تحقق من انتهاء الصلاحية
        expires_at = row.get("expires_at")
        if expires_at and expires_at < datetime.now():
            return {
                "success": False,
                "error": f"API key منتهي الصلاحية منذ {expires_at.date()}",
                "code": "KEY_EXPIRED"
            }

        # تحديث last_used وrequest_count
        try:
            self.db.execute(
                """UPDATE api_keys SET last_used = NOW(), request_count = request_count + 1
                   WHERE id = %s""",
                (row["id"],)
            )
        except Exception:
            pass

        rate_remaining = self.get_rate_limit_remaining(row["id"], row.get("rate_limit_rpm", 60))

        return {
            "success": True,
            "key_id": row["id"],
            "client_id": row["client_id"],
            "permissions": row.get("permissions", []),
            "rate_limit_rpm": row.get("rate_limit_rpm", 60),
            "rate_limit_remaining": rate_remaining,
            "name": row.get("name", ""),
        }

    def has_permission(self, key_data: dict, required_permission: str) -> bool:
        """يتحقق من صلاحية معينة"""
        if not key_data.get("success"):
            return False
        permissions = key_data.get("permissions", [])
        # full access
        if "full" in permissions:
            return True
        return required_permission in permissions

    # ─── Rate Limiting ────────────────────────────────────────

    def check_rate_limit(self, key_id: int, endpoint: str, limit_per_hour: int = None) -> bool:
        """
        يتحقق من حد الطلبات (sliding window — آخر ساعة).
        يُعيد True إذا مسموح · False إذا تجاوز الحد.
        """
        try:
            rows = self.db.execute(
                """SELECT COUNT(*) as cnt FROM api_usage_log
                   WHERE key_id = %s AND created_at > NOW() - INTERVAL '1 hour'""",
                (key_id,)
            )
            count = rows[0]["cnt"] if rows else 0

            # جلب limit من DB إذا لم يُعطَ
            if limit_per_hour is None:
                key_rows = self.db.execute(
                    "SELECT rate_limit_rpm FROM api_keys WHERE id=%s LIMIT 1",
                    (key_id,)
                )
                limit_per_hour = key_rows[0]["rate_limit_rpm"] if key_rows else 60

            return count < limit_per_hour

        except Exception as e:
            logger.error(f"check_rate_limit failed: {e}")
            return True  # نسمح بالمرور عند خطأ DB لا نوقف الخدمة

    def get_rate_limit_remaining(self, key_id: int, limit_per_hour: int) -> int:
        """يُعيد عدد الطلبات المتبقية في النافذة الحالية"""
        try:
            rows = self.db.execute(
                """SELECT COUNT(*) as cnt FROM api_usage_log
                   WHERE key_id = %s AND created_at > NOW() - INTERVAL '1 hour'""",
                (key_id,)
            )
            used = rows[0]["cnt"] if rows else 0
            return max(0, limit_per_hour - used)
        except Exception:
            return limit_per_hour

    def log_usage(
        self, key_id: int, client_id: str,
        endpoint: str, method: str,
        status_code: int, ip: str, duration_ms: int
    ) -> None:
        """يسجّل كل استخدام لـ API"""
        try:
            self.db.execute(
                """INSERT INTO api_usage_log
                   (key_id, client_id, endpoint, method, status_code, ip_address, duration_ms)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (key_id, client_id, endpoint[:200], method[:10], status_code, ip[:45], duration_ms)
            )
        except Exception as e:
            logger.error(f"log_usage failed: {e}")

    # ─── List / Stats ─────────────────────────────────────────

    def list_keys(self, client_id: str) -> list:
        """يُعيد قائمة المفاتيح للعرض في لوحة التحكم (بدون hash)"""
        try:
            rows = self.db.execute(
                """SELECT id, key_prefix, name, permissions, is_active,
                          last_used, request_count, rate_limit_rpm, expires_at, created_at
                   FROM api_keys
                   WHERE client_id = %s
                   ORDER BY created_at DESC""",
                (client_id,)
            )
            return [dict(r) for r in (rows or [])]
        except Exception as e:
            logger.error(f"list_keys failed: {e}")
            return []

    def get_usage_stats(self, client_id: str, key_id: int, days: int = 30) -> dict:
        """يُعيد إحصائيات الاستخدام"""
        try:
            rows = self.db.execute(
                """SELECT
                     COUNT(*) as total_requests,
                     COUNT(CASE WHEN status_code < 400 THEN 1 END) as successful,
                     COUNT(CASE WHEN status_code >= 400 THEN 1 END) as errors,
                     AVG(duration_ms) as avg_duration_ms,
                     endpoint,
                     COUNT(*) as endpoint_count
                   FROM api_usage_log
                   WHERE client_id = %s AND key_id = %s
                     AND created_at >= NOW() - INTERVAL '%s days'
                   GROUP BY endpoint
                   ORDER BY endpoint_count DESC
                   LIMIT 20""",
                (client_id, key_id, days)
            )
            return {"endpoints": [dict(r) for r in (rows or [])]}
        except Exception as e:
            return {"error": str(e)}

    # ─── Helpers ──────────────────────────────────────────────

    def _hash_key(self, raw_key: str) -> str:
        """SHA256 hash للمفتاح"""
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def _classify_permissions(self, permissions: list) -> str:
        """يصنّف المفتاح حسب الصلاحيات"""
        if "full" in permissions or len(permissions) > 3:
            return "full"
        if any(p.startswith("booking:") for p in permissions):
            return "booking"
        return "read_only"
