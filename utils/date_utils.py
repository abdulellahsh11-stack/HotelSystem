#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils/date_utils.py — Saudi Timezone Helpers
توقيت الرياض: UTC+3 — بدون DST
"""
import logging
from datetime import datetime, date, timedelta, timezone

# توقيت المملكة العربية السعودية — UTC+3 ثابت (لا DST)
SA_TZ = timezone(timedelta(hours=3))


log = logging.getLogger("dheuof.dates")


def sa_now() -> datetime:
    """الوقت الحالي بتوقيت السعودية"""
    return datetime.now(SA_TZ)


def sa_today() -> str:
    """تاريخ اليوم بتوقيت السعودية — YYYY-MM-DD"""
    return sa_now().strftime("%Y-%m-%d")


def sa_iso() -> str:
    """ISO timestamp بتوقيت السعودية"""
    return sa_now().isoformat()


def sa_time() -> str:
    """الوقت فقط — HH:MM"""
    return sa_now().strftime("%H:%M")


def nights_between(check_in: str, check_out: str) -> int:
    """عدد الليالي بين تاريخين"""
    try:
        d1 = date.fromisoformat(str(check_in))
        d2 = date.fromisoformat(str(check_out))
        return max(0, (d2 - d1).days)
    except (ValueError, TypeError):
        return 0


def days_until(target_date: str) -> int:
    """
    الأيام المتبقية حتى تاريخ. صفر لما مضى أو لتاريخ غير صالح.

    لا تُبنَ عليها صلاحيةُ اشتراك: الصفر هنا يعني ثلاثة أشياء مختلفة
    (اليوم، وما مضى، وتاريخ فاسد). استعمل `is_expired`.
    """
    try:
        target = date.fromisoformat(str(target_date))
        return max(0, (target - date.today()).days)
    except (ValueError, TypeError):
        return 0


def is_expired(target_date: str) -> bool:
    """
    هل انقضى التاريخ؟ اشتراكٌ ينتهي اليوم ما زال سارياً حتى نهايته.

    كانت تُبنى على `days_until`، وهي تُصفّر ما مضى **وتُصفّر التاريخ
    الفاسد أيضاً** — فتُنهي اشتراك من ينتهي اليوم قبل أوانه، وتُنهي
    اشتراك من حُفظ تاريخه بصيغة خاطئة بلا سبب. المقارنة هنا مباشرة،
    والتاريخ غير الصالح لا يُعدّ منتهياً لأنه خطأ بيانات لا انقضاء.
    """
    if not target_date:
        return False
    try:
        return date.fromisoformat(str(target_date)) < date.today()
    except (ValueError, TypeError):
        log.warning("تاريخ انتهاء غير صالح: %r — لا يُعدّ منتهياً", target_date)
        return False


def format_arabic_date(d: str) -> str:
    """تنسيق التاريخ للعرض العربي — مثل: الاثنين 12 مايو 2026"""
    try:
        dt = date.fromisoformat(str(d))
        months = [
            "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
            "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
        ]
        days_ar = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
        return f"{days_ar[dt.weekday()]} {dt.day} {months[dt.month - 1]} {dt.year}"
    except (ValueError, TypeError):
        return str(d)
