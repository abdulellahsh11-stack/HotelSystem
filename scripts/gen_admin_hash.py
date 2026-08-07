#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_admin_hash.py — يولّد ADMIN_PASS_HASH لوضعه في Railway Variables

الاستخدام:
    python3 scripts/gen_admin_hash.py

يسألك عن كلمة المرور (لا تظهر على الشاشة) ويطبع الهاش الذي تنسخه إلى
Railway → Variables → ADMIN_PASS_HASH

الهاش الآن Argon2id والملح مضمَّن داخله عشوائياً، فلم يعد PASS_SALT
مطلوباً لكلمة مرور المالك. الصيغة القديمة (PBKDF2 + ملح عام افتراضي
معروف في المستودع) ما زالت مقبولة عند الدخول للتوافق، لكن يُستحسن
إعادة توليد الهاش بهذا السكربت.
"""
import getpass
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.passwords import ARGON2_AVAILABLE, algorithm_of, hash_password  # noqa: E402

MIN_LENGTH = 12


def main() -> None:
    print("=" * 60)
    print("  مولّد كلمة مرور المالك — ضيوف")
    print("=" * 60)
    if not ARGON2_AVAILABLE:
        print("  ⚠️  argon2-cffi غير مثبّتة — سيُستخدم scrypt.")
        print("     ثبّتها بـ: pip install argon2-cffi")
        print("-" * 60)

    p1 = getpass.getpass("  أدخل كلمة المرور الجديدة: ")
    if len(p1) < MIN_LENGTH:
        print(f"  ⚠️  كلمة المرور قصيرة — {MIN_LENGTH} حرفاً على الأقل.")
        print("     هذه كلمة مرور مالك المنصة؛ لا تُقارن بكلمة مرور عادية.")
        return
    p2 = getpass.getpass("  أعد إدخال كلمة المرور للتأكيد: ")
    if p1 != p2:
        print("  ❌ كلمتا المرور غير متطابقتين.")
        return

    h = hash_password(p1)
    print("-" * 60)
    print(f"  ✅ تم — الخوارزمية: {algorithm_of(h)}")
    print("  انسخ السطر التالي إلى Railway Variables:")
    print()
    print(f"  ADMIN_PASS_HASH={h}")
    print()
    print("  ملاحظة: الملح مضمَّن في الهاش — لا تحتاج ضبط PASS_SALT.")
    print("=" * 60)


if __name__ == "__main__":
    main()
