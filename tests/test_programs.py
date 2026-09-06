#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_programs.py — تقييد بطاقات البرامج بالصلاحية (البند ٢).

يفحص: programs_for لكل دور (المالك يرى الكل، والأدوار المحدودة لا ترى ما
لا صلاحية له)، أن كل برنامجٍ يشير إلى صفحةٍ موجودة، ونقطة /api/staff/programs.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.programs import PROGRAMS, programs_for  # noqa: E402
from services.staff_roles import permissions_for  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sess(role):
    return {"client_id": "h1", "role": role, "permissions": permissions_for(role)}


class TestProgramsFor:
    def test_owner_sees_everything(self):
        allowed = programs_for({"permissions": ["*"]})
        assert allowed == [pid for pid, _ in PROGRAMS]

    def test_receptionist_subset(self):
        allowed = set(programs_for(_sess("receptionist")))
        assert "01-guests" in allowed and "07-pos" in allowed and "17-bookings" in allowed
        # لا صلاحية له في هذه — يجب أن تُخفى (كسرٌ قبل الوثوق)
        for hidden in ("09-hr", "00-setup", "04-inventory", "05-warehouse", "13-staff-tracker"):
            assert hidden not in allowed, f"{hidden} يجب أن يُخفى عن الاستقبال"

    def test_housekeeping_subset(self):
        allowed = set(programs_for(_sess("housekeeping")))
        assert "05-warehouse" in allowed and "08-smart-key" in allowed
        for hidden in ("01-guests", "06-accounting", "07-pos", "09-hr"):
            assert hidden not in allowed

    def test_permissionless_program_always_visible(self):
        # 16-staff-app صلاحيته None → يراه أضيق الأدوار
        assert "16-staff-app" in programs_for(_sess("pos_cashier"))

    def test_no_permissions_still_sees_only_open_programs(self):
        allowed = programs_for({"permissions": []})
        assert allowed == ["16-staff-app"]


class TestProgramsPointToRealPages:
    def test_every_program_has_a_page(self):
        for pid, _ in PROGRAMS:
            page = os.path.join(_ROOT, "static", "dheuof", "modules", pid, "index.html")
            assert os.path.exists(page), f"البرنامج {pid} لا صفحة له: {page}"


try:
    from main import app, _client_sessions
    from fastapi.testclient import TestClient
    HAS_APP = True
except Exception:
    HAS_APP = False


@pytest.mark.skipif(not HAS_APP, reason="App not importable")
class TestProgramsEndpoint:
    def test_anonymous_is_unauthorized(self):
        r = TestClient(app, raise_server_exceptions=False).get("/api/staff/programs")
        assert r.status_code == 401

    def test_receptionist_gets_filtered_list(self):
        from datetime import datetime
        _client_sessions["tok-recep"] = {
            "client_id": "h1", "role": "receptionist",
            "permissions": permissions_for("receptionist"),
            "created_at": datetime.now().isoformat(),
        }
        c = TestClient(app, raise_server_exceptions=False)
        c.cookies.set("client_token", "tok-recep")
        r = c.get("/api/staff/programs")
        assert r.status_code == 200
        allowed = r.json()["data"]["allowed"]
        assert "01-guests" in allowed and "09-hr" not in allowed
