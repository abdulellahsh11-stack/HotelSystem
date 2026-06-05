#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/cache_helpers.py — أنماط كاش شائعة لنظام ضيوف
========================================================
دوال مساعدة جاهزة للاستخدام في المسارات (routes) والخدمات.
تعتمد على RedisSession وتُطبّق نمط cache_key() من db/security.py:
    {tenant_id}:{resource}:{id}

الموارد المُعرَّفة:
    - room_status   : حالة الغرف لمنشأة (client)
    - kpi           : مؤشرات الأداء (KPI) لفترة زمنية معيّنة
"""
import logging
from typing import Any, Optional

from db.security import cache_key
from services.redis_session import RedisSession

log = logging.getLogger("dheuof.cache_helpers")

# ── ثوابت الموارد ─────────────────────────────────────────────
_RESOURCE_ROOM_STATUS = "room_status"
_RESOURCE_KPI = "kpi"

# ── TTL الافتراضية ────────────────────────────────────────────
_TTL_ROOM_STATUS = 300   # 5 دقائق — تتغيّر حالة الغرف بتعديلات متكررة
_TTL_KPI = 600           # 10 دقائق — حسابات KPI مكلفة نسبياً


# ═══════════════════════════════════════════════════════════════
# ── كاش حالة الغرف ────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def cache_room_status(
    redis_session: RedisSession,
    client_id: str,
    data: Any,
    ttl: int = _TTL_ROOM_STATUS,
) -> None:
    """
    يحفظ حالة الغرف لمنشأة في الكاش.

    المعاملات
    ----------
    redis_session : نسخة RedisSession الفاعلة.
    client_id     : معرف المنشأة (tenant).
    data          : بيانات حالة الغرف (قابلة للتسلسل بـ JSON).
    ttl           : مدة الصلاحية بالثواني (الافتراضي 300).
    """
    key = cache_key(client_id, _RESOURCE_ROOM_STATUS)
    redis_session.set_cache(key, data, ttl_seconds=ttl)
    log.debug("cache_room_status: حُفظت حالة الغرف للمنشأة %s (TTL=%ds)", client_id, ttl)


def get_room_status(
    redis_session: RedisSession,
    client_id: str,
) -> Optional[Any]:
    """
    يُعيد حالة الغرف المخزَّنة في الكاش أو ``None`` عند انتهاء الصلاحية.

    المعاملات
    ----------
    redis_session : نسخة RedisSession الفاعلة.
    client_id     : معرف المنشأة (tenant).
    """
    key = cache_key(client_id, _RESOURCE_ROOM_STATUS)
    data = redis_session.get_cache(key)
    if data is None:
        log.debug("cache_room_status miss: المنشأة %s", client_id)
    return data


# ═══════════════════════════════════════════════════════════════
# ── كاش مؤشرات الأداء (KPI) ──────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def cache_kpi(
    redis_session: RedisSession,
    client_id: str,
    period: str,
    data: Any,
    ttl: int = _TTL_KPI,
) -> None:
    """
    يحفظ بيانات KPI لمنشأة وفترة زمنية في الكاش.

    المعاملات
    ----------
    redis_session : نسخة RedisSession الفاعلة.
    client_id     : معرف المنشأة (tenant).
    period        : الفترة الزمنية — مثال: ``"2025-06"`` أو ``"today"``.
    data          : بيانات KPI (قابلة للتسلسل بـ JSON).
    ttl           : مدة الصلاحية بالثواني (الافتراضي 600).
    """
    key = cache_key(client_id, _RESOURCE_KPI, period)
    redis_session.set_cache(key, data, ttl_seconds=ttl)
    log.debug("cache_kpi: حُفظت KPI للمنشأة %s الفترة '%s' (TTL=%ds)", client_id, period, ttl)


def get_kpi(
    redis_session: RedisSession,
    client_id: str,
    period: str,
) -> Optional[Any]:
    """
    يُعيد بيانات KPI المخزَّنة في الكاش أو ``None`` عند انتهاء الصلاحية.

    المعاملات
    ----------
    redis_session : نسخة RedisSession الفاعلة.
    client_id     : معرف المنشأة (tenant).
    period        : الفترة الزمنية المُطلوبة.
    """
    key = cache_key(client_id, _RESOURCE_KPI, period)
    data = redis_session.get_cache(key)
    if data is None:
        log.debug("cache_kpi miss: المنشأة %s الفترة '%s'", client_id, period)
    return data


# ═══════════════════════════════════════════════════════════════
# ── إبطال كاش المنشأة بالكامل ────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def invalidate_tenant_cache(
    redis_session: RedisSession,
    client_id: str,
) -> int:
    """
    يحذف جميع مفاتيح الكاش المرتبطة بمنشأة واحدة.

    يُستدعى بعد:
    - تحديث بيانات المنشأة الجوهرية.
    - إعادة هيكلة الغرف أو الأسعار.
    - أي عملية تُبطل صحة الكاش الحالي.

    المعاملات
    ----------
    redis_session : نسخة RedisSession الفاعلة.
    client_id     : معرف المنشأة المراد إبطال كاشها.

    يُعيد عدد المفاتيح المحذوفة.
    """
    if not client_id or not client_id.strip():
        log.warning("invalidate_tenant_cache: client_id فارغ — تجاهَل")
        return 0

    # نمط البحث: {client_id}:* — يشمل كل موارد المنشأة
    pattern = f"{client_id.strip()}:*"
    deleted = redis_session.delete_by_pattern(pattern)
    log.info(
        "invalidate_tenant_cache: أُبطل كاش المنشأة %s — %d مفتاح محذوف",
        client_id,
        deleted,
    )
    return deleted
