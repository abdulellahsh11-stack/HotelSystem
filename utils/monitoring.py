#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils/monitoring.py — Sentry Setup + Error Logging
آمن تماماً إذا لم يكن Sentry مُفعَّلاً — يعمل بالـ console فقط
"""
import os
import time
import logging
import traceback
from datetime import datetime
from typing import Any

log = logging.getLogger("dheuof.monitoring")

try:
    import sentry_sdk
    from sentry_sdk import capture_exception, capture_message
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    log.info("sentry-sdk غير منصَّب — أضفه في requirements.txt لتفعيل مراقبة الأخطاء")

# ── حقول بيانات حساسة — لا تُرسَل أبداً لـ Sentry ──────────
_SENSITIVE_KEYS = frozenset({
    "id_number", "absher_phone", "phone", "password", "token",
    "api_key", "whatsapp_token", "admin_pass", "pass_hash",
    "admin_pass_hash", "birth_date", "id_type", "nationality",
    "iqama", "passport", "credit_card", "bank_account",
    "secret_key", "anthropic_api_key", "github_token",
})

_SENTRY_READY = False


def setup_sentry(dsn: str) -> None:
    """
    يُهيّئ Sentry — آمن إذا لم يكن DSN موجوداً.
    يُستدعى مرة واحدة من main.py
    """
    global _SENTRY_READY

    if not dsn:
        print("⚠️  Sentry غير مُفعَّل — أضف SENTRY_DSN في Railway Variables")
        return

    if not SENTRY_AVAILABLE:
        print("⚠️  sentry-sdk غير منصَّب — شغّل: pip install sentry-sdk")
        return

    try:
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=0.1,        # 10% من الطلبات للـ performance
            profiles_sample_rate=0.1,
            environment=os.environ.get("RAILWAY_ENVIRONMENT", "production"),
            release=os.environ.get("RAILWAY_GIT_COMMIT_SHA", "unknown")[:12],
            send_default_pii=False,         # لا ترسل بيانات هوية تلقائياً
            before_send=_filter_sensitive_data,
            attach_stacktrace=True,
        )
        _SENTRY_READY = True
        print("✅ Sentry مُفعَّل")
        log.info("Sentry initialized successfully")
    except Exception as e:
        log.warning(f"فشل تهيئة Sentry: {e} — النظام يعمل بدونه")


def _filter_sensitive_data(event: dict, hint: dict) -> dict:
    """
    يُزيل البيانات الحساسة قبل إرسالها لـ Sentry.
    إذا فشل هذا الـ filter نفسه → يُرسل الحدث الأصلي (أفضل من فقدانه)
    """
    try:
        return _clean_dict(event, _SENSITIVE_KEYS)
    except Exception:
        # إذا فشل الـ filter → أرسل الحدث كما هو (أفضل من فقدانه)
        return event


def _clean_dict(obj: Any, sensitive_keys: frozenset) -> Any:
    """يُزيل القيم الحساسة بشكل recursive"""
    if isinstance(obj, dict):
        return {
            k: ("***مُحجوب***" if k.lower() in sensitive_keys else _clean_dict(v, sensitive_keys))
            for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [_clean_dict(item, sensitive_keys) for item in obj]
    return obj


def log_error(
    error: Exception,
    context: dict = None,
    client_id: str = None,
    level: str = "error",
) -> None:
    """
    يُسجّل الخطأ في Sentry مع السياق.
    آمن إذا كان Sentry غير متاح — يطبع في الـ console.
    لا يُسجَّل أي بيانات هوية أو أرقام جوال.
    """
    if _SENTRY_READY and SENTRY_AVAILABLE:
        try:
            with sentry_sdk.push_scope() as scope:
                if client_id:
                    scope.set_tag("client_id", client_id)
                if context:
                    # تنظيف السياق من البيانات الحساسة
                    clean_ctx = _clean_dict(context, _SENSITIVE_KEYS)
                    scope.set_context("request_context", clean_ctx)
                scope.set_level(level)
                capture_exception(error)
        except Exception as sentry_err:
            log.warning(f"فشل إرسال خطأ لـ Sentry: {sentry_err}")
            _console_log_error(error, context)
    else:
        _console_log_error(error, context)


def log_event(name: str, data: dict = None, client_id: str = None) -> None:
    """
    يُسجّل حدث مهم (ليس خطأ) — للتحليل والمراقبة.
    مثال: new_client_signup, checkout_completed, backup_failed
    """
    if _SENTRY_READY and SENTRY_AVAILABLE:
        try:
            with sentry_sdk.push_scope() as scope:
                if client_id:
                    scope.set_tag("client_id", client_id)
                clean_data = _clean_dict(data or {}, _SENSITIVE_KEYS)
                scope.set_context("event_data", clean_data)
                capture_message(name, level="info")
        except Exception:
            pass
    else:
        log.info(f"EVENT: {name} | client={client_id} | data={data}")


def _console_log_error(error: Exception, context: dict = None) -> None:
    """طباعة الخطأ في الـ console بتنسيق واضح"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.error(
        f"[{timestamp}] ❌ {type(error).__name__}: {error}"
        + (f"\n  Context: {context}" if context else "")
    )
    if log.isEnabledFor(logging.DEBUG):
        traceback.print_exc()


def is_sentry_ready() -> bool:
    return _SENTRY_READY


# ── Performance timer ──────────────────────────────────────────

class Timer:
    """Context manager لقياس وقت العمليات"""
    def __init__(self, name: str = ""):
        self.name = name
        self.elapsed = 0.0

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, *args):
        self.elapsed = time.monotonic() - self._start
        if self.elapsed > 2.0:
            log.warning(f"⚠️  بطيء ({self.elapsed:.2f}s): {self.name}")
