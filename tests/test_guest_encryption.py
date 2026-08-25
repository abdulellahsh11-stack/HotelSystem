#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_guest_encryption.py — تشفير بيانات النزلاء وحجبها

يُثبت الآليتين معاً، وهما مختلفتان:

  **التشفير** يحمي من تسريب قاعدة البيانات — ما يصل القرص غير مقروء.
  **الصلاحيات** تحمي من مستخدمٍ غير مخوَّل داخل النظام.

من ملك أحدهما دون الآخر لم يملك حماية: قاعدةٌ مشفَّرة يقرؤها كل موظف
مكشوفة، وصلاحياتٌ محكمة على قاعدةٍ نصّية تُسرَّب بنسخةٍ احتياطية واحدة.

وأخصّ ما يُفحَص هنا: **ألّا يظهر الرقم الصريح في ما يُكتب فعلاً** — لا
في الجملة ولا في معاملاتها. اختبارٌ يفحص الواجهة وحدها كان سيمرّ على
قاعدةٍ تخزّن كل شيء صريحاً.
"""
from __future__ import annotations

import os
import warnings
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

def test_the_crypto_library_is_actually_installed():
    """
    حارسٌ ضد التخطّي الصامت.

    لو كُتب هذا الملف بـ`importorskip` لاختفت اختباراته كلها بلا ضجيج
    حين تُكسَر مكتبة التشفير — و«CI أخضر» يعني حينها «لم يُفحص شيء».
    وللمستودع سابقة: اختبارات RLS بقيت تُتخطّى صامتةً وهي تحمي صفراً.

    `cryptography` مثبَّتة في requirements.txt، فغيابها عطلٌ يستحق
    الصراخ لا التجاهل. (وقد وجدتُها فعلاً معطوبة محلياً — `_cffi_backend`
    مفقود — وكان التخطّي الصامت سيُخفي ذلك.)
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = os.urandom(32)
    nonce = os.urandom(12)
    blob = AESGCM(key).encrypt(nonce, b"probe", None)
    assert AESGCM(key).decrypt(nonce, blob, None) == b"probe"

from app_core import _client_sessions, _lock  # noqa: E402
from main import app  # noqa: E402
from services import guest_crypto as gc  # noqa: E402
from services.staff_roles import permissions_for  # noqa: E402

A, B = "hotel_A", "hotel_B"
ID_NUMBER = "1098765432"
PHONE = "+966552184422"
NAME = "سالم عبدالله العتيبي"


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv(gc.KEY_ENV, gc.generate_key())
    monkeypatch.setenv(gc.INDEX_KEY_ENV, gc.generate_key())
    return True


class GuestsDB:
    """
    قاعدة وهمية تحتفظ بما كُتب **حرفياً** لفحص ما يصل القرص.
    """

    use_postgres = True

    def __init__(self):
        self.rows: list[dict] = []
        self.written: list[tuple] = []      # كل (sql, params) كما أُرسلت
        self._next = 1

    def health(self):
        return {"ok": True}

    def execute(self, sql, params=(), fetch=None):
        low = " ".join(sql.split()).lower()
        p = tuple(params or ())
        self.written.append((low, p))

        if low.startswith("insert into guests"):
            row = {
                "id": self._next, "client_id": p[0], "id_type": p[1],
                "id_number": p[2], "full_name": p[3], "absher_phone": p[4],
                "nationality": p[5], "birth_date": p[6], "data_status": p[7],
                "source": p[8], "notes": p[9], "id_number_bidx": p[10],
                "created_at": "2026-08-25",
            }
            self.rows.append(row)
            self._next += 1
            # تُحاكي RETURNING id كما تفعل PostgreSQL: بدونها يبدو المسار
            # ناجحاً وهو لا يُعيد المعرّف الحقيقي.
            return {"id": row["id"]} if "returning id" in low else []

        if "from guests where client_id" in low and "id_number_bidx" in low:
            cid, bidx = p
            return next((dict(r) for r in self.rows
                         if r["client_id"] == cid and r.get("id_number_bidx") == bidx), None)

        if "from guests where client_id" in low and " and id = " in low:
            cid, gid = p
            return next((dict(r) for r in self.rows
                         if r["client_id"] == cid and r["id"] == gid), None)

        if "from guests where client_id" in low:
            return [dict(r) for r in self.rows if r["client_id"] == p[0]]

        return None if fetch == "one" else []


@pytest.fixture
def client(key):
    from db.store import DataStore

    db = GuestsDB()
    app.state.db = db
    store = DataStore.__new__(DataStore)
    store.db = db
    store._use_pg = True
    store.dual_write = False
    app.state.store = store

    class _Cfg:
        pass_salt = "s"
        admin_pass_hash = ""
        owner_client_id = ""

    app.state.cfg = _Cfg()
    now = datetime.now().isoformat()
    with _lock:
        _client_sessions.clear()
        for token, cid, role in (("owner", A, "owner"), ("bOwner", B, "owner")):
            _client_sessions[token] = {
                "client_id": cid, "role": role,
                "permissions": ["*"], "created_at": now,
            }
        for token, role in (("recep", "receptionist"), ("hk", "housekeeping"),
                            ("acct", "accountant")):
            _client_sessions[token] = {
                "client_id": A, "role": role,
                "permissions": permissions_for(role), "created_at": now,
            }
    yield TestClient(app, raise_server_exceptions=False), db, store
    with _lock:
        _client_sessions.clear()


AS_OWNER = {"client_token": "owner"}


def _add(c, cookies=AS_OWNER, **over):
    body = {"full_name": NAME, "id_number": ID_NUMBER, "absher_phone": PHONE,
            "birth_date": "1990-05-14", "nationality": "sa",
            "notes": "حساسية من الجلوتين"}
    body.update(over)
    return c.post("/api/guests", json=body, cookies=cookies)


# ── التشفير عند التخزين ────────────────────────────────────────
def test_the_id_number_never_reaches_the_database_in_clear(client):
    """الفحص الأهم: ما يصل القرص، لا ما تعرضه الواجهة."""
    c, db, _ = client
    assert _add(c).status_code == 200
    for sql, params in db.written:
        for value in params:
            assert ID_NUMBER not in str(value), f"رقم الهوية صريح في: {sql[:70]}"


@pytest.mark.parametrize("secret", [PHONE, "حساسية من الجلوتين", "1990-05-14"])
def test_other_sensitive_fields_are_encrypted_too(client, secret):
    c, db, _ = client
    _add(c)
    for _, params in db.written:
        for value in params:
            assert secret not in str(value), f"«{secret}» وصل صريحاً"


def test_the_stored_row_is_ciphertext(client):
    c, db, _ = client
    _add(c)
    row = db.rows[0]
    assert gc.is_encrypted(row["id_number"])
    assert gc.is_encrypted(row["absher_phone"])
    assert row["id_number"] != ID_NUMBER


def test_the_name_stays_readable_by_design(client):
    """
    الاسم لا يُشفَّر عمداً: يُبحَث به ويُعرَض في كل قائمة، وتشفيره يُعطّل
    البحث. يُحجب بالصلاحيات لا بالتشفير — وهذا قرارٌ موثَّق لا سهو.
    """
    c, db, _ = client
    _add(c)
    assert db.rows[0]["full_name"] == NAME


def test_the_birth_date_is_finally_persisted(client):
    """كان يُجمَع في النموذج ويُسقَط صامتاً — لا عمود له في جملة الإدخال."""
    c, db, _ = client
    _add(c)
    assert db.rows[0]["birth_date"], "تاريخ الميلاد ما زال يُهمَل"


def test_saving_a_guest_actually_succeeds(client):
    """
    خللٌ سابق لهذا العمل: المسار كان يخترع معرّفاً ست عشرياً لعمود
    SERIAL، فيرمي `int()` داخل `get_guest` ويعود ٥٠٠ — **في كل مرة**.
    فلم يُحفظ نزيلٌ واحد عبر هذا المسار قط، مهما بدت الواجهة سليمة.
    """
    c, db, _ = client
    r = _add(c)
    assert r.status_code == 200, f"فشل حفظ النزيل: {r.status_code} {r.text[:200]}"
    assert len(db.rows) == 1, "لم يُكتب صفٌّ رغم استجابةٍ ناجحة"


def test_the_response_carries_the_database_id(client):
    """
    الحجز التالي يشير إلى النزيل بمعرّفه. معرّفٌ مخترَع يعني حجزاً
    معلّقاً على نزيلٍ لا وجود له.
    """
    c, db, _ = client
    body = _add(c).json()["data"]
    assert str(body.get("id")) == str(db.rows[0]["id"])


# ── الاسترجاع ──────────────────────────────────────────────────
def test_an_authorised_user_reads_the_real_values(client):
    c, _, _ = client
    _add(c)
    g = c.get("/api/guests", cookies=AS_OWNER).json()["data"][0]
    assert g["id_number"] == ID_NUMBER
    assert g["absher_phone"] == PHONE
    assert g["full_name"] == NAME


def test_a_round_trip_survives_every_field(client):
    c, _, _ = client
    _add(c)
    g = c.get("/api/guests", cookies=AS_OWNER).json()["data"][0]
    assert g["notes"] == "حساسية من الجلوتين"
    assert g["birth_date"] == "1990-05-14"


# ── الصلاحيات: من يرى ماذا ─────────────────────────────────────
@pytest.mark.parametrize("token", ["owner", "recep"])
def test_the_owner_and_reception_see_the_full_record(client, token):
    """المالك والمدير والاستقبال — تسجيل الوصول لا يتمّ بلا هوية."""
    c, _, _ = client
    _add(c)
    g = c.get("/api/guests", cookies={"client_token": token}).json()["data"][0]
    assert g["id_number"] == ID_NUMBER, f"{token} لا يرى الهوية وهو مخوَّل"


@pytest.mark.parametrize("token", ["hk", "acct"])
def test_unauthorised_roles_get_a_masked_record(client, token):
    """الإشراف الداخلي والمحاسب: لا التنظيف ولا الفاتورة تحتاج هوية."""
    c, _, _ = client
    _add(c)
    body = c.get("/api/guests", cookies={"client_token": token})
    if body.status_code == 403:
        return                      # حجبٌ كامل حجبٌ أيضاً
    g = body.json()["data"][0]
    assert g["id_number"] != ID_NUMBER, f"{token} رأى رقم الهوية كاملاً"
    assert ID_NUMBER not in str(g), f"الرقم ظهر في مكانٍ آخر من الصفّ لـ{token}"
    assert g.get("_masked") is True


def test_the_masked_record_still_identifies_the_guest(client):
    """التقنيع الكامل يجعل القائمة عديمة الفائدة؛ الأربعة الأخيرة تكفي."""
    c, _, _ = client
    _add(c)
    g = c.get("/api/guests", cookies={"client_token": "hk"}).json()["data"][0]
    assert g["id_number"].endswith("5432")
    assert g["full_name"].startswith("سالم")


def test_masking_applies_to_the_single_guest_route_too(client):
    """مسارٌ واحد يُنسى يُبطل الحجب كلَّه."""
    c, db, _ = client
    _add(c)
    gid = db.rows[0]["id"]
    g = c.get(f"/api/guests/{gid}", cookies={"client_token": "hk"})
    if g.status_code == 200:
        assert ID_NUMBER not in str(g.json()), "المسار المفرد يكشف الهوية"


# ── البحث عبر الفهرس الأعمى ────────────────────────────────────
def test_a_guest_is_found_by_id_number_without_storing_it(client):
    c, db, store = client
    _add(c)
    found = store.find_guest_by_id_number(A, ID_NUMBER)
    assert found is not None, "تعطّل البحث برقم الهوية بعد التشفير"
    assert found["id_number"] == ID_NUMBER


def test_the_search_sends_a_fingerprint_not_the_number(client):
    c, db, store = client
    _add(c)
    db.written.clear()
    store.find_guest_by_id_number(A, ID_NUMBER)
    for sql, params in db.written:
        for value in params:
            assert ID_NUMBER not in str(value), "أُرسل الرقم الصريح في الاستعلام"


def test_a_wrong_number_finds_nothing(client):
    c, _, store = client
    _add(c)
    assert store.find_guest_by_id_number(A, "9999999999") is None


def test_the_search_is_scoped_to_the_tenant(client):
    """العزل يبقى قائماً: بصمةٌ واحدة لا تعبر المنشآت."""
    c, _, store = client
    _add(c)
    assert store.find_guest_by_id_number(B, ID_NUMBER) is None


def test_another_tenant_cannot_read_the_guest(client):
    c, _, _ = client
    _add(c)
    other = c.get("/api/guests", cookies={"client_token": "bOwner"}).json()["data"]
    assert other == []


# ── سلوك المفتاح ───────────────────────────────────────────────
def test_without_a_key_nothing_is_encrypted(monkeypatch):
    """
    التشفير اختياري للتطوير المحلي. لكن غيابه يجب أن يكون **صريحاً**:
    لا تشفير ولا ادّعاء تشفير.
    """
    monkeypatch.delenv(gc.KEY_ENV, raising=False)
    assert gc.is_enabled() is False
    # ولا يُشفّر صامتاً بلا مفتاح: التمرير الصامت يجعل «مشفَّر» و«صريح»
    # لا يُميَّزان، وهو بالضبط السقوط الصامت الذي يمنعه هذا المستودع.
    with pytest.raises(gc.CryptoNotConfigured):
        gc.encrypt("1234567890")


def test_a_missing_key_refuses_to_decrypt_rather_than_guess(monkeypatch, key):
    cipher = gc.encrypt(ID_NUMBER)
    monkeypatch.delenv(gc.KEY_ENV, raising=False)
    monkeypatch.delenv(gc.INDEX_KEY_ENV, raising=False)
    with pytest.raises(gc.CryptoNotConfigured):
        gc.decrypt(cipher)


def test_a_short_key_is_refused(monkeypatch):
    import base64

    monkeypatch.setenv(gc.KEY_ENV, base64.urlsafe_b64encode(os.urandom(16)).decode())
    with pytest.raises(gc.CryptoNotConfigured, match="٣٢"):
        gc.encrypt("x")


def test_tampering_is_detected_not_silently_wrong(key):
    """GCM يكشف العبث. نصٌّ يُعاد مشوَّهاً بصمت أسوأ من خطأ ظاهر."""
    cipher = gc.encrypt(ID_NUMBER)
    with pytest.raises(ValueError):
        gc.decrypt(cipher[:-6] + "AAAAAA")


def test_the_same_value_encrypts_differently_each_time(key):
    """التشفير الحتمي يُسرّب التكرار: من يتكرر رقمه يُعرَف دون فكّ."""
    assert gc.encrypt(ID_NUMBER) != gc.encrypt(ID_NUMBER)


def test_double_encryption_is_a_no_op(key):
    once = gc.encrypt(ID_NUMBER)
    assert gc.decrypt(gc.encrypt(once)) == ID_NUMBER


def test_empty_values_stay_empty(key):
    assert gc.encrypt("") == ""
    assert gc.encrypt(None) is None
