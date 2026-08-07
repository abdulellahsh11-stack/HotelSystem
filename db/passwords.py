#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/passwords.py — تجزئة كلمات المرور والتحقق منها.

لماذا وُجد هذا الملف
────────────────────
كان التوثيق يَعِد بشيء والكود يفعل غيره:

    وثيقة التصميم §13.1        →  «bcrypt cost 12 على الأقل»
    scripts/generate_dheuof_report.py:100 →  «bcrypt-12»
    specs/db/generate_erd.py:433          →  password_hash … bcrypt
    main1.py (الكود الفعلي)               →  PBKDF2-HMAC-SHA256, 100k

وPBKDF2 بمئة ألف دورة أضعف من توصية OWASP الحالية (600 ألف دورة على
الأقل لـ PBKDF2-SHA256)، وليس bcrypt ولا Argon2 كما يقول التوثيق.

مشكلة ثانية: الهاش المخزَّن كان سلسلة hex عارية بلا أي معرّف خوارزمية،
فلا سبيل لمعرفة كيف أُنتج ولا لترقية الخوارزمية دون إجبار كل المستخدمين
على إعادة تعيين كلمات مرورهم.

التصميم هنا
───────────
• Argon2id افتراضاً — الخيار الأول في توصيات OWASP، ومقاوم للعتاد
  المتخصّص لأنه يستهلك ذاكرة لا وقتاً فقط.
• scrypt بديلاً حين لا تتوفّر argon2-cffi — موجود في مكتبة بايثون
  القياسية وهو أيضاً صعب على الذاكرة.
• كل هاش يحمل وسم خوارزميته، فترقية المعاملات لاحقاً لا تكسر شيئاً.
• verify_password تتحقّق من الصيغ القديمة أيضاً وتُخبر المُستدعي أن
  الهاش يحتاج تحديثاً — فتتم الترقية بصمت عند أول تسجيل دخول ناجح،
  دون أن يُطلب من أحد تغيير كلمة مروره.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets

log = logging.getLogger("dheuof.passwords")

try:
    from argon2 import PasswordHasher
    from argon2 import exceptions as _argon2_exc
    from argon2.low_level import Type as _Argon2Type

    # معاملات OWASP الموصى بها لـ Argon2id: ذاكرة 19 ميبي، جولتان،
    # تفرّع واحد. توازن مقبول بين المقاومة وزمن تسجيل الدخول.
    _HASHER = PasswordHasher(
        time_cost=2, memory_cost=19456, parallelism=1,
        hash_len=32, salt_len=16, type=_Argon2Type.ID,
    )
    ARGON2_AVAILABLE = True
except Exception:  # pragma: no cover - يعتمد على البيئة
    _HASHER = None
    _argon2_exc = None
    ARGON2_AVAILABLE = False
    log.warning("argon2-cffi غير متاحة — سيُستخدم scrypt بديلاً")

# معاملات scrypt الاحتياطية (n=2^15، r=8، p=1) — نحو 32 ميبي لكل عملية.
# hashlib.scrypt يرث حدّ ذاكرة OpenSSL الافتراضي (32 ميبي) فيفشل بـ
# «memory limit exceeded» عند هذه المعاملات بالضبط؛ لذلك نُمرّر maxmem
# صراحةً بضعف الحاجة.
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 1 << 15, 8, 1
_SCRYPT_MAXMEM = 128 * _SCRYPT_N * _SCRYPT_R * 2

# دورات PBKDF2 حين لا يتوفّر غيره — توصية OWASP 2023
_PBKDF2_ROUNDS = 600_000

# دورات النسخة القديمة المخزَّنة كـ hex عارٍ بلا وسم
_LEGACY_PBKDF2_ROUNDS = 100_000


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


# ── الإنتاج ───────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """يُنتج هاشاً موسوماً بخوارزميته، بملح عشوائي داخلي.

    لا يحتاج المُستدعي إلى إدارة الملح — فهو مضمَّن في الناتج.
    """
    if not password:
        raise ValueError("كلمة المرور فارغة")

    if ARGON2_AVAILABLE:
        return _HASHER.hash(password)

    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32,
        maxmem=_SCRYPT_MAXMEM,
    )
    return f"$scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


# ── التحقق ───────────────────────────────────────────────────────────────────

def verify_password(
    password: str, stored: str, legacy_salt: str | None = None
) -> tuple[bool, bool]:
    """يتحقّق من كلمة المرور مقابل هاش مخزَّن بأي صيغة مدعومة.

    يُعيد (صحيحة، تحتاج_إعادة_تجزئة). الحقل الثاني يكون True حين يكون
    الهاش بصيغة قديمة أو بمعاملات أضعف من الحالية — وعندها يُستحسن
    استدعاء hash_password وتخزين الناتج، فتتم الترقية دون إزعاج المستخدم.

    legacy_salt: الملح المطلوب للصيغة القديمة (hex عارٍ بلا وسم) فقط.
    """
    if not password or not stored:
        return False, False

    # ── Argon2 ───────────────────────────────────────────────
    if stored.startswith("$argon2"):
        if not ARGON2_AVAILABLE:
            log.error("هاش Argon2 مخزَّن لكن argon2-cffi غير متاحة")
            return False, False
        try:
            _HASHER.verify(stored, password)
        except _argon2_exc.VerifyMismatchError:
            return False, False
        except Exception as e:
            log.warning(f"فشل التحقق من هاش Argon2: {e}")
            return False, False
        return True, _HASHER.check_needs_rehash(stored)

    # ── scrypt ───────────────────────────────────────────────
    if stored.startswith("$scrypt$"):
        try:
            _, _, n, r, p, salt_b64, hash_b64 = stored.split("$")
            expected = _unb64(hash_b64)
            actual = hashlib.scrypt(
                password.encode("utf-8"), salt=_unb64(salt_b64),
                n=int(n), r=int(r), p=int(p), dklen=len(expected),
                maxmem=128 * int(n) * int(r) * 2,
            )
        except Exception as e:
            log.warning(f"هاش scrypt تالف: {e}")
            return False, False
        ok = hmac.compare_digest(actual, expected)
        # يحتاج ترقية إن توفّرت Argon2 أو كانت المعاملات أضعف من الحالية
        return ok, ok and (ARGON2_AVAILABLE or int(n) < _SCRYPT_N)

    # ── PBKDF2 موسوم ─────────────────────────────────────────
    if stored.startswith("$pbkdf2-sha256$"):
        try:
            _, _, rounds, salt_b64, hash_b64 = stored.split("$")
            expected = _unb64(hash_b64)
            actual = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), _unb64(salt_b64),
                int(rounds), dklen=len(expected),
            )
        except Exception as e:
            log.warning(f"هاش PBKDF2 تالف: {e}")
            return False, False
        ok = hmac.compare_digest(actual, expected)
        return ok, ok and (ARGON2_AVAILABLE or int(rounds) < _PBKDF2_ROUNDS)

    # ── الصيغة القديمة: hex عارٍ، PBKDF2-100k بملح خارجي ─────
    if legacy_salt:
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), legacy_salt.encode("utf-8"),
            _LEGACY_PBKDF2_ROUNDS,
        ).hex()
        ok = hmac.compare_digest(actual, stored)
        return ok, ok  # ناجحة ⇒ رقِّها دائماً

    return False, False


def needs_upgrade(stored: str) -> bool:
    """هل الهاش المخزَّن بصيغة أضعف من الحالية؟ (بلا تحقّق من كلمة المرور)"""
    if not stored:
        return False
    if stored.startswith("$argon2"):
        return bool(ARGON2_AVAILABLE and _HASHER.check_needs_rehash(stored))
    return True  # كل ما عدا Argon2 يستحقّ الترقية


def algorithm_of(stored: str) -> str:
    """اسم الخوارزمية المستخدمة في هاش مخزَّن — للتشخيص والتقارير."""
    if not stored:
        return "none"
    if stored.startswith("$argon2id$"):
        return "argon2id"
    if stored.startswith("$argon2"):
        return stored.split("$")[1]
    if stored.startswith("$scrypt$"):
        return "scrypt"
    if stored.startswith("$pbkdf2-sha256$"):
        return "pbkdf2-sha256"
    return "legacy-pbkdf2-100k"
