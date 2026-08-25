#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_smart_alerts.py — الإنذارات والتبليغ ورصيد الرسائل

يثبت ثلاثة أشياء يصعب اكتشاف خللها بالتشغيل اليدوي:

١ — كل قناة مستقلة: فشل الواتساب لا يمنع البريد.
٢ — رصيد الرسائل يُخصم قبل الإرسال، ويُسترد إن فشل.
٣ — العزل: إنذارات منشأة لا تُرى ولا تُعدَّل من أخرى.
"""
from __future__ import annotations

import warnings
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

from app_core import _client_sessions, _lock  # noqa: E402
from main import app  # noqa: E402
from services.alert_notifier import sms_units  # noqa: E402

A, B = "hotel_A", "hotel_B"


class AlertsDB:
    """قاعدة وهمية تُطبّق الخصم المشروط كما تفعل PostgreSQL."""

    use_postgres = True

    def __init__(self):
        self.alerts: list[dict] = []
        self.deliveries: list[dict] = []
        self.credits: dict[str, int] = {}
        self.credit_log: list[dict] = []
        self._next = 1

    def health(self):
        return {"ok": True}

    def execute(self, sql, params=(), fetch=None):
        s = " ".join(sql.split())
        low = s.lower()
        p = tuple(params or ())

        if low.startswith("insert into smart_alerts"):
            row = {
                "id": self._next, "client_id": p[0], "alert_type": p[1],
                "severity": p[2], "room_number": p[3], "lock_id": p[4],
                "title": p[5], "message": p[6], "status": "active",
                "created_at": "2026-08-24", "resolved_at": None,
                "snoozed_until": None,
            }
            self.alerts.append(row)
            self._next += 1
            return dict(row)

        if "from smart_alerts where" in low and low.startswith("select *"):
            cid = p[0]
            rows = [a for a in self.alerts if a["client_id"] == cid]
            if len(p) > 1:
                rows = [a for a in rows if a["status"] == p[1]]
            return [dict(r) for r in rows]

        if low.startswith("select id from smart_alerts"):
            aid, cid = p
            return next((a for a in self.alerts
                         if a["id"] == aid and a["client_id"] == cid), None)

        if low.startswith("update smart_alerts"):
            aid, cid = p[-2], p[-1]
            for a in self.alerts:
                if a["id"] == aid and a["client_id"] == cid:
                    a["status"] = ("resolved" if "resolved" in low
                                   else "snoozed" if "snoozed" in low else "active")
            return 1

        if low.startswith("insert into alert_deliveries"):
            self.deliveries.append({
                "client_id": p[0], "alert_id": p[1], "channel": p[2],
                "recipient": p[3], "status": p[4], "error": p[5],
                "sent_at": "2026-08-24",
            })
            return []

        if "from alert_deliveries" in low:
            cid, aid = p
            return [d for d in self.deliveries
                    if d["client_id"] == cid and d["alert_id"] == aid]

        if low.startswith("select balance from sms_credits"):
            cid = p[0]
            return {"balance": self.credits.get(cid, 0)}

        if low.startswith("insert into sms_credits"):
            cid, amount = p
            self.credits[cid] = self.credits.get(cid, 0) + amount
            return []

        if low.startswith("update sms_credits set balance"):
            units, cid, need = p
            # الشرط الذرّي: لا خصم إن لم يكفِ الرصيد
            if self.credits.get(cid, 0) >= need:
                self.credits[cid] -= units
                return 1
            return 0

        if low.startswith("insert into sms_credit_log"):
            self.credit_log.append({"client_id": p[0], "delta": p[1]})
            return []

        if "from sms_credit_log" in low:
            return [{"delta": e["delta"], "reason": "", "balance_after": 0,
                     "created_at": "2026-08-24", "created_by": ""}
                    for e in self.credit_log if e["client_id"] == p[0]]
        return None if fetch == "one" else []


class _Store:
    def get_client(self, cid):
        return {"id": cid, "email": "owner@hotel.sa", "phone": "0500000000",
                "settings": {}}


@pytest.fixture
def client():
    app.state.db = AlertsDB()
    app.state.store = _Store()

    class _Cfg:
        smtp_host = ""
        pass_salt = "s"
        admin_pass_hash = ""

    app.state.cfg = _Cfg()
    with _lock:
        _client_sessions.clear()
        now = datetime.now().isoformat()
        _client_sessions["tokA"] = {"client_id": A, "role": "owner",
                                    "permissions": ["*"], "created_at": now}
        _client_sessions["tokB"] = {"client_id": B, "role": "owner",
                                    "permissions": ["*"], "created_at": now}
        _client_sessions["hk"] = {"client_id": A, "role": "housekeeping",
                                  "permissions": ["rooms.read"], "created_at": now}
    yield TestClient(app, raise_server_exceptions=False)
    with _lock:
        _client_sessions.clear()


AS_A = {"client_token": "tokA"}


def _create(client, **over):
    body = {"alert_type": "door_open", "severity": "critical",
            "room_number": "101", "message": "الباب مفتوح منذ ١٠ دقائق"}
    body.update(over)
    return client.post("/api/m09/alerts", json=body, cookies=AS_A)


# ── الإنذارات ──────────────────────────────────────────────────
def test_an_alert_is_recorded_and_listed(client):
    assert _create(client).status_code == 200
    data = client.get("/api/m09/alerts", cookies=AS_A).json()["data"]
    assert len(data["alerts"]) == 1
    assert data["alerts"][0]["type_label"] == "باب مفتوح"
    assert data["alerts"][0]["severity_label"] == "حرج"
    assert data["by_severity"]["critical"] == 1


@pytest.mark.parametrize("field,value", [
    ("alert_type", "حريق"),      # نوع غير مدعوم
    ("severity", "مرعب"),         # خطورة مجهولة
])
def test_invalid_alert_input_is_refused(client, field, value):
    assert _create(client, **{field: value}).status_code == 400


def test_resolving_an_alert_updates_its_status(client):
    _create(client)
    aid = app.state.db.alerts[0]["id"]
    assert client.patch(f"/api/m09/alerts/{aid}", json={"status": "resolved"},
                        cookies=AS_A).status_code == 200
    data = client.get("/api/m09/alerts?status=active", cookies=AS_A).json()["data"]
    assert data["alerts"] == []


# ── التبليغ ────────────────────────────────────────────────────
def test_each_channel_is_attempted_independently(client):
    """
    فشل قناة لا يمنع غيرها: إنذارٌ يصل بقناة واحدة أفضل من إنذار لا
    يصل لأن قناةً تعطّلت.
    """
    res = _create(client).json()
    channels = {d["channel"] for d in res["deliveries"]}
    assert channels == {"whatsapp", "email", "sms"}, "لم تُحاوَل القنوات الثلاث"


def test_every_delivery_attempt_is_logged(client):
    _create(client)
    aid = app.state.db.alerts[0]["id"]
    rows = client.get(f"/api/m09/alerts/{aid}/deliveries", cookies=AS_A).json()["data"]
    assert len(rows) == 3
    assert all(r["status"] in ("sent", "failed") for r in rows)


def test_a_failed_channel_records_its_reason(client):
    """«فشل» بلا سبب لا يُشخَّص."""
    res = _create(client).json()
    failed = [d for d in res["deliveries"] if d["status"] == "failed"]
    assert failed, "لم تفشل أي قناة في هذه البيئة"
    assert all(d["error"] for d in failed)


# ── رصيد الرسائل ───────────────────────────────────────────────
def test_topping_up_raises_the_balance(client):
    assert client.get("/api/m09/sms-credit", cookies=AS_A).json()["data"]["balance"] == 0
    r = client.post("/api/m09/sms-credit/topup", json={"amount": 100}, cookies=AS_A)
    assert r.status_code == 200
    assert r.json()["data"]["balance"] == 100


@pytest.mark.parametrize("amount", [0, -5, 200_000])
def test_invalid_topup_is_refused(client, amount):
    assert client.post("/api/m09/sms-credit/topup", json={"amount": amount},
                       cookies=AS_A).status_code == 400


def test_sms_without_credit_reports_the_reason(client):
    """بلا رصيد لا تُرسل، ويُقال السبب صراحةً."""
    res = _create(client).json()
    sms = next(d for d in res["deliveries"] if d["channel"] == "sms")
    assert sms["status"] == "failed"
    assert "رصيد" in sms["error"]


def test_a_failed_send_refunds_the_credit(client):
    """
    الخصم مقابل رسالةٍ لم تُرسل ظلم. المزوّد غير مُهيّأ هنا، فكل
    إرسال يفشل — والرصيد يجب أن يعود كما كان.
    """
    client.post("/api/m09/sms-credit/topup", json={"amount": 10}, cookies=AS_A)
    before = client.get("/api/m09/sms-credit", cookies=AS_A).json()["data"]["balance"]
    _create(client)
    after = client.get("/api/m09/sms-credit", cookies=AS_A).json()["data"]["balance"]
    assert after == before, f"لم يُسترد الرصيد: {before} → {after}"


@pytest.mark.parametrize("text,expected", [
    ("", 1),
    ("قصيرة", 1),
    ("ا" * 70, 1),
    ("ا" * 71, 2),
    ("ا" * 210, 3),
])
def test_sms_units_follow_message_length(text, expected):
    """الرسالة العربية تُقسَّم عند المزوّد، فالتكلفة بالطول لا بالعدد."""
    assert sms_units(text) == expected


# ── العزل والصلاحيات ───────────────────────────────────────────
def test_alerts_of_another_tenant_are_invisible(client):
    _create(client)
    other = client.get("/api/m09/alerts", cookies={"client_token": "tokB"})
    assert other.json()["data"]["alerts"] == []


def test_another_tenant_cannot_resolve_an_alert(client):
    _create(client)
    aid = app.state.db.alerts[0]["id"]
    r = client.patch(f"/api/m09/alerts/{aid}", json={"status": "resolved"},
                     cookies={"client_token": "tokB"})
    assert r.status_code == 404
    assert app.state.db.alerts[0]["status"] == "active"


def test_housekeeping_can_read_but_not_create_alerts(client):
    """الإشراف الداخلي يرى الإنذارات ولا يُنشئها."""
    hk = {"client_token": "hk"}
    assert client.get("/api/m09/alerts", cookies=hk).status_code == 200
    assert client.post("/api/m09/alerts", json={"alert_type": "door_open"},
                       cookies=hk).status_code == 403


def test_topping_up_requires_the_settings_permission(client):
    assert client.post("/api/m09/sms-credit/topup", json={"amount": 10},
                       cookies={"client_token": "hk"}).status_code == 403
