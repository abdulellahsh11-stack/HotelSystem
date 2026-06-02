#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/connection.py — Connection Pool لـ PostgreSQL مع JSON Fallback
Singleton — pool واحد للتطبيق كله
"""
import os
import json
import threading
import logging
from contextlib import contextmanager
from typing import Any, Optional

log = logging.getLogger("dheuof.db")

try:
    import psycopg2
    from psycopg2 import pool as pg_pool
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except (ImportError, Exception) as e:
    POSTGRES_AVAILABLE = False
    print(f"⚠️ psycopg2 error: {type(e).__name__}: {e}")

class DatabasePool:
    """
    Connection Pool لـ PostgreSQL مع fallback لـ JSON.

    الأوضاع:
    - PostgreSQL: عند توفر DATABASE_URL وpsycopg2
    - JSON Fallback: للتطوير المحلي بدون PostgreSQL
    """

    _instance: Optional["DatabasePool"] = None
    _init_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton — pool واحد للتطبيق كله"""
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        database_url: str = "",
        min_conn: int = 2,
        max_conn: int = int(os.environ.get("MAX_PG_CONN", "20")),
        json_path: str = "admin_store.json",
    ):
        # تجنب إعادة التهيئة (Singleton)
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self.database_url = database_url
        self.use_postgres = POSTGRES_AVAILABLE and bool(database_url)
        self._pool = None
        self._json_path = json_path
        self._json_lock = threading.Lock()

        if self.use_postgres:
            try:
                self._pool = pg_pool.ThreadedConnectionPool(
                    min_conn,
                    max_conn,
                    database_url,
                    options="-c timezone=Asia/Riyadh",  # توقيت السعودية
                )
                log.info(f"✅ PostgreSQL Pool جاهز — {min_conn}..{max_conn} اتصال")
            except Exception as e:
                log.error(f"❌ فشل اتصال PostgreSQL: {e} — يعود لـ JSON Fallback")
                self.use_postgres = False
                self._pool = None
        else:
            log.warning(
                "⚠️  JSON Fallback — أضف DATABASE_URL في Railway Variables لتفعيل PostgreSQL"
            )

    # ── PostgreSQL helpers ────────────────────────────────────

    @contextmanager
    def _get_conn(self):
        """Context manager لإدارة الاتصال تلقائياً"""
        if not self._pool:
            raise RuntimeError("PostgreSQL Pool غير مهيّأ")
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def execute(
        self,
        query: str,
        params: tuple = (),
        fetch: str = None,
    ) -> Any:
        """
        تنفيذ query مع:
        - Automatic connection management
        - Retry مرة واحدة عند انقطاع الاتصال
        - Error logging

        fetch: None | 'one' | 'all'
        """
        if not self.use_postgres:
            raise RuntimeError("PostgreSQL غير متاح — استخدم DataStore بدلاً من execute مباشرة")

        def _run():
            with self._get_conn() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, params)
                    if fetch == "one":
                        return cur.fetchone()
                    elif fetch == "all":
                        return cur.fetchall()
                    else:
                        return cur.rowcount

        try:
            return _run()
        except psycopg2.OperationalError as e:
            # Retry مرة واحدة عند انقطاع الاتصال
            log.warning(f"إعادة محاولة الاتصال بـ PostgreSQL: {e}")
            try:
                return _run()
            except Exception as retry_e:
                log.error(f"فشل الـ retry: {retry_e}")
                raise
        except Exception as e:
            log.error(f"خطأ في query: {e}\nSQL: {query[:200]}")
            raise

    def execute_many(self, query: str, params_list: list) -> int:
        """تنفيذ batch insert/update بكفاءة"""
        if not self.use_postgres or not params_list:
            return 0
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.executemany(query, params_list)
                return cur.rowcount

    # ── JSON Fallback helpers ─────────────────────────────────

    def json_read(self) -> dict:
        """قراءة admin_store.json بأمان"""
        with self._json_lock:
            if not os.path.exists(self._json_path):
                return {}
            try:
                with open(self._json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                log.error(f"خطأ في قراءة {self._json_path}: {e}")
                return {}

    def json_write(self, data: dict) -> bool:
        """كتابة admin_store.json بأمان (atomic write)"""
        with self._json_lock:
            tmp = self._json_path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp, self._json_path)
                return True
            except Exception as e:
                log.error(f"خطأ في كتابة {self._json_path}: {e}")
                return False

    # ── Migration ─────────────────────────────────────────────

    def run_migrations(self) -> None:
        """تطبيق الـ schema إذا لم يكن موجوداً — آمن للتشغيل أكثر من مرة"""
        if not self.use_postgres:
            log.info("JSON Fallback — لا migration مطلوب")
            return

        from db.migrations import run_all_migrations
        run_all_migrations(self)

    # ── Health ────────────────────────────────────────────────

    def health(self) -> dict:
        """يُعيد حالة قاعدة البيانات للـ health endpoint"""
        if self.use_postgres:
            try:
                self.execute("SELECT 1")
                return {"status": "ok", "type": "postgresql"}
            except Exception as e:
                return {"status": "error", "type": "postgresql", "message": str(e)}
        else:
            return {"status": "ok", "type": "json_fallback"}

    def close(self) -> None:
        """إغلاق كل الاتصالات عند إيقاف التشغيل"""
        if self._pool:
            self._pool.closeall()
            log.info("PostgreSQL Pool مُغلق")


# ── Singleton accessor ────────────────────────────────────────
_db: Optional[DatabasePool] = None


def init_db(database_url: str = "", json_path: str = "admin_store.json") -> DatabasePool:
    """يُهيّئ الـ pool مرة واحدة من main.py"""
    global _db
    _db = DatabasePool(database_url=database_url, json_path=json_path)
    return _db


def get_db() -> DatabasePool:
    """يُعيد الـ pool الوحيد — يُستدعى من كل مكان"""
    global _db
    if _db is None:
        raise RuntimeError("Database لم يُهيَّأ — استدعِ init_db() في main() أولاً")
    return _db
