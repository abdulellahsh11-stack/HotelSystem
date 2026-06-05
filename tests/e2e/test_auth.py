#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/e2e/test_auth.py — اختبارات تسجيل الدخول والجلسات (E2E)
ضيوف · Dheuof Hotel SaaS Platform

تغطي:
  - تحميل صفحة تسجيل الدخول والتحقق من عناصرها
  - الدخول ببيانات خاطئة → رسالة خطأ
  - الدخول ببيانات صحيحة → توجيه لصفحة اللوحة
  - تسجيل الخروج → عدم الوصول للوحة بدون جلسة
  - الجلسة تبقى نشطة بعد إعادة تحميل الصفحة
"""

import pytest
from playwright.sync_api import Page, expect

from conftest import BASE_URL, TEST_CLIENT_ID, TEST_PASSWORD


# ──────────────────────────────────────────────────────────────
#  1. تحميل صفحة تسجيل الدخول
# ──────────────────────────────────────────────────────────────

def test_login_page_loads(page: Page):
    """
    تتحقق من أن صفحة /login تُحمَّل بنجاح وتحتوي على
    العناصر الأساسية: الشعار، الحقول، والأزرار.
    """
    page.goto("/login")

    # تحقق من عنوان الصفحة
    expect(page).to_have_title(
        lambda t: "ضيوف" in t or "Dheuof" in t,
        timeout=10_000,
    )

    # حقل معرّف المنشأة
    login_id = page.locator("#login-id")
    expect(login_id).to_be_visible()
    expect(login_id).to_have_attribute("type", "text")

    # حقل كلمة المرور
    login_pass = page.locator("#login-pass")
    expect(login_pass).to_be_visible()
    expect(login_pass).to_have_attribute("type", "password")

    # زر الدخول
    login_btn = page.locator("button.btn:has-text('دخول')")
    expect(login_btn).to_be_visible()
    expect(login_btn).to_be_enabled()

    # التبويبات (دخول / تسجيل)
    tabs = page.locator(".tab")
    expect(tabs).to_have_count(2)

    # تبويب "تسجيل الدخول" نشط بشكل افتراضي
    active_tab = page.locator(".tab.active")
    expect(active_tab).to_contain_text("تسجيل الدخول")

    # التبديل إلى تبويب "تسجيل جديد" يُظهر حقل مفتاح التفعيل
    page.click(".tab:has-text('تسجيل جديد')")
    expect(page.locator("#reg-key")).to_be_visible()

    # العودة إلى تبويب الدخول
    page.click(".tab:has-text('تسجيل الدخول')")
    expect(page.locator("#pane-login")).to_have_class(lambda c: "active" in c)


# ──────────────────────────────────────────────────────────────
#  2. الدخول ببيانات خاطئة → رسالة خطأ
# ──────────────────────────────────────────────────────────────

def test_login_with_invalid_credentials(page: Page):
    """
    يتحقق من أن الدخول ببيانات غير صحيحة لا يُكمَل
    وتظهر رسالة خطأ واضحة للمستخدم.
    """
    page.goto("/login")
    page.wait_for_selector("#login-id")

    # أدخل بيانات خاطئة
    page.fill("#login-id", "hotel-does-not-exist-xyz")
    page.fill("#login-pass", "wrong_password_12345")

    # انقر زر الدخول — لا نتوقع انتقالاً ناجحاً
    page.click("button.btn:has-text('دخول')")

    # انتظر ظهور رسالة الخطأ (id="err-msg" أو .alert-error)
    error_locator = page.locator("#err-msg, .alert-error, .alert-error")
    error_locator.wait_for(state="visible", timeout=10_000)

    # تحقق من أن النص يشير إلى خطأ في البيانات
    error_text = error_locator.first.text_content() or ""
    assert any(
        keyword in error_text
        for keyword in ["خطأ", "غير صحيح", "غير موجود", "خاطئ", "بيانات"]
    ), f"رسالة الخطأ لا تحتوي على نص مفهوم: '{error_text}'"

    # يجب أن تبقى على صفحة تسجيل الدخول
    assert "/login" in page.url or page.url == f"{BASE_URL}/", (
        f"انتقل من صفحة الدخول بشكل غير متوقع إلى: {page.url}"
    )


def test_login_with_empty_fields(page: Page):
    """يتحقق من أن الحقول الفارغة لا تُتيح تسجيل الدخول."""
    page.goto("/login")
    page.wait_for_selector("#login-id")

    # انقر الزر مباشرة بدون ملء الحقول
    page.click("button.btn:has-text('دخول')")

    # يجب أن تظل في صفحة الدخول
    page.wait_for_timeout(1000)
    assert "/login" in page.url or page.url.rstrip("/") == BASE_URL.rstrip("/"), (
        f"انتقل بشكل غير متوقع إلى: {page.url}"
    )

    # رسالة خطأ أو الصفحة لم تتغير
    error_visible = page.locator("#err-msg").is_visible()
    still_on_login = "/login" in page.url
    assert error_visible or still_on_login, (
        "يجب إما أن تظهر رسالة خطأ أو يبقى المستخدم في صفحة الدخول"
    )


# ──────────────────────────────────────────────────────────────
#  3. الدخول ببيانات صحيحة → توجيه للوحة
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("client_id,password", [
    (TEST_CLIENT_ID, TEST_PASSWORD),
])
def test_login_redirects_to_dashboard(page: Page, client_id: str, password: str):
    """
    يتحقق من أن الدخول ببيانات صحيحة يُعيد التوجيه إلى
    اللوحة الرئيسية (/ أو /app أو ما شابه) وليس إلى /login.
    """
    page.goto("/login")
    page.wait_for_selector("#login-id")

    page.fill("#login-id", client_id)
    page.fill("#login-pass", password)

    # انتظر الـ redirect بعد النقر
    with page.expect_navigation(wait_until="domcontentloaded", timeout=20_000):
        page.click("button.btn:has-text('دخول')")

    # يجب ألا نبقى في /login
    assert "/login" not in page.url, (
        f"لم يتم التوجيه بعد الدخول الصحيح — URL الحالي: {page.url}"
    )

    # يجب أن تكون اللوحة موجودة — سواء sidebar أو dh-sidebar
    sidebar = page.locator(".sidebar, .dh-sidebar")
    expect(sidebar.first).to_be_visible(timeout=15_000)


# ──────────────────────────────────────────────────────────────
#  4. تسجيل الخروج → عدم الوصول للوحة
# ──────────────────────────────────────────────────────────────

def test_logout_clears_session(authenticated_page: Page):
    """
    يتحقق من أن تسجيل الخروج يحذف الجلسة، وأن محاولة
    الوصول إلى اللوحة بعد ذلك تُعيد التوجيه لصفحة الدخول.
    """
    # افتح اللوحة وتحقق أننا مسجّلون
    authenticated_page.goto("/")
    authenticated_page.wait_for_selector(".sidebar, .dh-sidebar", timeout=15_000)

    # سجّل الخروج عبر رابط /api/logout
    with authenticated_page.expect_navigation(wait_until="domcontentloaded", timeout=15_000):
        authenticated_page.goto("/api/logout")

    # يجب أن نعود إلى صفحة الدخول
    assert "/login" in authenticated_page.url, (
        f"بعد الخروج يجب الانتقال لـ /login — URL الحالي: {authenticated_page.url}"
    )

    # حاول الوصول للوحة — يجب إعادة التوجيه لصفحة الدخول
    authenticated_page.goto("/")
    authenticated_page.wait_for_load_state("domcontentloaded", timeout=10_000)

    # بعد الخروج: إما redirect لـ /login أو محتوى صفحة الدخول ظاهر
    is_login_page = (
        "/login" in authenticated_page.url
        or authenticated_page.locator("#login-id").is_visible()
    )
    assert is_login_page, (
        f"بعد الخروج يمكن الوصول للوحة بدون جلسة (URL: {authenticated_page.url})"
    )


# ──────────────────────────────────────────────────────────────
#  5. الجلسة تبقى نشطة بعد إعادة التحميل
# ──────────────────────────────────────────────────────────────

def test_session_persists_on_reload(authenticated_page: Page):
    """
    يتحقق من أن الجلسة تبقى نشطة بعد إعادة تحميل الصفحة
    (الكوكيز محفوظة ومُرسَلة مع كل طلب).
    """
    # افتح اللوحة
    authenticated_page.goto("/")
    authenticated_page.wait_for_selector(".sidebar, .dh-sidebar", timeout=15_000)

    # تحقق أننا لسنا في صفحة الدخول
    assert "/login" not in authenticated_page.url, (
        "يجب أن يكون المستخدم في اللوحة وليس في صفحة الدخول"
    )

    # أعد تحميل الصفحة
    authenticated_page.reload(wait_until="domcontentloaded", timeout=15_000)

    # يجب أن تبقى الجلسة نشطة — لا تعود لـ /login
    assert "/login" not in authenticated_page.url, (
        f"الجلسة انتهت بعد إعادة التحميل (URL: {authenticated_page.url})"
    )

    # الشريط الجانبي يجب أن يكون مرئياً
    sidebar = authenticated_page.locator(".sidebar, .dh-sidebar")
    expect(sidebar.first).to_be_visible(timeout=10_000)
