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
