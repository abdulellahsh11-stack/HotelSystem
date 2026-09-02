#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_setup_module.py — وحدة «إعداد المنشأة» موجودة وموصولة وحقيقية

كان تسجيل الغرف وحسابات الموظفين في `dashboard.html` وحدها، بينما
العمل اليومي في `modules/`. فصارت رسالة «سجّل غرفك من لوحة التحكم»
تُرسل المستخدم إلى شاشةٍ لا يشير إليها رابط.

وكانت `users.html` واجهةً صوريّة: صفر نداءات API وجدول مستخدمين مكتوب
في HTML. من فتحها ظنّ أنه أنشأ حساباً ولم يُنشأ شيء — وهذا أسوأ من
غياب الصفحة، لأن الغياب يُكتشف والصورية لا تُكتشف.

ما يحرسه هذا الملف: أن الصفحة الجديدة تنادي الخادم فعلاً، وأن الصورية
لا تعود، وأن الشريط يشير إليها.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SETUP_DIR = ROOT / "static/dheuof/modules/00-setup"
SETUP_HTML = SETUP_DIR / "index.html"
SETUP_JS = SETUP_DIR / "js/setup.js"
SIDEBAR = ROOT / "static/dheuof/shared/sidebar.js"
OLD_USERS = ROOT / "static/dheuof/modules/01-guests/users.html"
DASHBOARD = ROOT / "static/dashboard.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ── الوحدة موجودة ───────────────────────────────────────────────
@pytest.mark.parametrize("path", [SETUP_HTML, SETUP_JS, SETUP_DIR / "setup.css"])
def test_files_exist(path):
    assert path.exists(), f"{path} مفقود"


def test_html_loads_its_own_script():
    assert "00-setup/js/setup.js" in read(SETUP_HTML)


def test_no_file_exceeds_the_thousand_line_limit():
    """قاعدة المستودع: لا ملف يتجاوز ألف سطر."""
    for path in (SETUP_HTML, SETUP_JS, SETUP_DIR / "setup.css"):
        lines = len(read(path).splitlines())
        assert lines <= 1000, f"{path.name}: {lines} سطراً"


# ── الوحدة حقيقية لا صوريّة ─────────────────────────────────────
@pytest.mark.parametrize(
    "endpoint",
    ["/api/rooms", "/api/rooms/bulk", "/api/staff/accounts", "/api/staff/roles", "/api/staff/me"],
)
def test_calls_the_real_endpoint(endpoint):
    """
    الفحص الذي كان يكشف `users.html` لو وُجد: هل تُنادى نقطة الخادم؟
    صفحةٌ بلا نداءٍ واحد ليست صفحةً، بل صورةٌ لصفحة.
    """
    assert endpoint in read(SETUP_JS)


def test_no_hardcoded_room_list():
    """
    سابقة هذا المستودع: قائمة غرفٍ مكتوبة (١٠١…٤١٠) بقيت تُعرض بينما
    المنشأة بلا غرفة واحدة، فظنّ المالك أن غرفه سُجّلت.
    """
    js = read(SETUP_JS)
    assert not re.search(r"num\s*:\s*['\"][٠-٩0-9]{3}['\"]", js), "قائمة غرف مكتوبة"
    assert "١٠١'" not in js and '"101"' not in js


def test_html_has_no_prefilled_table_rows():
    """الجداول تُبنى من الخادم؛ صفٌّ مكتوبٌ في HTML بيانٌ كاذب."""
    html = read(SETUP_HTML)
    assert "<tbody" not in html and "<td" not in html


# ── الصفحة الصوريّة لا تعود ─────────────────────────────────────
def test_old_users_page_is_only_a_redirect():
    html = read(OLD_USERS)
    assert "00-setup" in html, "التحويل لا يشير إلى الوجهة"
    assert len(html.splitlines()) < 60, "الصفحة الصوريّة عادت"
    assert "<tbody" not in html


# ── موصولة من الشريط ────────────────────────────────────────────
def test_sidebar_links_to_setup():
    sidebar = read(SIDEBAR)
    assert '"00-setup"' in sidebar
    assert "إعداد المنشأة" in sidebar


def test_setup_page_marks_itself_active_in_sidebar():
    assert 'activeId: "00-setup"' in read(SETUP_HTML)


# ── الازدواج أُزيل من اللوحة ────────────────────────────────────
def test_dashboard_points_to_setup_instead_of_duplicating():
    """
    نموذجان لنفس العمل يتباعدان: يُصلَح أحدهما ويبقى الآخر، فيرى
    المستخدم سلوكين مختلفين للزرّ نفسه ولا يعرف أيّهما الصحيح.
    """
    dash = read(DASHBOARD)
    assert "00-setup" in dash, "اللوحة لا تشير إلى وحدة الإعداد"
    assert "openBulkRoomModal()" not in dash, "زرّ التسجيل المزدوج باقٍ"
    assert "openStaffModal()" not in dash, "زرّ الحساب المزدوج باقٍ"


# ── الصلاحيات مذكورة، والمنع على الخادم ─────────────────────────
def test_client_side_gating_is_documented_as_cosmetic():
    """
    إخفاء زرٍّ ليس حمايةً. الملف يجب أن يقول ذلك صراحةً حتى لا يبني
    عليه أحدٌ افتراض أمانٍ لاحقاً.
    """
    js = read(SETUP_JS)
    assert "المنع الحقيقي على الخادم" in js
    assert "rooms.write" in js and "staff.manage" in js
