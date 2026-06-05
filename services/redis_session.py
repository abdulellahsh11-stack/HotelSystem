#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/redis_session.py — إدارة الجلسات والكاش عبر Redis
============================================================
يُوفّر طبقة موحّدة لتخزين الجلسات والكاش باستخدام Redis مع
خطة احتياطية تلقائية (in-memory dict) عند غياب Redis.

نمط مفاتيح الجلسات : session:{sha256(token)}
نمط مفاتيح الكاش   : {tenant_id}:{resource}:{id}   ← مُطابق لـ cache_key() في db/security.py
"""
import hashlib
import json
import logging
import os
import threading
from typing import Any, Optional

log = logging.getLogger("dheuof.redis_session")

# ── الثوابت ──────────────────────────────────────────────────
_SESSION_KEY_PREFIX = "session"
_DEFAULT_SESSION_TTL_HOURS = 8       # يُطابق SESSION_TTL_HOURS في db/security.py
_DEFAULT_CACHE_TTL_SECONDS = 300     # 5 دقائق — TTL افتراضي للكاش


# ── أداة مساعدة: hash التوكن ─────────────────────────────────

def _token_hash(token: str) -> str:
    """SHA-256 للتوكن — لا يُخزَّن التوكن الخام أبداً."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── الكلاس الرئيسي ───────────────────────────────────────────

class RedisSession:
    """
    طبقة موحّدة لإدارة الجلسات والكاش.

    - إذا كان REDIS_URL موجوداً ويمكن الاتصال به → يستخدم Redis.
    - إذا تعذّر الاتصال بـ Redis → يتراجع تلقائياً إلى in-memory dict
      مع تسجيل تحذير واحد فقط (لتفادي إغراق السجلات).

    المعاملات
    ----------
    redis_url : str, optional
        عنوان Redis (مثال: ``redis://localhost:6379/0``).
        يُقرأ من ``REDIS_URL`` إذا لم يُمرَّر.
    """

    def __init__(self, redis_url: str = "") -> None:
        self._url: str = redis_url or os.environ.get("REDIS_URL", "")
        self._client = None          # redis.Redis — يُهيَّأ عند الاتصال الأول
        self._available: bool = False
        self._warned: bool = False   # نطبع التحذير مرة واحدة فقط

        # ── الاحتياط: in-memory stores ───────────────────────
        self._mem_sessions: dict = {}      # token_hash → json_str
        self._mem_cache: dict = {}         # cache_key  → json_str
        self._mem_ttl: dict = {}           # key        → expiry_epoch (float)
        self._lock = threading.RLock()     # حماية in-memory من التزامن

        # حاول الاتصال فوراً إذا كان الـ URL موجوداً
        if self._url:
            self._connect()

    # ── الاتصال ──────────────────────────────────────────────

    def _connect(self) -> None:
        """يحاول الاتصال بـ Redis — يُسجّل خطأ ولا يُوقف التطبيق عند الفشل."""
        try:
            import redis as _redis  # noqa: PLC0415
            self._client = _redis.Redis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
                retry_on_timeout=False,
            )
            # PING للتحقق من الاتصال الفعلي
            self._client.ping()
            self._available = True
            log.info("Redis متصل بنجاح — الجلسات والكاش عبر Redis ✅")
        except ImportError:
            log.warning(
                "مكتبة redis غير مُثبَّتة (pip install redis) — "
                "يُستخدم in-memory fallback ⚠️"
            )
            self._available = False
        except Exception as exc:
            log.warning(
                "تعذّر الاتصال بـ Redis (%s) — يُستخدم in-memory fallback ⚠️: %s",
                self._url,
                exc,
            )
            self._available = False

    def _warn_once(self) -> None:
        """يطبع تحذير in-memory مرة واحدة فقط لتفادي إغراق السجلات."""
        if not self._warned:
            log.warning(
                "RedisSession تعمل بوضع in-memory — البيانات لن تُشارَك بين العمليات"
            )
            self._warned = True

    @property
    def is_redis_available(self) -> bool:
        """True إذا كان Redis متصلاً وجاهزاً للاستخدام."""
        return self._available

    # ═══════════════════════════════════════════════════════════
    # ── إدارة الجلسات ─────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════

    def _session_key(self, token: str) -> str:
        """يُنشئ مفتاح Redis للجلسة: ``session:{sha256(token)}``."""
        return f"{_SESSION_KEY_PREFIX}:{_token_hash(token)}"

    def set_session(
        self,
        token: str,
        data: dict,
        ttl_hours: int = _DEFAULT_SESSION_TTL_HOURS,
    ) -> None:
        """
        يحفظ بيانات الجلسة مرتبطةً بالتوكن.

        المعاملات
        ----------
        token     : التوكن الخام (يُخزَّن hash فقط).
        data      : dict تحتوي على بيانات الجلسة (client_id، role، …).
        ttl_hours : مدة الصلاحية بالساعات — الافتراضي SESSION_TTL_HOURS.
        """
        key = self._session_key(token)
        payload = json.dumps(data, ensure_ascii=False, default=str)
        ttl_seconds = ttl_hours * 3600

        if self._available:
            try:
                self._client.setex(key, ttl_seconds, payload)
                return
            except Exception as exc:
                log.warning("set_session Redis فشل — يتراجع إلى in-memory: %s", exc)
                self._available = False

        # ── in-memory fallback ───────────────────────────────
        self._warn_once()
        import time
        with self._lock:
            self._mem_sessions[key] = payload
            self._mem_ttl[key] = time.time() + ttl_seconds

    def get_session(self, token: str) -> Optional[dict]:
        """
        يُعيد بيانات الجلسة أو ``None`` إذا انتهت صلاحيتها أو غير موجودة.
        """
        key = self._session_key(token)

        if self._available:
            try:
                raw = self._client.get(key)
                if raw is None:
                    return None
                return json.loads(raw)
            except Exception as exc:
                log.warning("get_session Redis فشل — يتراجع إلى in-memory: %s", exc)
                self._available = False

        # ── in-memory fallback ───────────────────────────────
        self._warn_once()
        import time
        with self._lock:
            raw = self._mem_sessions.get(key)
            if raw is None:
                return None
            # تحقق من انتهاء الصلاحية
            expiry = self._mem_ttl.get(key, 0)
            if time.time() > expiry:
                self._mem_sessions.pop(key, None)
                self._mem_ttl.pop(key, None)
                return None
            return json.loads(raw)

    def delete_session(self, token: str) -> None:
        """يحذف الجلسة فوراً (تسجيل الخروج، إلغاء الجلسة)."""
        key = self._session_key(token)

        if self._available:
            try:
                self._client.delete(key)
                return
            except Exception as exc:
                log.warning("delete_session Redis فشل — يتراجع إلى in-memory: %s", exc)
                self._available = False

        # ── in-memory fallback ───────────────────────────────
        with self._lock:
            self._mem_sessions.pop(key, None)
            self._mem_ttl.pop(key, None)

    def exists(self, token: str) -> bool:
        """يتحقق من وجود الجلسة دون إعادة بياناتها."""
        key = self._session_key(token)

        if self._available:
            try:
                return bool(self._client.exists(key))
            except Exception as exc:
                log.warning("exists Redis فشل — يتراجع إلى in-memory: %s", exc)
                self._available = False

        # ── in-memory fallback ───────────────────────────────
        import time
        with self._lock:
            if key not in self._mem_sessions:
                return False
            expiry = self._mem_ttl.get(key, 0)
            if time.time() > expiry:
                self._mem_sessions.pop(key, None)
                self._mem_ttl.pop(key, None)
                return False
            return True

    # ═══════════════════════════════════════════════════════════
    # ── إدارة الكاش ───────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════

    # نمط المفتاح: {tenant_id}:{resource}:{id}
    # مُطابق لـ cache_key() في db/security.py
    # لذلك نمرر المفتاح الجاهز مباشرةً (لا نُعيد بناءه هنا).

    def set_cache(
        self,
        key: str,
        data: Any,
        ttl_seconds: int = _DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        """
        يحفظ قيمة في الكاش مع TTL.

        المعاملات
        ----------
        key         : مفتاح الكاش — استخدم ``cache_key()`` من db/security.py.
        data        : القيمة (قابلة للتسلسل بـ JSON).
        ttl_seconds : مدة الصلاحية بالثواني.
        """
        payload = json.dumps(data, ensure_ascii=False, default=str)

        if self._available:
            try:
                self._client.setex(key, ttl_seconds, payload)
                return
            except Exception as exc:
                log.warning("set_cache Redis فشل — يتراجع إلى in-memory: %s", exc)
                self._available = False

        # ── in-memory fallback ───────────────────────────────
        self._warn_once()
        import time
        with self._lock:
            self._mem_cache[key] = payload
            self._mem_ttl[key] = time.time() + ttl_seconds

    def get_cache(self, key: str) -> Optional[Any]:
        """
        يُعيد قيمة الكاش أو ``None`` عند انتهاء الصلاحية أو غياب المفتاح.
        """
        if self._available:
            try:
                raw = self._client.get(key)
                if raw is None:
                    return None
                return json.loads(raw)
            except Exception as exc:
                log.warning("get_cache Redis فشل — يتراجع إلى in-memory: %s", exc)
                self._available = False

        # ── in-memory fallback ───────────────────────────────
        import time
        with self._lock:
            raw = self._mem_cache.get(key)
            if raw is None:
                return None
            expiry = self._mem_ttl.get(key, 0)
            if time.time() > expiry:
                self._mem_cache.pop(key, None)
                self._mem_ttl.pop(key, None)
                return None
            return json.loads(raw)

    def delete_cache(self, key: str) -> None:
        """يحذف مفتاح كاش واحد (إبطال فوري بعد التعديل)."""
        if self._available:
            try:
                self._client.delete(key)
                return
            except Exception as exc:
                log.warning("delete_cache Redis فشل — يتراجع إلى in-memory: %s", exc)
                self._available = False

        # ── in-memory fallback ───────────────────────────────
        with self._lock:
            self._mem_cache.pop(key, None)
            self._mem_ttl.pop(key, None)

    # ═══════════════════════════════════════════════════════════
    # ── أدوات مساعدة ──────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════

    def delete_by_pattern(self, pattern: str) -> int:
        """
        يحذف كل المفاتيح المُطابِقة للنمط (مثال: ``"hotel123:*"``).

        يعمل فقط مع Redis (SCAN + DEL).
        مع in-memory يُطابق يدوياً.
        يُعيد عدد المفاتيح المحذوفة.
        """
        import fnmatch

        deleted = 0

        if self._available:
            try:
                # SCAN أكثر أماناً من KEYS في بيئة الإنتاج
                cursor = 0
                keys_to_delete = []
                while True:
                    cursor, batch = self._client.scan(cursor, match=pattern, count=100)
                    keys_to_delete.extend(batch)
                    if cursor == 0:
                        break
                if keys_to_delete:
                    deleted = self._client.delete(*keys_to_delete)
                return deleted
            except Exception as exc:
                log.warning("delete_by_pattern Redis فشل: %s", exc)
                self._available = False

        # ── in-memory fallback ───────────────────────────────
        with self._lock:
            # جمع المفاتيح من كلا المخزنَين
            all_keys = set(self._mem_sessions) | set(self._mem_cache)
            to_del = [k for k in all_keys if fnmatch.fnmatch(k, pattern)]
            for k in to_del:
                self._mem_sessions.pop(k, None)
                self._mem_cache.pop(k, None)
                self._mem_ttl.pop(k, None)
            deleted = len(to_del)
        return deleted

    def flush_expired(self) -> int:
        """
        يُنظّف المفاتيح المنتهية الصلاحية من in-memory (مهمة صيانة دورية).
        لا تأثير له عند استخدام Redis (يتولى Redis التنظيف تلقائياً).
        يُعيد عدد المفاتيح المحذوفة.
        """
        if self._available:
            return 0  # Redis يُدير TTL داخلياً

        import time
        now = time.time()
        deleted = 0

        with self._lock:
            expired = [k for k, exp in self._mem_ttl.items() if now > exp]
            for k in expired:
                self._mem_sessions.pop(k, None)
                self._mem_cache.pop(k, None)
                self._mem_ttl.pop(k, None)
                deleted += 1

        if deleted:
            log.debug("flush_expired: أُزيل %d مفتاح منتهي الصلاحية", deleted)
        return deleted
