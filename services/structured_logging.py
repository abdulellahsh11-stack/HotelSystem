#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
السجلات المنظَّمة (Structured JSON Logging)
============================================
توصية #6 — تسجيل منظَّم بتنسيق JSON لتسهيل التحليل والتنبيه.

المكوّنات:
- setup_logging     — يُهيّئ Python logging بمُنسِّق JSON
- log_request       — يُسجّل كل طلب HTTP مع المدة والحالة
- log_error         — يُسجّل الأخطاء مع السياق الكامل والـ trace_id
- JsonFormatter     — مُنسِّق مخصَّص يُحوِّل سجلات Python إلى JSON
"""
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Optional


# ─────────────────────────────────────────────────────────────────────────────
#  مُنسِّق JSON المخصَّص
# ─────────────────────────────────────────────────────────────────────────────

class JsonFormatter(logging.Formatter):
    """
    يُحوِّل سجلات Python القياسية إلى JSON منظَّم.

    الحقول الثابتة في كل سجل:
        timestamp  — ISO 8601 بتوقيت UTC
        level      — DEBUG/INFO/WARNING/ERROR/CRITICAL
        service    — اسم الخدمة
        logger     — اسم الـ logger (dheuof.xxx)
        message    — نص الرسالة
    """

    def __init__(self, service_name: str = "dheuof", include_exc_info: bool = True):
        super().__init__()
        self.service_name = service_name
        self.include_exc_info = include_exc_info

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # حقول اختيارية — تُضاف عند وجودها
        if record.exc_info and self.include_exc_info:
            payload["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # الحقول المُضافة يدوياً عبر extra={}
        _extra_fields = (
            "trace_id", "span_id", "request_id", "client_id",
            "path", "method", "status_code", "duration_ms",
            "error_type", "context",
        )
        for field in _extra_fields:
            val = getattr(record, field, None)
            if val is not None:
                payload[field] = val

        try:
            return json.dumps(payload, ensure_ascii=False, default=str)
        except Exception:
            # بديل آمن في حالة خطأ التحويل
            return json.dumps({
                "timestamp": payload.get("timestamp", ""),
                "level": payload.get("level", "ERROR"),
                "service": self.service_name,
                "message": str(record.getMessage()),
                "serialization_error": True,
            })


# ─────────────────────────────────────────────────────────────────────────────
#  إعداد نظام التسجيل
# ─────────────────────────────────────────────────────────────────────────────

def setup_logging(
    service_name: str = "dheuof",
    log_level: str = "INFO",
    json_output: bool = True,
) -> logging.Logger:
    """
    يُهيّئ نظام التسجيل للتطبيق بأكمله.

    المعاملات:
        service_name — اسم الخدمة يظهر في كل سجل
        log_level    — مستوى التسجيل (DEBUG/INFO/WARNING/ERROR)
        json_output  — True = JSON منظَّم، False = نص عادي (للتطوير)

    يُعيد: الـ root logger الجاهز للاستخدام

    مثال:
        logger = setup_logging("dheuof", log_level="DEBUG", json_output=False)
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # تنظيف المعالجات القديمة
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # إنشاء المعالج
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)

    if json_output and not _is_development():
        # إنتاج — JSON منظَّم
        handler.setFormatter(JsonFormatter(service_name=service_name))
    else:
        # تطوير — نص مقروء
        fmt = "%(asctime)s %(levelname)-8s %(name)s — %(message)s"
        handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))

    root_logger.setLevel(numeric_level)
    root_logger.addHandler(handler)

    # تهدئة المكتبات الصاخبة
    for noisy in ("uvicorn.access", "httpcore", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    service_log = logging.getLogger(service_name)
    service_log.info(
        f"تهيئة نظام التسجيل: service={service_name} level={log_level} "
        f"json={json_output and not _is_development()}"
    )
    return service_log


def _is_development() -> bool:
    """يُعيد True في بيئة التطوير (DEBUG=true أو RAILWAY_ENVIRONMENT غير مضبوط)."""
    if os.environ.get("DEBUG", "").lower() == "true":
        return True
    if not os.environ.get("RAILWAY_ENVIRONMENT"):
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
#  تسجيل الطلبات
# ─────────────────────────────────────────────────────────────────────────────

_access_log = logging.getLogger("dheuof.access")


def log_request(
    request,
    response=None,
    duration: float = 0.0,
    trace_id: Optional[str] = None,
) -> None:
    """
    يُسجّل طلب HTTP منتهياً مع جميع تفاصيله.

    المعاملات:
        request   — FastAPI Request أو dict يحتوي method/path/client
        response  — FastAPI Response أو dict يحتوي status_code
        duration  — مدة المعالجة بالثواني
        trace_id  — معرّف التتبع من OTel (اختياري)
    """
    # استخراج بيانات الطلب
    if hasattr(request, "method"):
        method = request.method
        path = request.url.path if hasattr(request.url, "path") else str(request.url)
        client_ip = ""
        if hasattr(request, "client") and request.client:
            client_ip = request.client.host or ""
        query = str(request.url.query) if hasattr(request.url, "query") else ""
    elif isinstance(request, dict):
        method = request.get("method", "GET")
        path = request.get("path", "/")
        client_ip = request.get("client_ip", "")
        query = request.get("query", "")
    else:
        method, path, client_ip, query = "GET", "/", "", ""

    # استخراج رمز الحالة
    status_code = 200
    if response is not None:
        if hasattr(response, "status_code"):
            status_code = response.status_code
        elif isinstance(response, dict):
            status_code = response.get("status_code", 200)

    duration_ms = round(duration * 1000, 2)

    # مستوى التسجيل حسب رمز الحالة
    level = logging.INFO
    if status_code >= 500:
        level = logging.ERROR
    elif status_code >= 400:
        level = logging.WARNING

    extra = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "client_ip": client_ip,
    }
    if trace_id:
        extra["trace_id"] = trace_id
    if query:
        extra["query"] = query

    _access_log.log(level, f"{method} {path} {status_code} {duration_ms}ms", extra=extra)


# ─────────────────────────────────────────────────────────────────────────────
#  تسجيل الأخطاء
# ─────────────────────────────────────────────────────────────────────────────

_error_log = logging.getLogger("dheuof.errors")


def log_error(
    error: Exception,
    context: Optional[dict] = None,
    trace_id: Optional[str] = None,
    level: int = logging.ERROR,
) -> None:
    """
    يُسجّل خطأً مع السياق الكامل والـ trace_id.

    المعاملات:
        error    — الاستثناء المُلتقط
        context  — قاموس بسياق إضافي (client_id، path، ...إلخ)
        trace_id — معرّف التتبع من OTel
        level    — مستوى التسجيل (افتراضي: ERROR)
    """
    extra: dict[str, Any] = {
        "error_type": type(error).__name__,
    }
    if trace_id:
        extra["trace_id"] = trace_id
    if context:
        extra["context"] = context

    _error_log.log(
        level,
        f"{type(error).__name__}: {error}",
        exc_info=error,
        extra=extra,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  وسيط تسجيل الطلبات (Middleware) — للتوثيق المرجعي
# ─────────────────────────────────────────────────────────────────────────────

class RequestLoggingMiddleware:
    """
    وسيط ASGI بسيط يُسجّل جميع الطلبات تلقائياً.

    الاستخدام في main.py:
        from starlette.middleware.base import BaseHTTPMiddleware
        # يُضاف بعد CDNMiddleware
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()

        # التقاط رمز الحالة من الرد
        status_code_holder = [200]
        original_send = send

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code_holder[0] = message.get("status", 200)
            await original_send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.monotonic() - start
            # إعادة بناء request-like dict من scope
            req = {
                "method": scope.get("method", "GET"),
                "path": scope.get("path", "/"),
                "query": scope.get("query_string", b"").decode("utf-8", errors="replace"),
                "client_ip": (scope.get("client") or ("", 0))[0],
            }
            log_request(
                req,
                {"status_code": status_code_holder[0]},
                duration=duration,
            )
