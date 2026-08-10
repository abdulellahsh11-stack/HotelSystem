#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ZATCA — فواتير إلكترونية + QR Code (TLV معيار ZATCA الرسمي)"""
import base64
import json
import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

# المنطق الموحَّد لـ TLV/QR يعيش في services/zatca.py (مصدر واحد، بلا تكرار)
from services.zatca import (
    build_tlv,
    decode_tlv,
    generate_qr_image_base64,
    validate_vat_number,
)
from services.tax_config import get_client_tax_config, calculate_tax as _calc_tax

router = APIRouter(prefix="/api/zatca", tags=["ZATCA"])
log = logging.getLogger("dheuof.zatca")

TWO = Decimal("0.01")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


def _next_invoice_number(db, client_id: str) -> str:
    year = datetime.now().year
    if db.use_postgres:
        try:
            row = db.execute("""
                INSERT INTO sequences (client_id, invoice_seq)
                VALUES (%s, 1)
                ON CONFLICT (client_id) DO UPDATE
                    SET invoice_seq = sequences.invoice_seq + 1
                RETURNING invoice_seq
            """, (client_id,), fetch="one")
            seq = row["invoice_seq"] if row else 1
        except Exception:
            seq = 1
    else:
        seq = 1
    return f"ZATCA-{year}-{seq:06d}"


# ── Schemas ──────────────────────────────────────────────────────────────────

class GenerateInvoiceRequest(BaseModel):
    booking_id: str
    guest_name: Optional[str] = None
    guest_id: Optional[str] = None
    subtotal: float
    discount: float = 0.0
    supply_date: Optional[str] = None
    invoice_type: str = "SIMPLIFIED"
    tourism_tax_enabled: bool = False
    tax_absorbed_by: str = "guest"  # "guest" | "property"


class VerifyQrRequest(BaseModel):
    qr_data: str


class CreditNoteRequest(BaseModel):
    reason: str


class ReplyRequest(BaseModel):
    reply: str


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/invoices/generate")
async def generate_invoice(
    body: GenerateInvoiceRequest,
    request: Request,
    session=Depends(_require_client),
):
    db = request.app.state.db
    cid = session["client_id"]

    # بيانات المنشأة الضريبية
    if db.use_postgres:
        row = db.execute("SELECT * FROM clients WHERE id=%s", (cid,), fetch="one")
        client_data = dict(row) if row else {}
        inv_settings = client_data.get("invoice_settings") or {}
        if isinstance(inv_settings, str):
            try:
                inv_settings = json.loads(inv_settings)
            except Exception:
                inv_settings = {}
    else:
        store = db.json_read()
        client_data = next((c for c in store.get("clients", []) if c.get("id") == cid), {})
        inv_settings = client_data.get("invoice_settings", {})

    seller_name = inv_settings.get("company_name") or client_data.get("name", "منشأة ضيوف")
    vat_number  = inv_settings.get("vat_number", "")

    # التحقق من الرقم الضريبي (اختياري) — يُطبَّق فقط إذا أُدخل رقم.
    # القاعدة من services/zatca.py: 15 رقماً يبدأ وينتهي بـ 3.
    if vat_number and not validate_vat_number(vat_number):
        raise HTTPException(
            400, "الرقم الضريبي للمنشأة غير صالح — يجب أن يكون 15 رقماً يبدأ وينتهي بالرقم 3"
        )

    # حسابات مالية — تُقرأ الأسعار من إعدادات الضريبة للعميل
    tax_cfg = get_client_tax_config(db, cid)
    tax = _calc_tax(
        amount=body.subtotal,
        config=tax_cfg,
        discount=body.discount,
        tourism_enabled=body.tourism_tax_enabled,
        tax_absorbed_by=body.tax_absorbed_by,
    )
    subtotal       = Decimal(str(tax["subtotal"])).quantize(TWO, ROUND_HALF_UP)
    discount       = Decimal(str(tax["discount"])).quantize(TWO, ROUND_HALF_UP)
    vat_amount     = Decimal(str(tax["vat_amount"])).quantize(TWO, ROUND_HALF_UP)
    tourism_rate   = Decimal(str(tax["tourism_rate"])).quantize(Decimal("0.0001"), ROUND_HALF_UP)
    tourism_amount = Decimal(str(tax["tourism_tax_amount"])).quantize(TWO, ROUND_HALF_UP)
    absorbed_by    = tax["tax_absorbed_by"]
    total          = Decimal(str(tax["grand_total"])).quantize(TWO, ROUND_HALF_UP)

    # بناء TLV
    timestamp  = datetime.now().isoformat()
    tlv_bytes  = build_tlv(seller_name, vat_number or "0000000000000000",
                           timestamp, str(total), str(vat_amount))
    tlv_b64    = base64.b64encode(tlv_bytes).decode()
    qr_image   = generate_qr_image_base64(tlv_b64)
    inv_number = _next_invoice_number(db, cid)

    supply_date = body.supply_date or timestamp[:10]
    now_ts      = datetime.now()

    if db.use_postgres:
        try:
            row = db.execute("""
                INSERT INTO zatca_invoices
                    (client_id, invoice_number, booking_id, guest_id,
                     invoice_type, issue_date, supply_date,
                     subtotal, discount, vat_rate, vat_amount, total,
                     vat_number, buyer_name,
                     zatca_status, qr_tlv_base64, qr_image_base64,
                     tourism_tax_rate, tourism_tax_amount, tax_absorbed_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING *
            """, (
                cid, inv_number, body.booking_id, body.guest_id,
                body.invoice_type, now_ts, supply_date,
                float(subtotal), float(discount), float(tax_cfg.vat_rate),
                float(vat_amount), float(total),
                vat_number, body.guest_name,
                "CLEARED", tlv_b64, qr_image,
                float(tourism_rate), float(tourism_amount), absorbed_by,
            ), fetch="one")
            _ = dict(row) if row else {}
        except Exception as e:
            log.error("DB insert zatca_invoice: %s", e)
            pass
    else:
        pass

    return {
        "success": True,
        "data": {
            "invoice_number": inv_number,
            "subtotal": float(subtotal),
            "discount": float(discount),
            "vat_amount": float(vat_amount),
            "tourism_tax_rate": float(tourism_rate),
            "tourism_tax_amount": float(tourism_amount),
            "tax_absorbed_by": absorbed_by,
            "total": float(total),
            "vat_number": vat_number,
            "seller_name": seller_name,
            "buyer_name": body.guest_name,
            "issue_date": timestamp,
            "supply_date": supply_date,
            "zatca_status": "CLEARED",
            "qr_tlv_base64": tlv_b64,
            "qr_image_base64": qr_image,
            "invoice_type": body.invoice_type,
        },
        "message": f"تم إصدار الفاتورة {inv_number}",
    }


@router.get("/invoices")
async def list_invoices(
    request: Request,
    page: int = 1,
    per_page: int = 50,
    booking_id: Optional[str] = None,
    session=Depends(_require_client),
):
    db = request.app.state.db
    cid = session["client_id"]
    limit = min(per_page, 200)
    offset = (page - 1) * limit

    if db.use_postgres:
        try:
            conditions = ["client_id=%s", "is_deleted=FALSE"]
            params: list = [cid]
            if booking_id:
                conditions.append("booking_id=%s")
                params.append(booking_id)
            where = " AND ".join(conditions)
            rows = db.execute(
                f"SELECT * FROM zatca_invoices WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                params + [limit, offset], fetch="all"
            )
            total_row = db.execute(
                f"SELECT COUNT(*) AS n FROM zatca_invoices WHERE {where}", params, fetch="one"
            )
            total = total_row["n"] if total_row else 0
            items = [dict(r) for r in (rows or [])]
        except Exception as e:
            log.error("list_invoices: %s", e)
            items, total = [], 0
    else:
        items, total = [], 0

    return {
        "success": True,
        "data": items,
        "meta": {"page": page, "per_page": limit, "total": total},
    }


@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: int,
    request: Request,
    session=Depends(_require_client),
):
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        row = db.execute(
            "SELECT * FROM zatca_invoices WHERE id=%s AND client_id=%s AND is_deleted=FALSE",
            (invoice_id, cid), fetch="one"
        )
        if not row:
            raise HTTPException(404, "الفاتورة غير موجودة")
        return {"success": True, "data": dict(row)}
    raise HTTPException(404, "الفاتورة غير موجودة")


@router.get("/invoices/{invoice_id}/qr")
async def get_qr_image(
    invoice_id: int,
    request: Request,
    session=Depends(_require_client),
):
    """يُعيد صورة QR Code كـ PNG مباشرة"""
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        row = db.execute(
            "SELECT qr_image_base64, qr_tlv_base64 FROM zatca_invoices WHERE id=%s AND client_id=%s",
            (invoice_id, cid), fetch="one"
        )
        if row and row.get("qr_image_base64"):
            img_bytes = base64.b64decode(row["qr_image_base64"])
            return Response(content=img_bytes, media_type="image/png")
    raise HTTPException(404, "QR غير موجود")


@router.post("/verify-qr")
async def verify_qr(body: VerifyQrRequest, request: Request):
    """تحقق من QR Code — لا يتطلب تسجيل دخول"""
    try:
        tlv_bytes = base64.b64decode(body.qr_data)
        fields    = decode_tlv(tlv_bytes)
    except Exception:
        return {
            "success": False,
            "data": {"is_valid": False, "message": "رمز QR غير صالح ❌"},
        }

    seller_name = fields.get(1, "")
    vat_number  = fields.get(2, "")
    timestamp   = fields.get(3, "")
    total       = fields.get(4, "")
    vat_amount  = fields.get(5, "")

    # البحث عن الفاتورة في قاعدة البيانات
    invoice = None
    db = request.app.state.db
    if db.use_postgres:
        try:
            row = db.execute(
                "SELECT * FROM zatca_invoices WHERE qr_tlv_base64=%s AND is_deleted=FALSE LIMIT 1",
                (body.qr_data,), fetch="one"
            )
            invoice = dict(row) if row else None
        except Exception as e:
            log.warning("verify_qr db lookup: %s", e)

    is_valid = invoice is not None and invoice.get("zatca_status") in ("CLEARED", "REPORTED")

    return {
        "success": True,
        "data": {
            "is_valid": is_valid,
            "seller_name": seller_name,
            "vat_number": vat_number,
            "issue_date": timestamp,
            "total": total,
            "vat_amount": vat_amount,
            # لا تُعاد المعرّفات الداخلية (invoice_number · booking_id):
            # هذه نقطة عامة بلا مصادقة تبحث في فواتير كل المنشآت، فإعادة
            # معرّف داخلي منها تكشف بيانات منشأة لمن يحمل رمز QR فقط.
            # المطلوب للتحقق هو الصحة لا الهوية.
            "zatca_status": invoice.get("zatca_status") if invoice else "NOT_FOUND",
            "message": "فاتورة صحيحة ومعتمدة ✅" if is_valid else "فاتورة غير معروفة ❌",
        },
    }


@router.post("/invoices/{invoice_id}/credit-note")
async def issue_credit_note(
    invoice_id: int,
    body: CreditNoteRequest,
    request: Request,
    session=Depends(_require_client),
):
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        orig = db.execute(
            "SELECT * FROM zatca_invoices WHERE id=%s AND client_id=%s",
            (invoice_id, cid), fetch="one"
        )
        if not orig:
            raise HTTPException(404, "الفاتورة الأصلية غير موجودة")

        orig = dict(orig)
        tlv_bytes = build_tlv(
            orig.get("buyer_name") or "عميل",
            orig.get("vat_number") or "",
            datetime.now().isoformat(),
            f"-{orig['total']}",
            f"-{orig['vat_amount']}",
        )
        tlv_b64  = base64.b64encode(tlv_bytes).decode()
        qr_image = generate_qr_image_base64(tlv_b64)
        cn_number = _next_invoice_number(db, cid).replace("ZATCA-", "CN-")

        db.execute("""
            INSERT INTO zatca_invoices
                (client_id, invoice_number, booking_id, guest_id,
                 invoice_type, subtotal, vat_rate, vat_amount, total,
                 vat_number, buyer_name, zatca_status,
                 qr_tlv_base64, qr_image_base64)
            VALUES (%s,%s,%s,%s,'CREDIT',%s,%s,%s,%s,%s,%s,'CLEARED',%s,%s)
        """, (
            cid, cn_number, orig.get("booking_id"), orig.get("guest_id"),
            -float(orig["subtotal"]), float(orig.get("vat_rate", 0.15)),
            -float(orig["vat_amount"]), -float(orig["total"]),
            orig.get("vat_number"), orig.get("buyer_name"),
            tlv_b64, qr_image,
        ))

        return {
            "success": True,
            "data": {"credit_note_number": cn_number},
            "message": f"تم إصدار فاتورة الدائن {cn_number}",
        }
    raise HTTPException(400, "يتطلب قاعدة بيانات PostgreSQL")
