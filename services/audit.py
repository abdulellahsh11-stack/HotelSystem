#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/audit.py — الكتابة في سجل المراجعة.

الحالة السابقة
──────────────
جدول audit_log موجود ومُحصَّن ضد التعديل والحذف بمُشغّل، ومسحوبة من
الدور المُقيَّد صلاحيتا UPDATE و DELETE — وصفر موضع كتابة في المستودع
كله. أي أن البنية كاملة والسجل فارغ دائماً: لا أثر لمن غيّر سعراً، ولا
لمن حذف حجزاً، ولا لمن أعاد تعيين كلمة مرور منشأة.

لنظام يتعامل مع أموال ونزلاء، غياب أثر المراجعة يعني استحالة الإجابة عن
«من فعل هذا ومتى» بعد وقوع خلاف أو حادثة.

مبدآن في التصميم
────────────────
1. **الفشل لا يُسقط الطلب.** تعذّر الكتابة في السجل يُسجَّل تحذيراً ولا
   يُفشل العملية الأصلية. سجلّ مراجعة يُعطّل الفندق أسوأ من سجلّ ناقص.

2. **لا أسرار في السجل.** كلمات المرور وهاشاتها وأرقام الهوية ومفاتيح
   الـ API تُنقَّى قبل الكتابة — وإلا صار السجل نفسه هدفاً للتسريب.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

log = logging.getLogger("dheuof.audit")

# قيمة client_id لعمليات مالك المنصة التي لا تخصّ منشأة بعينها.
# العمود NOT NULL، وسياسات العزل تجعل هذه الصفوف غير مرئية لأي مستأجر.
PLATFORM_TENANT = "__platform__"

# مفاتيح لا تُكتب في السجل بحال — أسرار أو بيانات شخصية حسّاسة
_REDACTED_KEYS = frozenset({
    "password", "pass_hash", "pass_salt", "new_password", "old_password",
    "admin_pass_hash", "secret_key", "api_key", "key_hash", "token",
    "client_token", "admin_token", "credentials", "national_id",
    "iqama_number", "id_number", "zatca_qr", "invoice_hash",
})

_REDACTED_MARK = "[محجوب]"

# أفعال تُكتب دائماً مهما كانت النتيجة
SENSITIVE_ACTIONS = frozenset({
    "login.success", "login.failure", "login.rate_limited",
    "admin.login.success", "admin.login.failure", "admin.login.rate_limited",
    "logout", "password.reset", "client.create", "client.delete",
    "client.update", "permission.grant", "permission.revoke",
    "invoice.create", "invoice.void", "payment.record",
    "booking.create", "booking.cancel", "room.delete",
    "employee.create", "employee.terminate", "payroll.generate",
    "night_audit.run", "api_key.issue", "api_key.revoke",
})


def redact(data: Any, _depth: int = 0) -> Any:
    """يُزيل الأسرار والبيانات الشخصية من الحمولة قبل كتابتها.

    يعمل على العمق كي لا يفلت سرٌّ داخل كائن متداخل، وبحدّ للعمق كي لا
    تُسقط بنيةٌ دائرية الطلبَ.
    """
    if _depth > 6:
        return "[عميق جداً]"
    if isinstance(data, dict):
        return {
            k: (_REDACTED_MARK if str(k).lower() in _REDACTED_KEYS
                else redact(v, _depth + 1))
            for k, v in data.items()
        }
    if isinstance(data, (list, tuple)):
        return [redact(v, _depth + 1) for v in data[:50]]
    if isinstance(data, str):
        return data[:2000]
    return data


def audit(
    db,
    *,
    client_id: Optional[str],
    action: str,
    actor_id: str = "",
    actor_type: str = "staff",
    table_name: Optional[str] = None,
    record_id: Optional[Any] = None,
    old_data: Optional[dict] = None,
    new_data: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> bool:
    """يكتب حدثاً في سجل المراجعة. يُعيد True عند النجاح.

    الفشل يُسجَّل تحذيراً ولا يُرفع: العملية الأصلية أهم من أثرها.
    """
    if not db or not getattr(db, "use_postgres", False):
        return False

    try:
        db.execute(
            """
            INSERT INTO audit_log
                (client_id, actor_type, actor_id, action, table_name,
                 record_uuid, old_data, new_data, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::inet)
            """,
            (
                client_id or PLATFORM_TENANT,
                actor_type,
                (actor_id or "")[:100],
                action[:100],
                table_name,
                str(record_id) if record_id is not None else None,
                json.dumps(redact(old_data), ensure_ascii=False) if old_data else None,
                json.dumps(redact(new_data), ensure_ascii=False) if new_data else None,
                _clean_ip(ip_address),
            ),
        )
        return True
    except Exception as e:
        # لا نُفشل الطلب الأصلي — لكن نُبقي الأثر في سجل التطبيق
        log.warning(f"تعذّرت الكتابة في سجل المراجعة [{action}]: {e}")
        return False


def _clean_ip(ip: Optional[str]) -> Optional[str]:
    """عمود INET يرفض القيم غير الصالحة ويُسقط الإدراج كله."""
    if not ip:
        return None
    ip = str(ip).strip()
    if not ip or ip in ("unknown", "testclient"):
        return None
    try:
        import ipaddress
        ipaddress.ip_address(ip)
        return ip
    except ValueError:
        return None


def actor_from_session(session: Optional[dict]) -> tuple:
    """يستخرج (نوع الفاعل، معرّفه) من جلسة — أو فاعلاً مجهولاً."""
    if not session:
        return "anonymous", ""
    if session.get("is_admin"):
        return "admin", "platform_owner"
    employee_id = session.get("employee_id")
    if employee_id:
        return "staff", str(employee_id)
    return "staff", str(session.get("client_id", ""))


def read_audit(db, client_id: str, limit: int = 100, action: Optional[str] = None) -> list:
    """يقرأ أحدث أحداث المراجعة لمنشأة — للوحة التحكّم والتحقيقات."""
    if not db or not getattr(db, "use_postgres", False):
        return []
    query = """
        SELECT id, actor_type, actor_id, action, table_name, record_uuid,
               old_data, new_data, host(ip_address) AS ip_address, created_at
        FROM audit_log
        WHERE client_id = %s
    """
    params: list = [client_id]
    if action:
        query += " AND action = %s"
        params.append(action)
    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(min(int(limit), 500))
    rows = db.execute(query, tuple(params), fetch="all") or []
    return [dict(r) for r in rows]
