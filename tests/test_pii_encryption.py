#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_pii_encryption.py — تشفير أرقام الهوية والبحث فيها.

كانت أرقام الهوية الوطنية والإقامة وهويات النزلاء تُخزَّن نصاً صريحاً في
VARCHAR(20)، فأي نسخة احتياطية مسرَّبة تكشفها مباشرة — وهي بيانات
يصنّفها نظام حماية البيانات الشخصية السعودي حسّاسة.
"""

import base64
import os
import secrets

import pytest

import db.crypto as crypto

DATABASE_URL = os.environ.get("DATABASE_URL", "")
skip_no_db = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")

ID_NUMBER = "1098765432"


@pytest.fixture()
def keyed(monkeypatch):
    """يضبط مفتاحاً وفلفلاً للاختبار ثم يُعيد الحالة."""
    monkeypatch.setenv("PII_ENCRYPTION_KEY",
                       base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setenv("PII_BLIND_INDEX_PEPPER", "فلفل-اختباري")
    return crypto


# ── التشفير ───────────────────────────────────────────────────────────────────

def test_ciphertext_does_not_contain_plaintext(keyed):
    """أوضح ما يجب التحقّق منه: ألا يظهر الرقم في المخزَّن."""
    enc = keyed.encrypt_pii(ID_NUMBER)
    assert ID_NUMBER not in enc
    assert enc.startswith("enc:v1:")


def test_roundtrip(keyed):
    assert keyed.decrypt_pii(keyed.encrypt_pii(ID_NUMBER)) == ID_NUMBER


def test_same_value_encrypts_differently(keyed):
    """nonce عشوائي لكل عملية — وإلا كشف تطابقُ النصوص المشفَّرة تساوي
    القيم الأصلية دون فكّ أي تشفير."""
    assert keyed.encrypt_pii(ID_NUMBER) != keyed.encrypt_pii(ID_NUMBER)


def test_double_encryption_is_a_no_op(keyed):
    once = keyed.encrypt_pii(ID_NUMBER)
    assert keyed.encrypt_pii(once) == once


@pytest.mark.parametrize("value", ["", None])
def test_empty_values_pass_through(keyed, value):
    assert keyed.encrypt_pii(value) == value
    assert keyed.decrypt_pii(value) == value


def test_plaintext_reads_unchanged(keyed):
    """صفوف ما قبل الترحيل تُقرأ كما هي."""
    assert keyed.decrypt_pii("1234567890") == "1234567890"


def test_tampered_ciphertext_is_rejected(keyed):
    """AES-GCM مُصادَق: أي عبث يُبطل فكّ التشفير بدل إعادة قيمة مغلوطة."""
    enc = keyed.encrypt_pii(ID_NUMBER)
    tampered = enc[:-6] + ("AAAAAA" if not enc.endswith("AAAAAA") else "BBBBBB")
    assert keyed.decrypt_pii(tampered) is None


def test_wrong_key_cannot_decrypt(keyed, monkeypatch):
    enc = keyed.encrypt_pii(ID_NUMBER)
    monkeypatch.setenv("PII_ENCRYPTION_KEY",
                       base64.b64encode(secrets.token_bytes(32)).decode())
    assert keyed.decrypt_pii(enc) is None


def test_no_key_means_passthrough_not_crash(monkeypatch):
    """نشرٌ بلا مفتاح يجب أن يعمل (مع تحذير) لا أن ينهار."""
    monkeypatch.delenv("PII_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("PII_BLIND_INDEX_PEPPER", raising=False)
    assert crypto.encrypt_pii(ID_NUMBER) == ID_NUMBER
    assert crypto.encryption_available() is False


def test_malformed_key_is_refused(monkeypatch):
    monkeypatch.setenv("PII_ENCRYPTION_KEY", "ليس-base64-صالحاً!!")
    assert crypto.encryption_available() is False
    monkeypatch.setenv("PII_ENCRYPTION_KEY", base64.b64encode(b"short").decode())
    assert crypto.encryption_available() is False


def test_generated_key_is_valid(monkeypatch):
    monkeypatch.setenv("PII_ENCRYPTION_KEY", crypto.generate_key())
    assert crypto.encryption_available() is True


# ── الفهرس الأعمى ─────────────────────────────────────────────────────────────

def test_blind_index_is_deterministic(keyed):
    assert keyed.blind_index(ID_NUMBER) == keyed.blind_index(ID_NUMBER)


def test_blind_index_hides_the_value(keyed):
    idx = keyed.blind_index(ID_NUMBER)
    assert ID_NUMBER not in idx
    assert len(idx) == 64  # HMAC-SHA256 hex


def test_blind_index_differs_per_value(keyed):
    assert keyed.blind_index(ID_NUMBER) != keyed.blind_index("2098765432")


@pytest.mark.parametrize("variant", ["1098765432", "1098-765-432", "1098 765 432", "١٠٩٨٧٦٥٤٣٢"])
def test_normalization_finds_the_same_row(keyed, variant):
    """الشرطات والفراغات والأرقام العربية تُطبَّع قبل الفهرسة."""
    assert keyed.blind_index(variant) == keyed.blind_index(ID_NUMBER)


def test_blind_index_refuses_without_pepper(monkeypatch):
    """بلا فلفل يصير الفهرس SHA عادياً — وفضاء أرقام الهوية صغير يكفي
    لتخمينه بجدول مسبق. الامتناع أصدق من أمان وهمي."""
    monkeypatch.delenv("PII_BLIND_INDEX_PEPPER", raising=False)
    monkeypatch.delenv("PII_ENCRYPTION_KEY", raising=False)
    assert crypto.blind_index(ID_NUMBER) is None


# ── التكامل مع قاعدة البيانات ─────────────────────────────────────────────────

@skip_no_db
def test_guest_id_number_is_encrypted_at_rest(db_pool, keyed):
    """الاختبار الحاسم: قراءة الجدول مباشرة يجب ألا تُظهر الرقم."""
    from db.store import DataStore

    db_pool.execute("DELETE FROM clients WHERE id = 'pii_t'")
    db_pool.execute("INSERT INTO clients (id, name) VALUES ('pii_t', 'اختبار')")
    store = DataStore(db_pool, dual_write=False)

    store.save_guest("pii_t", {"full_name": "نزيل", "id_number": ID_NUMBER,
                               "id_type": "national"})
    try:
        raw = db_pool.execute(
            "SELECT id_number, id_number_enc, id_number_bidx FROM guests "
            "WHERE client_id = 'pii_t'", fetch="one",
        )
        assert raw["id_number_enc"], "لم يُخزَّن النص المشفَّر"
        assert ID_NUMBER not in (raw["id_number_enc"] or "")
        assert not raw["id_number"], "الرقم ما زال مخزَّناً نصاً صريحاً"
        assert raw["id_number_bidx"], "الفهرس الأعمى مفقود"

        # ويعود مقروءاً عبر طبقة الوصول
        guests = store.get_guests("pii_t")
        assert guests[0]["id_number"] == ID_NUMBER
        assert "id_number_enc" not in guests[0], "عمود التخزين تسرّب للمستهلك"
    finally:
        db_pool.execute("DELETE FROM clients WHERE id = 'pii_t'")


@skip_no_db
def test_search_by_id_number_works_without_decrypting(db_pool, keyed):
    from db.store import DataStore

    db_pool.execute("DELETE FROM clients WHERE id = 'pii_s'")
    db_pool.execute("INSERT INTO clients (id, name) VALUES ('pii_s', 'اختبار')")
    store = DataStore(db_pool, dual_write=False)
    store.save_guest("pii_s", {"full_name": "نزيل", "id_number": ID_NUMBER})
    try:
        found = store.find_guest_by_id_number("pii_s", ID_NUMBER)
        assert found is not None and found["id_number"] == ID_NUMBER
        # وبصيغة مكتوبة بشكل مختلف
        assert store.find_guest_by_id_number("pii_s", "1098-765-432") is not None
        assert store.find_guest_by_id_number("pii_s", "0000000000") is None
    finally:
        db_pool.execute("DELETE FROM clients WHERE id = 'pii_s'")
