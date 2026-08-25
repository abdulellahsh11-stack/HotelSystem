#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/dynamic_pricing.py — محرك التسعير الديناميكي
منصة ضيوف | Dheuof Hotel SaaS Platform
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

log = logging.getLogger("dheuof")

# ──────────────────────────────────────────────────────────────
#  مواسم المملكة العربية السعودية 2026
# ──────────────────────────────────────────────────────────────
SAUDI_SEASONS_2026: dict[str, dict] = {
    "new_year":      {"label": "رأس السنة",         "start": date(2026, 1, 1),  "end": date(2026, 1, 7),  "factor": 1.30},
    "winter":        {"label": "الشتاء العادي",      "start": date(2026, 1, 8),  "end": date(2026, 2, 28), "factor": 1.00},
    "ramadan":       {"label": "شهر رمضان",          "start": date(2026, 2, 18), "end": date(2026, 3, 18), "factor": 1.25},
    "eid_al_fitr":   {"label": "عيد الفطر",          "start": date(2026, 3, 19), "end": date(2026, 3, 26), "factor": 1.60},
    "spring":        {"label": "الربيع",             "start": date(2026, 3, 27), "end": date(2026, 5, 14), "factor": 1.10},
    "eid_al_adha":   {"label": "عيد الأضحى",         "start": date(2026, 6, 25), "end": date(2026, 7, 2),  "factor": 1.70},
    "national_day":  {"label": "اليوم الوطني",       "start": date(2026, 9, 22), "end": date(2026, 9, 24), "factor": 1.40},
    "fall_shoulder": {"label": "الخريف",             "start": date(2026, 9, 25), "end": date(2026, 11, 30),"factor": 1.05},
    "hajj":          {"label": "موسم الحج",          "start": date(2026, 6, 1),  "end": date(2026, 6, 24), "factor": 1.50},
    "summer_peak":   {"label": "ذروة الصيف",         "start": date(2026, 7, 3),  "end": date(2026, 8, 31), "factor": 0.85},
    "winter_peak":   {"label": "ذروة الشتاء",        "start": date(2026, 12, 20),"end": date(2026, 12, 31),"factor": 1.35},
}


def get_season_factor(day: date) -> tuple[float, str]:
    """يعيد (معامل الموسم, اسم الموسم) ليوم معيّن."""
    for key, s in SAUDI_SEASONS_2026.items():
        if s["start"] <= day <= s["end"]:
            return s["factor"], s["label"]
    return 1.0, "عادي"


def _occupancy_factor(occupancy_pct: float) -> float:
    """معامل الإشغال: كلما زاد الإشغال ارتفع السعر."""
    if occupancy_pct >= 90:
        return 1.40
    if occupancy_pct >= 75:
        return 1.20
    if occupancy_pct >= 60:
        return 1.10
    if occupancy_pct >= 40:
        return 1.00
    return 0.90


# ──────────────────────────────────────────────────────────────
#  محرك التسعير
# ──────────────────────────────────────────────────────────────
class DynamicPricingEngine:
    def __init__(self, db: Any) -> None:
        self.db = db

    # ── قواعد الغرفة ──────────────────────────────────────────

    def _get_rooms_with_rules(self, client_id: str) -> list[dict]:
        """يعيد جميع الغرف مع قواعد تسعيرها إن وجدت."""
        if not self.db.use_postgres:
            return []
        rows = self.db.execute(
            """
            SELECT r.id, r.room_number, r.room_type, r.base_price,
                   rp.id       AS rule_id,
                   rp.base_amount AS rule_price,
                   rp.min_stay, rp.max_stay,
                   rp.valid_from, rp.valid_to,
                   rp.is_active
            FROM rooms r
            LEFT JOIN rate_plans rp
                   ON rp.client_id = r.client_id
                  AND rp.code = r.room_number
                  AND rp.is_active = TRUE
            WHERE r.client_id = %s AND r.is_deleted = FALSE
            ORDER BY r.room_number
            """,
            (client_id,),
            fetch="all",
        )
        return [dict(r) for r in (rows or [])]

    def get_or_save_rules(
        self,
        client_id: str,
        room_id: int,
        data: Optional[dict] = None,
    ) -> dict:
        """إذا أُرسلت data: احفظ القاعدة. وإلا: ابحث عنها."""
        if not self.db.use_postgres:
            return {"success": True, "data": {}}

        # قراءة بيانات الغرفة
        room = self.db.execute(
            "SELECT * FROM rooms WHERE id=%s AND client_id=%s",
            (room_id, client_id),
            fetch="one",
        )
        if not room:
            return {"success": False, "error": "الغرفة غير موجودة"}
        room = dict(room)

        if data is None:
            # جلب القاعدة الحالية
            rule = self.db.execute(
                """
                SELECT * FROM rate_plans
                WHERE client_id=%s AND code=%s AND is_active=TRUE
                ORDER BY created_at DESC LIMIT 1
                """,
                (client_id, room["room_number"]),
                fetch="one",
            )
            return {"success": True, "room": room, "rule": dict(rule) if rule else None}

        # حفظ / تحديث القاعدة
        try:
            base_amount = float(data.get("base_amount") or data.get("rule_price") or room["base_price"] or 0)
            min_stay = int(data.get("min_stay", 1))
            max_stay = data.get("max_stay")
            valid_from = data.get("valid_from")
            valid_to = data.get("valid_to")

            # بحث عن قاعدة قائمة لتحديثها
            existing = self.db.execute(
                "SELECT id FROM rate_plans WHERE client_id=%s AND code=%s",
                (client_id, room["room_number"]),
                fetch="one",
            )
            if existing:
                self.db.execute(
                    """
                    UPDATE rate_plans
                    SET base_amount=%s, min_stay=%s, max_stay=%s,
                        valid_from=%s, valid_to=%s, is_active=TRUE
                    WHERE client_id=%s AND code=%s
                    """,
                    (base_amount, min_stay, max_stay, valid_from, valid_to,
                     client_id, room["room_number"]),
                )
            else:
                self.db.execute(
                    """
                    INSERT INTO rate_plans
                        (client_id, code, name_ar, base_amount, min_stay, max_stay,
                         valid_from, valid_to, is_active)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
                    """,
                    (client_id, room["room_number"],
                     f"سعر غرفة {room['room_number']}",
                     base_amount, min_stay, max_stay, valid_from, valid_to),
                )
            return {"success": True, "message": "تم حفظ قاعدة التسعير"}
        except Exception as exc:
            log.error(f"DynamicPricing save_rules error: {exc}", exc_info=True)
            return {"success": False, "error": str(exc)}

    # ── تقويم الأسعار ──────────────────────────────────────────

    def get_pricing_calendar(self, client_id: str, room_id: int, days: int = 30) -> list[dict]:
        """يولّد تقويم أسعار يومي للغرفة خلال عدد الأيام القادمة."""
        if not self.db.use_postgres:
            return []

        room = self.db.execute(
            "SELECT base_price, room_number FROM rooms WHERE id=%s AND client_id=%s",
            (room_id, client_id),
            fetch="one",
        )
        if not room:
            return []
        room = dict(room)
        base = float(room["base_price"] or 0)

        # الإشغال الحالي (تقريبي)
        total_rooms = self.db.execute(
            "SELECT COUNT(*) FROM rooms WHERE client_id=%s AND is_deleted=FALSE",
            (client_id,), fetch="one",
        )
        occupied = self.db.execute(
            """
            SELECT COUNT(*) FROM bookings
            WHERE client_id=%s AND status IN ('confirmed','checked_in')
              AND check_in <= CURRENT_DATE AND check_out > CURRENT_DATE
            """,
            (client_id,), fetch="one",
        )
        total_n = (total_rooms[0] if total_rooms else 1) or 1
        occ_n = occupied[0] if occupied else 0
        occ_pct = (occ_n / total_n) * 100

        today = date.today()
        calendar = []
        for i in range(days):
            day = today + timedelta(days=i)
            season_f, season_label = get_season_factor(day)
            occ_f = _occupancy_factor(occ_pct)
            price = Decimal(str(base * season_f * occ_f)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            calendar.append({
                "date": day.isoformat(),
                "price": float(price),
                "base_price": base,
                "season_factor": season_f,
                "occupancy_factor": occ_f,
                "season_label": season_label,
                "is_weekend": day.weekday() in (3, 4),  # الخميس والجمعة
            })
        return calendar

    # ── تطبيق التسعير على الحجوزات ─────────────────────────────

    def apply_pricing_for_client(self, client_id: str) -> dict:
        """يطبّق التسعير الديناميكي على الحجوزات القادمة."""
        if not self.db.use_postgres:
            return {"updated": 0}
        try:
            rows = self.db.execute(
                """
                SELECT b.id, b.room_id, b.check_in, b.check_out,
                       r.base_price
                FROM bookings b
                JOIN rooms r ON b.room_id = r.id AND r.client_id = b.client_id
                WHERE b.client_id=%s AND b.status='confirmed'
                  AND b.check_in > CURRENT_DATE
                """,
                (client_id,),
                fetch="all",
            )
            updated = 0
            for row in (rows or []):
                row = dict(row)
                check_in = row["check_in"]
                if isinstance(check_in, str):
                    check_in = date.fromisoformat(check_in)
                season_f, _ = get_season_factor(check_in)
                new_price = float(Decimal(str(float(row["base_price"]) * season_f)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ))
                # client_id زائدٌ منطقياً — المعرّفات من استعلام مُصفّى —
                # لكن كل استعلام يحمل عزله بنفسه، فلا يعتمد أمانُه على
                # صحّة نداءٍ في مكان آخر قد يتغيّر لاحقاً.
                self.db.execute(
                    "UPDATE bookings SET total_room=%s WHERE id=%s AND client_id=%s",
                    (new_price, row["id"], client_id),
                )
                updated += 1
            return {"updated": updated, "message": f"تم تحديث {updated} حجز"}
        except Exception as exc:
            log.error(f"apply_pricing error: {exc}", exc_info=True)
            raise

    # ── تجاوز يدوي ────────────────────────────────────────────

    def apply_manual_override(
        self, client_id: str, room_id: int, price: float,
        date_from: str, date_to: str, reason: str = ""
    ) -> dict:
        """يضع سعراً ثابتاً يدوياً لغرفة في نطاق تاريخ محدد."""
        if not self.db.use_postgres:
            return {"success": False, "error": "قاعدة البيانات غير متاحة"}
        try:
            room = self.db.execute(
                "SELECT room_number FROM rooms WHERE id=%s AND client_id=%s",
                (room_id, client_id), fetch="one",
            )
            if not room:
                return {"success": False, "error": "الغرفة غير موجودة"}

            room_number = room[0]
            code = f"OVERRIDE_{room_number}_{date_from}"

            # أوقف أي تجاوز سابق في نفس النطاق
            self.db.execute(
                """
                UPDATE rate_plans SET is_active=FALSE
                WHERE client_id=%s AND code LIKE %s
                  AND valid_from >= %s AND valid_to <= %s
                """,
                (client_id, f"OVERRIDE_{room_number}_%", date_from, date_to),
            )

            self.db.execute(
                """
                INSERT INTO rate_plans
                    (client_id, code, name_ar, rate_type, base_amount,
                     valid_from, valid_to, is_active)
                VALUES (%s,%s,%s,'override',%s,%s,%s,TRUE)
                """,
                (client_id, code,
                 f"تجاوز يدوي - {reason or room_number}",
                 price, date_from, date_to),
            )
            return {
                "success": True,
                "message": f"تم تطبيق السعر {price} من {date_from} إلى {date_to}",
            }
        except Exception as exc:
            log.error(f"manual_override error: {exc}", exc_info=True)
            return {"success": False, "error": str(exc)}

    # ── سجل التغييرات ──────────────────────────────────────────

    def get_pricing_history(self, client_id: str, room_id: Optional[int] = None) -> list[dict]:
        """يعيد سجل تغييرات التسعير (rate_plans) للعميل."""
        if not self.db.use_postgres:
            return []
        q = """
            SELECT rp.id, rp.code, rp.name_ar, rp.rate_type,
                   rp.base_amount, rp.min_stay, rp.max_stay,
                   rp.valid_from, rp.valid_to, rp.is_active,
                   rp.created_at,
                   r.room_number, r.id AS room_id
            FROM rate_plans rp
            LEFT JOIN rooms r
                   ON r.client_id = rp.client_id
                  AND r.room_number = rp.code
            WHERE rp.client_id = %s
        """
        params: list = [client_id]
        if room_id:
            q += " AND r.id = %s"
            params.append(room_id)
        q += " ORDER BY rp.created_at DESC LIMIT 200"
        rows = self.db.execute(q, params, fetch="all")
        return [dict(r) for r in (rows or [])]

    # ── تأثير التسعير ──────────────────────────────────────────

    def get_pricing_impact(self, client_id: str) -> dict:
        """يحسب تأثير التسعير الديناميكي مقارنةً بالأسعار الأساسية."""
        if not self.db.use_postgres:
            return {"base_revenue": 0, "dynamic_revenue": 0, "impact_pct": 0}
        try:
            rows = self.db.execute(
                """
                SELECT b.total_room AS dynamic_price,
                       r.base_price
                FROM bookings b
                JOIN rooms r ON b.room_id = r.id
                WHERE b.client_id=%s
                  AND b.status NOT IN ('cancelled')
                  AND b.check_in >= (CURRENT_DATE - INTERVAL '30 days')
                """,
                (client_id,), fetch="all",
            )
            base_total = 0.0
            dynamic_total = 0.0
            for row in (rows or []):
                row = dict(row)
                base_total += float(row.get("base_price") or 0)
                dynamic_total += float(row.get("dynamic_price") or 0)

            impact_pct = 0.0
            if base_total > 0:
                impact_pct = round(((dynamic_total - base_total) / base_total) * 100, 2)

            return {
                "base_revenue": round(base_total, 2),
                "dynamic_revenue": round(dynamic_total, 2),
                "impact_pct": impact_pct,
                "extra_revenue": round(dynamic_total - base_total, 2),
                "period": "آخر 30 يوم",
            }
        except Exception as exc:
            log.error(f"pricing_impact error: {exc}", exc_info=True)
            return {"base_revenue": 0, "dynamic_revenue": 0, "impact_pct": 0}
