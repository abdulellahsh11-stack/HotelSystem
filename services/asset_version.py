#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/asset_version.py — بصمة إصدارٍ لملفات الواجهة

## المشكلة التي يحلّها

كانت الملفات الثابتة تُخدَم بترويسة:

    Cache-Control: public, max-age=604800, immutable

و`immutable` تعني حرفياً: «لا تسأل عن هذا الملف ثانيةً» — لا عند تحديث
الصفحة، ولا عند العودة إليها. فيبقى المتصفّح على نسخةٍ قديمة **سبعة
أيام** بعد كل نشر، ويرى المستخدم منصةً لم تُصلَح بينما الخادم يحمل
الإصلاح.

هذا يُنتج أسوأ صنفٍ من الأعطال: يقول المطوّر «أصلحتُه» صادقاً، ويقول
المستخدم «لا يعمل» صادقاً، وكلاهما ينظر إلى نسخةٍ مختلفة.

## الحلّ

`immutable` سليمةٌ **فقط** لعنوانٍ يتغيّر حين يتغيّر محتواه. فتُلحَق
بصمةُ إصدار بكل عنوان:

    /static/js/app.js  →  /static/js/app.js?v=a3f9c1

ثم:

| العنوان | الترويسة | لماذا |
|---|---|---|
| ببصمةٍ مطابقة | سنة كاملة `immutable` | العنوان نفسه يتغيّر عند النشر |
| بلا بصمة أو ببصمةٍ قديمة | `no-cache` | يُعاد التحقق، وETag يجعله رخيصاً |
| صفحات HTML | `no-cache` | هي التي تحمل البصمات الجديدة |

فالصفحة تُطلب دائماً، وتأتي بعناوينٍ جديدة عند كل نشر، فتُحمَّل الملفات
الجديدة حتماً — دون أن يخسر المستخدم فائدة التخزين بين النشرات.

## من أين تأتي البصمة

من محتوى الملفات نفسها (الاسم والحجم ووقت التعديل)، لا من رقمٍ يدوي
يُنسى تحديثه. ولا تُقرأ محتويات الملفات: على مئات الملفات يكون ذلك
تأخيراً في كل إقلاع بلا مقابل — تغيّرُ الحجم أو الوقت يكفي للكشف.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re

log = logging.getLogger("dheuof.assets")

# الامتدادات التي تُبصَم. الصور والخطوط تتغيّر نادراً ولا يضرّ بقاؤها،
# لكن بصمها يجعل السلوك واحداً فلا يبقى استثناءٌ يُنسى.
VERSIONED_SUFFIXES = (".js", ".css")

_VERSION: str | None = None


def compute_version(root: str = "static") -> str:
    """
    بصمةٌ قصيرة تتغيّر متى تغيّر أي ملف واجهة.

    الفشل لا يُوقف الإقلاع: بصمةٌ ثابتة أسوأ من لا شيء، لكن انهيار
    المنصة لتعذّر قراءة مجلّد أسوأ منهما.
    """
    digest = hashlib.sha256()
    seen = 0
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for name in sorted(filenames):
                if not name.endswith(VERSIONED_SUFFIXES):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    stat = os.stat(path)
                except OSError:
                    continue
                digest.update(path.encode("utf-8"))
                digest.update(str(int(stat.st_mtime)).encode())
                digest.update(str(stat.st_size).encode())
                seen += 1
    except Exception as exc:
        log.warning("تعذّر حساب بصمة الملفات: %s", exc)
        return "dev"
    if not seen:
        # `os.walk` على مسارٍ غير موجود لا يرمي شيئاً بل يُنتج لا شيء،
        # فتخرج بصمةٌ ثابتة تبدو سليمة ولا تتغيّر أبداً عند النشر —
        # سقوطٌ صامت يُعيد العطل نفسه الذي جاء هذا الملف ليمنعه.
        log.warning("لم يُعثر على ملفات واجهة تحت %s — لا بصمة إصدار", root)
        return "dev"
    return digest.hexdigest()[:10]


def get_version() -> str:
    """البصمة الحالية، تُحسب مرةً عند أول طلب وتبقى لعمر العملية."""
    global _VERSION
    if _VERSION is None:
        _VERSION = compute_version()
        log.info("بصمة ملفات الواجهة: %s", _VERSION)
    return _VERSION


def reset_version() -> None:
    """للاختبارات فقط: يُجبر إعادة الحساب."""
    global _VERSION
    _VERSION = None


# ── حقن البصمة في HTML ─────────────────────────────────────────
#
# يُطابق src/href لملفات .js و.css تحت /static فقط. الروابط الخارجية
# (خطوط Google مثلاً) لا تُمسّ: بصمتُنا لا معنى لها على خادمٍ آخر.
_ASSET_REF = re.compile(
    r'(?P<attr>\b(?:src|href)=")(?P<path>/static/[^"?#]+\.(?:js|css))(?P<rest>[^"]*)"'
)


def stamp_html(html: str, version: str | None = None) -> str:
    """يُلحق `?v=` بكل مرجع ملفٍ ثابت داخل صفحة HTML."""
    tag = version or get_version()

    def _replace(match: re.Match) -> str:
        rest = match.group("rest")
        if "v=" in rest:
            # مبصوم سابقاً — يُستبدل لا يُضاعَف
            rest = re.sub(r"[?&]v=[^&]*", "", rest)
        joiner = "&" if rest.startswith("?") else "?"
        return f'{match.group("attr")}{match.group("path")}{rest}{joiner}v={tag}"'

    return _ASSET_REF.sub(_replace, html)


def cache_header(path: str, query_version: str | None) -> str:
    """
    ترويسة التخزين المناسبة لهذا المسار.

    `immutable` تُمنح فقط لعنوانٍ يحمل البصمة الجارية — وهذا شرطُ
    صحّتها: عنوانٌ ثابتُ المحتوى لأن اسمه يتغيّر متى تغيّر.
    """
    if path.endswith(".html") or not path.startswith("/static/"):
        return "no-cache, must-revalidate"
    if path.endswith(VERSIONED_SUFFIXES):
        if query_version and query_version == get_version():
            return "public, max-age=31536000, immutable"
        # بلا بصمة أو ببصمةٍ قديمة: يُعاد التحقق. ETag يجعل الردّ ٣٠٤
        # صغيراً حين لا يتغيّر شيء.
        return "no-cache, must-revalidate"
    # صور وخطوط: تخزينٌ متوسط بلا immutable
    return "public, max-age=86400"
