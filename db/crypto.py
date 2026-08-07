#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/crypto.py — تشفير حقول الهوية الشخصية (PII) والبحث فيها.

الدافع
──────
كانت أرقام الهوية الوطنية والإقامة وهويات النزلاء تُخزَّن نصاً صريحاً في
VARCHAR(20):

    guests.id_number          — رقم هوية النزيل
    employees.national_id     — الهوية الوطنية للموظف
    employees.iqama_number    — رقم الإقامة

أي نسخة احتياطية مسرَّبة أو وصول للقراءة على قاعدة البيانات يكشفها
مباشرة. ونظام حماية البيانات الشخصية السعودي يصنّف هذه الحقول بيانات
حسّاسة تستوجب حماية تقنية.

لماذا التشفير في التطبيق لا في قاعدة البيانات
────────────────────────────────────────────
pgcrypto يوجب تمرير المفتاح داخل نص كل استعلام:

    SELECT pgp_sym_decrypt(id_number_enc, 'المفتاح') FROM guests;

فينتهي المفتاح إلى سجلات الاستعلامات و pg_stat_statements وخطط التنفيذ —
أي إلى نفس المكان الذي نحمي البيانات منه. التشفير هنا يبقي المفتاح في
ذاكرة التطبيق ولا ترى قاعدة البيانات إلا النص المشفَّر.

البحث في حقل مشفَّر
───────────────────
النص المشفَّر بـ AES-GCM مختلف في كل مرة (nonce عشوائي)، فلا يصلح
للمقارنة ولا للفهرسة. لذلك يُخزَّن معه «فهرس أعمى»:

    blind_index(value) = HMAC-SHA256(القيمة المُطبَّعة, فلفل سرّي)

قيمة ثابتة لنفس المدخل، قابلة للفهرسة، ولا تكشف الأصل. تتيح البحث
بالمساواة (وهو كل ما يحتاجه البحث برقم هوية) دون فكّ تشفير أي صف.

المفاتيح
────────
PII_ENCRYPTION_KEY — 32 بايت بترميز base64 (توليدها: python -m db.crypto)
PII_BLIND_INDEX_PEPPER — سلسلة سرّية للفهرس الأعمى

بغياب المفتاح تعمل الوحدة في وضع التمرير: تُعيد النص كما هو مع تحذير
واضح. هذا مقصود كي لا ينهار نشرٌ قائم لم تُضبط متغيراته بعد — لكن
السجل يُظهر أن البيانات غير محمية.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets

log = logging.getLogger("dheuof.crypto")

# بادئة تُميّز النص المشفَّر عن النص الصريح وتحمل رقم الإصدار، فتمكن
# ترقية الخوارزمية لاحقاً دون التباس
_PREFIX = "enc:v1:"

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _AESGCM_AVAILABLE = True
except Exception:  # pragma: no cover - يعتمد على البيئة
    AESGCM = None
    _AESGCM_AVAILABLE = False


def _load_key() -> bytes | None:
    raw = os.environ.get("PII_ENCRYPTION_KEY", "").strip()
    if not raw:
        return None
    try:
        key = base64.b64decode(raw)
    except Exception:
        log.error("PII_ENCRYPTION_KEY ليس base64 صالحاً — التشفير معطّل")
        return None
    if len(key) != 32:
        log.error(f"PII_ENCRYPTION_KEY طوله {len(key)} بايت، والمطلوب 32 — التشفير معطّل")
        return None
    return key


def _pepper() -> bytes:
    """فلفل الفهرس الأعمى — يعود إلى مفتاح التشفير إن لم يُضبط منفصلاً."""
    p = os.environ.get("PII_BLIND_INDEX_PEPPER", "").strip()
    if p:
        return p.encode("utf-8")
    key = _load_key()
    return key if key else b""


def encryption_available() -> bool:
    """هل التشفير مُفعَّل فعلياً؟ يُستخدم في /health وتقارير الجاهزية."""
    return _AESGCM_AVAILABLE and _load_key() is not None


def is_encrypted(value: str | None) -> bool:
    return bool(value) and str(value).startswith(_PREFIX)


# ── التشفير وفكّه ─────────────────────────────────────────────────────────────

def encrypt_pii(plaintext: str | None) -> str | None:
    """يُشفّر قيمة حسّاسة بـ AES-256-GCM.

    يُعيد القيمة كما هي إن كانت فارغة، أو مشفّرة سلفاً، أو إن لم يُضبط
    المفتاح (وضع التمرير مع تحذير).
    """
    if plaintext is None or plaintext == "":
        return plaintext
    plaintext = str(plaintext)
    if is_encrypted(plaintext):
        return plaintext

    key = _load_key()
    if not key or not _AESGCM_AVAILABLE:
        log.warning(
            "PII_ENCRYPTION_KEY غير مضبوط — أرقام الهوية تُخزَّن نصاً صريحاً"
        )
        return plaintext

    nonce = secrets.token_bytes(12)
    blob = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return _PREFIX + base64.b64encode(nonce + blob).decode("ascii")


def decrypt_pii(ciphertext: str | None) -> str | None:
    """يفكّ التشفير. النص غير المشفَّر يُعاد كما هو (صفوف ما قبل الترحيل)."""
    if not ciphertext or not is_encrypted(ciphertext):
        return ciphertext

    key = _load_key()
    if not key or not _AESGCM_AVAILABLE:
        log.error("قيمة مشفَّرة بلا مفتاح — تعذّر فكّ التشفير")
        return None

    try:
        raw = base64.b64decode(ciphertext[len(_PREFIX):])
        return AESGCM(key).decrypt(raw[:12], raw[12:], None).decode("utf-8")
    except Exception as e:
        log.error(f"فشل فكّ التشفير: {e}")
        return None


# ── الفهرس الأعمى ─────────────────────────────────────────────────────────────

def normalize_id(value: str | None) -> str:
    """يُطبّع رقم الهوية قبل الفهرسة.

    يُزيل الفراغات والشرطات ويُحوّل الأرقام العربية الهندية إلى لاتينية،
    كي يجد البحث «١٢٣٤ ٥٦٧٨» و«1234-5678» نفس الصف.
    """
    if not value:
        return ""
    arabic = "٠١٢٣٤٥٦٧٨٩"
    out = []
    for ch in str(value):
        if ch in arabic:
            out.append(str(arabic.index(ch)))
        elif ch.isalnum():
            out.append(ch)
    return "".join(out).upper()


def blind_index(value: str | None) -> str | None:
    """يُنتج فهرساً أعمى قابلاً للفهرسة والبحث بالمساواة."""
    normalized = normalize_id(value)
    if not normalized:
        return None
    pepper = _pepper()
    if not pepper:
        # بلا فلفل يصبح الفهرس SHA عادياً قابلاً للتخمين بجدول قوس قزح —
        # أرقام الهوية فضاؤها صغير. نمتنع بدل إعطاء أمان وهمي.
        return None
    return hmac.new(pepper, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


# ── توليد المفاتيح ────────────────────────────────────────────────────────────

def generate_key() -> str:
    """يولّد مفتاح AES-256 بترميز base64 جاهزاً لمتغيرات البيئة."""
    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")


if __name__ == "__main__":  # pragma: no cover
    print("=" * 60)
    print("  مفاتيح تشفير بيانات الهوية — ضيوف")
    print("=" * 60)
    print("  أضف السطرين التاليين إلى متغيرات البيئة:")
    print()
    print(f"  PII_ENCRYPTION_KEY={generate_key()}")
    print(f"  PII_BLIND_INDEX_PEPPER={secrets.token_urlsafe(32)}")
    print()
    print("  ⚠️  احتفظ بنسخة آمنة من المفتاح. فقدانه يعني فقدان القدرة")
    print("     على قراءة أرقام الهوية المخزَّنة نهائياً.")
    print("=" * 60)
