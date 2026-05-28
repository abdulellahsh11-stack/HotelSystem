"""
services/dynamic_pricing.py
محرك التسعير الديناميكي لنظام ضيوف.

مبادئ التصميم:
- المالك يتحكم في الحدود (min/max)
- المحرك يعمل ضمن هذه الحدود فقط
- كل تغيير سعر مسجَّل مع السبب
- يمكن تعطيله بضغطة زر
- لا يُغيّر أسعار الحجوزات الموجودة
"""

import os
import json
import math
import logging
import threading
from datetime import datetime, date, timedelta
from typing import Optional

from models.reservation import PricingRules, PricingDecision

logger = logging.getLogger("dynamic_pricing")


# ─── Saudi Calendar ───────────────────────────────────────────

# المواسم والمناسبات السعودية (تواريخ تقريبية — الهجري يتغير سنوياً)
# يتم تحديثها يدوياً أو من API الهجري
SAUDI_SEASONS_2026 = {
    # رمضان 2026 — الأسبوع الأول فقط (انخفاض الطلب)
    "ramadan_first_week": {
        "start": date(2026, 2, 17),
        "end": date(2026, 2, 24),
        "factor": 0.85,
        "label": "أول رمضان"
    },
    # عيد الفطر 2026
    "eid_al_fitr": {
        "start": date(2026, 3, 19),
        "end": date(2026, 3, 24),
        "factor": 1.40,
        "label": "عيد الفطر"
    },
    # عيد الأضحى 2026
    "eid_al_adha": {
        "start": date(2026, 5, 26),
        "end": date(2026, 6, 1),
        "factor": 1.40,
        "label": "عيد الأضحى"
    },
    # الإجازة الصيفية
    "summer": {
        "start": date(2026, 6, 15),
        "end": date(2026, 8, 31),
        "factor": 1.20,
        "label": "الإجازة الصيفية"
    },
    # اليوم الوطني السعودي (23 سبتمبر ± 3 أيام)
    "national_day": {
        "start": date(2026, 9, 20),
        "end": date(2026, 9, 26),
        "factor": 1.35,
        "label": "اليوم الوطني"
    },
    # الموسم السياحي (ديسمبر - يناير)
    "tourist_season": {
        "start": date(2026, 12, 1),
        "end": date(2026, 12, 31),
        "factor": 1.10,
        "label": "الموسم السياحي"
    },
}


class DynamicPricingEngine:
    """
    محرك التسعير الذكي.
    thread-safe: يستخدم قفل لمنع race conditions مع Channel Manager.
    """

    def __init__(self, db, channel_manager=None):
        self.db = db
        self.channel_manager = channel_manager
        self._lock = threading.Lock()
        self._enabled = os.environ.get("DYNAMIC_PRICING_ENABLED", "false").lower() == "true"

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    # ─── Core Pricing Logic ───────────────────────────────────

    def calculate_price(
        self,
        client_id: str,
        room_type: str,
        target_date: str,
        current_occupancy: float,
        base_price: float,
        rules: PricingRules,
        previous_price: Optional[float] = None
    ) -> PricingDecision:
        """
        يحسب السعر المناسب لتاريخ معين.

        العوامل:
        1. نسبة الإشغال الحالية
        2. المسافة الزمنية من التاريخ (lead time)
        3. يوم الأسبوع (عطلة نهاية الأسبوع)
        4. المواسم والمناسبات السعودية
        """
        if rules.base_price <= 0:
            return PricingDecision(
                final_price=base_price,
                base_price=base_price,
                reason="base_price = 0: لا يمكن تطبيق التسعير",
                confidence="low",
                price_changed=False,
                previous_price=previous_price or base_price,
            )

        # حساب كل عامل
        occ_factor = self._occupancy_factor(current_occupancy) if rules.use_occupancy else 1.0
        lead_factor = self._lead_time_factor(target_date) if rules.use_lead_time else 1.0
        dow_factor = self._day_of_week_factor(target_date) if rules.use_day_of_week else 1.0
        season_factor, season_label = self._season_factor(target_date) if rules.use_seasons else (1.0, "")

        # السعر الخام
        raw_price = rules.base_price * occ_factor * lead_factor * dow_factor * season_factor

        # تطبيق حد التغيير (max_change_percent)
        was_capped = False
        if previous_price and previous_price > 0:
            max_up = previous_price * (1 + rules.max_change_percent / 100)
            max_down = previous_price * (1 - rules.max_change_percent / 100)
            if raw_price > max_up:
                raw_price = max_up
                was_capped = True
            elif raw_price < max_down:
                raw_price = max_down
                was_capped = True

        # تطبيق الحدود المطلقة
        capped = max(rules.min_price, min(rules.max_price, raw_price))

        # تقريب السعر
        final = self._round_price(capped, rules.round_to)

        # بناء السبب
        reason_parts = []
        occ_pct = int(current_occupancy * 100)
        if rules.use_occupancy:
            reason_parts.append(f"إشغال {occ_pct}%")
        if rules.use_day_of_week and dow_factor > 1.0:
            reason_parts.append("عطلة نهاية الأسبوع")
        if rules.use_seasons and season_factor != 1.0:
            reason_parts.append(season_label)
        if rules.use_lead_time and lead_factor != 1.0:
            days_left = (self._parse_date(target_date) - date.today()).days
            if days_left < 2:
                reason_parts.append("حجز لحظي")
            elif days_left > 30:
                reason_parts.append("حجز مبكر")
        if was_capped:
            reason_parts.append(f"محدود بـ {rules.max_change_percent}% تغيير")

        reason = " + ".join(reason_parts) if reason_parts else "سعر أساسي"

        # مستوى الثقة
        confidence = "high" if rules.use_occupancy and rules.use_seasons else "medium"
        if not rules.use_occupancy:
            confidence = "low"

        prev = previous_price if previous_price is not None else final
        price_changed = abs(final - prev) >= 1.0

        return PricingDecision(
            final_price=final,
            base_price=rules.base_price,
            occupancy_factor=round(occ_factor, 3),
            lead_time_factor=round(lead_factor, 3),
            day_of_week_factor=round(dow_factor, 3),
            season_factor=round(season_factor, 3),
            reason=reason,
            confidence=confidence,
            price_changed=price_changed,
            previous_price=prev,
            raw_calculated=round(raw_price, 2),
            was_capped=was_capped,
        )

    def _occupancy_factor(self, occupancy: float) -> float:
        """
        عامل الإشغال:
        < 30%  → 0.85
        30-50% → 0.95
        50-70% → 1.00
        70-85% → 1.15
        85-95% → 1.30
        > 95%  → 1.50
        """
        thresholds = [
            (0.30, 0.85),
            (0.50, 0.95),
            (0.70, 1.00),
            (0.85, 1.15),
            (0.95, 1.30),
        ]
        for threshold, factor in thresholds:
            if occupancy <= threshold:
                return factor
        return 1.50

    def _lead_time_factor(self, target_date_str: str) -> float:
        """
        عامل وقت الحجز المبكر:
        < 1 يوم  → 1.20 (last-minute premium)
        1-3 أيام → 1.10
        4-7 أيام → 1.00
        8-14 يوم → 0.97
        15-30 يوم → 0.95
        > 30 يوم  → 0.93
        """
        try:
            target = self._parse_date(target_date_str)
            days = (target - date.today()).days
        except Exception:
            return 1.0

        if days < 1:
            return 1.20
        elif days <= 3:
            return 1.10
        elif days <= 7:
            return 1.00
        elif days <= 14:
            return 0.97
        elif days <= 30:
            return 0.95
        else:
            return 0.93

    def _day_of_week_factor(self, target_date_str: str) -> float:
        """
        الخميس (3) والجمعة (4) والسبت (5) → 1.15 (عطلة سعودية)
        باقي الأيام → 1.00
        """
        try:
            target = self._parse_date(target_date_str)
            # weekday(): الاثنين=0 ... الأحد=6
            if target.weekday() in (3, 4, 5):  # خميس، جمعة، سبت
                return 1.15
        except Exception:
            pass
        return 1.00

    def _season_factor(self, target_date_str: str) -> tuple:
        """
        يتحقق من المواسم السعودية ويُعيد (factor, label).
        إذا تداخل موسمان يطبّق الأعلى.
        """
        try:
            target = self._parse_date(target_date_str)
        except Exception:
            return (1.0, "")

        best_factor = 1.0
        best_label = ""

        for season_name, season in SAUDI_SEASONS_2026.items():
            if season["start"] <= target <= season["end"]:
                if abs(season["factor"] - 1.0) > abs(best_factor - 1.0):
                    best_factor = season["factor"]
                    best_label = season["label"]

        return (best_factor, best_label)

    def _round_price(self, price: float, round_to: float) -> float:
        """يُقرّب السعر لأقرب round_to"""
        if round_to <= 0:
            return round(price, 2)
        return round(math.ceil(price / round_to) * round_to, 2)

    def _parse_date(self, date_str: str) -> date:
        """يحوّل string لـ date"""
        return date.fromisoformat(date_str[:10])

    # ─── Apply Pricing ────────────────────────────────────────

    def apply_pricing_for_client(self, client_id: str) -> dict:
        """
        يطبّق التسعير على الـ 30 يوم القادمة لكل الغرف.
        يُشغَّل كل 4 ساعات من CronManager.
        يُرسل التحديثات لكل القنوات عبر ChannelManager.
        """
        if not self._enabled:
            return {"status": "disabled", "message": "Dynamic Pricing معطَّل"}

        with self._lock:  # منع تشغيل متزامن
            return self._run_pricing_cycle(client_id)

    def _run_pricing_cycle(self, client_id: str) -> dict:
        """دورة التسعير الكاملة"""
        summary = {
            "client_id": client_id,
            "started_at": datetime.now().isoformat(),
            "rooms_processed": 0,
            "prices_changed": 0,
            "errors": [],
        }

        try:
            # جلب الغرف وقواعد التسعير
            rooms = self._get_rooms_with_rules(client_id)
            total_rooms = self._get_total_rooms(client_id)

            for room in rooms:
                room_id = room["id"]
                rules = self._build_rules(room)

                if not rules:
                    continue

                # تجاهل إذا كل الغرف محجوزة (لا تحديث مطلوب)
                room_occupancy = self._get_room_occupancy(client_id, room_id)
                if room_occupancy >= 1.0:
                    continue

                # تطبيق على كل يوم في الـ 30 يوم القادمة
                changes = []
                for days_ahead in range(0, 31):
                    target_date = (date.today() + timedelta(days=days_ahead)).isoformat()

                    # تجاهل الماضي
                    if self._parse_date(target_date) < date.today():
                        continue

                    # السعر الحالي
                    prev_price = self._get_current_rate(client_id, room_id, target_date)

                    # حساب السعر الجديد
                    decision = self.calculate_price(
                        client_id=client_id,
                        room_type=room.get("room_type", ""),
                        target_date=target_date,
                        current_occupancy=room_occupancy,
                        base_price=rules.base_price,
                        rules=rules,
                        previous_price=prev_price,
                    )

                    if decision.price_changed:
                        changes.append((target_date, decision))
                        summary["prices_changed"] += 1

                # حفظ التغييرات وإرسالها للقنوات
                if changes:
                    self._apply_room_changes(client_id, room_id, rules, changes)

                summary["rooms_processed"] += 1

        except Exception as e:
            logger.error(f"Pricing cycle failed for {client_id}: {e}")
            summary["errors"].append(str(e))

        summary["finished_at"] = datetime.now().isoformat()
        return summary

    def _apply_room_changes(
        self, client_id: str, room_id: int,
        rules: PricingRules, changes: list
    ) -> None:
        """يحفظ التغييرات في DB ويرسل للقنوات"""
        for target_date, decision in changes:
            # تحديث room_rates
            try:
                self.db.execute(
                    """INSERT INTO room_rates (client_id, room_id, rate_date, current_rate, is_dynamic)
                       VALUES (%s, %s, %s, %s, true)
                       ON CONFLICT (room_id, rate_date)
                       DO UPDATE SET current_rate = EXCLUDED.current_rate,
                                     is_dynamic = true,
                                     last_updated = NOW()""",
                    (client_id, room_id, target_date, decision.final_price)
                )
            except Exception as e:
                logger.error(f"room_rates update failed: {e}")

            # حفظ التاريخ
            try:
                self.db.execute(
                    """INSERT INTO pricing_history
                       (client_id, room_id, target_date, old_price, new_price,
                        occupancy_at_decision, occupancy_factor, lead_time_factor,
                        day_of_week_factor, season_factor, reason)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        client_id, room_id, target_date,
                        decision.previous_price, decision.final_price,
                        0.0,  # occupancy_at_decision — نحسبها لاحقاً
                        decision.occupancy_factor,
                        decision.lead_time_factor,
                        decision.day_of_week_factor,
                        decision.season_factor,
                        decision.reason,
                    )
                )
            except Exception as e:
                logger.error(f"pricing_history insert failed: {e}")

            # إرسال للقنوات عبر ChannelManager (في خيط منفصل)
            if self.channel_manager:
                room_type_id = self._get_channel_room_type(client_id, room_id)
                if room_type_id:
                    threading.Thread(
                        target=self.channel_manager.push_rate_all,
                        args=(client_id, room_type_id, target_date, target_date, decision.final_price),
                        daemon=True
                    ).start()

    # ─── DB Helpers ───────────────────────────────────────────

    def _get_rooms_with_rules(self, client_id: str) -> list:
        """يجلب الغرف مع قواعد التسعير"""
        try:
            return self.db.execute(
                """SELECT r.id, r.room_number, r.room_type,
                          pr.base_price, pr.min_price, pr.max_price,
                          pr.use_occupancy, pr.use_lead_time,
                          pr.use_day_of_week, pr.use_seasons,
                          pr.max_change_percent, pr.round_to, pr.is_active
                   FROM rooms r
                   LEFT JOIN pricing_rules pr
                     ON pr.room_id = r.id AND pr.is_active = true
                   WHERE r.client_id = %s
                   ORDER BY r.room_number""",
                (client_id,)
            ) or []
        except Exception as e:
            logger.error(f"get_rooms_with_rules failed: {e}")
            return []

    def _get_total_rooms(self, client_id: str) -> int:
        try:
            rows = self.db.execute(
                "SELECT COUNT(*) as cnt FROM rooms WHERE client_id=%s", (client_id,)
            )
            return rows[0]["cnt"] if rows else 0
        except Exception:
            return 0

    def _build_rules(self, room_data: dict) -> Optional[PricingRules]:
        """ينشئ PricingRules من بيانات الغرفة"""
        base = room_data.get("base_price")
        min_p = room_data.get("min_price")
        max_p = room_data.get("max_price")

        if not all([base, min_p, max_p]):
            return None

        try:
            rules = PricingRules(
                base_price=float(base),
                min_price=float(min_p),
                max_price=float(max_p),
                use_occupancy=bool(room_data.get("use_occupancy", True)),
                use_lead_time=bool(room_data.get("use_lead_time", True)),
                use_day_of_week=bool(room_data.get("use_day_of_week", True)),
                use_seasons=bool(room_data.get("use_seasons", True)),
                max_change_percent=float(room_data.get("max_change_percent", 20.0)),
                round_to=float(room_data.get("round_to", 5.0)),
            )
            errors = rules.validate()
            if errors:
                logger.warning(f"Invalid pricing rules: {errors}")
                return None
            return rules
        except (ValueError, TypeError) as e:
            logger.error(f"build_rules failed: {e}")
            return None

    def _get_room_occupancy(self, client_id: str, room_id: int) -> float:
        """
        يحسب نسبة الإشغال الحالية لغرفة معينة.
        يفترض إشغال 0% إذا لا بيانات.
        """
        try:
            rows = self.db.execute(
                """SELECT COUNT(*) as booked_days
                   FROM bookings
                   WHERE client_id = %s
                     AND room_id = %s
                     AND status = 'confirmed'
                     AND check_in <= NOW() + INTERVAL '30 days'
                     AND check_out >= NOW()""",
                (client_id, room_id)
            )
            if not rows:
                return 0.0

            booked_days = rows[0].get("booked_days", 0)
            # نسبة الإشغال من الـ 30 يوم القادمة
            return min(1.0, booked_days / 30.0)
        except Exception:
            return 0.0  # افتراضي عند نقص البيانات

    def _get_current_rate(self, client_id: str, room_id: int, date_str: str) -> Optional[float]:
        """يجلب السعر الحالي للغرفة في تاريخ معين"""
        try:
            rows = self.db.execute(
                "SELECT current_rate FROM room_rates WHERE room_id=%s AND rate_date=%s LIMIT 1",
                (room_id, date_str)
            )
            return float(rows[0]["current_rate"]) if rows else None
        except Exception:
            return None

    def _get_channel_room_type(self, client_id: str, room_id: int) -> Optional[str]:
        """يجلب نوع الغرفة في Booking.com من الـ room_mapping"""
        try:
            rows = self.db.execute(
                """SELECT cc.room_mapping, r.room_type
                   FROM channel_configs cc, rooms r
                   WHERE cc.client_id = %s
                     AND cc.channel_name = 'booking.com'
                     AND r.id = %s""",
                (client_id, room_id)
            )
            if rows:
                mapping = rows[0].get("room_mapping", {})
                if isinstance(mapping, str):
                    mapping = json.loads(mapping)
                room_type = rows[0].get("room_type", "")
                return mapping.get(room_type)
        except Exception:
            pass
        return None

    # ─── Calendar View ────────────────────────────────────────

    def get_pricing_calendar(self, client_id: str, room_id: int, days: int = 30) -> list:
        """
        يُعيد الأسعار والمبررات لكل يوم في الـ 30 يوم القادمة.
        للعرض في لوحة التحكم.
        """
        calendar = []
        today = date.today()

        # جلب القواعد للغرفة
        rooms = self._get_rooms_with_rules(client_id)
        room_data = next((r for r in rooms if r["id"] == room_id), None)
        rules = self._build_rules(room_data) if room_data else None
        occupancy = self._get_room_occupancy(client_id, room_id)

        for days_ahead in range(days):
            target = (today + timedelta(days=days_ahead)).isoformat()
            current_rate = self._get_current_rate(client_id, room_id, target)

            if rules:
                decision = self.calculate_price(
                    client_id, room_data.get("room_type", ""),
                    target, occupancy, rules.base_price, rules,
                    previous_price=current_rate
                )
                season_factor, season_label = self._season_factor(target)

                calendar.append({
                    "date": target,
                    "current_rate": current_rate or rules.base_price,
                    "suggested_rate": decision.final_price,
                    "reason": decision.reason,
                    "occupancy_pct": int(occupancy * 100),
                    "is_weekend": self._day_of_week_factor(target) > 1.0,
                    "season": season_label,
                    "season_factor": season_factor,
                    "price_level": self._price_level(decision.final_price, rules),
                })
            else:
                calendar.append({
                    "date": target,
                    "current_rate": current_rate or 0,
                    "suggested_rate": current_rate or 0,
                    "reason": "لا توجد قواعد تسعير",
                    "occupancy_pct": int(occupancy * 100),
                    "price_level": "base",
                })

        return calendar

    def _price_level(self, price: float, rules: PricingRules) -> str:
        """يحدد مستوى السعر للعرض بالألوان"""
        if price <= rules.base_price * 0.95:
            return "low"        # أخضر — اقتصادي
        elif price <= rules.base_price * 1.10:
            return "base"       # رمادي — أساسي
        elif price <= rules.base_price * 1.25:
            return "medium"     # برتقالي — متوسط
        else:
            return "high"       # أحمر — مرتفع

    def get_pricing_impact(self, client_id: str, days: int = 30) -> dict:
        """
        يحسب التأثير المالي للتسعير الديناميكي.
        مقارنة الإيراد الفعلي vs لو استخدمنا السعر الأساسي.
        """
        try:
            rows = self.db.execute(
                """SELECT
                     COALESCE(SUM(rr.current_rate), 0) as dynamic_revenue,
                     COALESCE(SUM(pr.base_price), 0) as base_revenue,
                     COUNT(DISTINCT rr.room_id) as rooms_with_rates
                   FROM room_rates rr
                   JOIN pricing_rules pr ON pr.room_id = rr.room_id AND pr.is_active = true
                   WHERE rr.client_id = %s
                     AND rr.is_dynamic = true
                     AND rr.rate_date >= CURRENT_DATE
                     AND rr.rate_date < CURRENT_DATE + INTERVAL '%s days'""",
                (client_id, days)
            )
            if not rows:
                return {"dynamic_revenue": 0, "base_revenue": 0, "difference": 0, "pct_gain": 0}

            dynamic = float(rows[0].get("dynamic_revenue", 0))
            base = float(rows[0].get("base_revenue", 0))
            diff = dynamic - base
            pct = (diff / base * 100) if base > 0 else 0

            return {
                "dynamic_revenue": round(dynamic, 2),
                "base_revenue": round(base, 2),
                "difference": round(diff, 2),
                "pct_gain": round(pct, 1),
                "rooms_with_rates": rows[0].get("rooms_with_rates", 0),
            }
        except Exception as e:
            logger.error(f"get_pricing_impact failed: {e}")
            return {}

    def get_or_save_rules(self, client_id: str, room_id: int, rules_dict: dict = None) -> dict:
        """جلب أو حفظ قواعد التسعير لغرفة"""
        if rules_dict:
            # حفظ
            try:
                self.db.execute(
                    """INSERT INTO pricing_rules
                       (client_id, room_id, base_price, min_price, max_price,
                        use_occupancy, use_lead_time, use_day_of_week, use_seasons,
                        max_change_percent, round_to)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (room_id) DO UPDATE
                         SET base_price=EXCLUDED.base_price,
                             min_price=EXCLUDED.min_price,
                             max_price=EXCLUDED.max_price,
                             use_occupancy=EXCLUDED.use_occupancy,
                             use_lead_time=EXCLUDED.use_lead_time,
                             use_day_of_week=EXCLUDED.use_day_of_week,
                             use_seasons=EXCLUDED.use_seasons,
                             max_change_percent=EXCLUDED.max_change_percent,
                             round_to=EXCLUDED.round_to,
                             updated_at=NOW()""",
                    (
                        client_id, room_id,
                        rules_dict.get("base_price"),
                        rules_dict.get("min_price"),
                        rules_dict.get("max_price"),
                        rules_dict.get("use_occupancy", True),
                        rules_dict.get("use_lead_time", True),
                        rules_dict.get("use_day_of_week", True),
                        rules_dict.get("use_seasons", True),
                        rules_dict.get("max_change_percent", 20.0),
                        rules_dict.get("round_to", 5.0),
                    )
                )
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        # جلب
        try:
            rows = self.db.execute(
                "SELECT * FROM pricing_rules WHERE client_id=%s AND room_id=%s AND is_active=true LIMIT 1",
                (client_id, room_id)
            )
            return dict(rows[0]) if rows else {}
        except Exception:
            return {}
