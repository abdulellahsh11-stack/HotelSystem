#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/tenant_context.py — سياق المستأجر الحالي عبر contextvars.

المشكلة التي يحلّها
───────────────────
كانت set_event_context() تنفّذ:

    db.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))

والمعامل الثالث `true` يعني «محلي للمعاملة». لكن db.execute() يستعير
اتصالاً من المجمّع، ينفّذ العبارة، **يُنفّذ COMMIT**، ثم يُعيد الاتصال.
وبانتهاء المعاملة يُمحى الضبط المحلي فوراً — فالاستعلام التالي يستعير
اتصالاً آخر بلا أي سياق. النتيجة: الدالة لا تفعل شيئاً، و app_tenant()
لا تجد قيمة أبداً، وأي سياسة RLS تعتمد عليها ترفض كل الصفوف.

الحل
────
نحفظ المستأجر في ContextVar (آمن مع asyncio والخيوط معاً)، ويتولّى
DatabasePool._get_conn() ضبط الإعداد على مستوى الجلسة عند استعارة كل
اتصال وإعادته إلى القيمة الفارغة عند تسليمه للمجمّع — فلا يتسرّب سياق
مستأجر إلى الطلب التالي الذي يستعير نفس الاتصال.
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Iterator, Optional

# اسم إعداد الجلسة في PostgreSQL — يجب أن يطابق app_tenant() وسياسات RLS
GUC_NAME = "app.tenant_id"

_current_tenant: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "dheuof_current_tenant", default=None
)


def set_current_tenant(client_id: Optional[str]) -> contextvars.Token:
    """يضبط المستأجر الحالي ويُعيد رمزاً لاستعادة القيمة السابقة."""
    if client_id is not None:
        client_id = str(client_id).strip()
        if not client_id:
            raise ValueError("client_id فارغ — لا يجوز ضبطه كسياق مستأجر")
    return _current_tenant.set(client_id)


def get_current_tenant() -> Optional[str]:
    """يُعيد المستأجر الحالي، أو None إن لم يُضبط."""
    return _current_tenant.get()


def reset_current_tenant(token: contextvars.Token) -> None:
    """يُعيد السياق إلى ما كان عليه قبل set_current_tenant."""
    _current_tenant.reset(token)


@contextmanager
def tenant_scope(client_id: Optional[str]) -> Iterator[Optional[str]]:
    """يُثبّت مستأجراً داخل الكتلة ثم يستعيد السياق السابق.

        with tenant_scope("hotel_123"):
            db.execute("SELECT * FROM guests")   # مُقيَّد بالمستأجر

    يُستخدم في المهام الخلفية والمزامنة حيث لا يوجد طلب HTTP يحمل جلسة.
    """
    token = set_current_tenant(client_id)
    try:
        yield client_id
    finally:
        reset_current_tenant(token)
