#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/guest_crypto.py — تشفير بيانات النزلاء الحسّاسة

## ما الذي يحميه هذا الملف، وما الذي لا يحميه

التشفير هنا **تشفيرٌ عند التخزين** (at rest). يحمي من:

  · نسخةٍ احتياطية مسروقة أو مسرَّبة
  · لقطة قاعدة بيانات تُنسَخ إلى جهاز مطوّر
  · من يملك وصولاً لقاعدة البيانات دون التطبيق (مزوّد الاستضافة، DBA)

و**لا يحمي** من: من يملك وصولاً إلى التطبيق نفسه ومفتاحه. لأن التطبيق
يجب أن يفكّ التشفير ليعرض الاسم لموظف الاستقبال — ومن ملك التطبيق ملك
قدرته على الفكّ.

لذلك «التشفير إلا لفلان» ليس آليةً واحدة بل اثنتان:

| الخطر | الآلية | مكانها |
|---|---|---|
| تسريب قاعدة البيانات | التشفير | هذا الملف |
| مستخدمٌ غير مخوَّل في النظام | الصلاحيات | `guests.pii` في المسارات |

من يخلط بينهما يظنّ نفسه محمياً وهو ليس كذلك.

## الصيغة

`v1:<nonce base64>:<ciphertext+tag base64>`

AES-256-GCM: يمنع القراءة **ويكشف العبث**. لو غُيّر حرفٌ في قاعدة
البيانات فشل الفكّ بدل أن يُعيد نصّاً خاطئاً بصمت.

البادئة `v1` لتدوير المفاتيح لاحقاً: صفٌّ قديم يُعرَف بصيغته.

## الفهرسة العمياء

الحقل المشفَّر لا يُبحَث فيه: نفس الرقم يُنتج نصّاً مختلفاً كل مرة
(وهذا مقصود — التشفير الحتمي يُسرّب التكرار). فلكي يبقى البحث برقم
الهوية ممكناً يُخزَّن معه **فهرسٌ أعمى**: HMAC-SHA256 للرقم بمفتاح
منفصل. يُطابَق ولا يُعكَس.

> المفتاح والفهرس مفتاحان **منفصلان** عمداً: تسريب أحدهما لا يُسقط
> الآخر.

## فقدان المفتاح = فقدان البيانات

لا باب خلفياً. المفتاح يُحفظ في متغيّر بيئة **وتُحفظ منه نسخة خارج
المنصة**. ضياعه يعني أن أرقام الهوية لا تعود أبداً.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
from typing import Optional

log = logging.getLogger("dheuof.crypto")

PREFIX = "v1"
_NONCE_BYTES = 12          # المقاس القياسي لـGCM
KEY_ENV = "GUEST_ENCRYPTION_KEY"
INDEX_KEY_ENV = "GUEST_INDEX_KEY"

# الحقول التي تُشفَّر. `full_name` ليس منها عمداً — انظر التفسير أسفله.
ENCRYPTED_FIELDS = ("id_number", "absher_phone", "birth_date", "notes")

# لماذا لا يُشفَّر الاسم؟
#
# الاسم يُعرَض في كل قائمة ويُبحَث به في كل شاشة. تشفيره يعني أن البحث
# بالاسم يتطلّب فكّ كل صفٍّ في الجدول عند كل استعلام — أي تعطيلُ البحث
# عملياً على أي عدد حقيقي من النزلاء. والاسم وحده — بلا رقم هوية ولا
# جوال ولا تاريخ ميلاد — قيمتُه لمن يسرق قاعدة البيانات ضئيلة.
#
# فالاسم يُحجب بالصلاحيات لا بالتشفير: من لا يملك `guests.pii` يراه
# مُقنَّعاً.


class CryptoNotConfigured(RuntimeError):
    """يُرفع حين يُطلب التشفير بلا مفتاح — ولا يُبتلع أبداً."""


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _load_key(env_name: str, purpose: str) -> Optional[bytes]:
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return None
    try:
        key = _b64d(raw)
    except Exception as exc:
        raise CryptoNotConfigured(
            f"{env_name} ليس base64 صالحاً ({purpose}): {exc}"
        ) from None
    if len(key) != 32:
        raise CryptoNotConfigured(
            f"{env_name} يجب أن يكون ٣٢ بايتاً (256 بت) بصيغة base64 — "
            f"وجدتُ {len(key)} بايت"
        )
    return key


def generate_key() -> str:
    """يولّد مفتاحاً جاهزاً للصق في متغيّر البيئة."""
    return _b64e(os.urandom(32))


def is_enabled() -> bool:
    """هل التشفير مُهيّأ؟ يُقرأ عند كل نداء ليتبع تغيّر البيئة في الاختبارات."""
    return bool(os.environ.get(KEY_ENV, "").strip())


def _cipher():
    key = _load_key(KEY_ENV, "تشفير بيانات النزلاء")
    if key is None:
        raise CryptoNotConfigured(
            f"{KEY_ENV} غير مضبوط — ولّد مفتاحاً بـ"
            f"`python3 -c \"from services.guest_crypto import generate_key; print(generate_key())\"`"
        )
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    return AESGCM(key)


def encrypt(plaintext: Optional[str]) -> Optional[str]:
    """
    يُشفّر نصّاً. الفارغ يبقى فارغاً — تشفير اللاشيء يُضخّم التخزين بلا فائدة
    ويجعل «لا قيمة» غير مميَّز عن «قيمة مشفَّرة».
    """
    if plaintext is None or plaintext == "":
        return plaintext
    text = str(plaintext)
    if is_encrypted(text):
        return text                      # لا تشفير مزدوج
    nonce = os.urandom(_NONCE_BYTES)
    blob = _cipher().encrypt(nonce, text.encode("utf-8"), None)
    return f"{PREFIX}:{_b64e(nonce)}:{_b64e(blob)}"


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX + ":") and value.count(":") == 2


def decrypt(value: Optional[str]) -> Optional[str]:
    """
    يفكّ التشفير. النصّ غير المشفَّر يُعاد كما هو — فالجدول يحوي القديم
    والجديد أثناء الترحيل.

    الفشل يُرفَع ولا يُبتلع: نصٌّ يُعاد مشوَّهاً بصمت أسوأ من خطأ ظاهر.
    """
    if value is None or value == "" or not is_encrypted(value):
        return value
    try:
        _, nonce_b64, blob_b64 = value.split(":", 2)
        raw = _cipher().decrypt(_b64d(nonce_b64), _b64d(blob_b64), None)
        return raw.decode("utf-8")
    except CryptoNotConfigured:
        raise
    except Exception as exc:
        # مفتاحٌ خاطئ أو صفٌّ مُعبَث به. لا يُعاد نصٌّ مزيَّف.
        log.error("تعذّر فكّ تشفير حقل نزيل: %s", type(exc).__name__)
        raise ValueError("تعذّر فكّ التشفير — مفتاحٌ خاطئ أو بيانات معطوبة") from None


# ── الفهرس الأعمى ──────────────────────────────────────────────
def blind_index(value: Optional[str]) -> Optional[str]:
    """
    بصمةٌ ثابتة للبحث. تُطابَق ولا تُعكَس.

    يُوحَّد الرقم قبل البصم (تجريد المسافات والشرطات ورفع الحروف) وإلا
    اختلفت بصمة «1234-567890» عن «1234567890» وفشل البحث عن نفس الشخص.
    """
    if value is None or value == "":
        return None
    normalized = "".join(str(value).split()).replace("-", "").replace("_", "").upper()
    if not normalized:
        return None
    key = _load_key(INDEX_KEY_ENV, "الفهرس الأعمى")
    if key is None:
        # الرجوع إلى مفتاح التشفير مع فصلٍ بالمجال: أفضل من تعطيل البحث،
        # وأضعف من مفتاحٍ مستقل. يُسجَّل مرةً لا عند كل نداء.
        base = _load_key(KEY_ENV, "تشفير بيانات النزلاء")
        if base is None:
            raise CryptoNotConfigured(f"{KEY_ENV} غير مضبوط — لا فهرس أعمى")
        key = hashlib.sha256(b"dheuof-blind-index-v1|" + base).digest()
    return hmac.new(key, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


# ── التقنيع ────────────────────────────────────────────────────
def mask_id(value: Optional[str]) -> str:
    """`**********7890` — يكفي لتمييز نزيلٍ عن آخر ولا يكشف الرقم."""
    if not value:
        return ""
    text = str(value)
    if len(text) <= 4:
        return "•" * len(text)
    return "•" * (len(text) - 4) + text[-4:]


def mask_phone(value: Optional[str]) -> str:
    if not value:
        return ""
    digits = [c for c in str(value) if c.isdigit()]
    if len(digits) <= 3:
        return "•" * len(digits)
    return "•" * (len(digits) - 3) + "".join(digits[-3:])


def mask_name(value: Optional[str]) -> str:
    """يُبقي الاسم الأول ويُقنّع الباقي: يكفي للنداء ولا يكفي للتعريف."""
    if not value:
        return ""
    parts = str(value).split()
    if len(parts) == 1:
        return parts[0]
    return parts[0] + " " + " ".join("•" * max(2, len(p)) for p in parts[1:])


_MASKERS = {
    "id_number": mask_id,
    "absher_phone": mask_phone,
    "phone": mask_phone,
    "full_name": mask_name,
    "birth_date": lambda v: "••••-••-••" if v else "",
    "notes": lambda v: "•••" if v else "",
}


def decrypt_guest(guest: dict) -> dict:
    """يفكّ كل الحقول المشفَّرة في صفّ نزيل ويُعيد نسخةً واضحة."""
    out = dict(guest or {})
    for field in ENCRYPTED_FIELDS:
        if field in out:
            try:
                out[field] = decrypt(out[field])
            except ValueError:
                # صفٌّ واحد معطوب لا يُسقط القائمة كلها
                out[field] = None
                out.setdefault("_decrypt_errors", []).append(field)
    return out


def encrypt_guest(guest: dict) -> dict:
    """يُشفّر الحقول الحسّاسة ويُضيف الفهرس الأعمى قبل الحفظ."""
    out = dict(guest or {})
    raw_id = out.get("id_number")
    for field in ENCRYPTED_FIELDS:
        if field in out and out[field] not in (None, ""):
            out[field] = encrypt(out[field])
    if raw_id and not is_encrypted(str(raw_id)):
        out["id_number_bidx"] = blind_index(raw_id)
    return out


def mask_guest(guest: dict) -> dict:
    """
    يُقنّع صفّاً لمن لا يملك `guests.pii`.

    يُستدعى **بعد** فكّ التشفير: التقنيع عرضٌ لا تخزين.
    """
    out = dict(guest or {})
    for field, masker in _MASKERS.items():
        if field in out:
            out[field] = masker(out[field])
    out["_masked"] = True
    return out
