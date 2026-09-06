#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/accounting_export.py — دفتر أستاذٍ موحّد وتصديره (البند ٤).

يجمع سجلّي المال في المنصّة — الدفعات (payments) والقيود المحاسبية
(journal_entries) — في صفوفٍ موحّدة، كلٌّ مربوطٌ بمصدره (dat: دفعة نقطة
بيع بجهازها · دفعة تسجيل دخولٍ بحجزها · قيدٌ خارجيٌّ بمرجعه)، ثم يُصدّرها
CSV (بترميز يقرؤه إكسل العربي) أو JSON.

منطقٌ خالصٌ لا يلمس قاعدة البيانات: يستقبل صفوفاً مقروءةً مسبقاً فيُختبَر
دون PostgreSQL.
"""
from __future__ import annotations

import csv
import io

LEDGER_COLUMNS = ["date", "kind", "source", "reference",
                  "description", "method", "amount", "currency"]


def _amount(v) -> float:
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _entry_total(lines) -> float:
    """مقدار القيد = مجموع المدين، وإلا مجموع الدائن (فالطرفان متساويان)."""
    debit = credit = 0.0
    for ln in lines or []:
        if not isinstance(ln, dict):
            continue
        debit += _amount(ln.get("debit"))
        credit += _amount(ln.get("credit"))
    return round(debit or credit, 2)


def build_ledger(payments, journal_entries) -> list[dict]:
    """يبني صفوف دفتر الأستاذ الموحّدة، الأحدث أولاً."""
    rows: list[dict] = []
    for p in payments or []:
        did = p.get("device_id")
        method = str(p.get("method") or "")
        source = f"pos_device:{did}" if did else (method or "payment")
        rows.append({
            "date": str(p.get("created_at") or "")[:10],
            "kind": "payment",
            "source": source,
            "reference": p.get("reference") or "",
            "description": "",
            "method": method,
            "amount": _amount(p.get("amount")),
            "currency": p.get("currency") or "SAR",
        })
    for j in journal_entries or []:
        rows.append({
            "date": str(j.get("entry_date") or j.get("created_at") or "")[:10],
            "kind": "journal",
            "source": j.get("source") or "external",
            "reference": j.get("reference") or "",
            "description": j.get("description") or "",
            "method": "",
            "amount": _entry_total(j.get("lines")),
            "currency": "SAR",
        })
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows


def to_csv(rows, columns=LEDGER_COLUMNS) -> str:
    """CSV سليمٌ (يهرّب الفواصل والاقتباس والأسطر) مع BOM ليقرأه إكسل عربيّاً."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore",
                            lineterminator="\n")
    writer.writeheader()
    for r in rows or []:
        writer.writerow(r)
    return "﻿" + buf.getvalue()


def to_json(rows) -> list[dict]:
    return list(rows or [])
