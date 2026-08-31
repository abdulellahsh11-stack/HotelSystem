#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_role_hierarchy.py — المدير العام لا يُنشئ نظيراً له

الهرم الذي وصفه مالك المنصة:

    مالك المنشأة → يُنشئ المدير العام والموظفين
    مدير عام     → يُنشئ الموظفين وحدهم — لا مديرين عامّين

صلاحيات `gm` هي `*`، فبلا حارسٍ صريح يستطيع مديرٌ عام إنشاء مديرٍ عام
آخر، أو إعادة كلمة مرور مديرٍ قائم والدخول بها. الحارس يُغلق الاتجاهين:
الإنشاء والترقية، والمساس بحسابٍ في المرتبة نفسها.

كل اختبار هنا يبدأ بحالةٍ **يجب أن تُرفض**، لا بحالةٍ تمرّ. اختبارٌ
يتحقّق من النجاح وحده لا يُثبت أن المنع يعمل.
"""
import pytest

from services.staff_roles import (
    OWNER_ONLY_ROLES,
    ROLES,
    assignable_by,
    assignable_roles,
    can_assign,
)

OWNER = {"role": "owner"}
GM = {"role": "gm"}
MANAGER = {"role": "manager"}


# ── ما يُمنع ────────────────────────────────────────────────────
def test_gm_cannot_assign_gm():
    """جوهر الاختبار: لو سقط الحارس مرّ هذا وفشل الاختبار."""
    assert can_assign(GM, "gm") is False


def test_manager_cannot_assign_gm():
    assert can_assign(MANAGER, "gm") is False


def test_gm_role_absent_from_gm_menu():
    """القائمة المعروضة لا تحوي ما لا يُقبل إرساله — وإلا وعدت بما تمنع."""
    values = [r["value"] for r in assignable_by(GM)]
    assert "gm" not in values


def test_owner_is_never_assignable_by_anyone():
    """المالك حساب الاشتراك؛ إسناده يُنشئ مالكاً ثانياً لا يُوقَف."""
    for session in (OWNER, GM, MANAGER, None):
        assert can_assign(session, "owner") is False


def test_unknown_role_rejected():
    assert can_assign(OWNER, "superuser") is False
    assert can_assign(OWNER, "") is False


# ── ما يُسمح ────────────────────────────────────────────────────
def test_owner_can_assign_gm():
    assert can_assign(OWNER, "gm") is True
    assert "gm" in [r["value"] for r in assignable_by(OWNER)]


@pytest.mark.parametrize(
    "role", [r for r in ROLES if r not in OWNER_ONLY_ROLES and r != "owner"]
)
def test_gm_can_assign_every_ordinary_role(role):
    """المنع مقصورٌ على المرتبة: المدير يعيّن الموظفين بلا استثناء."""
    assert can_assign(GM, role) is True
    assert role in [r["value"] for r in assignable_by(GM)]


def test_session_missing_role_treated_as_owner():
    """
    جلسة المالك في `app_core` قد تصل بلا مفتاح `role` — وافتراضها
    `owner` هو سلوك `db.security` نفسه. لو صار الافتراض غير مالك،
    انقطع المالك عن تعيين مديره العام.
    """
    assert can_assign({}, "gm") is True
    assert can_assign(None, "gm") is True


# ── الحارس لا يعتمد على `is_owner` المضلِّلة ─────────────────────
def test_is_owner_flag_does_not_grant_gm():
    """
    `/api/staff/me` تنشر `is_owner = role in (owner, gm)` لأغراض العرض.
    لو استُعملت للتصريح لعادت الثغرة: مديرٌ عام يحمل `is_owner=True`.
    """
    assert can_assign({"role": "gm", "is_owner": True}, "gm") is False


# ── القائمة الكاملة لم تتغيّر ────────────────────────────────────
def test_assignable_roles_still_excludes_owner_only_from_nothing():
    """
    `assignable_roles()` تبقى القائمة الكاملة قبل التصفية — التصفية
    مسؤولية `assignable_by`. خلطُهما يجعل المالك نفسه بلا «مدير عام».
    """
    assert "gm" in [r["value"] for r in assignable_roles()]
    assert "owner" not in [r["value"] for r in assignable_roles()]
