#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_dashboard_wiring.py — الجافاسكربت والصفحة يتحدّثان اللغة نفسها

`document.getElementById('x').value` على عنصرٍ غير موجود يرمي
`TypeError` فوراً، فيتوقّف تنفيذ الدالة عند أول حقلٍ مفقود. ثمانية
نماذج إضافة كانت تقرأ أسماء حقولٍ لا وجود لها — «حفظ الضيف» لم يحفظ
ضيفاً قط — وستُّ دوالِّ عرضٍ تنهار فتقطع أقسامها كاملة.

والسبب دريفٌ صامت: تُعاد تسمية الحقول في HTML ولا يتبعها الجافاسكربت،
ولا شيء يشتكي حتى يضغط المستخدم الزرّ.

وكذلك المسارات: اللوحة كانت تنادي البادئة `m04` وهي غير موجودة في
الخادم إطلاقاً — الحقيقيّتان `m07` لنقاط البيع و`m06acc` للمحاسبة.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = ROOT / "static/dashboard.html"
JS_DIR = ROOT / "static/js"

HTML = DASHBOARD.read_text(encoding="utf-8")
HTML_IDS = set(re.findall(r'id="([A-Za-z0-9_-]+)"', HTML))
JS_FILES = sorted(JS_DIR.glob("*.js"))


@pytest.mark.parametrize("path", JS_FILES, ids=lambda p: p.name)
def test_every_element_written_to_exists_in_the_page(path):
    """
    كتابةٌ في عنصرٍ مفقود تُوقف الدالة عند أول سطر — لا تُتجاهَل.
    """
    # كل مرجعٍ لا ما اتّصل بـ`.innerHTML` مباشرةً: الشيفرة كثيراً ما
    # تُسند العنصر لمتغيّر أولاً — `var el = getElementById('x'); el.innerHTML`
    # — فالفحص المقصور على السلسلة المباشرة يفوته، وقد فاته `hkTasksTable`
    # فعلاً بينما القسم ينهار عند كل فتح.
    src = path.read_text(encoding="utf-8")
    missing = {
        m.group(1)
        for m in re.finditer(r"getElementById\('([A-Za-z0-9_-]+)'\)", src)
        if m.group(1) not in HTML_IDS
    }
    assert not missing, "%s: عناصر غير موجودة في الصفحة: %s" % (
        path.name, ", ".join(sorted(missing))
    )


# ── المسارات المُناداة موجودة في الخادم ───────────────────────────
def _server_paths() -> set:
    """
    المسارات الكاملة لا البادئات وحدها.

    مقارنةُ البادئة تمرّ على `/api/m04/pos/items` لأن `/api/m04` بادئةٌ
    موجودة فعلاً — والمسار ليس فيها. فحصٌ يمرّ على العلّة التي وُضع لها
    أسوأ من غيابه: يمنح ثقةً كاذبة.
    """
    out = set()
    for f in (ROOT / "routes").glob("*.py"):
        src = f.read_text(encoding="utf-8")
        m = re.search(r'APIRouter\(prefix="([^"]*)"', src)
        prefix = m.group(1) if m else ""
        for route in re.findall(r'@router\.\w+\("([^"]+)"', src):
            full = route if route.startswith("/api/") else prefix + route
            out.add(re.sub(r"\{[^}]+\}", "*", full).rstrip("/"))
    return out


def _matches(called: str, known: set) -> bool:
    """
    يقبل المسار الحرفي، أو ما يطابق قالباً فيه معاملٌ في المسار.

    و`'/api/invoices/' + id + '/pay'` يصل هنا مقطوعاً عند `/api/invoices/*`
    فيُقبل إن كان بادئةَ مسارٍ معروف: الجزء الباقي يُلحق وقت التنفيذ.
    """
    if called in known:
        return True
    for k in known:
        if "*" in k:
            pat = "^" + re.escape(k).replace(r"\*", r"[^/]+") + "$"
            if re.match(pat, called):
                return True
        if called.endswith("/*") and k.startswith(called[:-1]):
            return True
    return False


@pytest.mark.parametrize("path", JS_FILES, ids=lambda p: p.name)
def test_no_call_to_a_path_the_server_does_not_serve(path):
    """
    `/api/m04/pos/items` و`/api/m04/cashier/summary` و`/api/channels/status`
    كانت تُنادى ولا وجود لها — كل واحدٍ ٤٠٤ صامت يبتلعه `apiFetch` ويُعيد
    `null`، فيبدو القسم فارغاً لا معطّلاً، ولا شيء يقول إن شيئاً انكسر.
    """
    src = path.read_text(encoding="utf-8")
    known = _server_paths()
    # النصّ المقطوع قبل تسلسلٍ (`'/api/m02/checkin/' + id`) ليس مساراً
    # كاملاً؛ احتسابه يجعل الفحص يصيح على شيفرةٍ سليمة فيُهمَل ثم يُطفأ.
    # فيُقبل ما يُطابق قالباً بمعاملٍ عند إلحاق جزءٍ به.
    called = set()
    for m in re.finditer(r"'(/api/[A-Za-z0-9_/-]+?)(/?)'(\s*\+)?", src):
        p_, trailing_slash, concatenated = m.group(1), m.group(2), m.group(3)
        called.add((p_ + "/*") if (trailing_slash and concatenated) else p_)

    unknown = sorted(c for c in called if not _matches(c, known))
    assert not unknown, "%s: مسارات لا يخدمها الخادم: %s" % (
        path.name, ", ".join(unknown)
    )
