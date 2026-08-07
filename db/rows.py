#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/rows.py — قراءة القيم من صفوف النتائج بأمان.

المشكلة التي يحلّها
───────────────────
مجمّع الاتصالات يستخدم RealDictCursor، فكل صف يعود قاموساً لا صفّاً
مفهرساً بالأرقام. وكان الكود يقرأ ناتج العدّ هكذا:

    count_result = db.execute("SELECT COUNT(*) …", params, fetch="one")
    total = count_result[0] if count_result else 0

فـ `count_result[0]` يبحث عن مفتاح اسمه 0 لا عن العمود الأول، ويرفع
`KeyError: 0`. النتيجة أن أربعة مسارات قوائم كانت تُعيد HTTP 500 في كل
استدعاء: الموظفون، حجوزات القنوات، مبيعات نقاط البيع، والفواتير
المحاسبية.

والعلة صامتة في القراءة: `row[0]` يبدو صحيحاً لمن اعتاد صفوف psycopg2
العادية، ولا يظهر خطؤه إلا عند التشغيل.
"""
from __future__ import annotations

from typing import Any

__all__ = ["scalar", "count_of"]


def scalar(row: Any, default: Any = None) -> Any:
    """يُعيد القيمة الأولى من صف نتيجة، أياً كان شكله.

    يتعامل مع RealDictRow (قاموس) ومع الصف المفهرس بالأرقام ومع None،
    فلا يعتمد على نوع المؤشّر المستخدم.
    """
    if row is None:
        return default
    if isinstance(row, dict):
        values = list(row.values())
        return values[0] if values else default
    try:
        return row[0]
    except (KeyError, IndexError, TypeError):
        return default


def count_of(row: Any) -> int:
    """يُعيد ناتج ‏SELECT COUNT(*)‎ عدداً صحيحاً، وصفراً عند غياب النتيجة."""
    value = scalar(row, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
