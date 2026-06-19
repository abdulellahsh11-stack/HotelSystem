#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/e2e/conftest.py — إعدادات Playwright المشتركة لاختبارات نهاية-لنهاية
ضيوف · Dheuof Hotel SaaS Platform
"""

import os
import sys
import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

# e2e_config.py lives in the same directory — ensure it is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_config import BASE_URL, TEST_CLIENT_ID, TEST_PASSWORD  # noqa: F401

# بيانات حساب المدير
ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "admin_secret")

# مهلة الانتظار الافتراضية بالمللي ثانية
DEFAULT_TIMEOUT: int = int(os.environ.get("PLAYWRIGHT_TIMEOUT", "30000"))


# ──────────────────────────────────────────────────────────────
#  fixture: اتصال Playwright على مستوى الجلسة
# ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def playwright_instance():
    """يُنشئ جلسة Playwright واحدة لكامل دورة الاختبار."""
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright_instance):
    """
    يفتح متصفح Chromium في الوضع الصامت (headless) افتراضياً.
    لتشغيله مرئياً: export PLAYWRIGHT_HEADLESS=false
    """
    headless = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    browser: Browser = playwright_instance.chromium.launch(
        headless=headless,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    yield browser
    browser.close()


# ──────────────────────────────────────────────────────────────
#  fixture: صفحة أساسية (بدون تسجيل دخول)
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def context(browser):
    """
    سياق متصفح معزول لكل اختبار — يمنع تسرب ملفات الكوكيز بين الاختبارات.
    يُضبط base_url تلقائياً من المتغير البيئي BASE_URL.
    """
    ctx: BrowserContext = browser.new_context(
        base_url=BASE_URL,
        locale="ar-SA",
        timezone_id="Asia/Riyadh",
        # لقطات الشاشة عند الفشل
        record_video_dir=os.environ.get("PLAYWRIGHT_VIDEO_DIR"),
    )
    ctx.set_default_timeout(DEFAULT_TIMEOUT)
    yield ctx
    ctx.close()


@pytest.fixture
def page(context) -> Page:
    """
    صفحة متصفح نظيفة لكل اختبار.
    base_url مضبوط من السياق — يكفي استخدام المسارات النسبية في navigate.
    """
    p: Page = context.new_page()
    yield p
    p.close()


# ──────────────────────────────────────────────────────────────
#  دالة مساعدة: تسجيل الدخول
# ──────────────────────────────────────────────────────────────

def _do_client_login(page: Page, client_id: str, password: str) -> None:
    """
    يُسجّل دخول مستخدم عميل عبر صفحة /login.
    يرمي AssertionError إذا لم ينتقل الـ redirect إلى الصفحة الرئيسية.
    """
    page.goto("/login")
    # انتظر ظهور حقل معرّف المنشأة
    page.wait_for_selector("#login-id", timeout=DEFAULT_TIMEOUT)

    # أدخل بيانات الاعتماد
    page.fill("#login-id", client_id)
    page.fill("#login-pass", password)

    # انقر زر الدخول وانتظر الانتقال
    with page.expect_navigation(wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT):
        page.click("button.btn:has-text('دخول')")

    # تحقق من نجاح تسجيل الدخول — الصفحة الرئيسية أو اللوحة
    assert page.url != f"{BASE_URL}/login", (
        f"فشل تسجيل الدخول — لم ينتقل من /login (URL الحالي: {page.url})"
    )


def _do_admin_login(page: Page, password: str) -> None:
    """
    يُسجّل دخول المدير عبر /admin.
    يرمي AssertionError إذا لم ينجح الدخول.
    """
    page.goto("/admin")
    page.wait_for_selector("input[type='password']", timeout=DEFAULT_TIMEOUT)

    page.fill("input[type='password']", password)
    with page.expect_navigation(wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT):
        page.click("button.btn:has-text('دخول')")

    # بعد نجاح الدخول تكون الـ URL هي /admin مع وجود لوحة الإدارة
    assert "/admin" in page.url or page.locator(".sidebar").is_visible(), (
        f"فشل تسجيل دخول المدير (URL: {page.url})"
    )


# ──────────────────────────────────────────────────────────────
#  fixture: صفحة مع جلسة عميل نشطة
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def authenticated_context(browser):
    """
    سياق متصفح مع جلسة عميل نشطة — يُستخدم في الاختبارات التي تحتاج تسجيل دخول.
    """
    ctx: BrowserContext = browser.new_context(
        base_url=BASE_URL,
        locale="ar-SA",
        timezone_id="Asia/Riyadh",
    )
    ctx.set_default_timeout(DEFAULT_TIMEOUT)

    # سجّل الدخول مرة واحدة وأبقِ على الكوكيز في السياق
    init_page = ctx.new_page()
    _do_client_login(init_page, TEST_CLIENT_ID, TEST_PASSWORD)
    init_page.close()

    yield ctx
    ctx.close()


@pytest.fixture
def authenticated_page(authenticated_context) -> Page:
    """
    صفحة متصفح جاهزة مع جلسة عميل فعّالة.
    استخدمها في أي اختبار يحتاج المستخدم مسجّل الدخول مسبقاً.
    """
    p: Page = authenticated_context.new_page()
    yield p
    p.close()


# ──────────────────────────────────────────────────────────────
#  fixture: صفحة مع جلسة مدير نشطة
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def admin_context(browser):
    """سياق متصفح مع جلسة مدير نشطة."""
    ctx: BrowserContext = browser.new_context(
        base_url=BASE_URL,
        locale="ar-SA",
        timezone_id="Asia/Riyadh",
    )
    ctx.set_default_timeout(DEFAULT_TIMEOUT)

    init_page = ctx.new_page()
    _do_admin_login(init_page, ADMIN_PASSWORD)
    init_page.close()

    yield ctx
    ctx.close()


@pytest.fixture
def admin_page(admin_context) -> Page:
    """
    صفحة متصفح جاهزة مع جلسة مدير فعّالة.
    استخدمها لاختبار لوحة التحكم الإدارية.
    """
    p: Page = admin_context.new_page()
    yield p
    p.close()


# ──────────────────────────────────────────────────────────────
#  Hook: التقاط لقطة شاشة عند فشل الاختبار
# ──────────────────────────────────────────────────────────────

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """يلتقط لقطة شاشة تلقائياً عند فشل أي اختبار Playwright."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        # ابحث عن أي fixture من نوع Page في الاختبار الفاشل
        for fixture_name in ("page", "authenticated_page", "admin_page"):
            p = item.funcargs.get(fixture_name)
            if p is not None:
                screenshots_dir = os.environ.get("PLAYWRIGHT_SCREENSHOTS_DIR", "test-results/screenshots")
                os.makedirs(screenshots_dir, exist_ok=True)
                safe_name = item.name.replace("/", "_").replace(":", "_")
                screenshot_path = os.path.join(screenshots_dir, f"{safe_name}.png")
                try:
                    p.screenshot(path=screenshot_path, full_page=True)
                    report.sections.append(
                        ("لقطة الشاشة", f"محفوظة في: {screenshot_path}")
                    )
                except Exception:
                    pass
                break
