#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/health.py — Health Check Endpoint
GET /api/health — يُعيد حالة كل الـ services للـ Railway و uptime monitors
"""
import time
import logging
from datetime import datetime

from utils.date_utils import SA_TZ
from utils.monitoring import is_sentry_ready

log = logging.getLogger("dheuof.routes.health")

_START_TIME = time.time()


class HealthRoutes:
    """يُسجّل /api/health في الـ router"""

    def __init__(self, db=None, cron_manager=None, whatsapp_service=None, config=None):
        self.db = db
        self.cron = cron_manager
        self.whatsapp = whatsapp_service
        self.config = config

    def register(self, router: dict) -> None:
        router[("GET", "/api/health")] = self.health_check
        router[("GET", "/health")] = self.health_check        # Railway default

    def health_check(self, request: dict) -> dict:
        """
        GET /api/health
        يُعيد حالة النظام الكاملة.
        لا يُفشل عند تعطّل أي service — يُظهر 'degraded' بدلاً من crash.
        """
        checks = {}
        overall = "healthy"
        import os

        # 1. قاعدة البيانات
        if self.db:
            db_health = self.db.health()
            checks["database"] = db_health
            if db_health.get("status") == "error":
                overall = "degraded"
        else:
            checks["database"] = {"status": "not_initialized"}
            overall = "degraded"

        # 2. Sentry
        checks["sentry"] = {
            "status": "ok" if is_sentry_ready() else "disabled"
        }

        # 3. واتساب
        if self.whatsapp and hasattr(self.whatsapp, "is_configured"):
            checks["whatsapp"] = {
                "status": "configured" if self.whatsapp.is_configured() else "not_configured"
            }
        else:
            checks["whatsapp"] = {"status": "not_loaded"}

        # 4. Scheduler threads
        if self.cron:
            from services.scheduler import CronManager
            checks["schedulers"] = {
                "status": "ok",
                "active_count": CronManager.active_count(),
                "threads": self.cron.status(),
            }
        else:
            checks["schedulers"] = {"status": "not_started", "active_count": 0}

        # 5. موارد النظام (بدون psutil — standard library فقط)
        uptime_s = int(time.time() - _START_TIME)
        checks["system"] = {
            "uptime_seconds": uptime_s,
            "uptime_human": (
                f"{uptime_s // 86400}d "
                f"{(uptime_s % 86400) // 3600}h "
                f"{(uptime_s % 3600) // 60}m"
            ),
        }

        # 6. إعدادات الـ config
        if self.config:
            checks["config"] = {
                "postgres": self.config.has_postgres,
                "github": self.config.has_github,
                "sentry": self.config.has_sentry,
                "dual_write": self.config.dual_write,
            }

        return {
            "ok": True,
            "status": overall,
            "timestamp": datetime.now(SA_TZ).isoformat(),
            "version": os.environ.get("RAILWAY_GIT_COMMIT_SHA", "dev")[:8],
            "checks": checks,
        }
