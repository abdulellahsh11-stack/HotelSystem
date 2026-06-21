#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""services/tax_config.py — منظومة الضريبة المركزية لجميع وحدات ضيوف

الوضعان:
  MODE_A — الضريبة تُضاف فوق المجموع:
            المجموع الكلي = المجموع × (1 + vat_rate + tourism_rate)
            مثال: 1000 → VAT=150، سياحة=25، الكلي=1175

  MODE_B — الضريبة مُضمَّنة في المجموع الكلي (شامل الضريبة):
            المجموع الكلي = 100%
            ضريبة القيمة المضافة  = المجموع الكلي × 15%  → 150
            ضريبة السياحة         = المجموع الكلي × 2.5% →  25
            صافي الإيراد          = المجموع الكلي × 82.5% → 825
            مثال: 1175 → VAT=176.25، سياحة=29.375، صافي=969.375
"""
import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

log = logging.getLogger("dheuof.tax")

_TWO  = Decimal("0.01")
_FOUR = Decimal("0.0001")

DEFAULT_VAT_RATE     = Decimal("0.15")   # ضريبة القيمة المضافة 15%
DEFAULT_TOURISM_RATE = Decimal("0.025")  # ضريبة السياحة      2.5%


class TaxConfig:
    """إعدادات الضريبة الخاصة بمنشأة فندقية واحدة."""

    __slots__ = ("mode", "vat_rate", "tourism_rate", "tourism_enabled")

    def __init__(
        self,
        mode: str = "MODE_A",
        vat_rate: Decimal = DEFAULT_VAT_RATE,
        tourism_rate: Decimal = DEFAULT_TOURISM_RATE,
        tourism_enabled: bool = True,
    ):
        self.mode            = mode            # "MODE_A" | "MODE_B"
        self.vat_rate        = vat_rate
        self.tourism_rate    = tourism_rate
        self.tourism_enabled = tourism_enabled


def get_client_tax_config(db, client_id: str) -> TaxConfig:
    """يقرأ إعدادات الضريبة من invoice_settings في جدول clients."""
    settings: dict = {}
    if getattr(db, "use_postgres", False):
        try:
            row = db.execute(
                "SELECT invoice_settings FROM clients WHERE id=%s",
                (client_id,), fetch="one",
            )
            if row:
                raw = dict(row).get("invoice_settings") or {}
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except Exception:
                        raw = {}
                settings = raw
        except Exception as exc:
            log.warning("get_client_tax_config: %s", exc)

    return TaxConfig(
        mode            = settings.get("tax_mode", "MODE_A"),
        vat_rate        = Decimal(str(settings.get("vat_rate",      "0.15"))),
        tourism_rate    = Decimal(str(settings.get("tourism_rate",  "0.025"))),
        tourism_enabled = bool(settings.get("tourism_enabled", True)),
    )


def calculate_tax(
    amount: float,
    config: TaxConfig,
    discount: float = 0.0,
    tourism_enabled: Optional[bool] = None,
    tax_absorbed_by: str = "guest",
) -> dict:
    """يحسب الضريبة ويُعيد تفصيلاً موحَّداً لجميع الوحدات.

    MODE_A (إضافة الضريبة فوق المجموع):
        amount  = المجموع قبل الضريبة
        net     = amount - discount
        VAT     = net × vat_rate
        tourism = net × tourism_rate
        grand   = net + VAT + tourism

    MODE_B (استخراج الضريبة من المجموع الكلي):
        amount  = المجموع الكلي الشامل للضريبة (100%)
        grand   = amount - discount
        VAT     = grand × vat_rate        (15%)
        tourism = grand × tourism_rate    (2.5%)
        net     = grand - VAT - tourism   (82.5%)

    الإرجاع:
        {tax_mode, subtotal, discount, net,
         vat_rate, vat_amount,
         tourism_rate, tourism_tax_amount, tourism_enabled,
         tax_absorbed_by, grand_total}
    """
    t_enabled = tourism_enabled if tourism_enabled is not None else config.tourism_enabled
    t_rate    = config.tourism_rate if t_enabled else Decimal("0")

    gross = Decimal(str(amount)).quantize(_TWO, ROUND_HALF_UP)
    disc  = Decimal(str(discount)).quantize(_TWO, ROUND_HALF_UP)

    if config.mode == "MODE_A":
        net            = (gross - disc).quantize(_TWO, ROUND_HALF_UP)
        vat_amount     = (net * config.vat_rate).quantize(_TWO, ROUND_HALF_UP)
        tourism_amount = (net * t_rate).quantize(_TWO, ROUND_HALF_UP)
        if t_enabled and tax_absorbed_by == "property":
            grand_total = (net + vat_amount).quantize(_TWO, ROUND_HALF_UP)
        else:
            grand_total = (net + vat_amount + tourism_amount).quantize(_TWO, ROUND_HALF_UP)
        subtotal = gross
    else:
        # MODE_B — الضريبة مُضمَّنة في المبلغ المُدخل
        grand_total    = (gross - disc).quantize(_TWO, ROUND_HALF_UP)
        vat_amount     = (grand_total * config.vat_rate).quantize(_TWO, ROUND_HALF_UP)
        tourism_amount = (grand_total * t_rate).quantize(_TWO, ROUND_HALF_UP)
        net            = (grand_total - vat_amount - tourism_amount).quantize(_TWO, ROUND_HALF_UP)
        subtotal       = gross

    return {
        "tax_mode":           config.mode,
        "subtotal":           float(subtotal),
        "discount":           float(disc),
        "net":                float(net),
        "vat_rate":           float(config.vat_rate),
        "vat_amount":         float(vat_amount),
        "tourism_rate":       float(t_rate),
        "tourism_tax_amount": float(tourism_amount),
        "tourism_enabled":    t_enabled,
        "tax_absorbed_by":    tax_absorbed_by,
        "grand_total":        float(grand_total),
    }
