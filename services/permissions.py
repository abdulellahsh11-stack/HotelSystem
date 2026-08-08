#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/permissions.py — صلاحيات الموظفين وحراسة المسارات.

الحالة السابقة
──────────────
البنية كانت كاملة على الورق: جدول staff_roles بستة أدوار قياسية،
وstaff_role_assignments لإسنادها، ودالة app_has_perm في قاعدة البيانات،
وcheck_permission و enforce_permission في db/security.py.

ولم تُستدعَ أيٌّ من دالتَي الحراسة ولا مرة واحدة في المستودع كله.

وهوية الموظف كانت تُمرَّر نصاً في جسم الطلب:

    staff_name = data.get("staff_name", "")

أي أن أي مستخدم للمنشأة ينسب أي عملية لأي موظف — لا مصادقة، ولا مساءلة،
ولا معنى لسجل «من نظّف الغرفة» أو «من أعطى الخصم».

ما يفعله هذا الملف
──────────────────
يربط الطرفين: يحسب الصلاحيات الفعلية للموظف من أدواره المُسندة، ويوفّر
require_permission كتبعية FastAPI تُغلق المسار على من لا يملك الصلاحية.

مبدأ الحساب: صلاحيات الموظف هي **اتحاد** صلاحيات كل أدواره، وتعريف
المنشأة لدور ما يَجُبّ القالب العام لنفس الدور. الصلاحية «rooms» تشمل
«rooms.read» — تدرّج بنقطة، لا قائمة مسطّحة تُنسى فيها الفروع.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException, Request

log = logging.getLogger("dheuof.permissions")

# صلاحية مطلقة — لمالك المنشأة
WILDCARD = "*"


def effective_permissions(db, client_id: str, employee_id: int) -> list:
    """يجمع صلاحيات كل الأدوار المُسندة لموظف.

    تعريف المنشأة لدور يَجُبّ القالب العام لنفس الدور، وتُجمع الأدوار
    المتعددة لا يُختار أحدها.
    """
    if not db or not getattr(db, "use_postgres", False):
        return []
    try:
        rows = db.execute(
            """
            SELECT DISTINCT perm
            FROM (
                SELECT DISTINCT ON (a.role_code) r.permissions
                FROM staff_role_assignments a
                JOIN staff_roles r
                  ON r.role_code = a.role_code
                 AND (r.client_id = a.client_id OR r.client_id IS NULL)
                WHERE a.client_id = %s AND a.employee_id = %s
                ORDER BY a.role_code, (r.client_id IS NULL)
            ) eff, LATERAL jsonb_array_elements_text(permissions) AS perm
            """,
            (client_id, employee_id), fetch="all",
        ) or []
        return [r["perm"] for r in rows]
    except Exception as e:
        log.warning(f"تعذّر حساب صلاحيات الموظف {employee_id}: {e}")
        return []


def role_codes(db, client_id: str, employee_id: int) -> list:
    if not db or not getattr(db, "use_postgres", False):
        return []
    try:
        rows = db.execute(
            "SELECT role_code FROM staff_role_assignments "
            "WHERE client_id = %s AND employee_id = %s",
            (client_id, employee_id), fetch="all",
        ) or []
        return [r["role_code"] for r in rows]
    except Exception:
        return []


def has_permission(permissions, wanted: str) -> bool:
    """هل تُغطّي القائمةُ الصلاحيةَ المطلوبة؟

    «rooms» تمنح «rooms.read» — التدرّج بنقطة يمنع الحاجة إلى تعداد كل
    فرع في كل دور، وهو ما يُنسى فيُترك المسار مفتوحاً أو مغلقاً خطأً.
    """
    if not permissions:
        return False
    for perm in permissions:
        if perm == WILDCARD or perm == wanted or wanted.startswith(f"{perm}."):
            return True
    return False


def session_permissions(session: Optional[dict]) -> list:
    if not session:
        return []
    if session.get("role") == "owner":
        return [WILDCARD]
    return session.get("permissions") or []


def require_permission(permission: str):
    """تبعية FastAPI تُغلق المسار على من لا يملك الصلاحية.

        @router.get("/payroll", dependencies=[Depends(require_permission("payroll"))])

    مالك المنشأة يمرّ دائماً؛ الموظف يمرّ بقدر أدواره.
    """
    def _guard(request: Request) -> dict:
        from main import require_client
        session = require_client(request)

        if has_permission(session_permissions(session), permission):
            return session

        # الرفض يُسجَّل: محاولات الوصول غير المصرَّح بها إشارة تحقيق
        try:
            from services.audit import audit
            audit(
                getattr(request.app.state, "db", None),
                client_id=session.get("client_id"),
                action="permission.denied",
                actor_id=str(session.get("employee_id") or session.get("client_id", "")),
                actor_type="staff",
                record_id=request.url.path,
                new_data={"required": permission,
                          "role": session.get("role"),
                          "path": request.url.path},
                ip_address=request.client.host if request.client else None,
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=403,
            detail=f"لا تملك صلاحية «{permission}» — دورك الحالي: "
                   f"{session.get('role') or 'غير محدد'}",
        )

    return _guard


def actor_name(session: dict) -> str:
    """اسم منفّذ العملية من الجلسة لا من جسم الطلب.

    كان الاسم يُقرأ من data["staff_name"]، فيكتب أي مستخدم أي اسم
    وينسب العملية لمن يشاء. الجلسة مصدر لا يملك المستخدم تزويره.
    """
    return (
        session.get("full_name")
        or session.get("employee_code")
        or session.get("client_id", "")
    )
