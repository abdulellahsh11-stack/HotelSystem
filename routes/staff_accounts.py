#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/staff_accounts.py — حسابات دخول الموظفين

صاحب المنشأة يُنشئ الحسابات ويُسند الأدوار؛ الموظف يدخل بحسابه فتحمل
جلسته `client_id` نفسه — فيسري عليها العزل بين المنشآت دون أي تغيير في
بقية النظام — مع دوره وصلاحياته فتُطبَّق عليه قيود الصلاحيات.

الأثر الذي تحلّه هذه الوحدة: قبلها كان موظف الاستقبال يدخل بحساب
المالك، فكل صلاحية مفتوحة له، وكل سجل «من فعل هذا» بلا قيمة إثباتية
لأن الفاعل نصٌّ في جسم الطلب.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app_core import (
    _COOKIE_SECURE, _client_sessions, _lock, _login_rate_ok, _make_password,
    _new_token, _verify_password, client_ip as _client_ip, log, require_client,
)
from services.staff_roles import assignable_by, can_assign, is_valid_role, permissions_for

router = APIRouter(prefix="/api/staff", tags=["Staff Accounts"])

USERNAME_RE = re.compile(r"^[a-zA-Z0-9._-]{3,60}$")
MIN_PASSWORD_LENGTH = 8


class _NoGlobalSalt:
    """
    بديل الإعدادات في التحقق من كلمة مرور الموظف.

    `_verify_password` تقبل الملح العام القديم احتياطاً لحسابات المنشآت
    التي سبقت الملح الفردي. حسابات الموظفين أحدث من ذلك: `pass_salt`
    فيها NOT NULL، فلا احتياط يُحتاج. تمرير هذا بدل `app.state.cfg`
    يزيل اعتماداً لا وظيفة له — وهو اعتمادٌ كان يُسقط الدخول كاملاً حين
    لا تكون الإعدادات محمَّلة.
    """

    pass_salt = ""


_NO_GLOBAL_SALT = _NoGlobalSalt()


def _require_staff_manage(session: dict) -> None:
    """إدارة الحسابات لصاحب المنشأة ومن مُنح `staff.manage` صراحةً."""
    from db.security import check_permission

    if not check_permission(session, "staff.manage"):
        raise HTTPException(
            status_code=403, detail="إدارة حسابات الموظفين تحتاج صلاحية staff.manage"
        )


def _guard_target(session: dict, row: dict) -> None:
    """
    يمنع المدير العام من المساس بحسابٍ في مرتبته.

    إغلاق الإنشاء وحده لا يكفي: مديرٌ عام يستطيع إعادة كلمة مرور مديرٍ
    عام آخر ثم الدخول بها، أو حذفه. المرتبة تُحمى في الاتجاهين.
    """
    from services.staff_roles import OWNER_ONLY_ROLES, _is_owner

    if row.get("role") in OWNER_ONLY_ROLES and not _is_owner(session):
        raise HTTPException(
            status_code=403,
            detail="حسابات المديرين العامّين يديرها مالك المنشأة وحده",
        )


def _db(request: Request):
    db = request.app.state.db
    if not getattr(db, "use_postgres", False):
        raise HTTPException(status_code=503, detail="قاعدة البيانات غير متاحة")
    return db


def _public_row(row: dict) -> dict:
    """صف صالح للعرض — بلا تجزئة ولا ملح."""
    return {
        "id": row.get("id"),
        "username": row.get("username"),
        "full_name": row.get("full_name"),
        "role": row.get("role"),
        "is_active": bool(row.get("is_active")),
        "last_login": str(row.get("last_login")) if row.get("last_login") else None,
        "created_at": str(row.get("created_at")) if row.get("created_at") else None,
    }


# ──────────────────────────────────────────────────────────────
#  الأدوار المتاحة
# ──────────────────────────────────────────────────────────────
@router.get("/roles")
async def list_roles(session=Depends(require_client)):
    """الأدوار التي يسند منها صاحب المنشأة، وما تعنيه كل صلاحية."""
    _require_staff_manage(session)
    from services.staff_roles import PERMISSIONS

    return {"success": True, "data": {"roles": assignable_by(session), "permissions": PERMISSIONS}}


# ──────────────────────────────────────────────────────────────
#  إدارة الحسابات — لصاحب المنشأة
# ──────────────────────────────────────────────────────────────
@router.get("/accounts")
async def list_accounts(request: Request, session=Depends(require_client)):
    _require_staff_manage(session)
    rows = _db(request).execute(
        """SELECT id, username, full_name, role, is_active, last_login, created_at
           FROM staff_users WHERE client_id=%s ORDER BY created_at DESC""",
        (session["client_id"],), fetch="all",
    )
    return {"success": True, "data": [_public_row(dict(r)) for r in (rows or [])]}


@router.post("/accounts")
async def create_account(request: Request, session=Depends(require_client)):
    """يُنشئ حساب دخول لموظف. كلمة المرور تُعرض مرة واحدة ولا تُخزَّن نصاً."""
    _require_staff_manage(session)
    data = await request.json()
    db = _db(request)
    cid = session["client_id"]

    username = str(data.get("username") or "").strip().lower()
    full_name = str(data.get("full_name") or "").strip()
    role = str(data.get("role") or "").strip()
    password = str(data.get("password") or "")

    if not USERNAME_RE.match(username):
        raise HTTPException(
            status_code=400,
            detail="اسم المستخدم: ٣ إلى ٦٠ محرفاً، حروف إنجليزية وأرقام و . _ - فقط",
        )
    if not full_name:
        raise HTTPException(status_code=400, detail="اسم الموظف مطلوب")
    if not is_valid_role(role):
        raise HTTPException(status_code=400, detail="الدور غير معروف")
    if not can_assign(session, role):
        raise HTTPException(
            status_code=403,
            detail="تعيين مديرٍ عام لمالك المنشأة وحده — المدير يعيّن الموظفين لا نظراءه",
        )
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400, detail=f"كلمة المرور {MIN_PASSWORD_LENGTH} محارف على الأقل"
        )

    extra = [p for p in (data.get("extra_permissions") or []) if isinstance(p, str)]
    pass_hash, pass_salt = _make_password(password)

    try:
        db.execute(
            """INSERT INTO staff_users
               (client_id, username, full_name, pass_hash, pass_salt, role,
                extra_perms, employee_id, created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (cid, username, full_name, pass_hash, pass_salt, role,
             json.dumps(extra, ensure_ascii=False), data.get("employee_id"),
             session.get("username") or "owner"),
        )
    except Exception as exc:
        text = str(exc).lower()
        if "unique" in text or "duplicate" in text:
            raise HTTPException(
                status_code=409, detail=f"اسم المستخدم «{username}» مستخدم في منشأتك"
            ) from exc
        log.error("فشل إنشاء حساب موظف للمنشأة %s: %s", cid, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="تعذّر إنشاء الحساب") from exc

    log.info("أُنشئ حساب موظف %s (%s) للمنشأة %s", username, role, cid)
    return {
        "success": True,
        "data": {"username": username, "full_name": full_name, "role": role},
        "note": "سلّم كلمة المرور للموظف الآن — النظام لا يحتفظ بها ولا يعرضها لاحقاً",
    }


@router.patch("/accounts/{account_id}")
async def update_account(account_id: int, request: Request, session=Depends(require_client)):
    """يُعدّل الدور أو الاسم أو حالة التفعيل. لا يُغيّر كلمة المرور."""
    _require_staff_manage(session)
    data = await request.json()
    db = _db(request)
    cid = session["client_id"]

    row = db.execute(
        "SELECT id, username, role FROM staff_users WHERE id=%s AND client_id=%s",
        (account_id, cid), fetch="one",
    )
    if not row:
        raise HTTPException(status_code=404, detail="الحساب غير موجود")
    _guard_target(session, dict(row))

    updates: list[str] = []
    params: list = []
    if "full_name" in data:
        name = str(data["full_name"]).strip()
        if not name:
            raise HTTPException(status_code=400, detail="اسم الموظف مطلوب")
        updates.append("full_name=%s")
        params.append(name)
    if "role" in data:
        if not is_valid_role(str(data["role"])):
            raise HTTPException(status_code=400, detail="الدور غير معروف")
        if not can_assign(session, str(data["role"])):
            raise HTTPException(
                status_code=403,
                detail="ترقية حسابٍ إلى مدير عام لمالك المنشأة وحده",
            )
        updates.append("role=%s")
        params.append(str(data["role"]))
    if "is_active" in data:
        updates.append("is_active=%s")
        params.append(bool(data["is_active"]))
    if "extra_permissions" in data:
        extra = [p for p in (data["extra_permissions"] or []) if isinstance(p, str)]
        updates.append("extra_perms=%s")
        params.append(json.dumps(extra, ensure_ascii=False))

    if not updates:
        raise HTTPException(status_code=400, detail="لا تغييرات")

    params.extend([account_id, cid])
    db.execute(
        f"UPDATE staff_users SET {', '.join(updates)} WHERE id=%s AND client_id=%s",
        tuple(params),
    )

    # الصلاحيات تُحسب عند الدخول وتُخزَّن في الجلسة، فأي تعديل عليها لا
    # يسري على جلسة قائمة. تخفيضُ دورٍ بلا إبطال يعني أن المدير المُنزَّل
    # يحتفظ بصلاحيات مديرٍ حتى تنتهي جلسته (١٢ ساعة).
    if any(k in data for k in ("is_active", "role", "extra_permissions")):
        _revoke_staff_sessions(request, cid, account_id)

    log.info("عُدّل حساب الموظف %s للمنشأة %s", account_id, cid)
    return {"success": True}


@router.post("/accounts/{account_id}/reset-password")
async def reset_password(account_id: int, request: Request, session=Depends(require_client)):
    """يُعيّن كلمة مرور جديدة ويقطع جلسات الموظف القائمة."""
    _require_staff_manage(session)
    data = await request.json()
    password = str(data.get("password") or "")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400, detail=f"كلمة المرور {MIN_PASSWORD_LENGTH} محارف على الأقل"
        )

    db = _db(request)
    cid = session["client_id"]
    # التحقق من الوجود أولاً: بدونه يُعاد «تم» لمعرّف وهمي أو لحساب في
    # منشأة أخرى، فيظنّ المالك أنه غيّر كلمة مرور ولم يتغيّر شيء —
    # ويكشف الردّ الناجح وجود حسابات غيره.
    target = db.execute(
        "SELECT id, role FROM staff_users WHERE id=%s AND client_id=%s",
        (account_id, cid), fetch="one",
    )
    if not target:
        raise HTTPException(status_code=404, detail="الحساب غير موجود")
    _guard_target(session, dict(target))

    pass_hash, pass_salt = _make_password(password)
    db.execute(
        "UPDATE staff_users SET pass_hash=%s, pass_salt=%s WHERE id=%s AND client_id=%s",
        (pass_hash, pass_salt, account_id, cid),
    )
    _revoke_staff_sessions(request, cid, account_id)
    log.info("أُعيدت كلمة مرور الموظف %s للمنشأة %s", account_id, cid)
    return {"success": True, "note": "سلّم كلمة المرور الجديدة للموظف"}


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, request: Request, session=Depends(require_client)):
    """يحذف حساب الدخول. سجلّ الموظف في الموارد البشرية لا يُمسّ."""
    _require_staff_manage(session)
    db = _db(request)
    cid = session["client_id"]
    target = db.execute(
        "SELECT id, role FROM staff_users WHERE id=%s AND client_id=%s",
        (account_id, cid), fetch="one",
    )
    if not target:
        raise HTTPException(status_code=404, detail="الحساب غير موجود")
    _guard_target(session, dict(target))
    db.execute("DELETE FROM staff_users WHERE id=%s AND client_id=%s", (account_id, cid))
    _revoke_staff_sessions(request, cid, account_id)
    log.info("حُذف حساب الموظف %s للمنشأة %s", account_id, cid)
    return {"success": True}


def _revoke_staff_sessions(request: Request, client_id: str, account_id: int) -> None:
    """
    يُسقط جلسات موظف بعينه من الذاكرة **ومن الجدول**.

    الاكتفاء بالذاكرة يعني أن الجلسة تُستعاد من قاعدة البيانات عند أول
    طلب بعدها، فيعود الموظفُ المُوقَف كأن شيئاً لم يكن.
    """
    with _lock:
        for token in [
            t for t, s in _client_sessions.items()
            if s.get("client_id") == client_id and s.get("staff_id") == account_id
        ]:
            _client_sessions.pop(token, None)
    try:
        db = request.app.state.db
        if getattr(db, "use_postgres", False):
            db.execute(
                "DELETE FROM client_sessions WHERE client_id=%s AND staff_id=%s",
                (client_id, account_id),
            )
    except Exception as exc:
        log.warning("تعذّر إبطال جلسات الموظف %s: %s", account_id, exc)


# ──────────────────────────────────────────────────────────────
#  دخول الموظف
# ──────────────────────────────────────────────────────────────
@router.post("/login")
async def staff_login(request: Request):
    """
    دخول الموظف برقم المنشأة واسم المستخدم وكلمة المرور.

    رقم المنشأة مطلوب لأن اسم المستخدم فريد داخلها لا عبر المنصة.
    """
    ip = _client_ip(request)
    if not _login_rate_ok(ip):
        raise HTTPException(status_code=429, detail="محاولات كثيرة — انتظر قليلاً")

    data = await request.json()
    client_id = str(data.get("client_id") or "").strip()
    username = str(data.get("username") or "").strip().lower()
    password = str(data.get("password") or "")

    if not (client_id and username and password):
        raise HTTPException(status_code=400, detail="رقم المنشأة واسم المستخدم وكلمة المرور مطلوبة")

    db = _db(request)
    row = db.execute(
        """SELECT id, client_id, username, full_name, pass_hash, pass_salt,
                  role, extra_perms, is_active
           FROM staff_users WHERE client_id=%s AND username=%s""",
        (client_id, username), fetch="one",
    )

    # رسالة واحدة لكل حالات الفشل: التمييز بين «لا يوجد مستخدم» و«كلمة
    # خاطئة» يكشف أي الحسابات موجودة فيُختصر نصف عمل من يخمّن.
    invalid = HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")
    if not row:
        raise invalid

    account = dict(row)
    password_ok = _verify_password(password, account, _NO_GLOBAL_SALT)
    if not password_ok:
        raise invalid
    if not account.get("is_active"):
        # نفس ردّ الفشل الموحَّد عمداً: ردٌّ مميّز للحساب المُوقَف يُخبر
        # المهاجم أن اسم المستخدم صحيح وكلمة المرور صحيحة أيضاً — وهو
        # أكثر مما يكشفه أي خطأ آخر. يُسجَّل الحدث للإدارة بدل عرضه.
        log.info("محاولة دخول لحساب مُوقَف: %s / %s", client_id, username)
        raise invalid

    try:
        extra = json.loads(account.get("extra_perms") or "[]")
    except (ValueError, TypeError):
        extra = []

    token = _new_token()
    session_data = {
        "client_id": account["client_id"],
        "staff_id": account["id"],
        "username": account["username"],
        "full_name": account["full_name"],
        "role": account["role"],
        "permissions": permissions_for(account["role"], extra),
        "created_at": datetime.now().isoformat(),
    }
    with _lock:
        _client_sessions[token] = session_data

    # تُحفظ الجلسة بهويتها الكاملة.
    # بلا حفظ، يُطرد كل الموظفين مع أي إعادة تشغيل أو نشر. وبحفظٍ بلا
    # دور، تُستعاد الجلسة بصلاحية مالك — ولهذا يُكتب الدور والصلاحيات
    # هنا معاً لا أحدهما.
    try:
        db.execute(
            """INSERT INTO client_sessions
                   (token, client_id, expires_at, ip_address, user_agent,
                    role, staff_id, username, full_name, permissions)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (token) DO NOTHING""",
            (token, account["client_id"],
             (datetime.now() + timedelta(hours=12)).isoformat(),
             _client_ip(request),
             request.headers.get("user-agent", "")[:200],
             account["role"], account["id"], account["username"],
             account["full_name"], json.dumps(session_data["permissions"])),
        )
    except Exception as exc:
        log.warning("تعذّر حفظ جلسة الموظف %s: %s", account["id"], exc)

    try:
        # client_id هنا زائدٌ منطقياً — الصفّ جُلب بشرطه أصلاً — لكن كل
        # استعلام يحمل عزله بنفسه، فلا يعتمد أمانُه على سياق نداءٍ بعيد.
        db.execute(
            "UPDATE staff_users SET last_login=NOW() WHERE id=%s AND client_id=%s",
            (account["id"], account["client_id"]),
        )
    except Exception as exc:
        log.warning("تعذّر تسجيل آخر دخول للموظف %s: %s", account["id"], exc)

    log.info("دخل الموظف %s (%s) للمنشأة %s", username, account["role"], client_id)
    response = JSONResponse({
        "success": True,
        "data": {
            "full_name": account["full_name"],
            "role": account["role"],
            "permissions": session_data["permissions"],
        },
    })
    response.set_cookie(
        "client_token", token, httponly=True, secure=_COOKIE_SECURE,
        samesite="lax", max_age=int(timedelta(hours=12).total_seconds()),
    )
    return response


@router.get("/me")
async def whoami(request: Request, session=Depends(require_client)):
    """
    هوية الجلسة الحالية وصلاحياتها — تبني عليها الواجهة ما تُظهره.

    اسم المنشأة منها: الشريط كان يقرأ الجلسة من `localStorage` وهي فارغة
    دائماً (الجلسة الحقيقية كوكي HttpOnly)، فيُعلن «زائر» لمالكٍ داخلٍ
    فعلاً. صار يسأل هذا المسار، فيحتاج الاسم ليعرضه.
    """
    property_name = ""
    try:
        client = request.app.state.store.get_client(session.get("client_id"))
        property_name = (client or {}).get("hotel_name") or (client or {}).get("name") or ""
    except Exception:  # الاسم زينةُ عرض؛ فشلُ قراءته لا يُسقط الهوية
        pass

    return {
        "success": True,
        "data": {
            "property_name": property_name,
            "client_id": session.get("client_id"),
            "username": session.get("username"),
            "full_name": session.get("full_name"),
            "role": session.get("role", "owner"),
            "permissions": session.get("permissions", []),
            "is_owner": session.get("role", "owner") in ("owner", "gm"),
        },
    }
