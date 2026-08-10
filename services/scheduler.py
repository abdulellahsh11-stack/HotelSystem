#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/scheduler.py — CronManager
يُدير كل الـ background threads في مكان واحد.
يُعيد تشغيل أي thread يموت تلقائياً.
"""
import threading
import logging
from typing import Callable, Dict, List, Optional

from utils.monitoring import log_error

log = logging.getLogger("dheuof.scheduler")


class _ManagedThread:
    """Thread مُدار مع إعادة تشغيل تلقائية عند الفشل"""

    def __init__(self, name: str, target: Callable, interval_sec: int = 0):
        self.name = name
        self.target = target
        self.interval_sec = interval_sec  # 0 = يعمل مرة واحدة فقط (loop داخلي)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

    def start(self) -> None:
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._run_with_restart,
            name=self.name,
            daemon=True,
        )
        self._thread.start()
        log.info(f"  ✓ Thread بدأ: {self.name}")

    def _run_with_restart(self) -> None:
        """يُشغّل الـ target مع إعادة تشغيل تلقائية عند الفشل"""
        while self._running and not self._stop_event.is_set():
            try:
                if self.interval_sec > 0:
                    # loop خارجي بفترة زمنية
                    while self._running and not self._stop_event.is_set():
                        self.target()
                        self._stop_event.wait(self.interval_sec)
                else:
                    # الـ loop داخل الـ target نفسه
                    self.target()
            except Exception as e:
                log_error(e, context={"thread": self.name})
                log.error(f"❌ Thread فشل: {self.name} — إعادة تشغيل بعد 30 ثانية")
                # انتظر قبل إعادة التشغيل لتجنب crash loop
                self._stop_event.wait(30)

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


class CronManager:
    """
    مُدير الـ background jobs — Singleton.
    كل jobs مُسجَّلة هنا تعمل كـ daemon threads.
    يُعيد تشغيل أي thread يموت تلقائياً.
    """

    _instance: Optional["CronManager"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._threads: Dict[str, _ManagedThread] = {}
        self._services: dict = {}

    def register(self, name: str, target: Callable, interval_sec: int = 0) -> None:
        """تسجيل job جديد (قبل start_all)"""
        self._threads[name] = _ManagedThread(name, target, interval_sec)

    def start_all(self, services: dict = None) -> None:
        """
        يُشغّل كل الـ threads المُسجَّلة.
        services: dict من instances لتمريرها للـ jobs
        """
        if services:
            self._services = services

        log.info("🚀 CronManager — بدء تشغيل كل الـ background jobs...")

        # تسجيل الـ jobs من الـ services إذا لم تُسجَّل مسبقاً
        self._register_service_jobs()

        for name, thread in self._threads.items():
            if not thread.is_alive:
                thread.start()

        log.info(f"✅ CronManager — {len(self._threads)} jobs تعمل")

    def _register_service_jobs(self) -> None:
        """يُسجّل jobs من الـ services تلقائياً"""
        services = self._services

        # WhatsApp Lifecycle — كل 5 دقائق
        if "whatsapp" in services and "whatsapp_lifecycle" not in self._threads:
            wa = services["whatsapp"]
            if hasattr(wa, "run_lifecycle"):
                self.register("whatsapp_lifecycle", wa.run_lifecycle, interval_sec=300)

        # Review Scheduler — كل 30 دقيقة
        if "reviews" in services and "review_scheduler" not in self._threads:
            rv = services["reviews"]
            if hasattr(rv, "run"):
                self.register("review_scheduler", rv.run)

        # iCal Sync — كل ساعة
        if "ical" in services and "ical_sync" not in self._threads:
            ic = services["ical"]
            if hasattr(ic, "run"):
                self.register("ical_sync", ic.run)

        # Backup Monitor — كل 6 ساعات
        if "backup_monitor" in services and "backup_monitor" not in self._threads:
            bm = services["backup_monitor"]
            if hasattr(bm, "run"):
                self.register("backup_monitor", bm.run)

        # Chatbot Pre-arrival — كل ساعة
        if "pre_arrival" in services and "pre_arrival_check" not in self._threads:
            pa = services["pre_arrival"]
            if hasattr(pa, "run_checks"):
                self.register("pre_arrival_check", pa.run_checks, interval_sec=3600)

    def stop_all(self) -> None:
        """إيقاف كل الـ threads بأمان"""
        log.info("🛑 CronManager — إيقاف كل الـ threads...")
        for thread in self._threads.values():
            thread.stop()
        log.info("✅ CronManager — تم الإيقاف")

    @classmethod
    def active_count(cls) -> int:
        """عدد الـ threads النشطة حالياً"""
        instance = cls._instance
        if not instance:
            return 0
        return sum(1 for t in instance._threads.values() if t.is_alive)

    def status(self) -> List[dict]:
        """حالة كل thread للـ health endpoint"""
        return [
            {
                "name": name,
                "alive": thread.is_alive,
                "interval_sec": thread.interval_sec,
            }
            for name, thread in self._threads.items()
        ]
