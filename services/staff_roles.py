#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/staff_roles.py — أدوار الموظفين وصلاحياتها

لماذا أدوار جاهزة لا صلاحيات فردية؟ لأن صاحب المنشأة ليس مسؤول أمن.
اختيار «موظف استقبال» من قائمة قرارٌ يفهمه، أما تجميع اثنتي عشرة صلاحية
يدوياً فيقود إلى منح الكل كل شيء لأنه أسهل. الأدوار هي الافتراض،
والصلاحيات الفردية متاحة لمن يحتاج استثناءً.

مبدأ الحدّ الأدنى: كل دور يحمل ما تحتاجه وظيفته لا أكثر. عاملة التنظيف
لا ترى الفواتير، وموظف الاستقبال لا يرى الرواتب.
"""
from __future__ import annotations

# ── الصلاحيات المعروفة ──────────────────────────────────────────
# كل صلاحية تُقرأ في مسار واحد على الأقل؛ لا تُضاف واحدة بلا فاحص.
PERMISSIONS: dict[str, str] = {
    "bookings.read":    "عرض الحجوزات",
    "bookings.write":   "إنشاء وتعديل الحجوزات",
    "guests.read":      "عرض بيانات النزلاء",
    "guests.write":     "إضافة وتعديل النزلاء",
    "guests.pii":       "كشف بيانات النزيل الكاملة (الهوية والجوال) — يمنحها مالك المنشأة",
    "rooms.read":       "عرض الغرف وحالتها",
    "rooms.write":      "تسجيل وتعديل الغرف",
    "housekeeping":     "مهام الإشراف الداخلي",
    "maintenance":      "طلبات الصيانة",
    "pos":              "نقطة البيع",
    "invoices.read":    "عرض الفواتير",
    "invoices.write":   "إصدار الفواتير",
    "reports":          "التقارير والتحليلات",
    "hr":               "الموارد البشرية والرواتب",
    "staff.manage":     "إدارة حسابات الموظفين",
    "backup":           "النسخ الاحتياطي",
    "settings":         "إعدادات المنشأة",
}

# ── هرم الصلاحيات ───────────────────────────────────────────────
#
#   مالك المنصة (admin)  — كل الصلاحيات، وعبر كل المنشآت.
#                          جلسة منفصلة (admin_token) ومسارات منفصلة،
#                          ولا يملك حساباً في أي منشأة.
#        │
#   مالك المنشأة (owner) — كل الصلاحيات داخل منشأته، ومنها إنشاء
#                          المدير والموظفين. حسابُ الاشتراك نفسه.
#        │
#   مدير عام (gm)        — كل صلاحيات التشغيل داخل المنشأة، ويُنشئ
#                          الموظفين. حسابٌ منفصل يمكن إيقافه — وهذا
#                          فرقه عن المالك: المالك لا يُوقَف.
#        │
#   بقية الأدوار         — كلٌّ بما تحتاجه وظيفته لا أكثر.
#
# لماذا لا يُسنَد `owner` من الواجهة: هو حساب الاشتراك، وإسناده لموظف
# يُنشئ مالكاً ثانياً لا يستطيع المالك الأصلي إيقافه.

# ── الأدوار ─────────────────────────────────────────────────────
ROLES: dict[str, dict] = {
    "owner": {
        "label": "صاحب المنشأة",
        "permissions": ["*"],
        "note": "صلاحية كاملة. لا يُنشأ من هنا — هو حساب الاشتراك نفسه.",
    },
    "gm": {
        "label": "مدير عام",
        "permissions": ["*"],
        "note": "كل صلاحيات المنشأة، ويُنشئ حسابات الموظفين. حسابٌ منفصل يمكن إيقافه.",
    },
    "manager": {
        "label": "مدير مناوبة",
        "permissions": [
            "bookings.read", "bookings.write", "guests.read", "guests.write",
            "rooms.read", "rooms.write", "housekeeping", "maintenance",
            "pos", "invoices.read", "invoices.write", "reports",
        ],
        "note": "يدير التشغيل اليومي. بلا رواتب ولا إنشاء حسابات.",
    },
    "receptionist": {
        "label": "موظف استقبال",
        "permissions": [
            "bookings.read", "bookings.write", "guests.read", "guests.write",
            "rooms.read", "invoices.read", "pos",
        ],
        "note": "يستقبل ويحجز. يرى بيانات النزيل مُقنَّعة — ومدير المنشأة "
                "يمنحه `guests.pii` فرداً فرداً إن احتاج الهوية كاملة.",
    },
    "housekeeping": {
        "label": "إشراف داخلي",
        "permissions": ["rooms.read", "housekeeping", "maintenance"],
        "note": "الغرف والتنظيف فقط. لا يرى بيانات النزلاء ولا الفواتير.",
    },
    "accountant": {
        "label": "محاسب",
        "permissions": ["invoices.read", "invoices.write", "reports", "bookings.read"],
        "note": "المالية والتقارير. لا يُعدّل الحجوزات، ولا يرى هويات "
                "النزلاء — الفاتورة لا تحتاج رقم الهوية.",
    },
    "pos_cashier": {
        "label": "كاشير",
        "permissions": ["pos", "invoices.read"],
        "note": "نقطة البيع فقط.",
    },
}

# أدوار لا يُنشئها صاحب المنشأة من الواجهة
NON_ASSIGNABLE_ROLES = frozenset({"owner"})


# أدوار لا يُنشئها إلا مالك المنشأة نفسه
#
# المدير العام صلاحياته `*`، فلو أنشأ مديراً عاماً آخر لخلق نِدّاً بنفس
# سلطته — يستطيع كلٌّ منهما إيقاف الآخر، والمالك لا يعلم بأيّهما البادئ.
# الهرم يقول: المدير يعيّن الموظفين، والمالك وحده يعيّن المدير.
OWNER_ONLY_ROLES = frozenset({"gm"})


def _is_owner(session: dict | None) -> bool:
    """
    المالك وحده. لا تستعمل `is_owner` المنشورة في `/me` هنا: هي تجمع
    المالك والمدير العام عمداً لأغراض العرض، واستعمالها للتصريح يُعيد
    الثغرة نفسها التي يُغلقها هذا الملف.
    """
    return (session or {}).get("role", "owner") == "owner"


def assignable_by(session: dict | None) -> list[dict]:
    """الأدوار التي يحقّ لصاحب هذه الجلسة إسنادها."""
    roles = assignable_roles()
    if _is_owner(session):
        return roles
    return [r for r in roles if r["value"] not in OWNER_ONLY_ROLES]


def can_assign(session: dict | None, role: str) -> bool:
    """هل يحقّ لصاحب الجلسة إسناد هذا الدور؟"""
    if not is_valid_role(role):
        return False
    if role in OWNER_ONLY_ROLES:
        return _is_owner(session)
    return True


def assignable_roles() -> list[dict]:
    """كل الأدوار القابلة للإسناد — قبل تصفيتها بحسب الجلسة."""
    return [
        {
            "value": key,
            "label": role["label"],
            "note": role["note"],
            "permissions": role["permissions"],
        }
        for key, role in ROLES.items()
        if key not in NON_ASSIGNABLE_ROLES
    ]


def permissions_for(role: str, overrides: list[str] | None = None) -> list[str]:
    """
    صلاحيات الدور، مع استثناءات اختيارية.

    الاستثناءات تُصفّى مقابل PERMISSIONS: صلاحية غير معروفة تعني خطأً
    مطبعياً يمنح — أو يمنع — بصمت. الأسلم إسقاطها.
    """
    base = list(ROLES.get(role, {}).get("permissions", []))
    if "*" in base:
        return ["*"]
    if overrides:
        for perm in overrides:
            if perm in PERMISSIONS and perm not in base:
                base.append(perm)
    return base


def is_valid_role(role: str) -> bool:
    return role in ROLES and role not in NON_ASSIGNABLE_ROLES
