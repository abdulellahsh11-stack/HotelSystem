#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_admin_hash.py — يولّد ADMIN_PASS_HASH لوضعه في Railway Variables

الاستخدام:
    python3 scripts/gen_admin_hash.py

يسألك عن كلمة المرور (لا تظهر على الشاشة) ويطبع الهاش الذي تنسخه إلى
Railway → Variables → ADMIN_PASS_HASH

ملاحظة: يجب أن يطابق الملح (PASS_SALT) ما هو مضبوط في Railway.
الافتراضي "HotelSaaS2025" إن لم تكن قد ضبطت PASS_SALT.
"""
import getpass
import hashlib
import os


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 100_000
    ).hex()


def main() -> None:
    salt = os.environ.get("PASS_SALT", "HotelSaaS2025")
    print("=" * 56)
    print("  مولّد كلمة مرور المالك — ضيوف")
    print("=" * 56)
    print(f"  الملح المستخدم (PASS_SALT): {salt}")
    print("-" * 56)

    p1 = getpass.getpass("  أدخل كلمة المرور الجديدة: ")
    if len(p1) < 6:
        print("  ⚠️  كلمة المرور قصيرة — استخدم 6 أحرف على الأقل.")
        return
    p2 = getpass.getpass("  أعد إدخال كلمة المرور للتأكيد: ")
    if p1 != p2:
        print("  ❌ كلمتا المرور غير متطابقتين.")
        return

    h = hash_password(p1, salt)
    print("-" * 56)
    print("  ✅ تم — انسخ السطر التالي إلى Railway Variables:")
    print()
    print(f"  ADMIN_PASS_HASH={h}")
    print()
    print("=" * 56)


if __name__ == "__main__":
    main()
