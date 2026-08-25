#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/channel_auth.py — توثيق حجوزات القنوات بتوقيع HMAC

ما كان قبل هذا الملف: `X-Channel-Token` يساوي رقم المنشأة. ورقم المنشأة
ليس سراً — يُرسل بالبريد عند التسجيل ويظهر في الواجهة — فمن يعرفه يحقن
حجوزات باسم المنشأة. أي أن التوثيق كان اسماً بلا معنى.

البديل: القناة توقّع جسم الطلب بسرٍّ مشترك، والخادم يُعيد حساب التوقيع
ويقارن. معرفة رقم المنشأة لم تعد تكفي، ولا يمكن تعديل الحمولة بعد
توقيعها.

يُغطّى إعادةُ الإرسال بطابع زمني ضمن التوقيع ونافذة قبول ضيّقة، فلا
يُعاد بثّ طلبٍ مُلتقَط بعد انقضائها.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

# نافذة قبول الطابع الزمني — تتسع لفروق الساعات بين الخوادم ولا تتسع
# لإعادة بثٍّ متأخّر
TIMESTAMP_TOLERANCE_SECONDS = 300

SIGNATURE_HEADER = "X-Channel-Signature"
TIMESTAMP_HEADER = "X-Channel-Timestamp"
TOKEN_HEADER = "X-Channel-Token"


class ChannelAuthError(Exception):
    """يفشل التوثيق. الرسالة صالحة للعرض ولا تكشف السرّ."""


def generate_secret() -> str:
    """سرٌّ جديد للقناة. يُعرض مرة واحدة عند الإنشاء."""
    return secrets.token_urlsafe(32)


def compute_signature(secret: str, timestamp: str, raw_body: bytes) -> str:
    """
    التوقيع = HMAC-SHA256(secret, "<timestamp>.<body>")

    الطابع الزمني داخل الرسالة الموقَّعة لا خارجها: لو كان خارجها لأمكن
    تبديله مع إبقاء التوقيع صالحاً، فتسقط الحماية من إعادة الإرسال.
    """
    message = timestamp.encode() + b"." + raw_body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_request(secret: str, timestamp: str, signature: str,
                   raw_body: bytes, now: float | None = None) -> None:
    """
    يتحقق من التوقيع والطابع الزمني، ويرمي ChannelAuthError عند الفشل.

    يفشل مغلقاً: سرٌّ مفقود أو توقيع مفقود أو طابع مُشوَّه كلها رفض.
    """
    if not secret:
        raise ChannelAuthError("لم يُضبط سرّ القناة لهذه المنشأة")
    if not signature:
        raise ChannelAuthError("توقيع القناة مفقود")
    if not timestamp:
        raise ChannelAuthError("طابع القناة الزمني مفقود")

    try:
        sent_at = float(timestamp)
    except (TypeError, ValueError):
        raise ChannelAuthError("طابع زمني غير صالح") from None

    current = time.time() if now is None else now
    if abs(current - sent_at) > TIMESTAMP_TOLERANCE_SECONDS:
        raise ChannelAuthError("الطلب خارج النافذة الزمنية المقبولة")

    expected = compute_signature(secret, timestamp, raw_body)
    # compare_digest لا المساواة العادية: المقارنة العادية تنتهي عند أول
    # اختلاف، فيتسرّب من زمنها ما يسمح باستنتاج التوقيع محرفاً محرفاً.
    if not hmac.compare_digest(expected, signature):
        raise ChannelAuthError("توقيع القناة غير صالح")
