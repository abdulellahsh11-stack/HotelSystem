#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/connection.py — Connection Pool لـ PostgreSQL مع JSON Fallback
Singleton — pool واحد للتطبيق كله
"""
import asyncio
import os
import json
import threading
import logging
from contextlib import contextmanager
from typing import Any, Optional

from db.tenant_context import (
    BRANCH_GUC_NAME, GUC_NAME, get_current_branches, get_current_tenant,
)

log = logging.getLogger("dheuof.db")

# الدور المُقيَّد الذي تُنفَّذ به استعلامات المستأجرين — يجب أن يطابق
# APP_ROLE في db/schema_v3.py
APP_ROLE = "dheuof_app"

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
        # التحوّل إلى الدور المُقيَّد يُفعَّل بـ RLS_ENFORCE=1 فقط. الإبقاء
        # عليه مطفأً افتراضياً يجعل السلوك مطابقاً تماماً لما قبل إضافة
        # العزل، فلا ينكسر مسار قائم عند الترقية. يُطفأ أيضاً عند أول
        # فشل في SET ROLE كي لا يتكرّر التحذير في كل طلب.
        self._app_role_available = os.environ.get(
            "RLS_ENFORCE", ""
        ).strip().lower() in ("1", "true", "yes")

        if self.use_postgres:
            try:
                self._pool = pg_pool.ThreadedConnectionPool(
                    min_conn,
                    max_conn,
                    database_url,
                    options="-c timezone=Asia/Riyadh -c statement_timeout=30000",
                    connect_timeout=10,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=3,
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
        """Context manager لإدارة الاتصال تلقائياً.

        يربط سياق المستأجر الحالي بالاتصال المُستعار قبل تسليمه، ويمسحه
        قبل إعادته للمجمّع. الضبط على مستوى الجلسة (is_local=False) لا
        محلياً للمعاملة، لأن db.execute() يُنفّذ COMMIT بعد كل عبارة —
        والضبط المحلي يُمحى عندها فيصبح app_tenant() بلا قيمة.
        """
        if not self._pool:
            raise RuntimeError("PostgreSQL Pool غير مهيّأ")
        conn = self._pool.getconn()
        try:
            self._bind_tenant(conn, get_current_tenant())
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            # المسح إلزامي: بدونه يرث الطلبُ التالي الذي يستعير هذا
            # الاتصال سياقَ المستأجر السابق.
            try:
                self._bind_tenant(conn, None)
                conn.commit()
            except Exception:
                conn.rollback()
            self._pool.putconn(conn)

    def _bind_tenant(self, conn, tenant: Optional[str]) -> None:
        """يربط سياق المستأجر بالاتصال، ويختار الدور المناسب.

        الدور يتبع السياق:
          • يوجد مستأجر  → SET ROLE dheuof_app، وهو دور مُقيَّد تسري عليه
            سياسات RLS فيتحقّق العزل فعلياً.
          • لا يوجد مستأجر → RESET ROLE، فيبقى الاتصال بالمالك. هذا ما
            تحتاجه الترحيلات ولوحة المالك والتقارير العابرة للمنشآت.

        بدون هذا التبديل يكون أمامنا خياران سيّئان: إمّا أن يتصل التطبيق
        كله بالمالك فيتجاوز RLS ويصبح العزل وهماً، أو أن نفرض RLS على
        المالك فتعود كل استعلامات الإدارة فارغة.
        """
        branches = get_current_branches()
        with conn.cursor() as cur:
            cur.execute("RESET ROLE")
            cur.execute("SELECT set_config(%s, %s, false)", (GUC_NAME, tenant or ""))
            # قيد الفروع يُضبط دائماً — فراغه يعني «كل الفروع»، وتركه من
            # الاستعارة السابقة يُسرّب قيداً لا يخصّ هذا الطلب
            cur.execute(
                "SELECT set_config(%s, %s, false)",
                (BRANCH_GUC_NAME, ",".join(branches) if branches else ""),
            )
            if tenant and self._app_role_available:
                try:
                    cur.execute(f"SET ROLE {APP_ROLE}")
                except Exception as e:
                    # الدور غير موجود (قاعدة قديمة) — نُسجّل مرة واحدة
                    # ونواصل بالمالك بدل إسقاط الطلب.
                    self._app_role_available = False
                    log.warning(
                        f"تعذّر التحوّل إلى الدور {APP_ROLE} ({e}) — "
                        "الاستعلامات تعمل بصلاحيات المالك، وسياسات RLS "
                        "لن تسري عليها."
                    )

    def execute(
        self,
        query: str,
        params: tuple = (),
        fetch: Optional[str] = None,
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
                    # params or None: عندما تكون المعاملات فارغة نُمرّر None كي
                    # يتخطّى psycopg2 مرحلة الاستبدال تماماً. لو مرّرنا ()
                    # فإنه يُفسّر كل «%» في النص كعلامة معامل، فينهار أي SQL
                    # يحوي «%» حرفياً — مثل LIKE 'x.%' — بـ
                    # «IndexError: tuple index out of range».
                    cur.execute(query, params or None)
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

    async def async_execute(
        self,
        query: str,
        params: tuple = (),
        fetch: Optional[str] = None,
    ) -> Any:
        """Non-blocking wrapper: runs db.execute in threadpool so asyncio event loop
        is not blocked while psycopg2 waits for the database."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute, query, params, fetch)

    @contextmanager
    def transaction(self):
        """Runs multiple execute() calls in a single atomic transaction.

        Usage:
            with db.transaction() as cur:
                cur.execute(sql1, params1)
                cur.execute(sql2, params2)
        All statements commit together; any exception rolls back all of them.
        """
        with self._get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                yield cur

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
        """إغلاق كل الاتصالات عند إيقاف التشغيل — آمن للاستدعاء أكثر من مرة"""
        if self._pool:
            try:
                self._pool.closeall()
            except Exception:
                pass
            self._pool = None
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
