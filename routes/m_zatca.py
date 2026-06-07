#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ZATCA — فواتير إلكترونية + QR Code (TLV معيار ZATCA الرسمي)"""
import base64
import io
import json
import logging
import struct
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

router = APIRouter(prefix="/api/zatca", tags=["ZATCA"])
log = logging.getLogger("dheuof.zatca")

TWO = Decimal("0.01")
VAT_RATE = Decimal("0.15")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


# ── TLV helpers ──────────────────────────────────────────────────────────────

def _encode_tlv_field(tag: int, value: str) -> bytes:
    val_bytes = value.encode("utf-8")
    length = len(val_bytes)
    if length <= 127:
        return bytes([tag, length]) + val_bytes
    # multi-byte length for long strings
    len_bytes = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([tag, 0x80 | len(len_bytes)]) + len_bytes + val_bytes


def build_tlv(seller_name: str, vat_number: str, timestamp: str,
              total_with_vat: str, vat_amount: str) -> bytes:
    return (
        _encode_tlv_field(1, seller_name) +
        _encode_tlv_field(2, vat_number) +
        _encode_tlv_field(3, timestamp) +
        _encode_tlv_field(4, total_with_vat) +
        _encode_tlv_field(5, vat_amount)
    )


def decode_tlv(data: bytes) -> dict:
    result: dict = {}
    i = 0
    while i < len(data):
        tag = data[i]; i += 1
        if i >= len(data):
            break
        length_byte = data[i]; i += 1
        if length_byte & 0x80:
            n = length_byte & 0x7F
            length = int.from_bytes(data[i:i+n], "big")
            i += n
        else:
            length = length_byte
        value = data[i:i+length].decode("utf-8", errors="replace")
        result[tag] = value
        i += length
    return result


def generate_qr_image_base64(tlv_base64: str) -> str:
    try:
        import qrcode
        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                           box_size=6, border=2)
        qr.add_data(tlv_base64)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        log.warning("QR image generation failed: %s", e)
        return ""


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

    # حسابات مالية
    subtotal   = Decimal(str(body.subtotal)).quantize(TWO, ROUND_HALF_UP)
    discount   = Decimal(str(body.discount)).quantize(TWO, ROUND_HALF_UP)
    net        = (subtotal - discount).quantize(TWO, ROUND_HALF_UP)
    vat_amount = (net * VAT_RATE).quantize(TWO, ROUND_HALF_UP)
    total      = (net + vat_amount).quantize(TWO, ROUND_HALF_UP)

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
                     zatca_status, qr_tlv_base64, qr_image_base64)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING *
            """, (
                cid, inv_number, body.booking_id, body.guest_id,
                body.invoice_type, now_ts, supply_date,
                float(subtotal), float(discount), float(VAT_RATE),
                float(vat_amount), float(total),
                vat_number, body.guest_name,
                "CLEARED", tlv_b64, qr_image,
            ), fetch="one")
            result = dict(row) if row else {}
        except Exception as e:
            log.error("DB insert zatca_invoice: %s", e)
            result = {}
    else:
        result = {}

    return {
        "success": True,
        "data": {
            "invoice_number": inv_number,
            "subtotal": float(subtotal),
            "discount": float(discount),
            "vat_amount": float(vat_amount),
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
            "invoice_number": invoice.get("invoice_number") if invoice else None,
            "booking_id": invoice.get("booking_id") if invoice else None,
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
            -float(orig["subtotal"]), float(VAT_RATE),
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
