#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils/middleware.py — Request Middleware
يُطبَّق على كل endpoint: timing + Sentry logging + request ID + error response
"""
import time
import secrets
import logging
import functools
from typing import Callable

from utils.monitoring import log_error, log_event

log = logging.getLogger("dheuof.middleware")


def request_middleware(handler_func: Callable) -> Callable:
    """
    Decorator يُطبَّق على كل handler function:
    - يُضيف request_id للتتبع
    - يقيس وقت الاستجابة
    - يُسجّل الأخطاء في Sentry تلقائياً
    - يُعيد error response منسَّق دائماً (لا stack trace للمستخدم)

    الاستخدام:
        @request_middleware
        def my_handler(request: dict) -> dict:
            ...
    """
    @functools.wraps(handler_func)
    def wrapper(request: dict, *args, **kwargs) -> dict:
        start_time = time.monotonic()
        request_id = secrets.token_hex(8)
        request["_request_id"] = request_id

        try:
            response = handler_func(request, *args, **kwargs)

            elapsed = time.monotonic() - start_time

            # تسجيل طلبات بطيئة (> 2 ثانية)
            if elapsed > 2.0:
                log_event("slow_request", {
                    "endpoint": request.get("path", ""),
                    "method": request.get("method", ""),
                    "elapsed_sec": round(elapsed, 2),
                    "request_id": request_id,
                }, client_id=request.get("client_id"))
                log.warning(
                    f"⚠️  طلب بطيء ({elapsed:.2f}s): "
                    f"{request.get('method')} {request.get('path')} "
                    f"[{request_id}]"
                )

            return response

        except Exception as e:
            elapsed = time.monotonic() - start_time
            log_error(e, context={
                "path": request.get("path", ""),
                "method": request.get("method", ""),
                "elapsed_sec": round(elapsed, 2),
                "request_id": request_id,
                # client_id آمن للإرسال (ليس بيانات شخصية)
            }, client_id=request.get("client_id"))

            log.error(
                f"❌ خطأ في {request.get('method')} {request.get('path')}: "
                f"{type(e).__name__}: {e} [{request_id}]"
            )

            return {
                "ok": False,
                "error": "حدث خطأ في الخادم — تم تسجيله للمراجعة",
                "request_id": request_id,
            }

    return wrapper


def require_client(handler_func: Callable) -> Callable:
    """
    Decorator يتحقق من أن الطلب يحتوي على client_id صحيح.
    يُستخدم مع request_middleware.
    """
    @functools.wraps(handler_func)
    def wrapper(request: dict, *args, **kwargs) -> dict:
        client_id = request.get("client_id", "")
        if not client_id:
            return {"ok": False, "error": "client_id مطلوب", "status": 401}
        return handler_func(request, *args, **kwargs)
    return wrapper


def validate_body(required_fields: list) -> Callable:
    """
    Decorator factory يتحقق من وجود الحقول المطلوبة في body الطلب.

    الاستخدام:
        @validate_body(["guest_id", "payment_method"])
        def checkout(request): ...
    """
    def decorator(handler_func: Callable) -> Callable:
        @functools.wraps(handler_func)
        def wrapper(request: dict, *args, **kwargs) -> dict:
            body = request.get("body", {})
            missing = [f for f in required_fields if f not in body or body[f] == ""]
            if missing:
                return {
                    "ok": False,
                    "error": f"الحقول التالية مطلوبة: {', '.join(missing)}",
                }
            return handler_func(request, *args, **kwargs)
        return wrapper
    return decorator
