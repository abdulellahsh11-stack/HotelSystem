#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_guest_required_fields.py — الحقول الإلزامية لتسجيل الضيف (البند ٥).

يفحص: منطق الخدمة (الافتراضي، التنقية، الكشف)، وفرض الخادم على /api/guests
(كسرٌ قبل الوثوق: حقلٌ مُفعَّل إلزامياً وغائبٌ يمنع الحفظ ٤٢٢، وتعطيله يسمح).
"""
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import guest_fields as gf  # noqa: E402


class TestGuestFieldsService:
    def test_default_required(self):
        assert gf.get_required(None) == ["full_name", "id_number"]
        assert gf.get_required({}) == ["full_name", "id_number"]

    def test_custom_required_sanitized(self):
        client = {"settings": {"guest_required_fields":
                               ["full_name", "absher_phone", "bogus", "full_name"]}}
        # المعروف فقط، بلا تكرار
        assert gf.get_required(client) == ["full_name", "absher_phone"]

    def test_sanitize_drops_unknown(self):
        assert gf.sanitize(["id_number", "xyz", "email"]) == ["id_number", "email"]

    def test_missing_detects_empty_and_absent(self):
        data = {"full_name": "  ", "id_number": "1"}
        miss = gf.missing_required(data, ["full_name", "id_number", "absher_phone"])
        assert set(miss) == {"full_name", "absher_phone"}   # فارغ + غائب
        assert gf.missing_required({"full_name": "أحمد", "id_number": "1"},
                                   ["full_name", "id_number"]) == []


# ── فرض الخادم عبر HTTP ────────────────────────────────────────
try:
    from main import app, _client_sessions
    from app_core import _lock
    from fastapi.testclient import TestClient
    HAS_APP = True
except Exception:
    HAS_APP = False


class _FakeStore:
    """مخزنٌ صغير يكفي لمسار الضيوف: get_client يحمل الإعداد المطلوب."""
    def __init__(self, required):
        self._required = required
        self.saved = None

    def get_client(self, cid):
        return {"id": cid, "settings": {"guest_required_fields": self._required}}

    def save_client(self, client):
        self.saved = client
        return client

    def save_guest(self, cid, data):
        d = dict(data)
        d.setdefault("id", 1)
        return d

    def get_guests(self, cid):
        return []


@pytest.mark.skipif(not HAS_APP, reason="App not importable")
class TestEnforcementEndpoint:
    def setup_method(self):
        with _lock:
            _client_sessions["own"] = {
                "client_id": "h1", "role": "owner",
                "permissions": ["*"], "created_at": datetime.now().isoformat(),
            }
        self._orig = getattr(app.state, "store", None)

    def teardown_method(self):
        app.state.store = self._orig

    def _client(self, required):
        app.state.store = _FakeStore(required)
        c = TestClient(app, raise_server_exceptions=False)
        c.cookies.set("client_token", "own")
        return c

    def test_missing_required_field_blocks_save(self):
        c = self._client(["full_name", "id_number", "absher_phone"])
        r = c.post("/api/guests", json={"full_name": "أحمد", "id_number": "1"})
        assert r.status_code == 422, "غياب حقلٍ إلزاميٍّ مُفعَّل يجب أن يمنع الحفظ"

    def test_providing_required_field_saves(self):
        c = self._client(["full_name", "id_number", "absher_phone"])
        r = c.post("/api/guests", json={"full_name": "أحمد", "id_number": "1",
                                        "absher_phone": "0500000000"})
        assert r.status_code == 200

    def test_disabling_field_allows_save_without_it(self):
        # نفس الطلب الناقص يمرّ حين لا يكون absher_phone إلزامياً
        c = self._client(["full_name", "id_number"])
        r = c.post("/api/guests", json={"full_name": "أحمد", "id_number": "1"})
        assert r.status_code == 200

    def test_get_required_fields_endpoint(self):
        c = self._client(["full_name", "id_number", "email"])
        r = c.get("/api/guests/required-fields")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["required"] == ["full_name", "id_number", "email"]
        assert "absher_phone" in data["fields"]
