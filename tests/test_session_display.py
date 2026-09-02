#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_session_display.py — الواجهة تعرف من دخل

الجلسة الحقيقية كوكي `HttpOnly` **لا يراها الجافاسكربت إطلاقاً**. وكان
الشريط يقرر من `localStorage.dheuof_session` — وهو فارغ دائماً لأن
`/login` لا يكتبه. فتُعلن كل صفحةٍ «زائر» لمالكٍ داخلٍ فعلاً، مع زرّ
«سجّل / دخول» يوحي أن دخوله فشل وهو ناجح.

وهذا صنفُ عطلٍ لا تكشفه اختبارات الخادم: الدخول يعمل، والكوكي تُضبط،
و`/api/rooms` يعود ٢٠٠ — والمستخدم مع ذلك يرى نفسه خارج النظام.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIDEBAR = ROOT / "static/dheuof/shared/sidebar.js"
STAFF_ROUTES = ROOT / "routes/staff_accounts.py"


def test_sidebar_asks_the_server_not_only_local_storage():
    js = SIDEBAR.read_text(encoding="utf-8")
    assert "/api/staff/me" in js, "الشريط لا يسأل الخادم عن الجلسة"
    assert "credentials: 'same-origin'" in js, "النداء بلا كوكي فلن يعرف الجلسة"


def test_server_answer_wins_over_local_storage():
    """
    `localStorage` ذاكرةٌ مؤقّتة تمنع وميضاً، لا مصدرَ حقيقة. لو عادت
    الأولوية إليها عاد العطل: قيمةٌ قديمة تُبقي «زائر» بعد الدخول.
    """
    js = SIDEBAR.read_text(encoding="utf-8")
    m = re.search(r"function getSession\(\)\s*\{(.*?)\n  \}", js, re.S)
    assert m, "getSession غير موجودة"
    body = m.group(1)
    assert body.index("SERVER_SESSION") < body.index("localStorage"), \
        "localStorage تسبق ردّ الخادم"


def test_me_endpoint_exposes_the_property_name():
    """الشريط يعرض اسم المنشأة؛ بدونه يبقى الاسم الافتراضي المكتوب."""
    src = STAFF_ROUTES.read_text(encoding="utf-8")
    assert '"property_name"' in src


def test_the_redraw_is_guarded_against_a_visitor():
    """زائرٌ بلا جلسة يجب أن يبقى زائراً — لا أن يُرسم مشتركاً بحقول فارغة."""
    js = SIDEBAR.read_text(encoding="utf-8")
    assert "if (!me || !me.client_id) return;" in js
