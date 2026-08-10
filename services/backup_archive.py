#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/backup_archive.py — نسخة احتياطية شهرية مضغوطة لكل منشأة

المشكلة التي يحلّها: النسخة السابقة كانت تكتب JSON غير مضغوط في قرص
الحاوية بلا أي نقطة تحميل — أي أن صاحب المنشأة لا يستطيع الحصول على
بياناته إطلاقاً، والملف يضيع عند إعادة النشر.

مبادئ:
- كل نسخة تخصّ منشأة واحدة (client_id) وتُبنى من استعلامات مُصفّاة به.
- ZIP مضغوط، بداخله ملف JSON لكل جدول + `manifest.json` للتحقق.
- اسم الملف يحمل المنشأة والشهر، فيسهل الأرشفة على الجهاز المحلي.
- لا يُخزَّن سرٌّ داخل النسخة (كلمات المرور والمفاتيح تُستثنى صراحةً).
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("dheuof.backup")

# الجداول المُصدَّرة — كلها تحمل client_id
EXPORT_TABLES: tuple[str, ...] = (
    "guests", "bookings", "rooms", "invoices", "zatca_invoices",
    "pos_sales", "employees", "attendance", "payroll",
    "maintenance_orders", "housekeeping_tasks", "warehouse_items",
    "booking_reviews", "channel_reservations", "pricing_rules",
    "check_in_log",
)

# أعمدة لا تخرج في النسخة مهما كان الجدول — أسرار لا بيانات
REDACTED_COLUMNS: frozenset[str] = frozenset({
    "pass_hash", "pass_salt", "password", "password_hash", "api_key",
    "api_secret", "token", "access_token", "refresh_token", "secret",
    "credentials", "channel_secret",
})


def _redact(row: dict) -> dict:
    """يُزيل الأسرار قبل الكتابة — النسخة تُحفظ على أجهزة خارج سيطرتنا."""
    return {k: v for k, v in row.items() if k.lower() not in REDACTED_COLUMNS}


def _fetch_table(db, table: str, client_id: str) -> list[dict]:
    """يقرأ جدولاً واحداً لمنشأة واحدة. اسم الجدول من ثابت داخلي لا من مُدخل."""
    try:
        rows = db.execute(
            f"SELECT * FROM {table} WHERE client_id=%s",  # noqa: S608 — الاسم من EXPORT_TABLES
            (client_id,),
            fetch="all",
        )
        return [_redact(dict(r)) for r in (rows or [])]
    except Exception as exc:
        # جدول غير موجود في هذا التركيب لا يُسقط النسخة كلها
        log.warning("النسخ الاحتياطي: تعذّرت قراءة %s — %s", table, exc)
        return []


def build_archive(db, client_id: str, period: str | None = None) -> tuple[bytes, dict]:
    """
    يبني أرشيف ZIP في الذاكرة ويعيد (المحتوى، البيان).

    `period` بصيغة YYYY-MM — يُستخدم في التسمية فقط؛ المحتوى كامل لا
    مقطعٌ بالشهر، لأن النسخة الاحتياطية تُراد للاستعادة لا للتقرير.
    """
    now = datetime.now(timezone.utc)
    period = period or now.strftime("%Y-%m")

    tables: dict[str, list[dict]] = {}
    counts: dict[str, int] = {}
    for table in EXPORT_TABLES:
        rows = _fetch_table(db, table, client_id)
        tables[table] = rows
        counts[table] = len(rows)

    manifest: dict[str, Any] = {
        "client_id": client_id,
        "period": period,
        "created_at": now.isoformat(),
        "format_version": 1,
        "tables": counts,
        "total_rows": sum(counts.values()),
        "redacted_columns": sorted(REDACTED_COLUMNS),
        "note": "نسخة احتياطية لمنشأة واحدة. الأعمدة السرّية مُستثناة عمداً.",
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for table, rows in tables.items():
            zf.writestr(
                f"data/{table}.json",
                json.dumps(rows, ensure_ascii=False, indent=1, default=str),
            )
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    content = buf.getvalue()
    manifest["sha256"] = hashlib.sha256(content).hexdigest()
    manifest["size_bytes"] = len(content)
    return content, manifest


def archive_filename(client_id: str, period: str) -> str:
    """اسم واضح للأرشفة المحلية: duyuf_backup_<المنشأة>_<الشهر>.zip"""
    safe = "".join(c for c in str(client_id) if c.isalnum() or c in "-_")
    return f"duyuf_backup_{safe}_{period}.zip"
