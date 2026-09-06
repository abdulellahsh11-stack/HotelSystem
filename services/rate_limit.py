#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/rate_limit.py — حدٌّ عامٌّ لمعدّل طلبات الـ API.

ما كان موجوداً
──────────────
`app_core` يحدّ ثلاثة مسارات حسّاسة فقط: دخول المنشأة (`/api/login`)،
وتسجيل منشأة جديدة (`/api/client/register`)، ودخول المالك
(`/api/admin/login`) — وعدّاداتها تُنظَّف عند بلوغ حدٍّ فلا تُسرّب الذاكرة.

الفجوة التي تسدّها هذه الوحدة
────────────────────────────
بقيّة مسارات الـ API — أكثر من مئة وستين — بلا أي حدّ: مستأجرٌ واحد
(أو عنوانٌ مجهول) يستطيع أن يُغرق مجمّع الاتصالات بوابلٍ من الطلبات
فيُبطئ المنصة على بقيّة المنشآت. هذا الحدّ العامّ يوقف الإساءة الصارخة
دون أن يمسّ المسارات الثلاثة أعلاه (تبقى بحدّها الأضيق الخاصّ).

التصميم
───────
نافذة منزلقة في الذاكرة، بمفتاح لكل (مستأجر) أو (عنوان للمجهولين).
التنظيف تدريجيٌّ مع الاستعمال فلا يحتاج خيطاً خلفياً، وبسقفٍ صارم لعدد
المفاتيح يُسقط الأقدم عند بلوغه — فأداةُ الحماية من الإساءة لا تصير هي
نفسها مساراً للإساءة عبر تدوير العناوين.

القيود سخيّة عمداً: فندقٌ مزدحم في موسم الحج يُصدر طلبات كثيرة، والحدُّ
الذي يُعطّل عميلاً شرعياً أسوأ من غيابه. الهدف إيقاف الإساءة الصارخة لا
ضبط الاستهلاك.

حدّ المسار الواحد
─────────────────
هذه الوحدة تعمل داخل عملية واحدة. مع تعدّد النسخ يصير الحدّ الفعلي
مضروباً في عددها؛ الحلّ عندئذ عدّاد مشترك في Redis. غير منفَّذ بعد.
"""
from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from itertools import islice
from typing import Optional

# الحدود الافتراضية (طلب/دقيقة) — تُضبط من متغيّرات البيئة.
# القراءة لا تُحدُّ (الحارس على مسارات الكتابة فقط)، فلا ثابت READ_LIMIT
# يوهم عاملاً بأنه يستطيع خنق القراءة بينما لا شيء يقرؤه.
WRITE_LIMIT = int(os.environ.get("RATE_LIMIT_WRITE", "180"))
ANON_LIMIT = int(os.environ.get("RATE_LIMIT_ANON", "60"))

# سقف عدد المفاتيح المحفوظة — يمنع نمو الذاكرة بلا حدّ
MAX_KEYS = int(os.environ.get("RATE_LIMIT_MAX_KEYS", "20000"))

WINDOW_SECONDS = 60

_buckets: "OrderedDict[str, list]" = OrderedDict()
_lock = threading.Lock()


def _prune(now: float) -> None:
    """تنظيف تدريجي: يُزيل المفاتيح التي انتهت نافذتها.

    يُستدعى تحت القفل. الحدّ الأعلى للفحص يُبقي الكلفة ثابتة مهما كبر
    القاموس، فلا يتحوّل التنظيف نفسه إلى بطء.
    """
    # نفحص أقدم ٦٤ مفتاحاً فقط. `islice` يُجسّد ٦٤ مفتاحاً لا القاموس كلّه،
    # فتبقى الكلفة ثابتة مهما كبر — والنسخ إلى قائمة يسمح بالحذف أثناء الجولة.
    for key in list(islice(_buckets, 64)):
        stamps = _buckets.get(key)
        if not stamps or now - stamps[-1] > WINDOW_SECONDS:
            _buckets.pop(key, None)

    # سقف صارم: يُسقط الأقدم استعمالاً
    while len(_buckets) > MAX_KEYS:
        _buckets.popitem(last=False)


def check(key: str, limit: int) -> bool:
    """يُعيد True إن كان الطلب ضمن الحدّ، ويُسجّله. حدٌّ ≤ 0 يعني بلا حدّ."""
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
    """كم طلباً بقي ضمن النافذة الحالية لهذا المفتاح."""
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
    """لمحةٌ تشغيلية عن حالة الحدّ."""
    with _lock:
        return {"keys": len(_buckets), "max_keys": MAX_KEYS,
                "write_limit": WRITE_LIMIT, "anon_limit": ANON_LIMIT}
