#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_password_upgrade.py — قوة التجزئة والانتقال إليها

الخطر الذي تحرسه هذه الاختبارات: رفع عدد دورات PBKDF2 يُبطل كل تجزئة
قائمة، فيُمنع كل عميل من الدخول دفعةً واحدة. الانتقال المُوسَّم يمنع
ذلك، وهذه الاختبارات تُثبت أنه يمنعه فعلاً لا نظرياً.
"""
from __future__ import annotations

from app_core import (
    PBKDF2_ITERATIONS_CURRENT,
    PBKDF2_ITERATIONS_LEGACY,
    _hash_password,
    _make_password,
    _parse_stored_hash,
    _verify_password,
    password_needs_upgrade,
)


class _Cfg:
    pass_salt = "ملح-عام-قديم"


def test_new_hashes_use_the_current_iteration_count():
    stored, salt = _make_password("كلمة-سر")
    iterations, _ = _parse_stored_hash(stored)
    assert iterations == PBKDF2_ITERATIONS_CURRENT
    assert PBKDF2_ITERATIONS_CURRENT >= 600_000, "أضعف من توصية OWASP"


def test_new_hashes_verify():
    stored, salt = _make_password("كلمة-سر")
    client = {"pass_hash": stored, "pass_salt": salt}
    assert _verify_password("كلمة-سر", client, _Cfg())
    assert not _verify_password("كلمة-خاطئة", client, _Cfg())


def test_legacy_bare_hashes_still_verify():
    """الحرج: تجزئة قديمة عارية بلا وسم يجب أن تظل تعمل."""
    salt = "ملح-قديم"
    legacy = _hash_password("كلمة-سر", salt, PBKDF2_ITERATIONS_LEGACY)
    client = {"pass_hash": legacy, "pass_salt": salt}
    assert _verify_password("كلمة-سر", client, _Cfg()), "كُسر دخول العملاء القدامى"
    assert not _verify_password("كلمة-خاطئة", client, _Cfg())


def test_legacy_hash_with_global_salt_still_verifies():
    """أقدم صيغة: بلا ملح خاص، تعتمد على الملح العام في الإعدادات."""
    legacy = _hash_password("كلمة-سر", _Cfg.pass_salt, PBKDF2_ITERATIONS_LEGACY)
    client = {"pass_hash": legacy}  # لا pass_salt إطلاقاً
    assert _verify_password("كلمة-سر", client, _Cfg())


def test_upgrade_is_flagged_for_legacy_and_not_for_current():
    legacy = _hash_password("كلمة-سر", "ملح", PBKDF2_ITERATIONS_LEGACY)
    assert password_needs_upgrade(legacy)

    current, _ = _make_password("كلمة-سر")
    assert not password_needs_upgrade(current)


def test_malformed_stored_hash_fails_closed():
    """تجزئة مُشوَّهة ترفض الدخول ولا ترمي استثناءً."""
    for bad in ("pbkdf2_sha256$", "pbkdf2_sha256$abc$xyz", "pbkdf2_sha256$$", ""):
        client = {"pass_hash": bad, "pass_salt": "ملح"}
        assert _verify_password("كلمة-سر", client, _Cfg()) is False


def test_login_upgrades_a_legacy_hash_in_place():
    """من طرف إلى طرف: دخول بتجزئة قديمة يكتب تجزئة قوية في قاعدة البيانات."""
    from routes.auth import _upgrade_password_if_weak

    salt = "ملح-قديم"
    legacy = _hash_password("كلمة-سر", salt, PBKDF2_ITERATIONS_LEGACY)
    written: list[tuple] = []

    class _DB:
        use_postgres = True

        def execute(self, sql, params=(), fetch=None):
            written.append((sql, params))
            return []

    class _Req:
        class app:
            class state:
                db = _DB()

    client = {"pass_hash": legacy, "pass_salt": salt}
    _upgrade_password_if_weak(_Req(), "c1", client, "كلمة-سر")

    assert written, "لم تُكتب الترقية"
    sql, params = written[0]
    assert "UPDATE clients SET pass_hash" in sql
    new_hash, new_salt, cid = params
    assert cid == "c1"
    assert not password_needs_upgrade(new_hash)
    # التجزئة الجديدة تتحقق من نفس كلمة المرور
    assert _verify_password("كلمة-سر", {"pass_hash": new_hash, "pass_salt": new_salt}, _Cfg())


def test_upgrade_is_skipped_when_already_current():
    from routes.auth import _upgrade_password_if_weak

    current, salt = _make_password("كلمة-سر")
    written: list = []

    class _DB:
        use_postgres = True

        def execute(self, sql, params=(), fetch=None):
            written.append(sql)
            return []

    class _Req:
        class app:
            class state:
                db = _DB()

    _upgrade_password_if_weak(_Req(), "c1", {"pass_hash": current, "pass_salt": salt}, "كلمة-سر")
    assert not written, "رقّى تجزئة قوية بلا داعٍ"
