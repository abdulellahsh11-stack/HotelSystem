#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_asset_cache.py — بصمة الإصدار وترويسات التخزين

العطل الذي يُصلحه هذا: كل ملفات JS/CSS كانت تُخدَم بـ

    Cache-Control: public, max-age=604800, immutable

بلا بصمةٍ في عنوانها. و`immutable` تعني حرفياً «لا تسأل عن هذا الملف
ثانيةً» — لا عند تحديث الصفحة ولا عند العودة إليها. فيبقى المتصفّح على
نسخةٍ قديمة **سبعة أيام** بعد كل نشر.

وهذا يُنتج أسوأ صنفٍ من الأعطال: يقول المطوّر «أصلحتُه» صادقاً، ويقول
المستخدم «لا يعمل» صادقاً، وكلاهما ينظر إلى نسخةٍ مختلفة من المنصة.
وقد وقع فعلاً في هذا المستودع أكثر من مرة.
"""
from __future__ import annotations

import warnings

import pytest

warnings.filterwarnings("ignore")

from services.asset_version import (  # noqa: E402
    cache_header, compute_version, get_version, reset_version, stamp_html,
)


# ── البصمة ─────────────────────────────────────────────────────
def test_a_version_is_produced():
    v = get_version()
    assert v and v != "dev" and len(v) == 10


def test_the_version_is_stable_within_one_process():
    """لو تغيّرت بين طلبين لبطلت `immutable` على عنوانٍ لم يتغيّر محتواه."""
    assert get_version() == get_version()


def test_the_version_changes_when_a_file_changes(tmp_path):
    """جوهر الإصلاح: نشرٌ جديد ⇒ بصمةٌ جديدة ⇒ عناوين جديدة."""
    asset = tmp_path / "app.js"
    asset.write_text("var a = 1;", encoding="utf-8")
    before = compute_version(str(tmp_path))
    asset.write_text("var a = 2; // إصلاح", encoding="utf-8")
    import os
    os.utime(asset, (0, 0))              # وقتٌ مختلف صراحةً
    assert compute_version(str(tmp_path)) != before


def test_an_unreadable_root_does_not_crash_startup():
    """بصمةٌ ثابتة أسوأ من لا شيء، وانهيار المنصة أسوأ منهما."""
    assert compute_version("/لا-وجود-له") == "dev"


# ── الترويسات ──────────────────────────────────────────────────
def test_a_correctly_versioned_asset_may_be_cached_forever():
    header = cache_header("/static/js/app.js", get_version())
    assert "immutable" in header and "31536000" in header


def test_an_unversioned_asset_is_never_immutable():
    """
    هذا هو العطل الأصلي حرفياً: `immutable` على عنوانٍ بلا بصمة تعني
    أسبوعاً كاملاً على نسخةٍ قديمة.
    """
    header = cache_header("/static/js/app.js", None)
    assert "immutable" not in header
    assert "no-cache" in header


def test_a_stale_version_is_never_immutable():
    """متصفّحٌ يحمل صفحةً قديمة يطلب ببصمةٍ قديمة — يجب أن يُعاد التحقق."""
    header = cache_header("/static/js/app.js", "بصمة-قديمة")
    assert "immutable" not in header


@pytest.mark.parametrize("path", [
    "/static/index.html",
    "/static/dheuof/modules/01-guests/registration.html",
])
def test_html_is_never_cached(path):
    """الصفحة هي التي تحمل البصمات الجديدة؛ تخزينُها يُبطل الآلية كلها."""
    assert "no-cache" in cache_header(path, None)


def test_images_are_cached_but_not_immutable():
    header = cache_header("/static/img/logo.png", None)
    assert "max-age" in header and "immutable" not in header


# ── حقن البصمة في HTML ─────────────────────────────────────────
def test_script_and_style_references_are_stamped():
    html = ('<script src="/static/js/a.js"></script>'
            '<link href="/static/css/b.css" rel="stylesheet">')
    out = stamp_html(html, "abc123")
    assert 'src="/static/js/a.js?v=abc123"' in out
    assert 'href="/static/css/b.css?v=abc123"' in out


def test_external_resources_are_left_alone():
    """بصمتُنا لا معنى لها على خادمٍ آخر — وإلحاقها قد يكسر الطلب."""
    html = '<link href="https://fonts.googleapis.com/css2?family=X" rel="stylesheet">'
    assert stamp_html(html, "abc123") == html


def test_non_asset_links_are_left_alone():
    html = '<a href="/static/dheuof/index.html">الرئيسية</a>'
    assert stamp_html(html, "abc123") == html


def test_an_existing_query_string_is_preserved():
    html = '<script src="/static/js/a.js?module=1"></script>'
    out = stamp_html(html, "abc123")
    assert "module=1" in out and "v=abc123" in out


def test_stamping_twice_does_not_duplicate_the_marker():
    """إعادة الختم تُستبدل لا تُضاعَف — وإلا تراكمت `?v=` عند كل مرور."""
    once = stamp_html('<script src="/static/js/a.js"></script>', "old")
    twice = stamp_html(once, "new")
    assert twice.count("v=") == 1
    assert "v=new" in twice and "old" not in twice


def test_a_page_without_assets_is_unchanged():
    html = "<p>لا ملفات هنا</p>"
    assert stamp_html(html, "abc123") == html


def test_the_stamp_uses_the_current_version_by_default():
    reset_version()
    out = stamp_html('<script src="/static/js/a.js"></script>')
    assert f"v={get_version()}" in out


# ── الصفحة تصل كاملةً حتى مع الضغط ─────────────────────────────
#
# عطلٌ أوقف الموقع بالكامل: ختمُ البصمة كان يعمل **بعد** GZip، فيتلقّى
# جسماً مضغوطاً ويحاول فكّه كنصّ — وقد استهلك المُكرِّر حينها، فتخرج
# الصفحة **فارغة**. وكل متصفّح يطلب gzip، فسقط الموقع للجميع.
#
# ولم تكشفه اختباراتي لأن `curl` لا يطلب الضغط افتراضياً، ولا `TestClient`.
# فهذه الاختبارات تطلبه صراحةً.
import warnings as _w  # noqa: E402

_w.filterwarnings("ignore")

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def app_client():
    from app_core import _client_sessions, _lock
    from main import app

    class _DB:
        use_postgres = True

        def health(self):
            return {"ok": True}

        def execute(self, *a, **k):
            return None if k.get("fetch") == "one" else []

    app.state.db = _DB()

    class _Cfg:
        pass_salt = "s"
        admin_pass_hash = ""
        owner_client_id = ""

    app.state.cfg = _Cfg()
    with _lock:
        _client_sessions.clear()
    yield TestClient(app, raise_server_exceptions=False)
    with _lock:
        _client_sessions.clear()


GZIP = {"accept-encoding": "gzip, deflate, br", "accept": "text/html"}


@pytest.mark.parametrize("path", ["/", "/static/index.html"])
def test_a_page_is_not_empty_when_the_browser_asks_for_gzip(app_client, path):
    """
    الحارس الذي كان ناقصاً — وغيابُه أسقط الموقع.

    الصفحة يجب أن تصل بجسمٍ حقيقي حين يُطلب الضغط، تماماً كما يطلبه كل
    متصفّح. صفرُ بايت باستجابة ٢٠٠ هو بالضبط ما رآه المستخدم.
    """
    r = app_client.get(path, headers=GZIP)
    assert r.status_code == 200
    assert len(r.content) > 0, f"{path} خرجت فارغة مع gzip"
    assert "<" in r.text, f"{path} ليست HTML صالحة"


@pytest.mark.parametrize("path", ["/", "/static/index.html"])
def test_the_body_is_identical_with_and_without_compression(app_client, path):
    """الضغط نقلٌ لا تغيير: المحتوى المفكوك يجب أن يطابق غير المضغوط."""
    plain = app_client.get(path, headers={"accept-encoding": "identity"})
    zipped = app_client.get(path, headers=GZIP)
    assert plain.text == zipped.text


def test_stamping_still_happens_under_compression(app_client):
    """
    الإصلاح الأول (تخطّي الجسم المضغوط) أعاد الصفحات لكنه ألغى الختم —
    والصفحة هي التي تحمل البصمات. فالترتيب الصحيح: يُختَم ثم يُضغط.
    """
    body = app_client.get("/static/dheuof/modules/01-guests/portal.html",
                          headers=GZIP).text
    if "/static/" not in body:
        pytest.skip("الصفحة بلا ملفات خارجية")
    assert "?v=" in body, "لم تُختم الصفحة تحت الضغط"


def test_gzip_is_registered_after_the_stamping_middleware():
    """
    يفشل إن أُعيد ترتيب الوسطاء يوماً.

    Starlette يجعل آخر وسيطٍ يُسجَّل هو الأبعد عن التطبيق. فالضغط يجب أن
    يكون الأخير تسجيلاً ليعمل الختم قبله على نصٍّ لا على بايتاتٍ مضغوطة.
    """
    from fastapi.middleware.gzip import GZipMiddleware

    from main import app

    classes = [m.cls for m in app.user_middleware]
    assert GZipMiddleware in classes, "الضغط غير مُسجَّل"
    # user_middleware[0] هو الأخير تسجيلاً = الأبعد = يضغط آخِراً
    assert classes[0] is GZipMiddleware, (
        "الضغط ليس الأبعد — سيرى الختمُ جسماً مضغوطاً وتخرج الصفحة فارغة"
    )
