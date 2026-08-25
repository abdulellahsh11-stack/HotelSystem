#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/connection.py — Connection Pool لـ PostgreSQL مع JSON Fallback
Singleton — pool واحد للتطبيق كله
"""
import asyncio
import contextvars
import os
import json
import threading
import logging
from contextlib import contextmanager
from typing import Any, Optional

# مفتاح هروبٍ للتطوير المحلي وحده. في الإنتاج يبقى مطفأً، فيتوقّف
# الإقلاع عند فشل قاعدة البيانات بدل التدهور صامتاً إلى مخزن مؤقّت.
ALLOW_JSON_FALLBACK = os.environ.get("ALLOW_JSON_FALLBACK", "").lower() in ("1", "true", "yes")

# تفعيل عزل قاعدة البيانات (RLS). مُطفأ افتراضياً: تشغيله قبل تطبيق
# السياسات على الجداول يجعل كل استعلام يُعيد صفراً. يُشغَّل بعد
# `db.rls.enable_rls` وبمستخدم قاعدة بيانات لا يتجاوز RLS.
RLS_ENABLED = os.environ.get("RLS_ENABLED", "").lower() in ("1", "true", "yes")

log = logging.getLogger("dheuof.db")

try:
    import psycopg2
    from psycopg2 import pool as pg_pool
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except (ImportError, Exception) as e:
    POSTGRES_AVAILABLE = False
    print(f"⚠️ psycopg2 error: {type(e).__name__}: {e}")

def _bind_tenant_context(cur) -> None:
    """
    يضبط سياق المستأجر داخل معاملة الاستعلام الجارية.

    يجب أن يقع على **نفس الـ cursor** وقبل الاستعلام مباشرةً: السياق
    محليٌّ للمعاملة، وكل `execute()` هنا معاملةٌ مستقلة. ضبطُه في نداء
    منفصل يضيع قبل أن يصل الاستعلام — قِسنا ذلك على خادم حقيقي.

    بلا سياق لا يُضبط شيء، فتتصرّف RLS كما صُمِّمت: لا بيانات. وهذا
    مقصود — الفشل المغلق أفضل من تسريبٍ صامت.
    """
    if not RLS_ENABLED:
        return
    try:
        from db.tenant_context import get_tenant, in_platform_scope

        if in_platform_scope():
            cur.execute("SELECT set_config('app.platform_admin', 'on', true)")
            return
        tenant = get_tenant()
        if tenant:
            cur.execute(
                "SELECT set_config('app.current_client_id', %s, true)", (tenant,)
            )
    except Exception as exc:
        # لا يُبتلع الفشل بصمت: بلا سياق تُعيد الاستعلامات صفراً، وتشخيص
        # ذلك بلا هذا السطر يستغرق ساعات.
        log.error("تعذّر ضبط سياق المستأجر: %s", exc)
        raise


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
                    options="-c timezone=Asia/Riyadh -c statement_timeout=30000",
                    connect_timeout=10,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=3,
                )
                log.info(f"✅ PostgreSQL Pool جاهز — {min_conn}..{max_conn} اتصال")
            except Exception as e:
                # لا سقوطَ صامت إلى JSON.
                # كان الفشل هنا يُحوِّل المنصة كلها إلى مخزن JSON بلا إنذار
                # سوى سطر في السجل: بيانات المنشآت في PostgreSQL تختفي عن
                # الواجهة، وما يُكتب يذهب إلى ملف يُمحى مع الحاوية. انقطاعٌ
                # لحظي وقت النشر كان يكفي لذلك.
                # العمل بقاعدة بيانات خاطئة أسوأ من التوقف: التوقف يُلاحَظ
                # ويُصلَح، والتدهور الصامت يُكتشف بعد ضياع البيانات.
                log.critical("❌ فشل اتصال PostgreSQL: %s", e)
                if ALLOW_JSON_FALLBACK:
                    log.warning(
                        "⚠️  ALLOW_JSON_FALLBACK مُفعَّل — المتابعة بمخزن JSON. "
                        "للتطوير المحلي فقط، لا للإنتاج."
                    )
                    self.use_postgres = False
                    self._pool = None
                else:
                    raise RuntimeError(
                        "تعذّر الاتصال بقاعدة البيانات وDATABASE_URL مضبوط. "
                        "أُوقف الإقلاع بدل العمل على مخزن مؤقّت. "
                        "للتطوير المحلي اضبط ALLOW_JSON_FALLBACK=1."
                    ) from e
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
                    _bind_tenant_context(cur)
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

    async def async_execute(
        self,
        query: str,
        params: tuple = (),
        fetch: Optional[str] = None,
    ) -> Any:
        """
        غلافٌ غير حاجب: يُنفّذ execute في خيط منفصل حتى لا تتوقف حلقة
        asyncio بانتظار psycopg2.

        `copy_context` ضرورية: `run_in_executor` لا تنقل ContextVars إلى
        الخيط، فيفقد الاستعلامُ سياقَ المستأجر وتُعيد RLS صفر صفوف —
        عطلٌ يظهر في المسارات غير المتزامنة وحدها فيبدو عشوائياً.
        """
        loop = asyncio.get_event_loop()
        ctx = contextvars.copy_context()
        return await loop.run_in_executor(
            None, lambda: ctx.run(self.execute, query, params, fetch)
        )

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
                _bind_tenant_context(cur)
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
