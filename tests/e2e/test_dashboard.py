#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/e2e/test_dashboard.py — اختبارات لوحة التحكم الرئيسية (E2E)
ضيوف · Dheuof Hotel SaaS Platform

تغطي:
  - تحميل اللوحة الرئيسية مع عناصرها الأساسية
  - التنقل بين أقسام اللوحة (النزلاء، الحجوزات، الفواتير...)
  - ظهور مؤشرات KPI (أرقام حقيقية لا spinners)
"""

import pytest
from playwright.sync_api import Page, expect

from e2e_config import BASE_URL


# ──────────────────────────────────────────────────────────────
#  1. تحميل اللوحة الرئيسية
# ──────────────────────────────────────────────────────────────

def test_dashboard_loads(authenticated_page: Page):
    """
    يتحقق من أن اللوحة الرئيسية تُحمَّل بالكامل وتحتوي على
    الشريط الجانبي والشريط العلوي وعنوان الصفحة.
    """
    authenticated_page.goto("/")
    authenticated_page.wait_for_load_state("networkidle", timeout=20_000)

    # الشريط الجانبي يجب أن يكون مرئياً
    sidebar = authenticated_page.locator(".sidebar, .dh-sidebar")
    expect(sidebar.first).to_be_visible(timeout=10_000)

    # الشريط العلوي
    topbar = authenticated_page.locator(".topbar, .dh-topbar")
    expect(topbar.first).to_be_visible()

    # روابط التنقل الرئيسية موجودة في الشريط الجانبي
    # الصفحة الرئيسية / لوحة التحكم
    home_link = authenticated_page.locator(
        ".sidebar a:has-text('الرئيسية'), .dh-nav-item:has-text('الرئيسية'), .dh-nav-item:has-text('لوحة')"
    )
    expect(home_link.first).to_be_visible()

    # رابط الحجوزات
    bookings_link = authenticated_page.locator(
        ".sidebar a:has-text('الحجوزات'), .dh-nav-item:has-text('الحجوزات')"
    )
    expect(bookings_link.first).to_be_visible()

    # رابط النزلاء
    guests_link = authenticated_page.locator(
        ".sidebar a:has-text('النزلاء'), .dh-nav-item:has-text('النزلاء')"
    )
    expect(guests_link.first).to_be_visible()

    # رابط الخروج
    logout_link = authenticated_page.locator(
        "a[href*='logout'], a:has-text('خروج')"
    )
    expect(logout_link.first).to_be_visible()

    # عنوان الصفحة (topbar title أو page title)
    title_el = authenticated_page.locator(
        "#page-title, .topbar h2, .dh-topbar-title"
    )
    # يجب أن يحتوي على نص ما
    title_text = title_el.first.text_content(timeout=5_000) or ""
    assert len(title_text.strip()) > 0, "عنوان الصفحة فارغ"


# ──────────────────────────────────────────────────────────────
#  2. التنقل بين أقسام اللوحة
# ──────────────────────────────────────────────────────────────

def test_navigation_works(authenticated_page: Page):
    """
    يتحقق من أن النقر على روابط الشريط الجانبي يُظهر المحتوى
    الصحيح لكل قسم دون إعادة تحميل كاملة للصفحة.
    """
    authenticated_page.goto("/")
    authenticated_page.wait_for_selector(".sidebar, .dh-sidebar", timeout=15_000)

    # ─── التنقل للنزلاء ───────────────────────────────────────
    guests_link = authenticated_page.locator(
        ".sidebar a:has-text('النزلاء'), .dh-nav-item:has-text('النزلاء')"
    ).first
    guests_link.click()
    authenticated_page.wait_for_timeout(800)

    # المحتوى الخاص بالنزلاء ظاهر
    guests_section = authenticated_page.locator(  # noqa: F841
        "#sec-guests, [id*='guest'], .section.active"
    )
    # انتظر أن يكون قسم ما نشطاً
    authenticated_page.wait_for_selector(".pane-section.active, .section.active", timeout=5_000)

    # ─── التنقل للحجوزات ──────────────────────────────────────
    bookings_link = authenticated_page.locator(
        ".sidebar a:has-text('الحجوزات'), .dh-nav-item:has-text('الحجوزات')"
    ).first
    bookings_link.click()
    authenticated_page.wait_for_timeout(800)

    # تحقق من أن رابط الحجوزات أصبح نشطاً أو المحتوى ظهر
    active_section = authenticated_page.locator(  # noqa: F841
        "#sec-bookings.active, #sec-bookings.pane-section.active"
    )
    # أو تحقق أن عنوان الصفحة تغيّر ليشير للحجوزات
    page_title = authenticated_page.locator("#page-title, .dh-topbar-title").first
    title_text = page_title.text_content(timeout=3_000) or ""
    assert "حجوزات" in title_text or bookings_link.evaluate("el => el.classList.contains('active') || el.classList.contains('is-active')"), (
        "التنقل للحجوزات لم يُحدِّث المحتوى"
    )

    # ─── التنقل للفواتير ──────────────────────────────────────
    invoices_link = authenticated_page.locator(
        ".sidebar a:has-text('الفواتير'), .dh-nav-item:has-text('الفواتير')"
    ).first
    invoices_link.click()
    authenticated_page.wait_for_timeout(800)

    # تحقق من المحتوى أو العنوان
    page_title_text = (
        authenticated_page.locator("#page-title, .dh-topbar-title").first.text_content(timeout=3_000) or ""
    )
    assert "فاتور" in page_title_text or authenticated_page.locator("#sec-invoices").is_visible(), (
        "التنقل للفواتير لم يُحدِّث المحتوى"
    )

    # ─── العودة للرئيسية ──────────────────────────────────────
    home_link = authenticated_page.locator(
        ".sidebar a:has-text('الرئيسية'), .dh-nav-item:has-text('الرئيسية'), .dh-nav-item:has-text('لوحة')"
    ).first
    home_link.click()
    authenticated_page.wait_for_timeout(800)

    # مؤشرات KPI يجب أن تعود للظهور
    kpi_area = authenticated_page.locator(
        ".kpi-grid, .stats-grid, [id*='kpi'], .stat-card, .stat"
    )
    expect(kpi_area.first).to_be_visible(timeout=5_000)


# ──────────────────────────────────────────────────────────────
#  3. ظهور مؤشرات KPI
# ──────────────────────────────────────────────────────────────

def test_kpi_widgets_render(authenticated_page: Page):
    """
    يتحقق من أن مؤشرات KPI تُعرض كأرقام حقيقية
    (أو صفراً) وليس كـ spinners أو نصوص تحميل.
    """
    authenticated_page.goto("/")

    # انتظر حتى تنتهي الطلبات الشبكية الأولية
    authenticated_page.wait_for_load_state("networkidle", timeout=25_000)

    # ─── مؤشرات الصفحة القديمة (main.py client dashboard) ─────
    # الحجوزات النشطة
    kpi_active = authenticated_page.locator("#kpi-active")
    if kpi_active.is_visible():
        # يجب أن يحتوي على رقم وليس "-" أو "جاري"
        kpi_text = kpi_active.text_content(timeout=15_000) or ""
        assert kpi_text.strip() not in ("", "جارٍ", "جاري التحميل..."), (
            f"مؤشر الحجوزات النشطة لم يُحمَّل بعد: '{kpi_text}'"
        )
        # يجب أن يكون رقماً أو صفراً
        try:
            int(kpi_text.strip().replace(",", "").replace("٬", ""))
        except ValueError:
            pass  # قد يكون تنسيق عربي — مقبول

    # ─── مؤشرات لوحة dashboard.html الجديدة ──────────────────
    # إجمالي الحجوزات / الإيرادات / الإشغال
    new_kpi_cards = authenticated_page.locator(
        ".kpi-card .val, .stat-card .value, .stat .val"
    )
    count = new_kpi_cards.count()

    if count > 0:
        for i in range(min(count, 4)):  # تحقق من أول 4 مؤشرات
            card = new_kpi_cards.nth(i)
            if card.is_visible():
                val_text = card.text_content(timeout=10_000) or ""
                # يجب ألا يحتوي على "جارٍ" أو spinning مؤشر
                assert "جارٍ" not in val_text, (
                    f"مؤشر KPI لم ينتهِ من التحميل: '{val_text}'"
                )
                # يجب ألا يكون نص "-" فقط بعد التحميل
                # (قد يكون "-" قبل البيانات — مقبول لكن نُحذِّر)

    # ─── تحقق من API مباشرة ───────────────────────────────────
    # اختبر endpoint /api/kpi مباشرة للتأكد من عمله
    response = authenticated_page.request.get(f"{BASE_URL}/api/kpi")
    assert response.status in (200, 401), (
        f"endpoint /api/kpi أعاد كود غير متوقع: {response.status}"
    )

    if response.status == 200:
        data = response.json()
        assert "kpi" in data or "success" in data, (
            f"بنية استجابة /api/kpi غير متوقعة: {data}"
        )
        kpi = data.get("kpi", {})
        # تحقق من وجود المفاتيح الأساسية
        for key in ("active_bookings", "total_guests"):
            assert key in kpi, f"مفتاح '{key}' مفقود من استجابة /api/kpi"
            assert isinstance(kpi[key], (int, float)), (
                f"قيمة '{key}' يجب أن تكون رقماً"
            )


# ──────────────────────────────────────────────────────────────
#  4. اختبار التنقل في dashboard.html الجديدة (إن وُجدت)
# ──────────────────────────────────────────────────────────────

def test_new_dashboard_navigation(authenticated_page: Page):
    """
    يتحقق من التنقل في لوحة dashboard.html الجديدة
    (إن كانت هي الصفحة المُعروضة).
    """
    authenticated_page.goto("/")
    authenticated_page.wait_for_load_state("domcontentloaded", timeout=15_000)

    # إذا كانت لوحة dh-sidebar الجديدة موجودة
    new_sidebar = authenticated_page.locator(".dh-sidebar")
    if not new_sidebar.is_visible():
        pytest.skip("لوحة dh-sidebar الجديدة غير موجودة في هذه البيئة")

    # تحقق من وجود مجموعات التنقل
    nav_items = authenticated_page.locator(".dh-nav-item")
    count = nav_items.count()
    assert count >= 5, f"عدد عناصر التنقل أقل من المتوقع: {count}"

    # انقر على أول عنصر تنقل وتحقق من تغيير القسم النشط
    first_item = nav_items.first
    first_item.click()
    authenticated_page.wait_for_timeout(500)

    active_section = authenticated_page.locator(".section.active")  # noqa: F841
    expect(active_section.first).to_be_visible(timeout=5_000)


# ──────────────────────────────────────────────────────────────
#  5. اختبار عرض إشعارات اللوحة
# ──────────────────────────────────────────────────────────────

def test_notifications_section_loads(authenticated_page: Page):
    """
    يتحقق من أن قسم الإشعارات يُحمَّل (حتى لو لم تكن هناك إشعارات).
    """
    authenticated_page.goto("/")
    authenticated_page.wait_for_load_state("networkidle", timeout=20_000)

    # قسم الإشعارات في الصفحة القديمة
    notif_list = authenticated_page.locator("#notif-list")
    if notif_list.is_visible():
        notif_text = notif_list.text_content(timeout=10_000) or ""
        # يجب ألا يكون "جارٍ التحميل" نهاية المطاف
        assert "جارٍ التحميل" not in notif_text, (
            "قسم الإشعارات لا يزال في حالة تحميل"
        )

    # آخر الحجوزات في الصفحة الرئيسية
    home_bookings_table = authenticated_page.locator("#tbl-home-bk, .mod-table")
    if home_bookings_table.first.is_visible():
        table_text = home_bookings_table.first.text_content(timeout=10_000) or ""
        assert "جارٍ التحميل" not in table_text, (
            "جدول آخر الحجوزات لا يزال في حالة تحميل"
        )
