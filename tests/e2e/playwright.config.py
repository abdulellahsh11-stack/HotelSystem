#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/e2e/playwright.config.py — إعدادات Playwright المركزية
ضيوف · Dheuof Hotel SaaS Platform

يُستخدم هذا الملف مرجعاً للإعدادات المشتركة ومتغيرات البيئة.
الإعدادات الفعلية التي يقرأها pytest-playwright موجودة في conftest.py.

الاستخدام المرجعي:
    # تشغيل الاختبارات مع إعدادات مخصصة:
    BASE_URL=https://dheuof.com pytest tests/e2e/ -v

    # تشغيل مرئي (لا headless):
    PLAYWRIGHT_HEADLESS=false pytest tests/e2e/ -v

    # تسجيل فيديو:
    PLAYWRIGHT_VIDEO_DIR=test-results/videos pytest tests/e2e/ -v

    # حفظ لقطات الشاشة:
    PLAYWRIGHT_SCREENSHOTS_DIR=test-results/screenshots pytest tests/e2e/ -v
"""

import os


# ──────────────────────────────────────────────────────────────
#  إعدادات الاتصال
# ──────────────────────────────────────────────────────────────

BASE_URL: str = os.environ.get("BASE_URL", "http://localhost:8000")
"""
عنوان الخادم المستهدف.
البيئة المحلية:  http://localhost:8000
الإنتاج:        https://dheuof.com  (لا تُشغِّل اختبارات تعديل على الإنتاج)
المرحلة:        https://staging.dheuof.com
"""


# ──────────────────────────────────────────────────────────────
#  إعدادات المهلات
# ──────────────────────────────────────────────────────────────

TIMEOUTS = {
    # مهلة الانتظار الافتراضية لجميع العمليات (ms)
    "default": int(os.environ.get("PLAYWRIGHT_TIMEOUT", "30000")),

    # مهلة التنقل (فتح صفحة، redirect) (ms)
    "navigation": int(os.environ.get("PLAYWRIGHT_NAV_TIMEOUT", "30000")),

    # مهلة انتظار العناصر في الصفحة (ms)
    "element": int(os.environ.get("PLAYWRIGHT_ELEMENT_TIMEOUT", "15000")),

    # مهلة انتهاء اختبار واحد كاملاً (ms)
    "test": int(os.environ.get("PLAYWRIGHT_TEST_TIMEOUT", "60000")),

    # مهلة انتظار network idle (ms)
    "network_idle": int(os.environ.get("PLAYWRIGHT_NETWORK_TIMEOUT", "25000")),
}


# ──────────────────────────────────────────────────────────────
#  إعدادات المتصفح
# ──────────────────────────────────────────────────────────────

BROWSER_CONFIG = {
    # وضع headless (صامت) — false لمشاهدة الاختبار مرئياً
    "headless": os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() != "false",

    # تباطؤ العمليات (ms) — مفيد للتصحيح المرئي
    "slow_mo": int(os.environ.get("PLAYWRIGHT_SLOW_MO", "0")),

    # وسائط المتصفح الإضافية
    "args": [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
    ],
}

CONTEXT_CONFIG = {
    # اللغة والمنطقة الزمنية — الرياض للتطابق مع النظام
    "locale": "ar-SA",
    "timezone_id": "Asia/Riyadh",

    # الصفحة الافتراضية
    "viewport": {"width": 1440, "height": 900},

    # Accept-Language header
    "extra_http_headers": {
        "Accept-Language": "ar-SA,ar;q=0.9,en;q=0.8",
    },
}


# ──────────────────────────────────────────────────────────────
#  إعدادات لقطات الشاشة والفيديو
# ──────────────────────────────────────────────────────────────

SCREENSHOT_CONFIG = {
    # مسار حفظ لقطات الشاشة عند الفشل
    "dir": os.environ.get("PLAYWRIGHT_SCREENSHOTS_DIR", "test-results/screenshots"),

    # تلقائي = يلتقط فقط عند الفشل
    "on_failure": True,

    # لقطة شاشة كاملة للصفحة
    "full_page": True,
}

VIDEO_CONFIG = {
    # مسار حفظ مقاطع الفيديو (None = لا تسجيل)
    "dir": os.environ.get("PLAYWRIGHT_VIDEO_DIR"),

    # جودة الفيديو
    "size": {"width": 1440, "height": 900},
}


# ──────────────────────────────────────────────────────────────
#  بيانات الاعتماد للاختبار
# ──────────────────────────────────────────────────────────────

TEST_CREDENTIALS = {
    # حساب عميل للاختبار — يجب إنشاؤه مسبقاً في قاعدة البيانات
    "client": {
        "id": os.environ.get("TEST_CLIENT_ID", "test-hotel-e2e"),
        "password": os.environ.get("TEST_PASSWORD", "TestPass@2025!"),
    },

    # حساب المدير — من متغير البيئة فقط (لا تضع بيانات حقيقية هنا)
    "admin": {
        "password": os.environ.get("ADMIN_PASSWORD", "admin_secret"),
    },
}


# ──────────────────────────────────────────────────────────────
#  تكوين pytest.ini المقابل (للمرجع)
# ──────────────────────────────────────────────────────────────

PYTEST_CONFIG_REFERENCE = """
# يُنسَخ هذا في pytest.ini أو pyproject.toml لاستخدامه:

[tool:pytest]
# تشغيل الاختبارات بالتوازي (يحتاج pytest-xdist)
# addopts = -n auto

# تقليل الإخراج المكرر
addopts = -v --tb=short

# مهلة كل اختبار (يحتاج pytest-timeout)
# timeout = 60

# تصفية التحذيرات
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
"""


# ──────────────────────────────────────────────────────────────
#  دالة طباعة الإعدادات (للتشخيص)
# ──────────────────────────────────────────────────────────────

def print_config() -> None:
    """يطبع ملخص الإعدادات النشطة — مفيد عند التشغيل اليدوي."""
    print("\n" + "=" * 60)
    print("  ضيوف · Dheuof — إعدادات اختبارات Playwright E2E")
    print("=" * 60)
    print(f"  BASE_URL:       {BASE_URL}")
    print(f"  headless:       {BROWSER_CONFIG['headless']}")
    print(f"  slow_mo:        {BROWSER_CONFIG['slow_mo']} ms")
    print(f"  timeout:        {TIMEOUTS['default']} ms")
    print(f"  screenshots:    {SCREENSHOT_CONFIG['dir']}")
    print(f"  video:          {VIDEO_CONFIG['dir'] or 'معطّل'}")
    print(f"  test_client_id: {TEST_CREDENTIALS['client']['id']}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    print_config()
