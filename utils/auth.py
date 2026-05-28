#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils/auth.py — Authentication Helpers
"""
import os
import hashlib
import secrets
import logging

log = logging.getLogger("dheuof.auth")


def hash_password(password: str, salt: str = None) -> str:
    """PBKDF2-SHA256 — 260,000 iteration — لا يمكن عكسه"""
    if salt is None:
        salt = os.environ.get("PASS_SALT", "HotelSaaS2025")
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 260_000
    ).hex()


def verify_password(entered: str, stored_hash: str, salt: str = None) -> bool:
    """مقارنة آمنة — تمنع Timing Attack"""
    computed = hash_password(entered, salt)
    return secrets.compare_digest(computed, stored_hash)


def generate_token(length: int = 32) -> str:
    """مفتاح جلسة عشوائي"""
    return secrets.token_hex(length)


def generate_client_id(prefix: str = "DHUA") -> str:
    """مُعرّف فريد للعميل — مثل DHUA-1715500000000"""
    from utils.date_utils import sa_now
    ts = int(sa_now().timestamp() * 1000)
    return f"{prefix}-{ts}"
