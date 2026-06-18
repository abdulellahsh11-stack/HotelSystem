#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
خدمة CDN وتخزين المحتوى الثابت مؤقتاً
========================================
توصية #5 — توصيل ملفات الـ static عبر CDN مع ترويسات تخزين مؤقت صحيحة.

الاستراتيجية:
- ملفات .js/.css/.woff2 → تخزين مؤقت لمدة سنة كاملة (immutable)
- ملفات .png/.jpg/.svg  → تخزين مؤقت لمدة أسبوع
- ملفات .html           → تخزين مؤقت لساعة واحدة
- مسارات API           → no-cache إجباري
- CDN_URL مضبوطة        → إعادة توجيه طلبات static إلى الـ CDN
"""
import hashlib
import logging
from pathlib import Path
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette.types import ASGIApp

log = logging.getLogger("dheuof.cdn")

# ── مجموعات امتدادات الملفات حسب استراتيجية التخزين المؤقت ────────────────
_LONG_CACHE_EXTS = {".js", ".css", ".woff", ".woff2", ".ttf", ".otf", ".ico"}
_MEDIUM_CACHE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif"}
_SHORT_CACHE_EXTS = {".html", ".htm"}

# مدد التخزين المؤقت بالثواني
_CACHE_1_YEAR   = 31_536_000   # سنة كاملة للأصول المعدّلة بالإصدار
_CACHE_1_WEEK   = 604_800      # أسبوع للصور
_CACHE_1_HOUR   = 3_600        # ساعة للصفحات
_CACHE_NO_STORE = 0            # لا تخزين لمسارات الـ API


def _file_etag(file_path: str) -> Optional[str]:
    """يُنشئ ETag بناءً على بصمة SHA-256 لمحتوى الملف."""
    try:
        with open(file_path, "rb") as fh:
            content = fh.read()
        return '"' + hashlib.sha256(content).hexdigest()[:32] + '"'
    except OSError:
        return None


def _cache_policy(path: str) -> tuple[str, int]:
    """
    يُحدد سياسة التخزين المؤقت للمسار المُعطى.
    يُعيد (Cache-Control value, max_age_seconds).
    """
    suffix = Path(path).suffix.lower()

    if suffix in _LONG_CACHE_EXTS:
        # أصول مُعرَّفة بالإصدار — immutable لسنة كاملة
        return f"public, max-age={_CACHE_1_YEAR}, immutable", _CACHE_1_YEAR

    if suffix in _MEDIUM_CACHE_EXTS:
        # صور — أسبوع
        return f"public, max-age={_CACHE_1_WEEK}", _CACHE_1_WEEK

    if suffix in _SHORT_CACHE_EXTS:
        # صفحات HTML — ساعة
        return f"public, max-age={_CACHE_1_HOUR}", _CACHE_1_HOUR

    # افتراضي للـ static غير المعروف — ساعة
    return f"public, max-age={_CACHE_1_HOUR}", _CACHE_1_HOUR


class CDNMiddleware(BaseHTTPMiddleware):
    """
    وسيط Starlette يُضيف ترويسات التخزين المؤقت الصحيحة للملفات الثابتة،
    ويُعيد التوجيه إلى CDN_URL عند ضبطه.

    الاستخدام:
        app.add_middleware(CDNMiddleware, cdn_url=os.environ.get("CDN_URL", ""))
    """

    def __init__(self, app: ASGIApp, cdn_url: str = "", static_root: str = "static"):
        super().__init__(app)
        # CDN URL الأساسي — مثال: https://cdn.dheuof.com
        self.cdn_url = cdn_url.rstrip("/")
        # مجلد الملفات الثابتة على القرص (لحساب الـ ETag)
        self.static_root = static_root

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # ── مسارات API — no-cache إجباري ───────────────────────
        if path.startswith("/api/"):
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

        # ── ملفات Static ────────────────────────────────────────
        if path.startswith("/static/"):
            # إعادة توجيه إلى CDN إذا كان CDN_URL مضبوطاً
            if self.cdn_url:
                cdn_target = self.cdn_url + path
                log.debug(f"CDN redirect: {path} → {cdn_target}")
                return RedirectResponse(url=cdn_target, status_code=302)

            # تطبيق ترويسات التخزين المؤقت الصحيحة على الرد المحلي
            response = await call_next(request)

            # تجاهل الردود الخاطئة
            if response.status_code >= 400:
                return response

            cache_control, _ = _cache_policy(path)
            response.headers["Cache-Control"] = cache_control
            response.headers["Vary"] = "Accept-Encoding"
            response.headers["X-Content-Type-Options"] = "nosniff"

            # إضافة ETag إذا أمكن قراءة الملف
            file_rel = path.lstrip("/")  # static/...
            etag = _file_etag(file_rel)
            if etag:
                response.headers["ETag"] = etag

                # دعم If-None-Match (304 Not Modified)
                if_none_match = request.headers.get("if-none-match", "")
                if if_none_match and etag in if_none_match:
                    return Response(status_code=304, headers={"ETag": etag})

            return response

        # ── باقي المسارات — تمرير بدون تعديل ─────────────────
        return await call_next(request)


# ─────────────────────────────────────────────────────────────────────────────
#  دوال مساعدة عامة
# ─────────────────────────────────────────────────────────────────────────────

def get_static_url(path: str, cdn_url: str = "") -> str:
    """
    يُعيد عنوان URL الكامل للملف الثابت.
    إذا كان CDN_URL مضبوطاً يُعيد عنوان الـ CDN، وإلا المسار المحلي.

    مثال:
        get_static_url("/static/app.css", "https://cdn.dheuof.com")
        # → "https://cdn.dheuof.com/static/app.css"
    """
    cdn = cdn_url.rstrip("/")
    if cdn:
        clean_path = "/" + path.lstrip("/")
        return cdn + clean_path
    return path


def setup_cdn_middleware(app: ASGIApp, cdn_url: str = "") -> None:
    """
    يُضيف CDNMiddleware إلى التطبيق.

    يُستدعى من main.py أو lifespan بعد إنشاء التطبيق:
        setup_cdn_middleware(app, cdn_url=cfg.cdn_url)
    """
    app.add_middleware(CDNMiddleware, cdn_url=cdn_url)
    status = f"CDN: {cdn_url}" if cdn_url else "CDN: local (لا يوجد CDN_URL)"
    log.info(f"✓ {status}")
