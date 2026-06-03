#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
خدمة الفوترة الإلكترونية المتوافقة مع هيئة الزكاة والضريبة (ZATCA / فاتورة)
=========================================================================
تُطبّق متطلبات المرحلة الأولى (Phase 1 — Generation) لفاتورة ضريبية مبسّطة:

حقول إلزامية في رمز QR (مُرمّزة TLV ثم Base64):
  Tag 1 — اسم البائع (Seller name)            ← اسم الشركة
  Tag 2 — الرقم الضريبي (VAT registration no.)
  Tag 3 — الطابع الزمني (Timestamp ISO-8601)
  Tag 4 — إجمالي الفاتورة شامل الضريبة
  Tag 5 — إجمالي ضريبة القيمة المضافة

كذلك يُضاف: اسم الضيف (المشتري)، رقمه الضريبي (اختياري)، UUID، وبصمة hash.
نسبة ض.ق.م القياسية في السعودية: 15%.
"""
import base64
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone

log = logging.getLogger("dheuof.zatca")

VAT_RATE = 0.15  # 15% ضريبة القيمة المضافة في السعودية


# ── ترميز TLV (Tag-Length-Value) ──────────────────────────────
def _tlv(tag: int, value: str) -> bytes:
    """يُرمّز حقلاً واحداً بصيغة TLV (UTF-8)."""
    vb = value.encode("utf-8")
    return bytes([tag, len(vb)]) + vb


def generate_qr_base64(seller_name: str, vat_number: str, timestamp: str,
                       total_with_vat, vat_total) -> str:
    """
    يُولّد سلسلة QR متوافقة مع ZATCA (Base64 لتسلسل TLV من 5 حقول).
    تُحقن هذه السلسلة في رمز QR على الفاتورة.
    """
    payload = (
        _tlv(1, str(seller_name)) +
        _tlv(2, str(vat_number)) +
        _tlv(3, str(timestamp)) +
        _tlv(4, f"{float(total_with_vat):.2f}") +
        _tlv(5, f"{float(vat_total):.2f}")
    )
    return base64.b64encode(payload).decode("ascii")


def validate_vat_number(vat: str) -> bool:
    """
    الرقم الضريبي السعودي: 15 رقماً، يبدأ بـ 3 وينتهي بـ 3 (قاعدة الهيئة).
    """
    vat = (vat or "").strip()
    return (len(vat) == 15 and vat.isdigit()
            and vat.startswith("3") and vat.endswith("3"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ZatcaInvoiceService:
    """خدمة بناء وتخزين الفواتير الضريبية المتوافقة مع ZATCA."""

    def __init__(self, db):
        self.db = db
        try:
            self.ensure_schema()
        except Exception as e:  # pragma: no cover
            log.warning(f"تعذّر تهيئة مخطط فواتير ZATCA: {e}")

    def ensure_schema(self) -> None:
        """يضيف حقول ZATCA إلى جدول الفواتير الموجود (idempotent)."""
        if not getattr(self.db, "use_postgres", False):
            return
        cols = [
            ("zatca_uuid",    "VARCHAR(40)"),
            ("company_name",  "VARCHAR(200)"),   # اسم الشركة (البائع)
            ("seller_vat",    "VARCHAR(20)"),    # الرقم الضريبي للبائع
            ("buyer_name",    "VARCHAR(200)"),   # اسم الضيف (المشتري)
            ("buyer_vat",     "VARCHAR(20)"),    # الرقم الضريبي للمشتري (اختياري)
            ("zatca_qr",      "TEXT"),           # سلسلة QR (Base64 TLV)
            ("invoice_hash",  "VARCHAR(64)"),    # بصمة الفاتورة
            ("invoice_type",  "VARCHAR(20)"),    # standard | simplified
        ]
        for name, typ in cols:
            try:
                self.db.execute(
                    f"ALTER TABLE invoices ADD COLUMN IF NOT EXISTS {name} {typ}")
            except Exception as e:  # pragma: no cover
                log.warning(f"تعذّر إضافة العمود {name}: {e}")

    # ── بناء الفاتورة ─────────────────────────────────────────
    def build_invoice(self, company_name: str, seller_vat: str,
                      guest_name: str, line_items: list,
                      buyer_vat: str = "", invoice_type: str = "simplified",
                      timestamp: str = None) -> dict:
        """
        يبني فاتورة ضريبية كاملة من بنود الخدمة.
        line_items: [{description, qty, unit_price}]
        يُعيد: subtotal, vat_amount, total, qr, hash, uuid + كل الحقول.
        """
        if not company_name or not str(company_name).strip():
            raise ValueError("اسم الشركة مطلوب")
        if not validate_vat_number(seller_vat):
            raise ValueError("الرقم الضريبي للبائع غير صالح — يجب 15 رقماً يبدأ وينتهي بـ 3")
        if buyer_vat and not validate_vat_number(buyer_vat):
            raise ValueError("الرقم الضريبي للمشتري غير صالح")
        if not line_items:
            raise ValueError("بنود الفاتورة مطلوبة")

        ts = timestamp or _now_iso()
        # حساب الإجماليات
        items = []
        subtotal = 0.0
        for it in line_items:
            qty = float(it.get("qty", 1))
            unit = float(it.get("unit_price", 0))
            line_total = round(qty * unit, 2)
            subtotal += line_total
            items.append({
                "description": str(it.get("description", "")),
                "qty": qty, "unit_price": unit, "line_total": line_total,
            })
        subtotal = round(subtotal, 2)
        vat_amount = round(subtotal * VAT_RATE, 2)
        total = round(subtotal + vat_amount, 2)

        qr = generate_qr_base64(company_name, seller_vat, ts, total, vat_amount)
        inv_uuid = str(uuid.uuid4())
        hash_src = f"{company_name}|{seller_vat}|{guest_name}|{ts}|{total}|{vat_amount}|{inv_uuid}"
        inv_hash = hashlib.sha256(hash_src.encode("utf-8")).hexdigest()

        return {
            "zatca_uuid": inv_uuid,
            "invoice_type": invoice_type,
            "company_name": company_name,
            "seller_vat": seller_vat,
            "buyer_name": guest_name,
            "buyer_vat": buyer_vat or "",
            "timestamp": ts,
            "line_items": items,
            "subtotal": subtotal,
            "vat_rate": VAT_RATE,
            "vat_amount": vat_amount,
            "total_amount": total,
            "currency": "SAR",
            "zatca_qr": qr,
            "invoice_hash": inv_hash,
        }

    # ── تخزين الفاتورة ────────────────────────────────────────
    def save_invoice(self, client_id: str, inv: dict, booking_id: str = None) -> dict:
        """يخزّن الفاتورة في جدول invoices مع حقول ZATCA."""
        inv_id = "INV-" + inv["zatca_uuid"][:8].upper()
        if not getattr(self.db, "use_postgres", False):
            return {"id": inv_id, **inv, "stored": False}
        self.db.execute(
            """INSERT INTO invoices
               (id, client_id, booking_id, issue_date, subtotal, vat_amount,
                total_amount, payment_status, line_items,
                zatca_uuid, company_name, seller_vat, buyer_name, buyer_vat,
                zatca_qr, invoice_hash, invoice_type)
               VALUES (%s,%s,%s,CURRENT_DATE,%s,%s,%s,'paid',%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (id) DO NOTHING""",
            (inv_id, client_id, booking_id, inv["subtotal"], inv["vat_amount"],
             inv["total_amount"], json.dumps(inv["line_items"], ensure_ascii=False),
             inv["zatca_uuid"], inv["company_name"], inv["seller_vat"],
             inv["buyer_name"], inv["buyer_vat"], inv["zatca_qr"],
             inv["invoice_hash"], inv["invoice_type"]))
        return {"id": inv_id, **inv, "stored": True}

    def get_invoice(self, client_id: str, invoice_id: str) -> dict:
        if not getattr(self.db, "use_postgres", False):
            return None
        row = self.db.execute(
            "SELECT * FROM invoices WHERE client_id=%s AND id=%s",
            (client_id, invoice_id), fetch="one")
        return dict(row) if row else None

    def list_invoices(self, client_id: str, limit: int = 100) -> list:
        if not getattr(self.db, "use_postgres", False):
            return []
        rows = self.db.execute(
            """SELECT id, issue_date, company_name, buyer_name, subtotal,
                      vat_amount, total_amount, payment_status, zatca_uuid
               FROM invoices WHERE client_id=%s
               ORDER BY created_at DESC LIMIT %s""",
            (client_id, limit), fetch="all")
        return [dict(r) for r in (rows or [])]
