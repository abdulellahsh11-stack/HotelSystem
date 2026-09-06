#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_i18n.py — طبقة تعدّد اللغة (البند ١).

يفحص: خدمة i18n (اللغة والاتجاه والحزمة والحلّ)، نقطة /api/i18n/bundle
وتثبيت الكوكي، والمفردات ثنائية اللغة.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import i18n  # noqa: E402
from db.schema_listings import kind_labels, amenity_labels, UNIT_KINDS  # noqa: E402


class TestI18nService:
    def test_unknown_lang_falls_back_to_arabic(self):
        assert i18n.normalize("fr") == "ar"
        assert i18n.normalize("") == "ar"
        assert i18n.normalize(None) == "ar"

    def test_supported_langs(self):
        assert i18n.normalize("en") == "en"
        assert i18n.normalize("EN") == "en"
        assert i18n.normalize("ar") == "ar"

    def test_direction(self):
        assert i18n.direction("ar") == "rtl"
        assert i18n.direction("en") == "ltr"
        assert i18n.direction("zz") == "rtl"   # يعود للعربية → rtl

    def test_strings_have_both_languages(self):
        ar = i18n.strings("ar")
        en = i18n.strings("en")
        assert ar.get("app.name") == "ضيوف"
        assert en.get("app.name") == "Dheuof"
        # الإنجليزية تُكمَّل بالعربية إن نقص مفتاح — لا فراغ
        assert set(ar).issubset(set(en)) or set(en).issuperset(set(ar) & set(en))


class TestI18nBilingualVocabulary:
    def test_english_labels_differ_and_share_keys(self):
        ar = kind_labels("ar")
        en = kind_labels("en")
        assert set(ar) == set(UNIT_KINDS)       # نفس المفاتيح
        assert set(en) == set(UNIT_KINDS)
        assert ar["chalet"] == "شاليه"
        assert en["chalet"] == "Chalet"

    def test_amenities_english(self):
        en = amenity_labels("en")
        assert en["pool"] == "Pool"
        assert en["private_pool"] == "Private pool"

    def test_unknown_lang_returns_arabic(self):
        assert kind_labels("fr")["chalet"] == "شاليه"


try:
    from main import app
    from fastapi.testclient import TestClient
    HAS_APP = True
except Exception:
    HAS_APP = False


@pytest.mark.skipif(not HAS_APP, reason="App not importable")
class TestI18nBundleEndpoint:
    def _c(self):
        return TestClient(app, raise_server_exceptions=False)

    def test_default_is_arabic_rtl(self):
        r = self._c().get("/api/i18n/bundle")
        assert r.status_code == 200
        b = r.json()
        assert b["lang"] == "ar" and b["dir"] == "rtl"
        assert b["strings"]["app.name"] == "ضيوف"

    def test_english_param_flips_ltr_and_sets_cookie(self):
        r = self._c().get("/api/i18n/bundle?lang=en")
        assert r.status_code == 200
        b = r.json()
        assert b["lang"] == "en" and b["dir"] == "ltr"
        assert b["strings"]["app.name"] == "Dheuof"
        assert "lang=en" in r.headers.get("set-cookie", "")

    def test_unknown_param_falls_back_arabic(self):
        b = self._c().get("/api/i18n/bundle?lang=fr").json()
        assert b["lang"] == "ar" and b["dir"] == "rtl"

    def test_cookie_is_honoured(self):
        c = self._c()
        c.cookies.set("lang", "en")
        b = c.get("/api/i18n/bundle").json()
        assert b["lang"] == "en" and b["dir"] == "ltr"
