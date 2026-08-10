#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils/validators.py — Saudi ID validation + Phone normalization
"""
import re
from typing import Tuple


def validate_saudi_id(id_number: str) -> Tuple[bool, str]:
    """
    يُتحقق من صحة رقم الهوية الوطنية السعودية أو الإقامة.
    - هوية وطنية: تبدأ بـ 1، 10 أرقام
    - إقامة: تبدأ بـ 2، 10 أرقام
    يُعيد (صحيح, نوع_الهوية) أو (خطأ, رسالة_الخطأ)
    """
    if not id_number:
        return False, "رقم الهوية فارغ"

    clean = re.sub(r"\D", "", str(id_number))

    if len(clean) != 10:
        return False, f"رقم الهوية يجب أن يكون 10 أرقام (المُدخل: {len(clean)})"

    if clean[0] == "1":
        return True, "national"
    elif clean[0] == "2":
        return True, "iqama"
    else:
        return False, "رقم الهوية يجب أن يبدأ بـ 1 (وطني) أو 2 (إقامة)"


def normalize_phone(phone: str, country_code: str = "966") -> str:
    """
    يُوحّد تنسيق رقم الجوال السعودي.
    المدخل: 0501234567 أو +966501234567 أو 966501234567
    المخرج: 966501234567
    """
    if not phone:
        return ""

    clean = re.sub(r"[\s\-\(\)\+]", "", str(phone))

    if clean.startswith("00"):
        clean = clean[2:]
    elif clean.startswith("0"):
        clean = country_code + clean[1:]
    elif clean.startswith(country_code):
        pass
    elif len(clean) == 9 and clean.startswith("5"):
        clean = country_code + clean

    return clean


def validate_phone(phone: str) -> Tuple[bool, str]:
    """يتحقق من صحة رقم الجوال السعودي"""
    normalized = normalize_phone(phone)
    if not normalized:
        return False, "رقم الجوال فارغ"
    if not re.match(r"^9665\d{8}$", normalized):
        return False, "رقم الجوال غير صحيح — يجب أن يبدأ بـ 05"
    return True, normalized


def validate_email(email: str) -> bool:
    """تحقق بسيط من البريد الإلكتروني"""
    if not email:
        return True  # البريد اختياري
    return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", str(email).strip()))


def validate_vat_number(vat: str) -> bool:
    """رقم ضريبي سعودي — 15 رقماً تبدأ وتنتهي بـ 3"""
    if not vat:
        return True  # اختياري
    clean = re.sub(r"\D", "", str(vat))
    return len(clean) == 15 and clean.startswith("3") and clean.endswith("3")


def sanitize_string(s: str, max_len: int = 500) -> str:
    """تنظيف النصوص من مدخلات المستخدم"""
    if not s:
        return ""
    return str(s).strip()[:max_len]
