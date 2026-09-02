#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_query_result_access.py — قراءة نتائج الاستعلام لا تفترض شكلاً

المجمَّع يستعمل `RealDictCursor`، فالصفّ العائد قاموسٌ لا صفٌّ عادي.
`row[0]` عليه يرمي `KeyError: 0` — **لا `IndexError`** — فيمرّ من
`except Exception` ويعود ٥٠٠ برسالةٍ لا تدلّ على شيء. أربعة مسارات
صفحيّة كانت تفعلها: الموظفون، نقاط البيع، الفواتير، حجوزات القنوات —
معطّلة بالكامل، وكل اختباراتها تمرّ لأنها لا تمسّ قاعدة بيانات حقيقية.

والعلّة الثانية من جنسها: عمودٌ غير موجود داخل `COALESCE`. PostgreSQL
يتحقّق من كل عمودٍ مذكور ولو لم تُستعمل قيمته، فيسقط الاستعلام كلّه.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ROUTES = sorted((ROOT / "routes").glob("*.py"))

# أعمدة `guests` كما هي في المخطط — المصدر: db/schema*.py
GUEST_COLUMNS = {
    "id", "client_id", "id_type", "id_number", "full_name", "absher_phone",
    "nationality", "birth_date", "data_status", "source", "notes",
    "created_at", "updated_at", "id_number_bidx",
}


@pytest.mark.parametrize("path", ROUTES, ids=lambda p: p.name)
def test_no_numeric_index_on_a_fetched_row(path):
    """
    `count_result[0]` وأمثاله. الصفّ قاموس، والفهرسة الرقمية تكسره.
    البديل `db.connection.count_of` يقرأ الشكلين.
    """
    src = path.read_text(encoding="utf-8")
    bad = re.findall(r"\b(\w*(?:result|row|rec)\w*)\s*\[\s*0\s*\]", src, re.I)
    assert not bad, "%s: فهرسة رقمية على صفّ قاموس: %s" % (path.name, set(bad))


def test_count_of_reads_both_row_shapes():
    """الحارس نفسه مُختبَر — لا يُوثَق بمساعدٍ بلا فحص."""
    from db.connection import count_of

    assert count_of({"count": 42}) == 42          # RealDictRow
    assert count_of({"n": 7}) == 7                # COUNT(*) AS n
    assert count_of((5,)) == 5                    # صفّ عادي
    assert count_of(None) == 0 and count_of({}) == 0


@pytest.mark.parametrize("path", ROUTES, ids=lambda p: p.name)
def test_no_reference_to_a_nonexistent_guest_column(path):
    """
    `COALESCE(g.full_name, g.name, '')` كان يُسقط ثلاثة استعلامات في
    `accounting.py`: `guests.name` لا وجود له، والعمود المذكور يُتحقَّق
    منه ولو لم يُقرأ.
    """
    src = path.read_text(encoding="utf-8")
    # داخل نصوص SQL وحدها: `g.get("id")` في بايثون نداءُ قاموسٍ لا عمود،
    # واحتسابه يجعل الفحص يصيح على شيفرةٍ سليمة فيُهمَل.
    sql = " ".join(
        m.group(0)
        for m in re.finditer(r"(?is)\bSELECT\b.*?(?=\"\"\"|\'\'\'|$)", src)
    )
    used = {c for c in re.findall(r"\bg\.([a-z_]+)\b", sql) if c != "get"}
    unknown = used - GUEST_COLUMNS
    assert not unknown, "%s: أعمدة guests غير موجودة: %s" % (path.name, sorted(unknown))
