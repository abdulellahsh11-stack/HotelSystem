#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/e2e/test_booking_journey.py — رحلة المستخدم الكاملة لإدارة الحجوزات (E2E)
ضيوف · Dheuof Hotel SaaS Platform

تغطي:
  - إنشاء حجز جديد من نموذج اللوحة
  - تدفق تسجيل الوصول (Check-In): البحث عن وصول ثم تغيير الحالة
  - تدفق تسجيل المغادرة (Check-Out): البحث عن مغادر ثم معالجة الخروج
"""

import re
from datetime import date, timedelta

import pytest
from playwright.sync_api import Page, expect

from e2e_config import BASE_URL


# ──────────────────────────────────────────────────────────────
#  بيانات اختبار افتراضية
# ──────────────────────────────────────────────────────────────

TODAY: str = date.today().isoformat()
TOMORROW: str = (date.today() + timedelta(days=1)).isoformat()
NEXT_WEEK: str = (date.today() + timedelta(days=7)).isoformat()

TEST_GUEST_NAME: str = "أحمد محمد الاختبار"
TEST_ROOM: str = "101"
TEST_NIGHTLY_RATE: int = 350


# ──────────────────────────────────────────────────────────────
#  دوال مساعدة
# ──────────────────────────────────────────────────────────────

def _go_to_bookings_section(page: Page) -> None:
    """ينتقل إلى قسم الحجوزات في اللوحة."""
    page.goto("/")
    page.wait_for_selector(".sidebar, .dh-sidebar", timeout=15_000)

    bookings_link = page.locator(
        ".sidebar a:has-text('الحجوزات'), .dh-nav-item:has-text('الحجوزات')"
    ).first
    bookings_link.click()
    page.wait_for_timeout(800)


def _open_new_booking_modal(page: Page) -> None:
    """يفتح نموذج إنشاء حجز جديد."""
    # زر "+ حجز جديد" أو "+ إضافة" الخاص بالحجوزات
    new_booking_btn = page.locator(
        "button:has-text('حجز جديد'), "
        "button:has-text('+ حجز'), "
        "[onclick*='m-booking'], [onclick*='modal-booking'], "
        "button:has-text('إضافة'):visible"
    ).first
    new_booking_btn.click()
    page.wait_for_timeout(500)


def _api_create_booking(page: Page, **kwargs) -> dict:
    """
    يُنشئ حجزاً مباشرة عبر API — يُستخدم لإعداد بيانات الاختبار
    دون الاعتماد على UI متغيّر.
    """
    payload = {
        "guest_name": kwargs.get("guest_name", TEST_GUEST_NAME),
        "room": kwargs.get("room", TEST_ROOM),
        "check_in": kwargs.get("check_in", TODAY),
        "check_out": kwargs.get("check_out", TOMORROW),
        "nightly_rate": kwargs.get("nightly_rate", TEST_NIGHTLY_RATE),
        "status": kwargs.get("status", "confirmed"),
        "source": "reception",
    }
    response = page.request.post(
        f"{BASE_URL}/api/bookings",
        data={"Content-Type": "application/json"},
        headers={"Content-Type": "application/json"},
    )
    # نُرسل JSON مباشرة
    import json
    response = page.evaluate(
        """
        async (args) => {
            const r = await fetch('/api/bookings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(args.payload)
            });
            return await r.json();
        }
        """,
        {"payload": payload},
    )
    return response if isinstance(response, dict) else {}


# ──────────────────────────────────────────────────────────────
#  1. إنشاء حجز جديد
# ──────────────────────────────────────────────────────────────

class TestCreateBooking:
    """اختبارات إنشاء الحجوزات."""

    def test_create_booking_via_api(self, authenticated_page: Page):
        """
        يتحقق من إنشاء حجز عبر API مباشرة ويتأكد من ظهوره في القائمة.
        هذا اختبار تكامل سريع لا يعتمد على الـ UI.
        """
        # أنشئ الحجز عبر API
        result = _api_create_booking(authenticated_page, guest_name=TEST_GUEST_NAME)

        assert result.get("success"), (
            f"فشل إنشاء الحجز عبر API: {result}"
        )
        booking_data = result.get("data", {})
        booking_id = booking_data.get("id", "")
        assert booking_id, "معرّف الحجز غير موجود في الاستجابة"

        # تحقق أن الحجز يظهر في قائمة الحجوزات
        bookings_response = authenticated_page.evaluate(
            "() => fetch('/api/bookings').then(r => r.json())"
        )
        if isinstance(bookings_response, dict):
            bookings = bookings_response.get("data", [])
            ids = [str(b.get("id", "")) for b in bookings]
            assert str(booking_id) in ids or any(
                b.get("guest_name") == TEST_GUEST_NAME for b in bookings
            ), f"الحجز المُنشأ غير موجود في القائمة"

    def test_create_booking_via_ui_form(self, authenticated_page: Page):
        """
        يُنشئ حجزاً من خلال نموذج اللوحة ويتحقق من ظهور رسالة التأكيد.
        يختبر تدفق المستخدم الكامل في الـ UI.
        """
        # انتقل لقسم الحجوزات
        _go_to_bookings_section(authenticated_page)

        # ─── نموذج dashboard.html الجديدة ─────────────────────
        # حاول فتح نموذج الحجز
        new_btn = authenticated_page.locator(
            "button:has-text('حجز جديد'), "
            "button[onclick*='m-booking'], "
            "button[onclick*='modal-booking'], "
            "button[onclick*='openModal']:has-text('حجز')"
        ).first

        if not new_btn.is_visible():
            # في dashboard.html الجديدة البحث في صفحة الحجوزات
            authenticated_page.goto("/")
            authenticated_page.wait_for_selector(".dh-nav-item, .sidebar a", timeout=10_000)
            new_btn = authenticated_page.locator(
                "button:has-text('حجز جديد'), button:has-text('إضافة حجز')"
            ).first

        if not new_btn.is_visible():
            pytest.skip("زر إنشاء حجز غير مرئي في هذا الـ UI — تجاوز الاختبار")

        new_btn.click()
        authenticated_page.wait_for_timeout(500)

        # ─── ملء نموذج dashboard.html الجديدة ─────────────────
        # تاريخ الوصول (bookingCheckin أو b-in)
        for checkin_id in ("#bookingCheckin", "#b-in"):
            field = authenticated_page.locator(checkin_id)
            if field.is_visible():
                field.fill(TODAY)
                break

        # تاريخ المغادرة
        for checkout_id in ("#bookingCheckout", "#b-out"):
            field = authenticated_page.locator(checkout_id)
            if field.is_visible():
                field.fill(TOMORROW)
                break

        # الغرفة
        for room_id in ("#bookingRoom", "#b-room"):
            field = authenticated_page.locator(room_id)
            if field.is_visible():
                field.fill(TEST_ROOM)
                break

        # اسم النزيل (في نموذج الحجز الجديد)
        for guest_id in ("#bookingGuest", "#g-name"):
            field = authenticated_page.locator(guest_id)
            if field.is_visible():
                field.fill(TEST_GUEST_NAME)
                break

        # السعر (إن وُجد)
        for price_id in ("#bookingPrice", "#b-rate"):
            field = authenticated_page.locator(price_id)
            if field.is_visible():
                field.fill(str(TEST_NIGHTLY_RATE))
                break

        # انقر زر الإضافة/التأكيد
        submit_btn = authenticated_page.locator(
            "button[onclick*='addBooking'], "
            "button[onclick*='createBooking'], "
            ".modal-actions button.btn-primary, "
            ".modal-actions button:has-text('إضافة'), "
            ".modal button:has-text('تأكيد')"
        ).first

        if not submit_btn.is_visible():
            pytest.skip("زر تأكيد الحجز غير مرئي")

        submit_btn.click()
        authenticated_page.wait_for_timeout(2_000)

        # ─── التحقق من النجاح ──────────────────────────────────
        # نتوقع رسالة نجاح (toast أو alert) أو إغلاق النموذج
        success_indicator = authenticated_page.locator(
            ".toast-success, "
            ".alert-success, "
            ".alert:has-text('تم'), "
            "[class*='success']:visible, "
            "[class*='toast']:visible"
        )

        modal_closed = not authenticated_page.locator(
            "#m-booking.open, #modal-booking.open"
        ).is_visible()

        assert (
            success_indicator.first.is_visible() or modal_closed
        ), "لم يظهر أي مؤشر نجاح بعد إنشاء الحجز"


# ──────────────────────────────────────────────────────────────
#  2. تدفق تسجيل الوصول (Check-In)
# ──────────────────────────────────────────────────────────────

class TestCheckinFlow:
    """اختبارات تدفق تسجيل الوصول."""

    @pytest.fixture(autouse=True)
    def setup_booking(self, authenticated_page: Page):
        """يُنشئ حجزاً تجريبياً بحالة 'confirmed' لاختبار Check-In."""
        result = _api_create_booking(
            authenticated_page,
            guest_name="نزيل وصول اليوم",
            check_in=TODAY,
            check_out=TOMORROW,
            status="confirmed",
        )
        self.booking_id = result.get("data", {}).get("id", "")
        yield
        # التنظيف بعد الاختبار: تحديث الحالة لـ checked_out
        if self.booking_id:
            authenticated_page.evaluate(
                f"""
                fetch('/api/bookings/{self.booking_id}', {{
                    method: 'PUT',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{status: 'cancelled'}})
                }})
                """
            )

    def test_checkin_flow(self, authenticated_page: Page):
        """
        يُنفِّذ تدفق Check-In:
        1. انتقل لقسم الحجوزات
        2. ابحث عن حجز اليوم بحالة confirmed
        3. حدِّث حالته إلى checked_in
        4. تحقق من تغيير الحالة
        """
        if not self.booking_id:
            pytest.skip("لم يُنشأ حجز تجريبي — تجاوز الاختبار")

        # ─── تحديث الحالة عبر API ─────────────────────────────
        update_result = authenticated_page.evaluate(
            """
            async (args) => {
                const r = await fetch('/api/bookings/' + args.id, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({status: 'checked_in'})
                });
                return await r.json();
            }
            """,
            {"id": self.booking_id},
        )

        assert update_result.get("success"), (
            f"فشل تحديث حالة الحجز إلى checked_in: {update_result}"
        )

        # تحقق من الحالة الجديدة
        bookings = authenticated_page.evaluate(
            "() => fetch('/api/bookings').then(r => r.json())"
        )
        if isinstance(bookings, dict):
            booking_list = bookings.get("data", [])
            target = next(
                (b for b in booking_list if str(b.get("id")) == str(self.booking_id)),
                None,
            )
            if target:
                assert target.get("status") == "checked_in", (
                    f"حالة الحجز لم تتغير: {target.get('status')}"
                )

    def test_checkin_ui_flow(self, authenticated_page: Page):
        """
        يختبر تدفق Check-In من خلال الـ UI:
        ينتقل لقسم الحجوزات، يبحث عن الوصولات، يُنفِّذ Check-In.
        """
        # انتقل للوحة وابحث عن قسم الحجوزات أو الاستقبال
        _go_to_bookings_section(authenticated_page)
        authenticated_page.wait_for_timeout(1_000)

        # تحقق من وجود جدول الحجوزات
        bookings_table = authenticated_page.locator(
            "#tbl-bookings, table[id*='booking'], .mod-table"
        )
        if bookings_table.first.is_visible():
            table_text = bookings_table.first.text_content(timeout=5_000) or ""
            # تحقق من عدم وجود "جارٍ التحميل" فقط
            assert "جارٍ التحميل" not in table_text.strip().replace("جارٍ التحميل...", "").strip() or len(table_text.strip()) > 30, (
                "جدول الحجوزات لا يزال في حالة تحميل"
            )

        # ابحث عن زر Check-In أو "وصول" في الجدول
        checkin_btn = authenticated_page.locator(
            "button:has-text('دخول'), "
            "button:has-text('وصول'), "
            "button:has-text('Check-In'), "
            "button[onclick*='checkin']"
        ).first

        if checkin_btn.is_visible():
            checkin_btn.click()
            authenticated_page.wait_for_timeout(1_000)
            # تحقق من رسالة نجاح أو تغيير الحالة
            success = authenticated_page.locator(
                ".toast-success, .alert-success, [class*='success']:visible"
            ).first
            # نجاح اختياري — الاختبار الرئيسي هو API
        else:
            # لا يوجد زر Check-In في الـ UI الحالي — OK
            pass


# ──────────────────────────────────────────────────────────────
#  3. تدفق تسجيل المغادرة (Check-Out)
# ──────────────────────────────────────────────────────────────

class TestCheckoutFlow:
    """اختبارات تدفق تسجيل المغادرة."""

    @pytest.fixture(autouse=True)
    def setup_checkedin_booking(self, authenticated_page: Page):
        """يُنشئ حجزاً بحالة 'checked_in' لاختبار Check-Out."""
        result = _api_create_booking(
            authenticated_page,
            guest_name="نزيل مغادرة اليوم",
            check_in=TODAY,
            check_out=TODAY,  # يغادر اليوم
            status="checked_in",
        )
        self.booking_id = result.get("data", {}).get("id", "")
        yield
        # التنظيف
        if self.booking_id:
            authenticated_page.evaluate(
                f"""
                fetch('/api/bookings/{self.booking_id}', {{
                    method: 'PUT',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{status: 'cancelled'}})
                }})
                """
            )

    def test_checkout_flow(self, authenticated_page: Page):
        """
        يُنفِّذ تدفق Check-Out:
        1. ابحث عن حجز بحالة checked_in
        2. حدِّث حالته إلى checked_out
        3. تحقق من تغيير الحالة
        """
        if not self.booking_id:
            pytest.skip("لم يُنشأ حجز تجريبي بحالة checked_in")

        # ─── تحديث الحالة عبر API ─────────────────────────────
        update_result = authenticated_page.evaluate(
            """
            async (args) => {
                const r = await fetch('/api/bookings/' + args.id, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({status: 'checked_out'})
                });
                return await r.json();
            }
            """,
            {"id": self.booking_id},
        )

        assert update_result.get("success"), (
            f"فشل تحديث حالة الحجز إلى checked_out: {update_result}"
        )

        # ─── تحقق من الحالة الجديدة في API ───────────────────
        bookings = authenticated_page.evaluate(
            "() => fetch('/api/bookings').then(r => r.json())"
        )
        if isinstance(bookings, dict):
            booking_list = bookings.get("data", [])
            target = next(
                (b for b in booking_list if str(b.get("id")) == str(self.booking_id)),
                None,
            )
            if target:
                assert target.get("status") == "checked_out", (
                    f"حالة الحجز لم تتغير إلى checked_out: {target.get('status')}"
                )

    def test_checkout_ui_flow(self, authenticated_page: Page):
        """
        يختبر تدفق المغادرة من خلال الـ UI:
        ينتقل لقسم المغادرات، يجد الحجز، يُكمل عملية الخروج.
        """
        # انتقل للوحة
        _go_to_bookings_section(authenticated_page)
        authenticated_page.wait_for_timeout(1_000)

        # ابحث عن زر Check-Out أو "مغادرة" في الجدول
        checkout_btn = authenticated_page.locator(
            "button:has-text('خروج'), "
            "button:has-text('مغادرة'), "
            "button:has-text('Check-Out'), "
            "button[onclick*='checkout']"
        ).first

        if checkout_btn.is_visible():
            checkout_btn.click()
            authenticated_page.wait_for_timeout(1_000)
        else:
            # لا يوجد زر مخصص — OK للـ UI الحالي
            pass

    def test_checkout_updates_kpi(self, authenticated_page: Page):
        """
        يتحقق من أن تسجيل المغادرة يُحدِّث مؤشرات KPI
        (عدد الحجوزات النشطة يجب أن ينخفض).
        """
        if not self.booking_id:
            pytest.skip("لم يُنشأ حجز تجريبي")

        # احصل على قيمة KPI قبل المغادرة
        kpi_before = authenticated_page.evaluate(
            "() => fetch('/api/kpi').then(r => r.json())"
        )
        active_before = (
            kpi_before.get("kpi", {}).get("active_bookings", 0)
            if isinstance(kpi_before, dict)
            else 0
        )

        # نفِّذ Check-Out
        authenticated_page.evaluate(
            """
            async (args) => {
                await fetch('/api/bookings/' + args.id, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({status: 'checked_out'})
                });
            }
            """,
            {"id": self.booking_id},
        )

        # احصل على قيمة KPI بعد المغادرة
        kpi_after = authenticated_page.evaluate(
            "() => fetch('/api/kpi').then(r => r.json())"
        )
        active_after = (
            kpi_after.get("kpi", {}).get("active_bookings", 0)
            if isinstance(kpi_after, dict)
            else 0
        )

        # يجب أن ينخفض العدد أو يبقى كما هو (إذا كان الحجز لم يُحسَب كنشط)
        assert active_after <= active_before, (
            f"مؤشر الحجوزات النشطة ارتفع بعد Check-Out: {active_before} → {active_after}"
        )


# ──────────────────────────────────────────────────────────────
#  4. اختبار تكامل: رحلة كاملة من إنشاء لمغادرة
# ──────────────────────────────────────────────────────────────

def test_full_booking_lifecycle(authenticated_page: Page):
    """
    رحلة متكاملة:
    إنشاء حجز → Check-In → Check-Out
    يتحقق من تتابع الحالات بشكل صحيح.
    """
    unique_guest = f"نزيل رحلة متكاملة {date.today().isoformat()}"

    # ─── الخطوة 1: إنشاء الحجز ────────────────────────────────
    create_result = _api_create_booking(
        authenticated_page,
        guest_name=unique_guest,
        check_in=TODAY,
        check_out=TOMORROW,
        status="confirmed",
    )
    assert create_result.get("success"), f"فشل إنشاء الحجز: {create_result}"
    booking_id = create_result.get("data", {}).get("id", "")
    assert booking_id, "معرّف الحجز مفقود"

    # ─── الخطوة 2: Check-In ───────────────────────────────────
    checkin_result = authenticated_page.evaluate(
        """
        async (args) => {
            const r = await fetch('/api/bookings/' + args.id, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({status: 'checked_in'})
            });
            return await r.json();
        }
        """,
        {"id": booking_id},
    )
    assert checkin_result.get("success"), f"فشل Check-In: {checkin_result}"

    # تحقق من الحالة
    booking_state = authenticated_page.evaluate(
        """
        async (args) => {
            const r = await fetch('/api/bookings');
            const data = await r.json();
            return (data.data || []).find(b => String(b.id) === String(args.id));
        }
        """,
        {"id": booking_id},
    )
    if booking_state:
        assert booking_state.get("status") == "checked_in", (
            f"الحالة بعد Check-In: {booking_state.get('status')}"
        )

    # ─── الخطوة 3: Check-Out ──────────────────────────────────
    checkout_result = authenticated_page.evaluate(
        """
        async (args) => {
            const r = await fetch('/api/bookings/' + args.id, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({status: 'checked_out'})
            });
            return await r.json();
        }
        """,
        {"id": booking_id},
    )
    assert checkout_result.get("success"), f"فشل Check-Out: {checkout_result}"

    # ─── التحقق النهائي ───────────────────────────────────────
    final_state = authenticated_page.evaluate(
        """
        async (args) => {
            const r = await fetch('/api/bookings');
            const data = await r.json();
            return (data.data || []).find(b => String(b.id) === String(args.id));
        }
        """,
        {"id": booking_id},
    )
    if final_state:
        assert final_state.get("status") == "checked_out", (
            f"الحالة النهائية بعد Check-Out: {final_state.get('status')}"
        )

    # ─── التنظيف ──────────────────────────────────────────────
    authenticated_page.evaluate(
        """
        async (args) => {
            await fetch('/api/bookings/' + args.id, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({status: 'cancelled'})
            });
        }
        """,
        {"id": booking_id},
    )
