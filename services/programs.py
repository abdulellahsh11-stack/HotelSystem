#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/programs.py — أيّ برامج المنصّة يراها صاحب الجلسة.

الرئيسية تعرض بطاقات البرامج الثمانية عشر؛ لكن عاملة التنظيف لا شأن لها
بالمحاسبة، والكاشير لا يفتح الموارد البشرية. تُخفى البطاقة إن لم يملك
المستخدم صلاحيتها — لا تُعطَّل فقط — والقرار **من الخادم** لا من الواجهة.

كل برنامج يُربط بصلاحيةٍ واحدة من `PERMISSIONS`؛ برنامجٌ صلاحيته None يُرى
لكل موظفٍ داخلٍ (مثل تطبيق الموظفين). المالك والمدير العام (`*`) يريان الكل.
"""
from __future__ import annotations

# (معرّف الوحدة في static/dheuof/modules، الصلاحية المطلوبة) — بالترتيب.
PROGRAMS: list[tuple[str, str | None]] = [
    ("00-setup",            "settings"),
    ("01-guests",           "guests.read"),
    ("02-shumus",           "guests.read"),
    ("03-tourism",          "guests.read"),
    ("04-inventory",        "rooms.write"),
    ("05-warehouse",        "maintenance"),
    ("06-accounting",       "invoices.read"),
    ("07-pos",              "pos"),
    ("08-smart-key",        "rooms.read"),
    ("09-hr",               "hr"),
    ("10-channel-marketing", "bookings.write"),
    ("11-kpis",             "reports"),
    ("12-analytics",        "reports"),
    ("13-staff-tracker",    "staff.manage"),
    ("14-manager-goals",    "reports"),
    ("15-tourism-trips",    "bookings.write"),
    ("16-staff-app",        None),
    ("17-bookings",         "bookings.read"),
    ("18-listing",          "rooms.write"),
]


def programs_for(session: dict | None) -> list[str]:
    """معرّفات البرامج التي يحقّ لصاحب الجلسة رؤيتها، بترتيبها الثابت."""
    perms = list((session or {}).get("permissions") or [])
    if "*" in perms:
        return [pid for pid, _ in PROGRAMS]
    granted = set(perms)
    return [pid for pid, need in PROGRAMS if need is None or need in granted]
