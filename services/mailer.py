#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/mailer.py — خدمة إرسال البريد الإلكتروني
منصة ضيوف | Dheuof Hotel SaaS Platform
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import Config

log = logging.getLogger("dheuof")


def send_email(cfg: "Config", to: str, subject: str, html: str) -> bool:
    """
    يُرسل بريداً إلكترونياً عبر SMTP.
    يعيد True عند النجاح، False عند الفشل (لا يرمي استثناء).
    """
    if not cfg.has_smtp:
        log.warning("SMTP غير مُفعَّل — تحقق من SMTP_HOST/SMTP_USER/SMTP_PASS في Railway")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg.smtp_from or cfg.smtp_user
        msg["To"] = to
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg.smtp_user, cfg.smtp_pass)
            server.sendmail(cfg.smtp_user, [to], msg.as_bytes())

        log.info(f"✉️  بريد أُرسل إلى {to} — {subject}")
        return True
    except Exception as exc:
        log.error(f"فشل إرسال البريد إلى {to}: {exc}")
        return False


def send_registration_email(cfg: "Config", to: str, hotel_name: str, client_id: str) -> bool:
    """يُرسل بريد تفعيل الحساب مع المعرّف الرقمي."""
    subject = "✅ تم تفعيل حسابك في منصة ضيوف"
    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: 'Segoe UI', Tahoma, Arial, sans-serif; background:#f1f5f9; margin:0; padding:20px; }}
  .card {{ background:#fff; max-width:520px; margin:0 auto; border-radius:16px;
           padding:40px 36px; box-shadow:0 4px 20px rgba(0,0,0,0.08); }}
  .logo {{ text-align:center; margin-bottom:28px; }}
  .logo h1 {{ color:#0F2640; font-size:1.8rem; margin:0; }}
  .logo p  {{ color:#64748b; margin:4px 0 0; font-size:.9rem; }}
  h2 {{ color:#0F2640; margin:0 0 8px; }}
  .id-box {{ background:#f0f9ff; border:2px solid #185FA5; border-radius:12px;
             text-align:center; padding:24px; margin:24px 0; }}
  .id-box .label {{ color:#64748b; font-size:.85rem; margin-bottom:8px; }}
  .id-box .id {{ color:#0F2640; font-size:2.4rem; font-weight:700;
                 letter-spacing:6px; font-family:monospace; }}
  .note {{ background:#fefce8; border-right:4px solid #f59e0b; padding:14px 16px;
           border-radius:8px; color:#78350f; font-size:.88rem; margin:16px 0; }}
  .btn {{ display:block; width:fit-content; margin:24px auto 0;
          background:#185FA5; color:#fff; text-decoration:none;
          padding:12px 32px; border-radius:8px; font-size:1rem; font-weight:600; }}
  .footer {{ text-align:center; color:#94a3b8; font-size:.8rem; margin-top:28px; }}
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <h1>&#127960; ضيوف</h1>
    <p>نظام إدارة الفنادق والشقق المخدومة</p>
  </div>

  <h2>مرحباً بك في منصة ضيوف 🎉</h2>
  <p style="color:#475569">تم تسجيل منشأتك <strong>{hotel_name}</strong> بنجاح.<br>
  معرّفك الرقمي الخاص للدخول إلى النظام:</p>

  <div class="id-box">
    <div class="label">معرّف المنشأة (للدخول لاحقاً)</div>
    <div class="id">{client_id}</div>
  </div>

  <div class="note">
    ⚠️ احتفظ بهذا المعرّف — ستحتاجه في كل مرة تسجّل فيها الدخول.<br>
    لا تشاركه مع أحد لحماية حسابك.
  </div>

  <a class="btn" href="https://dheuof.com/login">الدخول إلى النظام ←</a>

  <div class="footer">
    منصة ضيوف · dheuof.com<br>
    للدعم: <a href="mailto:info@dheuof.com" style="color:#185FA5">info@dheuof.com</a> |
    واتساب: +966 56 500 9696
  </div>
</div>
</body>
</html>"""
    return send_email(cfg, to, subject, html)
