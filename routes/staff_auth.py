#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/staff_auth.py — دخول الموظفين وإدارة أدوارهم.

لماذا
─────
كانت هوية الموظف تُمرَّر نصاً في جسم الطلب (`staff_name`)، فينسب أي
مستخدم للمنشأة أي عملية لأي موظف. سجلّ «من نظّف الغرفة» و«من أعطى
الخصم» و«من أغلق الوردية» كان بلا قيمة إثباتية.

وجدولا staff_roles و staff_role_assignments موجودان منذ البداية بستة
أدوار قياسية، وdالة app_has_perm جاهزة — ولم يكن هناك ما يربطهما
بمستخدم حقيقي: لا مسار دخول للموظفين ولا عمود كلمة مرور.

نموذج الحسابات
──────────────
  حساب المنشأة (المالك)  →  /api/login        دور owner، صلاحية مطلقة
  حساب الموظف            →  /api/staff/login  دور مُسند، صلاحيات محدودة

المالك وحده يُنشئ حسابات موظفيه ويُسند أدوارهم.
"""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from db.passwords import hash_password, verify_password
from services.audit import audit
from services.permissions import effective_permissions, require_permission, role_codes

router = APIRouter(prefix="/api/staff", tags=["StaffAuth"])
logger = logging.getLogger("dheuof")

STAFF_SESSION_HOURS = 12   # وردية عمل واحدة
MIN_STAFF_PASSWORD = 8


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


def _require_owner(request: Request) -> dict:
    """إدارة حسابات الموظفين وأدوارهم مقصورة على مالك المنشأة."""
    session = _require_client(request)
    if session.get("role") != "owner":
        raise HTTPException(403, "إدارة حسابات الموظفين مقصورة على مالك المنشأة")
    return session


# ── دخول الموظف ───────────────────────────────────────────────────────────────

@router.post("/login")
async def staff_login(request: Request):
    """دخول موظف بمعرّف المنشأة ورقمه الوظيفي وكلمة مروره."""
    import main1

    body = {}
    try:
        body = await request.json()
    except Exception:
        form = await request.form()
        body = dict(form)

    client_id = str(body.get("client_id", "")).strip()
    employee_code = str(body.get("employee_id", "")).strip()
    password = str(body.get("password", ""))
    client_ip = request.client.host if request.client else "unknown"

    # المفتاح يشمل الرقم الوظيفي: موظفو الفندق يشتركون غالباً في عنوان
    # واحد خلف NAT، فالتحديد بالعنوان وحده يجعل محاولات موظف واحد
    # تُغلق الدخول على زملائه جميعاً. الحماية من التخمين تبقى قائمة —
    # الحدّ لكل حسابٍ مستهدَف على حدة.
    if not main1._login_rate_ok(f"staff:{client_ip}:{employee_code}"):
        audit(request.app.state.db, client_id=client_id or None,
              action="staff.login.rate_limited", actor_type="anonymous",
              ip_address=client_ip)
        return JSONResponse({"success": False, "error": "محاولات كثيرة — انتظر دقيقة"},
                            status_code=429)

    if not client_id or not employee_code or not password:
        raise HTTPException(422, "معرّف المنشأة والرقم الوظيفي وكلمة المرور مطلوبة")

    db = request.app.state.db
    if not db.use_postgres:
        raise HTTPException(503, "دخول الموظفين يتطلّب PostgreSQL")

    row = db.execute(
        """SELECT id, client_id, employee_id, full_name_ar, pass_hash,
                  status, can_login, branch_id
           FROM employees WHERE client_id = %s AND employee_id = %s""",
        (client_id, employee_code), fetch="one",
    )

    # رسالة واحدة لكل حالات الفشل: تمييزها يكشف أي أرقام وظيفية موجودة
    def _reject(reason: str):
        audit(db, client_id=client_id, action="staff.login.failure",
              actor_type="anonymous", actor_id=employee_code,
              new_data={"reason": reason}, ip_address=client_ip)
        return JSONResponse({"success": False, "error": "بيانات الدخول غير صحيحة"},
                            status_code=401)

    if not row:
        return _reject("لا يوجد موظف بهذا الرقم")
    if not row["can_login"]:
        return _reject("الحساب غير مُفعَّل للدخول")
    if row["status"] != "active":
        return _reject(f"حالة الموظف: {row['status']}")
    if not row["pass_hash"]:
        return _reject("لا كلمة مرور مضبوطة")

    ok, needs_rehash = verify_password(password, row["pass_hash"])
    if not ok:
        return _reject("كلمة مرور خاطئة")

    if needs_rehash:
        try:
            db.execute("UPDATE employees SET pass_hash = %s WHERE id = %s",
                       (hash_password(password), row["id"]))
        except Exception as e:
            logger.warning(f"تعذّرت ترقية هاش الموظف: {e}")

    permissions = effective_permissions(db, client_id, row["id"])
    roles = role_codes(db, client_id, row["id"])
    if not roles:
        return _reject("لا دور مُسند للموظف")

    token = main1._new_token()
    session = {
        "client_id": client_id,
        "created_at": datetime.now().isoformat(),
        "actor_type": "staff",
        "employee_id": row["id"],
        "employee_code": row["employee_id"],
        "full_name": row["full_name_ar"],
        "role": roles[0],
        "roles": roles,
        "permissions": permissions,
        # None تعني كل الفروع (للمدير العام)؛ قائمة تعني فروعاً بعينها
        "branch_ids": [row["branch_id"]] if row["branch_id"] else None,
    }
    with main1._lock:
        main1._client_sessions[token] = session

    try:
        db.execute("UPDATE employees SET last_login_at = NOW() WHERE id = %s", (row["id"],))
        expires = datetime.now() + timedelta(hours=STAFF_SESSION_HOURS)
        db.execute(
            """INSERT INTO client_sessions (token, client_id, expires_at, ip_address, user_agent)
               VALUES (%s, %s, %s, %s, %s) ON CONFLICT (token) DO NOTHING""",
            (token, client_id, expires.isoformat(), client_ip,
             request.headers.get("user-agent", "")[:200]),
        )
    except Exception as e:
        logger.debug(f"staff session persist skipped: {e}")

    audit(db, client_id=client_id, action="staff.login.success", actor_type="staff",
          actor_id=str(row["id"]), new_data={"roles": roles}, ip_address=client_ip)

    response = JSONResponse({
        "success": True,
        "data": {"employee_id": row["employee_id"], "full_name": row["full_name_ar"],
                 "roles": roles, "permissions": permissions},
    })
    response.set_cookie("client_token", token, httponly=True, samesite="lax",
                        secure=main1._COOKIE_SECURE, max_age=STAFF_SESSION_HOURS * 3600)
    return response


@router.get("/me")
async def staff_me(request: Request, session=Depends(_require_client)):
    """هوية المستخدم الحالي وصلاحياته — تبني عليها الواجهة قوائمها."""
    return {"success": True, "data": {
        "client_id": session.get("client_id"),
        "role": session.get("role"),
        "roles": session.get("roles") or ([session["role"]] if session.get("role") else []),
        "permissions": session.get("permissions") or [],
        "employee_id": session.get("employee_code"),
        "full_name": session.get("full_name"),
        "branch_ids": session.get("branch_ids"),
        "is_owner": session.get("role") == "owner",
    }}


# ── إدارة حسابات الموظفين — للمالك وحده ──────────────────────────────────────

@router.post("/accounts/{emp_id}/password")
async def set_staff_password(emp_id: int, request: Request,
                             session=Depends(_require_owner)):
    """يضبط كلمة مرور موظف ويُفعّل دخوله."""
    body = await request.json()
    password = str(body.get("password", ""))
    if len(password) < MIN_STAFF_PASSWORD:
        raise HTTPException(422, f"كلمة المرور قصيرة — {MIN_STAFF_PASSWORD} أحرف على الأقل")

    db = request.app.state.db
    cid = session["client_id"]
    updated = db.execute(
        "UPDATE employees SET pass_hash = %s, can_login = TRUE "
        "WHERE id = %s AND client_id = %s",
        (hash_password(password), emp_id, cid),
    )
    if not updated:
        raise HTTPException(404, "الموظف غير موجود")

    audit(db, client_id=cid, action="staff.password.set", actor_type="staff",
          actor_id=str(session.get("client_id")), table_name="employees",
          record_id=emp_id, ip_address=request.client.host if request.client else None)
    return {"success": True}


@router.post("/accounts/{emp_id}/roles")
async def assign_role(emp_id: int, request: Request, session=Depends(_require_owner)):
    """يُسند دوراً لموظف."""
    body = await request.json()
    role_code = str(body.get("role_code", "")).strip()
    branch_id = body.get("branch_id")
    if not role_code:
        raise HTTPException(422, "role_code مطلوب")

    db = request.app.state.db
    cid = session["client_id"]

    known = db.execute(
        "SELECT 1 FROM staff_roles WHERE role_code = %s AND (client_id = %s OR client_id IS NULL) LIMIT 1",
        (role_code, cid), fetch="one",
    )
    if not known:
        raise HTTPException(422, f"دور غير معروف: {role_code}")

    if not db.execute("SELECT 1 FROM employees WHERE id = %s AND client_id = %s",
                      (emp_id, cid), fetch="one"):
        raise HTTPException(404, "الموظف غير موجود")

    db.execute(
        """INSERT INTO staff_role_assignments (client_id, employee_id, role_code, branch_id, granted_by)
           VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (client_id, employee_id, role_code) DO NOTHING""",
        (cid, emp_id, role_code, branch_id, session.get("client_id")),
    )
    audit(db, client_id=cid, action="permission.grant", actor_type="staff",
          actor_id=str(session.get("client_id")), table_name="staff_role_assignments",
          record_id=emp_id, new_data={"role_code": role_code, "branch_id": branch_id},
          ip_address=request.client.host if request.client else None)
    return {"success": True}


@router.delete("/accounts/{emp_id}/roles/{role_code}")
async def revoke_role(emp_id: int, role_code: str, request: Request,
                      session=Depends(_require_owner)):
    db = request.app.state.db
    cid = session["client_id"]
    db.execute(
        "DELETE FROM staff_role_assignments WHERE client_id = %s AND employee_id = %s AND role_code = %s",
        (cid, emp_id, role_code),
    )
    audit(db, client_id=cid, action="permission.revoke", actor_type="staff",
          actor_id=str(session.get("client_id")), table_name="staff_role_assignments",
          record_id=emp_id, old_data={"role_code": role_code},
          ip_address=request.client.host if request.client else None)
    return {"success": True}


@router.get("/roles")
async def list_roles(request: Request, session=Depends(_require_client)):
    """الأدوار المتاحة وصلاحياتها."""
    db = request.app.state.db
    rows = db.execute(
        "SELECT role_code, name_ar, permissions, (client_id IS NULL) AS is_template "
        "FROM staff_roles WHERE client_id = %s OR client_id IS NULL ORDER BY role_code",
        (session["client_id"],), fetch="all",
    ) or []
    return {"success": True, "data": [dict(r) for r in rows]}


@router.get("/accounts")
async def list_staff_accounts(request: Request,
                              session=Depends(require_permission("hr"))):
    """حسابات الموظفين وأدوارهم — يتطلّب صلاحية الموارد البشرية."""
    db = request.app.state.db
    rows = db.execute(
        """SELECT e.id, e.employee_id, e.full_name_ar, e.status, e.can_login,
                  e.last_login_at, e.branch_id,
                  COALESCE(ARRAY_AGG(a.role_code) FILTER (WHERE a.role_code IS NOT NULL), '{}') AS roles
           FROM employees e
           LEFT JOIN staff_role_assignments a
                  ON a.employee_id = e.id AND a.client_id = e.client_id
           WHERE e.client_id = %s
           GROUP BY e.id ORDER BY e.full_name_ar""",
        (session["client_id"],), fetch="all",
    ) or []
    return {"success": True, "data": [dict(r) for r in rows]}
