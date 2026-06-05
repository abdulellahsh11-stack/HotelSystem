#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مانيفست الملفات الثابتة (Static Asset Manifest)
==================================================
توصية #5 — يُنشئ جدولاً لجميع الملفات الثابتة مع بصماتها لكسر التخزين المؤقت.

الاستخدام النموذجي:
    manifest = build_manifest("static")
    url = get_versioned_url("/static/app.css", manifest)
    # → "/static/app.css?v=a1b2c3d4"

يُقرأ manifest.json إذا كان موجوداً (من خطوة البناء)،
أو يُنشأ في الذاكرة عند أول استدعاء.
"""
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger("dheuof.cdn.manifest")

# مسار ملف الـ manifest المُولَّد عند البناء
MANIFEST_FILE = "static/manifest.json"


def _file_hash(file_path: Path, length: int = 8) -> str:
    """يُحسب بصمة MD5 مختصرة لمحتوى الملف."""
    try:
        with open(file_path, "rb") as fh:
            digest = hashlib.md5(fh.read(), usedforsecurity=False).hexdigest()
        return digest[:length]
    except OSError as exc:
        log.debug(f"تعذّرت قراءة الملف لحساب البصمة: {file_path} — {exc}")
        return ""


def build_manifest(static_dir: str = "static") -> dict[str, str]:
    """
    يُنشئ (أو يُحمِّل) مانيفست الملفات الثابتة.

    الأولوية:
    1. يقرأ static/manifest.json إذا كان موجوداً وحديثاً.
    2. يفحص جميع الملفات في static_dir ويُنشئ المانيفست في الذاكرة.

    القاموس المُعاد: {"/static/app.css": "/static/app.css?v=a1b2c3d4", ...}
    """
    # ── محاولة تحميل manifest.json الجاهز ───────────────────────
    manifest_path = Path(MANIFEST_FILE)
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and data:
                log.debug(f"تم تحميل المانيفست من {manifest_path} ({len(data)} ملف)")
                return data
        except (json.JSONDecodeError, OSError) as exc:
            log.warning(f"تعذّرت قراءة {manifest_path}: {exc} — سيُنشأ مانيفست جديد")

    # ── بناء المانيفست من محتويات المجلد ────────────────────────
    root = Path(static_dir)
    if not root.is_dir():
        log.warning(f"مجلد static غير موجود: {static_dir}")
        return {}

    manifest: dict[str, str] = {}

    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        # تجاهل ملفات النظام والمخفية
        if file_path.name.startswith(".") or file_path.name == "manifest.json":
            continue

        # المسار النسبي بصيغة URL — مثل /static/app.css
        rel = "/" + file_path.as_posix()
        file_hash = _file_hash(file_path)
        if file_hash:
            manifest[rel] = f"{rel}?v={file_hash}"
        else:
            manifest[rel] = rel

    log.info(f"✓ مانيفست static: {len(manifest)} ملف")
    return manifest


def get_versioned_url(path: str, manifest: Optional[dict] = None) -> str:
    """
    يُعيد عنوان URL بمعامل الإصدار ?v=... للكسر الصحيح للتخزين المؤقت.

    مثال:
        get_versioned_url("/static/app.css", manifest)
        # → "/static/app.css?v=a1b2c3d4"
    """
    if manifest is None:
        return path
    return manifest.get(path, path)


def save_manifest(manifest: dict[str, str], output_path: str = MANIFEST_FILE) -> None:
    """
    يحفظ المانيفست إلى ملف JSON (يُستدعى عادةً في خطوة البناء).
    """
    try:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)
        log.info(f"✓ تم حفظ المانيفست في {output_path} ({len(manifest)} ملف)")
    except OSError as exc:
        log.error(f"تعذّر حفظ المانيفست: {exc}")


# ── تخزين مؤقت للمانيفست على مستوى العملية ──────────────────────────────────
_manifest_cache: Optional[dict[str, str]] = None


def get_manifest(static_dir: str = "static") -> dict[str, str]:
    """
    يُعيد نسخة مُخزَّنة مؤقتاً من المانيفست (singleton).
    يُبنى في أول استدعاء ثم يُعاد استخدامه.
    """
    global _manifest_cache
    if _manifest_cache is None:
        _manifest_cache = build_manifest(static_dir)
    return _manifest_cache


def invalidate_manifest_cache() -> None:
    """يمسح التخزين المؤقت للمانيفست — مفيد في بيئة التطوير."""
    global _manifest_cache
    _manifest_cache = None
    log.debug("تم مسح تخزين المانيفست المؤقت")
