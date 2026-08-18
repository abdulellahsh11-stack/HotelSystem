#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/tenant_context.py — سياق المستأجر للطلب الجاري

المشكلة التي يحلّها: RLS تحتاج معرفة المستأجر داخل **نفس معاملة**
الاستعلام. وطبقة الاتصال هنا تُنفّذ كل `execute()` في معاملة مستقلة،
فسياقٌ يُضبط بنداءٍ منفصل يضيع قبل الاستعلام التالي — قِسنا ذلك عملياً.

الحل: يُسجَّل المستأجر في `ContextVar` عند بداية الطلب، وتقرأه طبقةُ
الاتصال فتضبطه داخل معاملة كل استعلام قبل تنفيذه. فتعمل RLS دون إعادة
كتابة مئات مواضع النداء.

لماذا `ContextVar` لا متغيّر عام؟ لأن الخادم يخدم طلبات متزامنة؛
المتغيّر العام يجعل طلبَ منشأةٍ يقرأ سياق منشأة أخرى تحت الحِمل —
وهو أسوأ أنواع التسريب: يظهر عشوائياً ويصعب إعادة إنتاجه.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional

log = logging.getLogger("dheuof.db.tenant")

# المستأجر الحالي — يُضبط مرة لكل طلب
_current_tenant: ContextVar[Optional[str]] = ContextVar("current_tenant", default=None)

# نطاق مالك المنصة: يرى كل المنشآت.
# منفصلٌ عن المستأجر عمداً، فلا يُبلغ إليه أحدٌ بتمرير معرّف — يُفتح من
# مسارات المشرف وحدها بعد `require_admin`.
_platform_scope: ContextVar[bool] = ContextVar("platform_scope", default=False)


def set_tenant(client_id: Optional[str]) -> None:
    """يضبط مستأجر الطلب الجاري."""
    _current_tenant.set(str(client_id) if client_id else None)


def get_tenant() -> Optional[str]:
    return _current_tenant.get()


def clear_tenant() -> None:
    _current_tenant.set(None)
    _platform_scope.set(False)


def in_platform_scope() -> bool:
    return _platform_scope.get()


@contextmanager
def platform_scope():
    """
    نطاق مالك المنصة — وصولٌ عابر للمنشآت.

    يُستعمل في مسارات المشرف وحدها، وضمن أضيق حدود ممكنة: كل استعلام
    داخل هذا النطاق يتجاوز عزل RLS، فاتساعه يُلغي الحماية.

    يُعيد الحالة السابقة عند الخروج ولو وقع استثناء، فلا يبقى النطاق
    مفتوحاً على طلبٍ تالٍ يشترك في نفس السياق.
    """
    token = _platform_scope.set(True)
    log.debug("فُتح نطاق مالك المنصة")
    try:
        yield
    finally:
        _platform_scope.reset(token)


@contextmanager
def tenant_scope(client_id: str):
    """يُثبّت مستأجراً لكتلة من العمل — للمهام الخلفية والاختبارات."""
    token = _current_tenant.set(str(client_id))
    try:
        yield
    finally:
        _current_tenant.reset(token)
