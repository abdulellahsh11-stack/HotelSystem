#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_booking_app.py — تطبيق الحجوزات بمسارَيه

    المنشأة  `routes/listings.py`  تُخصّص ما تعرضه — `require_manager`
    الزائر   `routes/search.py`    يبحث ويتصفّح — بلا جلسة

المخاطر التي تحرسها هذه الملفات:

    ١ مسوّدةٌ نصف مكتملة تُعرض على العالم
    ٢ رقم غرفةٍ أو اسم نزيلٍ يتسرّب في نتيجة بحث
    ٣ حقنُ SQL في مسارٍ عامّ بلا جلسة — يبلغ كل بيانات المنصة
    ٤ منشأةٌ تقرأ توفّر غرف منشأةٍ أخرى بربطٍ برقمٍ مُخمَّن
"""
import ast
import re
from pathlib import Path

import pytest

from db.schema_listings import AMENITIES, UNIT_KINDS

ROOT = Path(__file__).resolve().parent.parent
LISTINGS = ROOT / "routes/listings.py"
SEARCH = ROOT / "routes/search.py"
SCHEMA = ROOT / "db/schema_listings.py"


def src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ── المفردات المضبوطة ───────────────────────────────────────────
@pytest.mark.parametrize("kind", [
    "room", "suite", "apartment", "chalet", "resort", "farm", "villa",
])
def test_every_requested_unit_kind_exists(kind):
    """الأنواع التي طلبها المالك: غرف وشقق ومنتجعات وشاليهات ومزارع وأجنحة."""
    assert kind in UNIT_KINDS


@pytest.mark.parametrize("amenity", [
    "wifi", "parking", "pool", "private_pool", "kitchen", "ac",
    "breakfast", "sea_view", "kids_ok", "pets_ok", "accessible",
])
def test_amenities_cover_the_common_marketplace_set(amenity):
    """الحدّ الأدنى المشترك بين بوكينق وإكسبيديا وأقودا وجاذرن."""
    assert amenity in AMENITIES


def test_amenities_are_filtered_against_the_vocabulary():
    """
    مرفقٌ غير معروف يُسقَط لا يُخزَّن.

    تخزينُه يعني وحدةً لا تظهر في البحث أبداً بلا سبب مفهوم: الزائر
    يبحث عن `pool` والمخزَّن `pooll`.
    """
    body = src(LISTINGS)
    assert "def _clean_amenities" in body
    assert "a in AMENITIES" in body


def test_vocabulary_is_served_not_hardcoded_in_the_ui():
    """
    الواجهة تبني القوائم من الخادم.

    قائمتان لنفس المفردات تتباعدان: يُضاف نوعٌ هنا ولا يظهر هناك، أو
    تُرسل قيمةٌ يرفضها الخادم بلا سبب يفهمه المستخدم.
    """
    assert '@router.get("/vocabulary")' in src(LISTINGS)


# ── ما لا يُعرض ─────────────────────────────────────────────────
def test_search_shows_only_published_on_both_levels():
    """
    النشر مطلوبٌ على المنشأة **وعلى الوحدة**.

    الاكتفاء بأحدهما يعرض مسوّدةً نصف مكتملة على العالم.
    """
    body = src(SEARCH)
    assert "l.is_published = TRUE" in body
    assert "p.is_published = TRUE" in body
    # المستويان في كلٍّ من البحث وصفحة الوحدة. فحصُ «is_published»
    # وحدها يمرّ بشرط الوحدة فقط، فتظهر وحدةٌ منشورة في منشأةٍ سحبت
    # نفسها من العرض.
    for chunk in ("async def search", "async def unit_details"):
        section = body.split(chunk)[1][:2500]
        assert "l.is_published = TRUE" in section, "%s بلا شرط نشر الوحدة" % chunk
        assert "p.is_published = TRUE" in section, "%s بلا شرط نشر المنشأة" % chunk


def test_search_never_selects_room_numbers_or_guests():
    """
    نتيجة البحث لا تحمل رقم غرفةٍ ولا اسم نزيل.

    أرقام الغرف وحالاتها تكشف إشغال المنشأة ومن في أي غرفة.
    """
    body = src(SEARCH)
    for banned in ("room_number", "current_guest", "guests.", "id_number"):
        assert banned not in body, "البحث يكشف %s" % banned


# ── حقن SQL في مسارٍ عامّ ───────────────────────────────────────
def test_no_user_value_is_interpolated_into_sql():
    """
    كل قيمةٍ مُمعلَمة. البحث مسارٌ عامّ بلا جلسة، فأي حقنٍ فيه يبلغ
    بيانات كل منشآت المنصة لا منشأةً واحدة.

    يُفحص ما يصل SQL وحده: f-string يحوي كلمةً مفتاحية. بناء **قيمةٍ**
    مُمعلَمة بـf-string — نمط `ILIKE` مثلاً — لا يمسّ نصّ الاستعلام،
    وفحصُه يجعل الاختبار يشتكي مما لا خطر فيه فيُهمَل.

    المسموح داخل SQL: شروط `where` و`order` و`_PUBLISHED` — وكلها
    مبنيّةٌ من قوائم ثابتة في الملف نفسه.
    """
    body = src(SEARCH)
    tree = ast.parse(body)
    keywords = ("SELECT", "FROM", "WHERE", "ORDER BY", "INSERT", "UPDATE", "DELETE")

    def _flag(node, why):
        raise AssertionError("قيمة تُركَّب في SQL (%s): %s" % (why, ast.unparse(node)))

    for node in ast.walk(tree):
        # (أ) f-string يحوي كلمةً مفتاحية = نصّ استعلام
        if isinstance(node, ast.JoinedStr):
            literal = "".join(v.value for v in node.values
                              if isinstance(v, ast.Constant) and isinstance(v.value, str))
            if any(k in literal.upper() for k in keywords):
                for part in node.values:
                    if isinstance(part, ast.FormattedValue) and ast.unparse(part.value) \
                            not in ("' AND '.join(where)", "order", "_PUBLISHED"):
                        _flag(part.value, "نصّ استعلام")

        # (ب) أي f-string يُلحق بـ`where` — ولو بلا كلمةٍ مفتاحية.
        #     `where.append(f"p.city = '{city}'")` لا يحوي SELECT، ومع
        #     ذلك يصير شرطاً في الاستعلام. الفحص بالكلمات وحده أعماني
        #     عن أخطر حالةٍ ممكنة.
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "where.append":
            for arg in node.args:
                if isinstance(arg, ast.JoinedStr):
                    _flag(arg, "يُلحق بـwhere")


def test_like_wildcards_in_visitor_input_are_escaped():
    """
    `%` و`_` رمزا بدلٍ في ILIKE.

    البحث عن «_» وحده يطابق كل معلمٍ في المنصة. لا حقن — القيمة
    مُمعلَمة — لكن النتيجة تصير خاطئة بصمت.
    """
    section = src(SEARCH).split("if landmark.strip():")[1][:600]
    assert 'replace("%"' in section and 'replace("_"' in section
    assert "ESCAPE" in section


def test_order_by_comes_from_a_fixed_map():
    """
    الترتيب من خريطةٍ ثابتة لا من نصّ المستخدم.

    تمريره خاماً يجعل `ORDER BY` قناة حقنٍ حتى مع تمعيل بقية القيم.
    """
    body = src(SEARCH)
    block = body.split("order = {")[1]
    table, tail = block.split("}.get(sort", 1)
    assert "sort" not in table, "خريطة الترتيب تقرأ نصّ المستخدم"
    assert '"price"' in table and "l.base_price ASC" in table
    # والافتراض عند مفتاحٍ غير معروف: `.get(sort, sort)` يُعيد نصّ
    # المستخدم خاماً إلى ORDER BY — وهي الحالة التي فاتت الفحص أولاً.
    default = tail.split(")")[0]
    assert "sort" not in default, "افتراض الترتيب يُعيد نصّ المستخدم"


def test_search_pagination_is_bounded():
    """صفحةٌ بلا حدّ تجعل طلباً واحداً يسحب كل المعروض."""
    body = src(SEARCH)
    assert "le=MAX_PAGE_SIZE" in body
    assert "MAX_PAGE_SIZE = 60" in body


# ── عزل المنشآت في طبقة العرض ───────────────────────────────────
def test_linking_rooms_verifies_they_belong_to_the_facility():
    """
    الغرف المربوطة تُتحقّق مقابل `client_id`.

    بدونه تربط منشأةٌ غرفة منشأةٍ أخرى برقمٍ مُخمَّن فتقرأ توفّرها.
    """
    body = src(LISTINGS)
    section = body.split("async def link_rooms")[1]
    assert "FROM rooms WHERE client_id=%s" in section


def test_every_listing_query_filters_by_client_id():
    """كل استعلامٍ على جداول العرض مُصفّى بالمنشأة."""
    body = src(LISTINGS)
    for match in re.finditer(
        r"(SELECT|UPDATE|DELETE|INSERT)[^\"']*?(listings|listing_photos|listing_units)",
        body, re.S,
    ):
        window = body[match.start():match.start() + 500]
        assert "client_id" in window, "استعلام عرضٍ بلا عزل: %s" % window[:70]


def test_facility_routes_require_manager():
    """
    العرض واجهة المنشأة للعالم — ليس عملاً يومياً لموظف استقبال.
    """
    body = src(LISTINGS)
    tree = ast.parse(body)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") in
                   ("get", "post", "put", "delete") for d in node.decorator_list):
            continue
        section = ast.get_source_segment(body, node) or ""
        assert "require_manager(request)" in section, "%s بلا حارس" % node.name


# ── الصور ───────────────────────────────────────────────────────
def test_photo_urls_are_validated():
    """
    عنوان الصورة يُتحقّق من بادئته.

    `javascript:` في `src` صفحةٍ عامّة تُشارَك = XSS مخزَّن على كل زائر.
    """
    body = src(LISTINGS)
    section = body.split("async def add_photo")[1]
    assert 'startswith(("https://", "http://", "/static/"))' in section


def test_photo_and_unit_counts_are_capped():
    """بلا حدٍّ يملأ حسابٌ واحد القاعدة بصورٍ ووحداتٍ وهمية."""
    body = src(LISTINGS)
    assert "MAX_PHOTOS = 30" in body and "MAX_UNITS = 200" in body


# ── التوفّر يُحسب لا يُكتب ──────────────────────────────────────
def test_availability_is_derived_from_inventory():
    """
    لا عمود توفّرٍ يُكتب يدوياً.

    كتابته تعني إعلاناً يقول «متاح» وغرفةً مشغولة، فيصل الزائر ولا
    يجد مكاناً — والربط بـ`listing_units` هو ما يجعله حقيقياً.
    """
    schema = src(SCHEMA)
    block = schema.split("CREATE TABLE IF NOT EXISTS listings")[1].split(");")[0]
    for banned in ("available_count", "is_available", "availability"):
        assert banned not in block, "عمود توفّرٍ يُكتب يدوياً: %s" % banned
    assert "listing_units" in schema


def test_files_stay_reviewable():
    """قاعدة المستودع: لا ملف يتجاوز ألف سطر."""
    for path in (LISTINGS, SEARCH, SCHEMA):
        lines = len(src(path).splitlines())
        assert lines <= 1000, "%s: %s سطراً" % (path.name, lines)
