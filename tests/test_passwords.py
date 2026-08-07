#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_passwords.py — تجزئة كلمات المرور والترقية الصامتة.

خلفية
─────
كان التوثيق يعد بـ bcrypt-12 في ثلاثة مواضع بينما الكود يستخدم
PBKDF2-SHA256 بمئة ألف دورة — أضعف من توصية OWASP (600 ألف لـ PBKDF2)
وليس ما يقوله التوثيق. والهاش المخزَّن كان hex عارياً بلا وسم خوارزمية،
فلا سبيل للترقية دون إجبار الجميع على تغيير كلمات مرورهم.
"""

import hashlib

import pytest

from db.passwords import (
    ARGON2_AVAILABLE, algorithm_of, hash_password, needs_upgrade, verify_password,
)

PASSWORD = "كلمة-مرور-قوية-2026!"


# ── الإنتاج والتحقق ───────────────────────────────────────────────────────────

def test_hash_is_tagged_with_its_algorithm():
    """بلا وسم لا يمكن معرفة كيف أُنتج الهاش ولا ترقيته لاحقاً."""
    h = hash_password(PASSWORD)
    assert h.startswith("$")
    assert algorithm_of(h) in ("argon2id", "scrypt")


def test_uses_argon2id_when_available():
    if not ARGON2_AVAILABLE:
        pytest.skip("argon2-cffi غير مثبّتة")
    assert algorithm_of(hash_password(PASSWORD)) == "argon2id"


def test_correct_password_verifies():
    ok, _ = verify_password(PASSWORD, hash_password(PASSWORD))
    assert ok is True


def test_wrong_password_rejected():
    ok, _ = verify_password("خاطئة", hash_password(PASSWORD))
    assert ok is False


def test_same_password_hashes_differently_each_time():
    """ملح عشوائي لكل عملية — وإلا كشف تطابقُ الهاشات المستخدمين
    الذين يتشاركون كلمة المرور نفسها."""
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


@pytest.mark.parametrize("value", ["", None])
def test_empty_password_is_refused(value):
    with pytest.raises((ValueError, AttributeError, TypeError)):
        hash_password(value)


def test_empty_stored_hash_never_verifies():
    assert verify_password(PASSWORD, "") == (False, False)


def test_fresh_hash_does_not_need_upgrade():
    assert needs_upgrade(hash_password(PASSWORD)) is False


# ── التوافق مع الصيغة القديمة ─────────────────────────────────────────────────

def _legacy_hash(password: str, salt: str) -> str:
    """الصيغة القديمة: PBKDF2-SHA256 بمئة ألف دورة، hex عارٍ."""
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 100_000
    ).hex()


def test_legacy_hash_still_verifies():
    """لا يجوز أن تُخرج الترقيةُ المستخدمين القدامى من حساباتهم."""
    stored = _legacy_hash(PASSWORD, "ملح_قديم")
    ok, needs_rehash = verify_password(PASSWORD, stored, legacy_salt="ملح_قديم")
    assert ok is True
    assert needs_rehash is True, "الهاش القديم يجب أن يُعلَّم للترقية"


def test_legacy_hash_rejects_wrong_password():
    stored = _legacy_hash(PASSWORD, "ملح_قديم")
    ok, _ = verify_password("خاطئة", stored, legacy_salt="ملح_قديم")
    assert ok is False


def test_legacy_hash_without_salt_fails_closed():
    stored = _legacy_hash(PASSWORD, "ملح_قديم")
    assert verify_password(PASSWORD, stored) == (False, False)


def test_legacy_algorithm_is_reported():
    assert algorithm_of(_legacy_hash(PASSWORD, "s")) == "legacy-pbkdf2-100k"


def test_scrypt_roundtrip():
    """المسار البديل حين لا تتوفّر argon2-cffi."""
    import base64
    import secrets as _s
    salt = _s.token_bytes(16)
    # maxmem صريح — الحدّ الافتراضي في OpenSSL (32 ميبي) أقل من الحاجة
    digest = hashlib.scrypt(PASSWORD.encode(), salt=salt, n=1 << 15, r=8, p=1,
                            dklen=32, maxmem=128 * (1 << 15) * 8 * 2)
    stored = (f"$scrypt$32768$8$1$"
              f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}")
    ok, _ = verify_password(PASSWORD, stored)
    assert ok is True
    assert algorithm_of(stored) == "scrypt"
    assert verify_password("خاطئة", stored)[0] is False


def test_corrupt_hash_fails_closed_without_raising():
    for bad in ("$scrypt$نص$تالف", "$pbkdf2-sha256$abc", "$argon2id$مشوَّه"):
        assert verify_password(PASSWORD, bad)[0] is False


# ── تكامل مع مسارات التطبيق ───────────────────────────────────────────────────

def test_make_password_returns_tagged_hash():
    from main1 import _make_password
    h, _salt = _make_password(PASSWORD)
    assert algorithm_of(h) in ("argon2id", "scrypt")


def test_verify_password_accepts_legacy_client_record():
    from main1 import _verify_password

    class _Cfg:
        pass_salt = "الملح_العام"

    client = {"id": "c1", "pass_hash": _legacy_hash(PASSWORD, "ملح_الحساب"),
              "pass_salt": "ملح_الحساب"}
    assert _verify_password(PASSWORD, client, _Cfg()) is True
    assert _verify_password("خاطئة", client, _Cfg()) is False


def test_login_upgrades_legacy_hash_in_place():
    """الترقية الصامتة: أول دخول ناجح يحوّل الهاش إلى Argon2id."""
    from main1 import _verify_password

    class _Cfg:
        pass_salt = "الملح_العام"

    class _Store:
        saved = None

        def save_client(self, c):
            self.saved = c

    client = {"id": "c1", "pass_hash": _legacy_hash(PASSWORD, "ملح_الحساب"),
              "pass_salt": "ملح_الحساب"}
    store = _Store()

    assert _verify_password(PASSWORD, client, _Cfg(), store=store) is True
    assert store.saved is not None, "الهاش المُرقّى لم يُحفظ"
    assert algorithm_of(client["pass_hash"]) in ("argon2id", "scrypt")
    # وكلمة المرور نفسها ما زالت تعمل بعد الترقية
    assert _verify_password(PASSWORD, client, _Cfg()) is True


def test_admin_password_accepts_both_formats():
    from main1 import _verify_admin_password

    class _CfgNew:
        admin_pass_hash = hash_password(PASSWORD)
        pass_salt = "غير_مستخدم"

    class _CfgLegacy:
        admin_pass_hash = _legacy_hash(PASSWORD, "HotelSaaS2025")
        pass_salt = "HotelSaaS2025"

    assert _verify_admin_password(PASSWORD, _CfgNew()) is True
    assert _verify_admin_password("خاطئة", _CfgNew()) is False
    assert _verify_admin_password(PASSWORD, _CfgLegacy()) is True
    assert _verify_admin_password("خاطئة", _CfgLegacy()) is False


def test_admin_reset_updates_hash_and_salt_together():
    """كان إعادة تعيين كلمة المرور من لوحة المالك يكتب pass_hash بالملح
    العام ويترك pass_salt الخاص بالحساب — فيتحقّق الدخول بملح مختلف عن
    الذي جُزّئت به كلمة المرور، وتخرج المنشأة من حسابها بصمت."""
    from main1 import _make_password, _verify_password

    class _Cfg:
        pass_salt = "الملح_العام"

    client = {"id": "c1"}
    client["pass_hash"], client["pass_salt"] = _make_password("القديمة-2026")
    assert _verify_password("القديمة-2026", client, _Cfg()) is True

    # ما يفعله مسار إعادة التعيين الآن
    client["pass_hash"], client["pass_salt"] = _make_password("الجديدة-2026")

    assert _verify_password("الجديدة-2026", client, _Cfg()) is True, \
        "إعادة التعيين أخرجت المنشأة من حسابها"
    assert _verify_password("القديمة-2026", client, _Cfg()) is False
