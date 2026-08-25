#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_channel_auth.py — توثيق حجوزات القنوات

الهجوم الذي تحرس منه: قبل التوقيع كان `X-Channel-Token` يساوي رقم
المنشأة، ورقمُها يُرسل بالبريد ويظهر في الواجهة. فمن رآه حقن حجوزات
باسمها. أول اختبار هنا يُعيد تمثيل ذلك الهجوم بالضبط ويتوقّع رفضه.
"""
from __future__ import annotations

import time

import pytest

from services.channel_auth import (
    ChannelAuthError,
    TIMESTAMP_TOLERANCE_SECONDS,
    compute_signature,
    generate_secret,
    verify_request,
)

BODY = b'{"reservation_id":"R-1","guest":"\xd8\xb6\xd9\x8a\xd9\x81"}'


def test_knowing_the_client_id_is_no_longer_enough():
    """الهجوم القديم: معرفة رقم المنشأة وحدها. يجب أن يُرفض الآن."""
    with pytest.raises(ChannelAuthError):
        verify_request(generate_secret(), str(time.time()), "", BODY)


def test_a_correctly_signed_request_is_accepted():
    secret = generate_secret()
    ts = str(time.time())
    sig = compute_signature(secret, ts, BODY)
    verify_request(secret, ts, sig, BODY)  # لا يرمي


def test_tampering_with_the_body_invalidates_the_signature():
    secret = generate_secret()
    ts = str(time.time())
    sig = compute_signature(secret, ts, BODY)
    with pytest.raises(ChannelAuthError):
        verify_request(secret, ts, sig, BODY.replace(b"R-1", b"R-2"))


def test_a_wrong_secret_is_rejected():
    ts = str(time.time())
    sig = compute_signature(generate_secret(), ts, BODY)
    with pytest.raises(ChannelAuthError):
        verify_request(generate_secret(), ts, sig, BODY)


def test_a_replayed_request_expires():
    secret = generate_secret()
    old = str(time.time() - TIMESTAMP_TOLERANCE_SECONDS - 60)
    sig = compute_signature(secret, old, BODY)
    with pytest.raises(ChannelAuthError):
        verify_request(secret, old, sig, BODY)


def test_the_timestamp_cannot_be_swapped_while_keeping_the_signature():
    """الطابع داخل الرسالة الموقَّعة، فتبديله يُبطل التوقيع."""
    secret = generate_secret()
    old = str(time.time() - TIMESTAMP_TOLERANCE_SECONDS - 60)
    sig = compute_signature(secret, old, BODY)
    with pytest.raises(ChannelAuthError):
        verify_request(secret, str(time.time()), sig, BODY)


@pytest.mark.parametrize("secret,ts,sig", [
    ("", str(time.time()), "أ" * 64),          # لا سرّ مضبوط
    (generate_secret(), "", "أ" * 64),          # لا طابع
    (generate_secret(), "ليس-رقماً", "أ" * 64),  # طابع مُشوَّه
])
def test_missing_or_malformed_input_fails_closed(secret, ts, sig):
    with pytest.raises(ChannelAuthError):
        verify_request(secret, ts, sig, BODY)
