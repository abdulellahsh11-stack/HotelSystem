#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_booking_ui.py — واجهتا تطبيق الحجوزات

    المنشأة  `modules/18-listing/`  تُخصّص ما تعرضه
    الزائر   `booking/`             يبحث ويتصفّح ويطلب

المخاطر التي يحرسها هذا الملف:

    ١ واجهةٌ صوريّة — عناصر بلا نداء API، فيظنّ المستخدم أنه حفظ ولم يُحفظ
    ٢ حقل هويةٍ يتسلّل إلى بوابةٍ عامّة
    ٣ عنصرٌ يُنادى ولا وجود له في HTML — فتنهار الشاشة عند أوّله
    ٤ قوائم مكتوبة في الواجهة تتباعد عن قاعدة الخادم
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LISTING_DIR = ROOT / "static/dheuof/modules/18-listing"
BOOKING_DIR = ROOT / "static/dheuof/booking"

PAGES = {
    "listing": (LISTING_DIR / "index.html", LISTING_DIR / "js/listing.js"),
    "search":  (BOOKING_DIR / "index.html", BOOKING_DIR / "js/booking.js"),
    "unit":    (BOOKING_DIR / "unit.html",  BOOKING_DIR / "js/unit.js"),
    "account": (BOOKING_DIR / "account.html", BOOKING_DIR / "js/account.js"),
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ── الملفات موجودة وموصولة ──────────────────────────────────────
@pytest.mark.parametrize("name", sorted(PAGES))
def test_page_and_script_exist(name):
    html, js = PAGES[name]
    assert html.exists(), "%s مفقودة" % html
    assert js.exists(), "%s مفقود" % js


@pytest.mark.parametrize("name", sorted(PAGES))
def test_page_loads_its_own_script(name):
    html, js = PAGES[name]
    assert js.name in read(html), "%s لا تُحمّل %s" % (html.name, js.name)


# ── واجهةٌ بلا نداء API ليست واجهة ──────────────────────────────
@pytest.mark.parametrize("name,endpoints", [
    ("listing", ["/api/listing/profile", "/api/listing/units",
                 "/api/listing/vocabulary", "/api/rooms"]),
    ("search",  ["/api/search/filters", "/api/search?"]),
    ("unit",    ["/api/search/"]),
    ("account", ["/api/visit/me", "/api/visit/login", "/api/visit/register",
                 "/api/visit/bookings", "/api/visit/rooms"]),
])
def test_screen_actually_calls_the_server(name, endpoints):
    """
    سابقة هذا المستودع: `users.html` عرضت جدولاً مكتوباً في HTML وصفر
    نداءات، فظنّ من فتحها أنه أنشأ حساباً ولم يُنشأ شيء.
    """
    js = read(PAGES[name][1])
    for endpoint in endpoints:
        assert endpoint in js, "%s لا ينادي %s" % (name, endpoint)


@pytest.mark.parametrize("name", sorted(PAGES))
def test_no_prefilled_table_rows_in_html(name):
    """الجداول والبطاقات تُبنى من الخادم؛ صفٌّ مكتوبٌ في HTML بيانٌ كاذب."""
    html = read(PAGES[name][0])
    assert "<tbody" not in html and "<td" not in html


# ── كل عنصرٍ يُنادى موجود ───────────────────────────────────────
@pytest.mark.parametrize("name", sorted(PAGES))
def test_every_element_referenced_exists(name):
    """
    `getElementById` لعنصرٍ غير موجود يُعيد `null`، والكتابة عليه ترمي
    فتنقطع بقيّة التهيئة بصمت.

    تُستثنى المُعرّفات المبنيّة ديناميكياً (نصوص HTML تُحقن ثم تُقرأ).
    """
    html_path, js_path = PAGES[name]
    html, js = read(html_path), read(js_path)
    dynamic = set(re.findall(r"id=\"([a-zA-Z0-9_-]+)\"", js))  # ما تحقنه الشيفرة
    for match in re.finditer(r"""\$\(['"]([a-zA-Z0-9_-]+)['"]\)""", js):
        el = match.group(1)
        if el in dynamic:
            continue
        assert 'id="%s"' % el in html, "%s ينادي #%s وهو غير موجود" % (js_path.name, el)


# ── لا هويةَ في بوابةٍ عامّة ────────────────────────────────────
@pytest.mark.parametrize("name", ["search", "unit", "account"])
def test_visitor_pages_never_ask_for_a_national_id(name):
    """
    البوابة لا تطلب رقم هوية — لا في HTML ولا في الجافاسكربت.

    طلبُها من نموذجٍ عامّ يعني تخزين هوياتٍ لم يتحقّق منها أحد، ويجعل
    الصفحة قناة إدخال بياناتٍ لا يملكها المُدخِل.
    """
    html, js = PAGES[name]
    both = read(html) + read(js)
    for banned in ("id_number", "national_id", "iqama", "passport", "رقم الهوية"):
        assert banned not in both, "%s تطلب %s" % (name, banned)


def test_account_page_states_that_identity_is_taken_on_arrival():
    """
    الصفحة تقول ذلك صراحةً: الغياب وحده يترك الزائر يتساءل، والتصريح
    يجعل القرار مفهوماً.
    """
    assert "لا يُطلب رقم هويتك" in read(PAGES["account"][0])


def test_booking_request_sends_no_third_party_identity():
    """طلب الحجز يرسل التواريخ والعدد والنوع — لا اسم شخصٍ ولا هويته."""
    js = read(PAGES["account"][1])
    body = js.split("async function requestBooking")[1].split("\n  }")[0]
    for banned in ("full_name", "guest_name", "id_number"):
        assert banned not in body, "طلب الحجز يرسل %s" % banned


# ── القوائم من الخادم لا من الواجهة ─────────────────────────────
def test_vocabulary_is_not_hardcoded_in_the_facility_ui():
    """
    الأنواع والمرافق تُبنى من `/api/listing/vocabulary`.

    كتابتها هنا تُنتج قائمتين تتباعدان: يُضاف نوعٌ في القاعدة ولا يظهر،
    أو تُرسل قيمةٌ يرفضها الخادم بلا سبب مفهوم.
    """
    js = read(PAGES["listing"][1])
    assert "/api/listing/vocabulary" in js
    for hardcoded in ("chalet", "private_pool", "شاليه", "مسبح خاص"):
        assert hardcoded not in js, "المفردات مكتوبة في الواجهة: %s" % hardcoded


def test_search_filters_come_from_the_server():
    """
    عرض مدنٍ لا معروض فيها يُنتج بحثاً يعود فارغاً دائماً، فيظنّ الزائر
    أن التطبيق معطَّل.
    """
    js = read(PAGES["search"][1])
    assert "/api/search/filters" in js
    for hardcoded in ("جدة", "الرياض", "chalet", "private_pool"):
        assert hardcoded not in js, "خيارات مكتوبة في الواجهة: %s" % hardcoded


# ── التهريب ─────────────────────────────────────────────────────
@pytest.mark.parametrize("name", sorted(PAGES))
def test_server_values_are_escaped_before_injection(name):
    """
    كل قيمةٍ من الخادم تمرّ بـ`esc` قبل `innerHTML`.

    عنوان وحدةٍ يكتبه مالك منشأةٍ يُعرض على كل زائر — فهو مُدخَلٌ من
    طرفٍ ثالث لا نصٌّ موثوق.
    """
    js = read(PAGES[name][1])
    assert "function esc(" in js

    # يُفحص كل ما يُجمع داخل نصوص HTML، لا سطر `innerHTML =` وحده:
    # البطاقات تُبنى في دوالٍّ منفصلة (`card`, `renderUnit`) ثم تُجمع
    # بـ`join`، فحصرُ الفحص في سطر الإسناد أعماني عن جسم البطاقة كلّه
    # — حيث يُعرض عنوانٌ يكتبه مالك منشأةٍ على كل زائر.
    ALLOWED = ("esc(", "encodeURIComponent(", "Number(", "String(", "Math.")
    for line in js.splitlines():
        code = line.split("//")[0]
        if "'<" not in code and '"<' not in code:
            continue                       # ليس بناء HTML
        for token in re.findall(r"\+\s*([a-zA-Z_$][\w.$]*)\s*(?:\+|;|\)|,|$)", code):
            if token.split(".")[0] in ("esc", "encodeURIComponent", "Number",
                                       "String", "Math", "JSON"):
                continue
            assert False, "%s: قيمة غير مُهرَّبة في HTML: %s ← %s" % (
                name, token, code.strip()[:70])
    assert any(a in js for a in ALLOWED)


# ── التهيئة تنتظر الصفحة ────────────────────────────────────────
@pytest.mark.parametrize("name", sorted(PAGES))
def test_init_waits_for_dom(name):
    """
    تنفيذُ التهيئة فور التحليل قبل رسم العناصر يرمي على `null` ويقطع
    بقيّتها بصمت — سابقةٌ كلّفت هذا المستودع لوحةً كاملة.
    """
    assert "DOMContentLoaded" in read(PAGES[name][1])


@pytest.mark.parametrize("name", sorted(PAGES))
def test_file_stays_reviewable(name):
    """قاعدة المستودع: لا ملف يتجاوز ألف سطر."""
    for path in PAGES[name]:
        lines = len(read(path).splitlines())
        assert lines <= 1000, "%s: %s سطراً" % (path.name, lines)


# ── الوصل بالشريط ───────────────────────────────────────────────
def test_facility_module_is_linked_from_the_sidebar():
    """وحدةٌ لا يشير إليها رابطٌ من أي شاشة كوحدةٍ غير موجودة."""
    sidebar = read(ROOT / "static/dheuof/shared/sidebar.js")
    assert '"18-listing"' in sidebar and "العرض والحجز" in sidebar
    assert 'activeId: "18-listing"' in read(PAGES["listing"][0])


def test_facility_ui_links_to_the_public_portal():
    """المالك يعاين ما يراه الزائر — بلا معاينةٍ ينشر على غير بصيرة."""
    html = read(PAGES["listing"][0])
    assert "/static/dheuof/booking/index.html" in html


def test_search_results_link_to_the_unit_page():
    """بطاقة نتيجةٍ لا تُفتح ليست نتيجة."""
    js = read(PAGES["search"][1])
    assert "unit.html?c=" in js and "encodeURIComponent" in js


def test_unit_page_reads_ids_from_the_query_string():
    """صفحة الوحدة عنوانٌ يُشارَك — تقرأ المنشأة والوحدة من الرابط."""
    js = read(PAGES["unit"][1])
    assert "URLSearchParams" in js
    assert "encodeURIComponent" in js


# ── لا شيفرة ميتة في الواجهات الجديدة ───────────────────────────
@pytest.mark.parametrize("name", sorted(PAGES))
def test_no_dead_function_in_the_new_screens(name):
    """دالةٌ لا يناديها شيء تُقرأ في كل مراجعة وتُوهم بميزةٍ لا وجود لها."""
    js = read(PAGES[name][1])
    tree = ast_free_function_names(js)
    for fn in tree:
        assert len(re.findall(r"\b%s\b" % re.escape(fn), js)) > 1, \
            "%s: دالة ميتة %s" % (name, fn)


def ast_free_function_names(js: str) -> list[str]:
    """أسماء الدوال المعرَّفة بـ`function name(` — بلا محلّل جافاسكربت."""
    return re.findall(r"^\s*(?:async\s+)?function\s+([a-zA-Z_]\w*)", js, re.M)


# ── لا أرقام غرفٍ في واجهة الزائر ───────────────────────────────
@pytest.mark.parametrize("name", ["search", "unit"])
def test_visitor_ui_never_renders_room_numbers(name):
    """أرقام الغرف وحالاتها تكشف إشغال المنشأة ومن في أي غرفة."""
    js = read(PAGES[name][1])
    for banned in ("room_number", "current_guest", "occupied"):
        assert banned not in js, "%s يعرض %s" % (name, banned)
