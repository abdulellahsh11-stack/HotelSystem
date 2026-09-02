#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_leads.py — الزوّار المهتمّون: من يكتب ومن يقرأ

الكتابة عامّة بالضرورة — نموذجٌ لا يقبل من زائر ليس نموذجاً. والقراءة
لمالك المنصة وحده: مالك منشأةٍ يرى قائمة عملاء منصّتك المحتملين تسريبٌ
تجاري، وليس مجرّد خطأٍ في الصلاحيات.

والاختبار هنا **بالكسر**: كل حالةٍ تبدأ بما يجب أن يُرفض.
"""
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LEADS = ROOT / "routes/leads.py"
SITE = ROOT / "static/dheuof/website/index.html"
ADMIN = ROOT / "html_pages.py"

SRC = LEADS.read_text(encoding="utf-8")


# ── الصلاحيات ───────────────────────────────────────────────────
def test_reading_requires_the_platform_owner():
    """كل مسار قراءةٍ أو تعديل خلف `require_admin` — بلا استثناء."""
    for m in re.finditer(r'@router\.(get|patch|delete)\("(/api/admin/leads[^"]*)"\)\s*\n\s*async def \w+\(([^)]*)\)',
                         SRC, re.S):
        assert "require_admin" in m.group(3), "%s بلا حارس" % m.group(2)


def test_writing_is_public_but_rate_limited():
    """
    الكتابة بلا جلسة عمداً؛ الحدّ هو ما يمنع الإغراق. حذفُه يفتح الجدول
    لآلاف السجلات المزيّفة في دقائق.
    """
    assert re.search(r'@router\.post\("/api/leads"\)\s*\nasync def create_lead\(request: Request\)', SRC)
    assert "_rate_ok" in SRC and "MAX_PER_HOUR" in SRC
    assert "status_code=429" in SRC


def test_the_ip_is_never_stored_in_full():
    """
    منصّةٌ تحفظ هويات نزلاء لا يليق بها أن تُسجّل عناوين زوّارها كاملة.
    المقطع الأخير يُصفَّر: يكفي للحدّ من الإغراق ولا يُعرّف شخصاً.
    """
    assert "_anon_ip" in SRC
    assert 'ip_prefix' in SRC
    assert "client_ip(request)" not in SRC.split("def _anon_ip")[0], \
        "العنوان يُقرأ خارج دالة التصفير"


def test_anonymises_ipv4_and_ipv6():
    import sys
    sys.path.insert(0, str(ROOT))

    class _Req:
        def __init__(self, ip): self._ip = ip
        headers = {}
        client = None

    import routes.leads as mod
    real = None
    try:
        import app_core
        real = app_core.client_ip
        app_core.client_ip = lambda r: r._ip
        assert mod._anon_ip(_Req("203.0.113.42")) == "203.0.113.0"
        assert mod._anon_ip(_Req("2001:db8:1:2:3:4:5:6")).endswith("::")
        assert mod._anon_ip(_Req("")) == "0.0.0.0"
    finally:
        if real:
            app_core.client_ip = real


# ── التحقق من المُدخَل ──────────────────────────────────────────
def test_contact_details_are_required_and_validated():
    """اسمٌ بلا وسيلة تواصل سجلٌّ لا ينفع — والغرض من النموذج التواصل."""
    assert "الاسم مطلوب" in SRC
    assert "أدخل رقم جوال أو بريداً إلكترونياً" in SRC
    assert "EMAIL_RE" in SRC and "PHONE_RE" in SRC


def test_status_values_are_closed():
    """حالةٌ مفتوحة تُفسد الفرز والعدّ بصمت."""
    assert '{"new", "contacted", "converted", "dropped"}' in SRC


# ── الواجهتان حقيقيّتان ─────────────────────────────────────────
def test_the_marketing_page_actually_posts():
    """
    كان «تواصل معنا» رابط `mailto:` فقط، فيضيع كل زائرٍ لا يفتح بريده.
    """
    html = SITE.read_text(encoding="utf-8")
    assert "/api/leads" in html, "الصفحة لا تُرسل إلى الخادم"
    assert 'id="leadForm"' in html
    assert "mailto:hello@dheuof.com" not in html, "الرابط القديم ما زال بديلاً صامتاً"


def test_the_admin_panel_shows_them():
    src = ADMIN.read_text(encoding="utf-8")
    assert "/api/admin/leads" in src, "اللوحة لا تجلبها"
    assert 'id="pane-leads"' in src and "loadLeads" in src


def test_admin_table_escapes_visitor_text():
    """
    نصّ الزائر يُعرض في لوحة مالك المنصة — وهو أخطر مكانٍ لحقن HTML:
    جلسة `admin_token` تملك كل شيء عبر كل المنشآت.
    """
    src = ADMIN.read_text(encoding="utf-8")
    assert "function escLead(" in src
    body = src[src.index("async function loadLeads"):src.index("async function setLeadStatus")]
    for field in ("full_name", "phone", "email", "hotel_name", "city", "message"):
        assert "escLead(l.%s" % field in body, "%s يُعرض بلا تهريب" % field
