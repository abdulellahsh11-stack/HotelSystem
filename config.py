#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config.py — إعدادات مركزية لنظام ضيوف
يُحمَّل مرة واحدة عند بدء التشغيل من Railway Environment Variables
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    # ── السيرفر ──────────────────────────────────────────────
    port: int = 5050
    admin_port: int = 5051
    debug: bool = False

    # ── قاعدة البيانات ──────────────────────────────────────
    database_url: str = ""          # postgresql://... من Railway

    # ── الخدمات الخارجية ────────────────────────────────────
    anthropic_api_key: str = ""
    github_token: str = ""
    github_repo: str = ""
    github_branch: str = "main"
    github_backup_token: str = ""
    github_backup_repo: str = ""

    # ── التخزين المؤقت / الجلسات الموزّعة ─────────────────
    redis_url: str = ""             # redis://... من Railway — اختياري

    # ── المراقبة ────────────────────────────────────────────
    sentry_dsn: str = ""            # جديد في الشهر 2

    # ── شبكة توصيل المحتوى (CDN) ───────────────────────────
    cdn_url: str = ""               # مثال: https://cdn.dheuof.com — فارغ = محلي

    # ── الأمان ──────────────────────────────────────────────
    admin_pass_hash: str = ""
    pass_salt: str = "HotelSaaS2025"
    secret_key: str = ""            # لـ token generation

    # ── الميزات ──────────────────────────────────────────────
    dual_write: bool = True         # يُوقف بعد 48h من نجاح PostgreSQL

    # ── حساب المالك ─────────────────────────────────────────
    owner_client_id: str = ""       # معرف حساب المالك — يُميَّز بشارة في لوحة الإدارة

    # ── البريد الإلكتروني (SMTP) ────────────────────────────
    smtp_host: str = ""             # مثال: smtp.gmail.com
    smtp_port: int = 587
    smtp_user: str = ""             # البريد المُرسِل
    smtp_pass: str = ""             # كلمة مرور التطبيق
    smtp_from: str = ""             # اسم + بريد: "ضيوف <info@dheuof.com>"

    @classmethod
    def from_env(cls) -> "Config":
        """يُنشئ Config من Railway Environment Variables مع validation"""
        required = ["ADMIN_PASS_HASH"]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            raise ValueError(
                f"❌ Railway Variables ناقصة: {missing}\n"
                f"   أضفها في Railway → Variables tab"
            )

        secret_key = os.environ.get("SECRET_KEY", "")
        if not secret_key:
            import secrets as _sec
            secret_key = _sec.token_hex(32)
            print("⚠️  SECRET_KEY غير موجود — يُستخدم مفتاح مؤقت (أضفه في Railway Variables)")

        return cls(
            port=int(os.environ.get("PORT", 5050)),
            admin_port=int(os.environ.get("ADMIN_PORT", 5051)),
            debug=os.environ.get("DEBUG", "false").lower() == "true",
            database_url=os.environ.get("DATABASE_URL", ""),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            github_token=os.environ.get("GITHUB_TOKEN", ""),
            github_repo=os.environ.get("GITHUB_REPO", ""),
            github_branch=os.environ.get("GITHUB_BRANCH", "main"),
            github_backup_token=os.environ.get("GITHUB_BACKUP_TOKEN", ""),
            github_backup_repo=os.environ.get("GITHUB_BACKUP_REPO", ""),
            sentry_dsn=os.environ.get("SENTRY_DSN", ""),
            cdn_url=os.environ.get("CDN_URL", ""),
            admin_pass_hash=os.environ["ADMIN_PASS_HASH"],
            pass_salt=os.environ.get("PASS_SALT", "HotelSaaS2025"),
            secret_key=secret_key,
            redis_url=os.environ.get("REDIS_URL", ""),
            dual_write=os.environ.get("DUAL_WRITE", "true").lower() == "true",
            owner_client_id=os.environ.get("OWNER_CLIENT_ID", ""),
            smtp_host=os.environ.get("SMTP_HOST", ""),
            smtp_port=int(os.environ.get("SMTP_PORT", "587")),
            smtp_user=os.environ.get("SMTP_USER", ""),
            smtp_pass=os.environ.get("SMTP_PASS", ""),
            smtp_from=os.environ.get("SMTP_FROM", "ضيوف <info@dheuof.com>"),
        )

    @property
    def has_smtp(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_pass)

    @property
    def has_redis(self) -> bool:
        return bool(self.redis_url)

    @property
    def has_postgres(self) -> bool:
        return bool(self.database_url)

    @property
    def has_github(self) -> bool:
        return bool(self.github_token and self.github_repo)

    @property
    def has_sentry(self) -> bool:
        return bool(self.sentry_dsn)

    @property
    def has_cdn(self) -> bool:
        return bool(self.cdn_url)

    def summary(self) -> str:
        """طباعة ملخص الإعدادات عند البدء"""
        lines = [
            "=" * 60,
            "  نظام ضيوف — dheuof.com  |  الشهر الثاني ✓",
            "=" * 60,
            f"  Client Port  → {self.port}",
            f"  Admin Port   → {self.admin_port}",
            f"  PostgreSQL   → {'✅ متصل' if self.has_postgres else '⚠️  JSON Fallback'}",
            f"  Redis        → {'✅ مُفعَّل' if self.has_redis else '⚠️  In-Memory Fallback'}",
            f"  GitHub       → {'✅ ' + self.github_repo if self.has_github else '⚠️  غير مُفعَّل'}",
            f"  Sentry       → {'✅ مُفعَّل' if self.has_sentry else '⚠️  غير مُفعَّل'}",
            f"  CDN          → {'✅ ' + self.cdn_url if self.has_cdn else '⚠️  محلي (بدون CDN)'}",
            f"  Claude AI    → {'✅ متاح' if self.anthropic_api_key else '⚠️  غير مُفعَّل'}",
            f"  Dual-Write   → {'✅ مُفعَّل' if self.dual_write else '❌ موقوف'}",
            f"  Debug        → {'✅' if self.debug else '❌'}",
            "=" * 60,
        ]
        return "\n".join(lines)


# Singleton — يُستخدم في كل الـ modules
_config: Optional[Config] = None


def get_config() -> Config:
    """يُعيد الـ Config الوحيد للتطبيق"""
    global _config
    if _config is None:
        raise RuntimeError(
            "Config لم يُهيَّأ بعد — استدعِ Config.from_env() في main() أولاً"
        )
    return _config


def init_config(config: Config) -> None:
    """يُهيّئ الـ Config (يُستدعى مرة واحدة من main.py)"""
    global _config
    _config = config
