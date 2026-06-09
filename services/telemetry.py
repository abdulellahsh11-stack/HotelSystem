#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
خدمة OpenTelemetry والمراقبة الشاملة
======================================
توصية #6 — مراقبة الأداء والتتبع الموزّع عبر OpenTelemetry + Prometheus.

المكوّنات:
- TracerProvider مع OTLP exporter (لـ Grafana Tempo / Jaeger / Honeycomb)
- FastAPI / psycopg2 / httpx instrumentation تلقائي
- مقاييس Prometheus مُخصَّصة لضيوف
- نقطة /metrics لمرقب Prometheus
- دالة health_with_telemetry للفحص الشامل
- alert_on_error لإرسال تنبيهات منظّمة
"""
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

log = logging.getLogger("dheuof.telemetry")

# ── اختياري: OpenTelemetry — يتدهور بأمان إذا لم تُثبَّت الحزمة ─────────────
try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False
    log.warning("opentelemetry-sdk غير مُثبَّتة — تتبع الطلبات معطّل")

try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    _OTLP_AVAILABLE = True
except ImportError:
    _OTLP_AVAILABLE = False

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    _FASTAPI_INSTR_AVAILABLE = True
except ImportError:
    _FASTAPI_INSTR_AVAILABLE = False

try:
    from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
    _PSYCOPG2_INSTR_AVAILABLE = True
except ImportError:
    _PSYCOPG2_INSTR_AVAILABLE = False

try:
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    _HTTPX_INSTR_AVAILABLE = True
except ImportError:
    _HTTPX_INSTR_AVAILABLE = False

# ── اختياري: Prometheus ───────────────────────────────────────────────────────
try:
    from prometheus_client import (
        Counter, Gauge, Histogram,
        generate_latest, CONTENT_TYPE_LATEST,
        REGISTRY,
    )
    from fastapi.responses import Response as _Response
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    log.warning("prometheus-client غير مُثبَّتة — /metrics معطّل")


# ─────────────────────────────────────────────────────────────────────────────
#  مقاييس Prometheus المُخصَّصة لمنصة ضيوف
# ─────────────────────────────────────────────────────────────────────────────

_metrics_initialized = False
_http_requests_total: Optional[Any] = None
_active_sessions: Optional[Any] = None
_bookings_total: Optional[Any] = None
_response_time_seconds: Optional[Any] = None


def _init_metrics() -> None:
    """يُهيّئ مقاييس Prometheus — مرة واحدة فقط لتفادي التسجيل المزدوج."""
    global _metrics_initialized, _http_requests_total, _active_sessions
    global _bookings_total, _response_time_seconds

    if _metrics_initialized or not _PROMETHEUS_AVAILABLE:
        return

    try:
        # عدد طلبات HTTP المُنتهية مع التصنيف الكامل
        _http_requests_total = Counter(
            "dheuof_http_requests_total",
            "إجمالي طلبات HTTP المُعالَجة",
            ["method", "path", "status_code"],
        )

        # عدد جلسات العملاء النشطة حالياً
        _active_sessions = Gauge(
            "dheuof_active_sessions",
            "عدد جلسات العملاء النشطة",
        )

        # عدد الحجوزات المُسجَّلة مع التصنيف
        _bookings_total = Counter(
            "dheuof_bookings_total",
            "إجمالي الحجوزات المُسجَّلة في النظام",
            ["client_id", "status"],
        )

        # توزيع أوقات الاستجابة (histogram)
        _response_time_seconds = Histogram(
            "dheuof_response_time_seconds",
            "توزيع أوقات استجابة واجهة برمجة التطبيقات",
            ["method", "path"],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )

        _metrics_initialized = True
        log.info("✓ مقاييس Prometheus مُهيَّأة")

    except Exception as exc:
        # التسجيل المزدوج شائع في بيئات الاختبار — نتجاهله بأمان
        log.debug(f"تحذير تهيئة المقاييس: {exc}")
        _metrics_initialized = True


# ─────────────────────────────────────────────────────────────────────────────
#  دوال تحديث المقاييس — يستدعيها كود الأعمال
# ─────────────────────────────────────────────────────────────────────────────

def record_http_request(method: str, path: str, status_code: int, duration: float) -> None:
    """يُسجّل طلب HTTP منتهياً في مقاييس Prometheus."""
    if not _PROMETHEUS_AVAILABLE or not _metrics_initialized:
        return
    try:
        # تجميع المسارات الديناميكية لتقليل عدد التسميات
        clean_path = _normalize_path(path)
        if _http_requests_total:
            _http_requests_total.labels(
                method=method, path=clean_path, status_code=str(status_code)
            ).inc()
        if _response_time_seconds:
            _response_time_seconds.labels(method=method, path=clean_path).observe(duration)
    except Exception:
        pass


def set_active_sessions(count: int) -> None:
    """يُحدِّث مقياس الجلسات النشطة."""
    if _active_sessions and _PROMETHEUS_AVAILABLE:
        try:
            _active_sessions.set(count)
        except Exception:
            pass


def record_booking(client_id: str, status: str) -> None:
    """يُسجّل حجزاً جديداً في مقياس الحجوزات."""
    if _bookings_total and _PROMETHEUS_AVAILABLE:
        try:
            _bookings_total.labels(client_id=client_id, status=status).inc()
        except Exception:
            pass


def _normalize_path(path: str) -> str:
    """
    يُجمِّع المسارات الديناميكية لتقليل عدد تسميات Prometheus.
    مثال: /api/clients/hotel-001/bookings → /api/clients/{id}/bookings
    """
    import re
    # UUID ومعرّفات الأرقام وكودات المنشآت
    path = re.sub(r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "/{uuid}", path)
    path = re.sub(r"/\d{4,}", "/{id}", path)
    # معرّفات المنشآت (نمط: hotel-xxx أو أي نص مع شرطة)
    path = re.sub(r"/[a-z][a-z0-9\-]{3,}(?=/|$)", "/{id}", path)
    return path


# ─────────────────────────────────────────────────────────────────────────────
#  إعداد OpenTelemetry Tracing
# ─────────────────────────────────────────────────────────────────────────────

def setup_telemetry(app, config=None) -> None:
    """
    يُهيّئ OpenTelemetry TracerProvider وينسجم مع FastAPI/psycopg2/httpx تلقائياً.

    المتغيّرات البيئية المدعومة:
        OTEL_EXPORTER_OTLP_ENDPOINT  — نقطة OTLP (مثال: http://tempo:4317)
        OTEL_SERVICE_VERSION         — نسخة الخدمة (افتراضي: 3.0.0)
    """
    if not _OTEL_AVAILABLE:
        log.warning("تخطّي إعداد OTEL — opentelemetry-sdk غير مُثبَّتة")
        return

    service_version = os.environ.get("OTEL_SERVICE_VERSION", "3.0.0")
    environment = "development"
    debug_mode = False
    if config is not None:
        environment = "production" if not getattr(config, "debug", True) else "development"
        debug_mode = getattr(config, "debug", False)

    # مورد الخدمة — يُعرِّف الـ service في منصة التتبع
    resource = Resource(attributes={
        SERVICE_NAME: "dheuof",
        SERVICE_VERSION: service_version,
        "service.namespace": "hotelsystem",
        "deployment.environment": environment,
    })

    provider = TracerProvider(resource=resource)

    # OTLP exporter — يُفعَّل إذا ضُبط OTEL_EXPORTER_OTLP_ENDPOINT
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if otlp_endpoint and _OTLP_AVAILABLE:
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            log.info(f"✓ OTLP exporter → {otlp_endpoint}")
        except Exception as exc:
            log.warning(f"تعذّر إعداد OTLP exporter: {exc}")

    # Console exporter في وضع التطوير
    if debug_mode:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        log.info("✓ Console span exporter مُفعَّل (وضع التطوير)")

    trace.set_tracer_provider(provider)
    log.info("✓ OpenTelemetry TracerProvider مُهيَّأ")

    # تفعيل الـ instrumentations
    if _FASTAPI_INSTR_AVAILABLE and app is not None:
        try:
            FastAPIInstrumentor().instrument_app(app)
            log.info("✓ FastAPI instrumentation مُفعَّل")
        except Exception as exc:
            log.warning(f"FastAPI instrumentation: {exc}")

    if _PSYCOPG2_INSTR_AVAILABLE:
        try:
            Psycopg2Instrumentor().instrument()
            log.info("✓ psycopg2 instrumentation مُفعَّل")
        except Exception as exc:
            log.warning(f"psycopg2 instrumentation: {exc}")

    if _HTTPX_INSTR_AVAILABLE:
        try:
            HTTPXClientInstrumentor().instrument()
            log.info("✓ httpx instrumentation مُفعَّل")
        except Exception as exc:
            log.warning(f"httpx instrumentation: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
#  إعداد نقطة /metrics لـ Prometheus
# ─────────────────────────────────────────────────────────────────────────────

def setup_metrics(app) -> None:
    """
    يُهيّئ مقاييس Prometheus ويُضيف نقطة /metrics للتطبيق.

    يُستدعى من lifespan أو app startup:
        setup_metrics(app)
    """
    _init_metrics()

    if not _PROMETHEUS_AVAILABLE:
        log.warning("prometheus-client غير مُثبَّتة — تخطّي إعداد /metrics")
        return

    # نقطة /metrics — تُعيد مقاييس Prometheus بتنسيق النص القياسي
    @app.get("/metrics", include_in_schema=False, tags=["monitoring"])
    async def metrics_endpoint():
        """نقطة مقاييس Prometheus — يُراقبها prometheus scraper كل 15 ثانية."""
        output = generate_latest(REGISTRY)
        return _Response(
            content=output,
            media_type=CONTENT_TYPE_LATEST,
        )

    log.info("✓ نقطة /metrics جاهزة لـ Prometheus scraper")


# ─────────────────────────────────────────────────────────────────────────────
#  فحص الصحة الشامل مع تتبع OTel
# ─────────────────────────────────────────────────────────────────────────────

def health_with_telemetry(db=None, redis_session=None) -> dict:
    """
    يُعيد تقرير صحة شاملاً مع معلومات OTel.

    المعاملات:
        db            — كائن قاعدة البيانات (الـ connection أو DataStore)
        redis_session — عميل Redis (اختياري)

    المُعاد: dict يصلح كردّ لـ /api/health
    """
    started_at = time.monotonic()
    result: dict[str, Any] = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "dheuof",
        "checks": {},
    }

    # ── فحص قاعدة البيانات ──────────────────────────────────────
    db_ok = None   # None = لم يُفحص (db غير مُمرَّر)
    db_latency_ms = -1
    if db is not None:
        t0 = time.monotonic()
        try:
            # دعم كلا النوعين: DataStore أو connection مباشر
            if hasattr(db, "db"):
                conn = db.db
            else:
                conn = db
            if hasattr(conn, "use_postgres") and conn.use_postgres:
                conn.execute("SELECT 1", fetch="one")
            # JSON store أو PostgreSQL ناجح — صحي
            db_ok = True
        except Exception as exc:
            log.warning(f"فحص قاعدة البيانات فشل: {exc}")
            db_ok = False
        db_latency_ms = round((time.monotonic() - t0) * 1000, 2)

    result["checks"]["database"] = {
        "healthy": db_ok,
        "latency_ms": db_latency_ms,
    }

    # ── فحص Redis ───────────────────────────────────────────────
    redis_ok = False
    redis_latency_ms = -1
    if redis_session is not None:
        t0 = time.monotonic()
        try:
            redis_session.ping()
            redis_ok = True
        except Exception as exc:
            log.warning(f"فحص Redis فشل: {exc}")
        redis_latency_ms = round((time.monotonic() - t0) * 1000, 2)
    else:
        redis_ok = None  # غير مُضبوط — ليس خطأ

    result["checks"]["redis"] = {
        "healthy": redis_ok,
        "latency_ms": redis_latency_ms,
    }

    # ── معلومات OTel ─────────────────────────────────────────────
    trace_id = None
    span_id = None
    if _OTEL_AVAILABLE:
        try:
            current_span = trace.get_current_span()
            ctx = current_span.get_span_context()
            if ctx.is_valid:
                trace_id = format(ctx.trace_id, "032x")
                span_id = format(ctx.span_id, "016x")
        except Exception:
            pass

    result["telemetry"] = {
        "otel_available": _OTEL_AVAILABLE,
        "prometheus_available": _PROMETHEUS_AVAILABLE,
        "trace_id": trace_id,
        "span_id": span_id,
    }

    # الحالة الإجمالية — تُصبح degraded إذا فشل DB (None = لم يُفحص → لا تغيير)
    if db_ok is False:
        result["status"] = "degraded"

    result["total_latency_ms"] = round((time.monotonic() - started_at) * 1000, 2)
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  إرسال تنبيهات عند الأخطاء الحرجة
# ─────────────────────────────────────────────────────────────────────────────

def alert_on_error(error: Exception, context: dict = None) -> None:
    """
    يُسجّل خطأً حرجاً بتنسيق JSON منظَّم يصلح للتقاطه من قبل أدوات التنبيه
    الخارجية (Sentry / Grafana Alerting / PagerDuty عبر log aggregation).

    يُضيف trace_id الحالي إذا كان OTel مُفعَّلاً.
    """
    trace_id = None
    span_id = None
    if _OTEL_AVAILABLE:
        try:
            current_span = trace.get_current_span()
            ctx = current_span.get_span_context()
            if ctx.is_valid:
                trace_id = format(ctx.trace_id, "032x")
                span_id = format(ctx.span_id, "016x")
        except Exception:
            pass

    alert_payload = {
        "level": "error",
        "event": "dheuof.error.alert",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error_type": type(error).__name__,
        "error_message": str(error),
        "trace_id": trace_id,
        "span_id": span_id,
        "context": context or {},
        "service": "dheuof",
    }

    # يُطبع إلى stderr بتنسيق JSON — يُلتقط من قبل log aggregators
    log.error(json.dumps(alert_payload, ensure_ascii=False))


def get_tracer(name: str = "dheuof"):
    """
    يُعيد OpenTelemetry tracer لاستخدامه في الكود الداخلي.

    مثال:
        tracer = get_tracer()
        with tracer.start_as_current_span("process_booking"):
            ...
    """
    if not _OTEL_AVAILABLE:
        return _NoopTracer()
    return trace.get_tracer(name)


class _NoopTracer:
    """بديل صامت عند غياب OpenTelemetry — يتجنّب الانهيار."""

    def start_as_current_span(self, name: str, **kwargs):
        from contextlib import contextmanager

        @contextmanager
        def _noop():
            yield None

        return _noop()
