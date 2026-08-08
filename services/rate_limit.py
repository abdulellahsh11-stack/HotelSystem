#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/rate_limit.py — تحديد معدّل الطلبات.

الحالة السابقة
──────────────
الحماية كانت على ثلاثة مسارات فقط: دخول المنشأة، وتسجيل منشأة جديدة،
ودخول المالك (أُضيف لاحقاً). وباقي المسارات — أكثر من مئة وستين — بلا
أي حدّ: يستطيع حسابٌ واحد أن يستنزف مجمّع الاتصالات ويُعطّل المنصة على
بقية المنشآت.

وعدّاد المحاولات كان قاموساً لا يُنظَّف أبداً:

    _login_attempts: dict = {}   # ip → [timestamps]

كل عنوان جديد يُضيف مفتاحاً يبقى إلى الأبد. مُهاجم يُدوّر العناوين
يُنمّي القاموس بلا حدّ حتى تنفد الذاكرة — أي أن أداة الحماية من الإساءة
كانت هي نفسها مساراً للإساءة.

التصميم
───────
نافذة منزلقة في الذاكرة، بمفتاح لكل (مستأجر أو عنوان). التنظيف يجري
تدريجياً مع الاستعمال فلا يحتاج خيطاً خلفياً، وبسقف صارم لعدد المفاتيح
يُسقط الأقدم عند بلوغه.

القيود سخيّة عمداً: فندق مزدحم في موسم الحج يُصدر طلبات كثيرة، والحدّ
الذي يُعطّل عميلاً شرعياً أسوأ من غيابه. الهدف إيقاف الإساءة الصارخة
لا ضبط الاستهلاك.

حدود المسار الواحد
──────────────────
هذه الوحدة تعمل داخل عملية واحدة. مع تعدّد النسخ يصير الحدّ الفعلي
مضروباً في عددها؛ الحلّ عندئذ عدّاد مشترك في Redis. مذكور في
specs/db/06-security-and-scale.md تحت «غير منفَّذ».
"""
from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from typing import Optional

# الحدود الافتراضية (طلب/دقيقة) — تُضبط من متغيّرات البيئة
READ_LIMIT = int(os.environ.get("RATE_LIMIT_READ", "600"))
WRITE_LIMIT = int(os.environ.get("RATE_LIMIT_WRITE", "180"))
ANON_LIMIT = int(os.environ.get("RATE_LIMIT_ANON", "60"))

# سقف عدد المفاتيح المحفوظة — يمنع نمو الذاكرة بلا حدّ
MAX_KEYS = int(os.environ.get("RATE_LIMIT_MAX_KEYS", "20000"))

WINDOW_SECONDS = 60

_buckets: OrderedDict = OrderedDict()
_lock = threading.Lock()


def _prune(now: float) -> None:
    """تنظيف تدريجي: يُزيل المفاتيح التي انتهت نافذتها.

    يُستدعى تحت القفل. الحدّ الأعلى للفحص يُبقي الكلفة ثابتة مهما كبر
    القاموس، فلا يتحوّل التنظيف نفسه إلى بطء.
    """
    checked = 0
    for key in list(_buckets.keys()):
        if checked >= 64:
            break
        checked += 1
        stamps = _buckets[key]
        if not stamps or now - stamps[-1] > WINDOW_SECONDS:
            _buckets.pop(key, None)

    # سقف صارم: يُسقط الأقدم استعمالاً
    while len(_buckets) > MAX_KEYS:
        _buckets.popitem(last=False)


def check(key: str, limit: int) -> bool:
    """يُعيد True إن كان الطلب ضمن الحدّ، ويُسجّله."""
    if limit <= 0:
        return True
    now = time.time()
    with _lock:
        _prune(now)
        stamps = [t for t in _buckets.get(key, []) if now - t < WINDOW_SECONDS]
        if len(stamps) >= limit:
            _buckets[key] = stamps
            _buckets.move_to_end(key)
            return False
        stamps.append(now)
        _buckets[key] = stamps
        _buckets.move_to_end(key)
        return True


def remaining(key: str, limit: int) -> int:
    now = time.time()
    with _lock:
        stamps = [t for t in _buckets.get(key, []) if now - t < WINDOW_SECONDS]
    return max(0, limit - len(stamps))


def reset(key: Optional[str] = None) -> None:
    """يُصفّر مفتاحاً بعينه أو الجميع — للاختبارات وللتدخّل التشغيلي."""
    with _lock:
        if key is None:
            _buckets.clear()
        else:
            _buckets.pop(key, None)


def stats() -> dict:
    with _lock:
        return {"keys": len(_buckets), "max_keys": MAX_KEYS,
                "read_limit": READ_LIMIT, "write_limit": WRITE_LIMIT,
                "anon_limit": ANON_LIMIT}
