#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_dead_code.py — لا شيفرة ميتة، ولا تهيئة تعتمد على ترتيبٍ هشّ

شيفرةٌ ميتة ليست حياديّة: تُقرأ عند كل مراجعة، وتُصلَح خطأً فيها لا
أثر له، وتُوهم أن ميزةً موجودة. وأسوأها ما **يكذب** — دالةٌ تقول «تم
إنشاء المهمة» ولا تُنشئ شيئاً.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS_DIR = ROOT / "static/js"
DASHBOARD = ROOT / "static/dashboard.html"


def _all_js() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(JS_DIR.glob("*.js")))


def test_no_dead_functions_in_dashboard_js():
    """
    كل دالة معرَّفة يجب أن تُنادى مرةً على الأقل خارج تعريفها.
    الاستثناء: ما تناديه HTML بـ`onclick` — وهو محسوبٌ لأننا نفحص
    `dashboard.html` معها.
    """
    js = _all_js()
    haystack = js + DASHBOARD.read_text(encoding="utf-8")
    dead = [
        name
        for name in re.findall(r"^(?:async )?function ([a-zA-Z_]\w*)", js, re.M)
        if len(re.findall(r"\b%s\b" % re.escape(name), haystack)) <= 1
    ]
    assert not dead, "دوال ميتة: " + ", ".join(sorted(dead))


def test_no_modal_without_an_opener():
    """نافذةٌ لا يفتحها شيء = شيفرة ميتة في HTML."""
    html = DASHBOARD.read_text(encoding="utf-8")
    both = html + _all_js()
    orphans = [
        mid
        for mid in re.findall(r'id="(modal-[a-z-]+)"', html)
        if "openModal('%s'" % mid not in both
    ]
    assert not orphans, "نوافذ لا تُفتح: " + ", ".join(orphans)


def test_no_function_that_only_claims_success():
    """
    دالةٌ تعرض «تم» ولا تنادي الخادم تكذب على المستخدم — وهذا أسوأ من
    غيابها: الغياب يُكتشف والكذب لا يُكتشف. كانت `createStaffTask`
    تفعلها حرفياً.
    """
    for path in sorted(JS_DIR.glob("*.js")):
        for body in re.findall(
            r"^(?:async )?function \w+\([^)]*\)\{(.{0,400}?)\}\s*$",
            path.read_text(encoding="utf-8"), re.M | re.S,
        ):
            if re.search(r"showToast\([^)]*'success'|تم ", body) and not re.search(
                r"apiSend|apiFetch|fetch\(", body
            ):
                pytest.fail("%s: دالة تدّعي النجاح بلا نداء خادم: %s" % (path.name, body[:80]))


# ── التهيئة لا تعتمد على ترتيبٍ هشّ ─────────────────────────────
def test_core_init_waits_for_the_other_scripts():
    """
    `dashboard-core.js` يُحمَّل **أولاً** وينادي `applySessionPermissions`
    المعرَّفة في `dashboard-staff.js` بعده. تنفيذُ التهيئة فور التحليل
    كان يرمي «is not defined» فيقطع بقيّتها بصمت: لا مستمعات إغلاق
    للنوافذ، ولا صلاحيات مُطبَّقة على الشريط، ولا شيء يقول إن شيئاً وقع.
    """
    core = (JS_DIR / "dashboard-core.js").read_text(encoding="utf-8")
    assert "DOMContentLoaded" in core, "التهيئة لا تنتظر تحميل بقية الملفات"
    assert not re.search(r"\(function init\(\)\{.*\}\)\(\);", core, re.S), \
        "التهيئة عادت لتُنفَّذ فور التحليل"


def test_setup_module_owns_registration_not_the_dashboard():
    """نموذجان لنفس العمل يتباعدان — التسجيل في وحدة الإعداد وحدها."""
    both = DASHBOARD.read_text(encoding="utf-8") + _all_js()
    for gone in ("openRoomModal", "openBulkRoomModal", "openStaffModal",
                 "createStaffAccount", "deleteStaff"):
        assert gone not in both, "%s عادت إلى اللوحة" % gone


def test_no_orphan_static_files():
    """
    ملفٌّ لا يشير إليه شيء لن يُصان — يُحذف لا يُترك.

    الملف نفسه مستثنىً من عدّ المراجع: احتسابُه يجعل كل ملفٍ يبدو
    مُشاراً إليه بذاته، فيمرّ الفحص وهو أعمى.
    """
    sources = [
        p for p in ROOT.rglob("*")
        if p.is_file()
        and p.suffix in {".html", ".js", ".py"}
        and "node_modules" not in str(p)
        and ".git" not in str(p)
    ]
    orphans = []
    for path in sorted((ROOT / "static").rglob("*")):
        if path.suffix not in {".css", ".js"} or "node_modules" in str(path):
            continue
        if not any(
            path.name in p.read_text(encoding="utf-8", errors="ignore")
            for p in sources
            if p != path
        ):
            orphans.append(str(path.relative_to(ROOT)))
    assert not orphans, "ملفات يتيمة: " + ", ".join(orphans)
