"""
models/reservation.py
صيغة موحدة لكل الحجوزات من كل المصادر.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class UnifiedReservation:
    """
    صيغة موحدة لكل الحجوزات من كل المصادر.
    كل قناة تحوّل حجوزها لهذه الصيغة قبل الحفظ.
    """

    # المصدر
    channel: str                        # booking.com · mawasim · direct · airbnb
    channel_reservation_id: str         # رقم الحجز في القناة الأصلية

    # النزيل
    guest_name: str
    guest_phone: str = ""               # قد لا يُرسله Booking.com
    guest_email: str = ""
    guest_nationality: str = ""
    guest_id_number: str = ""           # نادراً متاح من القنوات

    # الحجز
    room_number: str = ""               # قد يكون فارغاً (نُعيّن غرفة يدوياً)
    room_type: str = ""
    check_in: Optional[date] = None
    check_out: Optional[date] = None
    adults: int = 1
    children: int = 0

    # المالي
    total_amount: float = 0.0
    currency: str = "SAR"
    payment_status: str = "pending"     # pending · paid · refunded
    commission: float = 0.0             # عمولة القناة
    net_amount: float = 0.0             # الصافي بعد العمولة

    # ميتاداتا
    special_requests: str = ""
    raw_data: dict = field(default_factory=dict)   # البيانات الأصلية من القناة

    def validate(self) -> list:
        """يتحقق من صحة البيانات — يُعيد قائمة أخطاء (فارغة = صحيح)"""
        errors = []
        if not self.guest_name or not self.guest_name.strip():
            errors.append("guest_name مطلوب")
        if not self.channel_reservation_id:
            errors.append("channel_reservation_id مطلوب")
        if not self.check_in:
            errors.append("check_in مطلوب")
        if not self.check_out:
            errors.append("check_out مطلوب")
        if self.check_in and self.check_out and self.check_in >= self.check_out:
            errors.append("check_out يجب أن يكون بعد check_in")
        if self.total_amount < 0:
            errors.append("total_amount لا يمكن أن يكون سالباً")
        return errors

    def to_dict(self) -> dict:
        """يحوّل لـ dict للحفظ في قاعدة البيانات"""
        return {
            "channel": self.channel,
            "channel_reservation_id": self.channel_reservation_id,
            "guest_name": self.guest_name,
            "guest_phone": self.guest_phone,
            "guest_email": self.guest_email,
            "guest_nationality": self.guest_nationality,
            "room_number": self.room_number,
            "room_type": self.room_type,
            "check_in": str(self.check_in) if self.check_in else None,
            "check_out": str(self.check_out) if self.check_out else None,
            "adults": self.adults,
            "children": self.children,
            "total_amount": self.total_amount,
            "currency": self.currency,
            "payment_status": self.payment_status,
            "commission": self.commission,
            "net_amount": self.net_amount,
            "special_requests": self.special_requests,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UnifiedReservation":
        """ينشئ من dict"""
        from datetime import date as date_type

        check_in = data.get("check_in")
        check_out = data.get("check_out")

        if isinstance(check_in, str) and check_in:
            try:
                check_in = date_type.fromisoformat(check_in[:10])
            except ValueError:
                check_in = None

        if isinstance(check_out, str) and check_out:
            try:
                check_out = date_type.fromisoformat(check_out[:10])
            except ValueError:
                check_out = None

        return cls(
            channel=data.get("channel", "direct"),
            channel_reservation_id=data.get("channel_reservation_id", ""),
            guest_name=data.get("guest_name", ""),
            guest_phone=data.get("guest_phone", ""),
            guest_email=data.get("guest_email", ""),
            guest_nationality=data.get("guest_nationality", ""),
            room_number=data.get("room_number", ""),
            room_type=data.get("room_type", ""),
            check_in=check_in,
            check_out=check_out,
            adults=int(data.get("adults", 1)),
            children=int(data.get("children", 0)),
            total_amount=float(data.get("total_amount", 0)),
            currency=data.get("currency", "SAR"),
            payment_status=data.get("payment_status", "pending"),
            commission=float(data.get("commission", 0)),
            net_amount=float(data.get("net_amount", 0)),
            special_requests=data.get("special_requests", ""),
            raw_data=data.get("raw_data", {}),
        )


@dataclass
class PricingRules:
    """قواعد التسعير التي يضبطها المالك"""

    # الحدود
    min_price: float            # لا ينزل السعر تحته أبداً
    max_price: float            # لا يرتفع فوقه أبداً
    base_price: float           # السعر الافتراضي (عند إشغال 50-70%)

    # تفعيل العوامل
    use_occupancy: bool = True
    use_lead_time: bool = True
    use_day_of_week: bool = True
    use_seasons: bool = True

    # حد التغيير في دورة واحدة
    max_change_percent: float = 20.0    # لا يتغير السعر أكثر من 20% دفعة واحدة

    # تقريب السعر
    round_to: float = 5.0               # يُقرَّب لأقرب 5 ريالات

    def validate(self) -> list:
        errors = []
        if self.base_price <= 0:
            errors.append("base_price يجب أن يكون أكبر من 0")
        if self.min_price <= 0:
            errors.append("min_price يجب أن يكون أكبر من 0")
        if self.max_price <= self.min_price:
            errors.append("max_price يجب أن يكون أكبر من min_price")
        if not (self.min_price <= self.base_price <= self.max_price):
            errors.append("base_price يجب أن يكون بين min_price و max_price")
        if self.max_change_percent <= 0 or self.max_change_percent > 100:
            errors.append("max_change_percent يجب أن يكون بين 1 و 100")
        return errors


@dataclass
class PricingDecision:
    """نتيجة قرار التسعير مع الشرح الكامل"""

    final_price: float
    base_price: float

    # العوامل المطبقة
    occupancy_factor: float = 1.0
    lead_time_factor: float = 1.0
    day_of_week_factor: float = 1.0
    season_factor: float = 1.0

    # الشرح للمالك
    reason: str = ""                # "إشغال 82% + عطلة نهاية الأسبوع"
    confidence: str = "medium"     # "high" | "medium" | "low"

    # هل تغيّر السعر؟
    price_changed: bool = False
    previous_price: float = 0.0

    # تفاصيل إضافية
    raw_calculated: float = 0.0    # السعر قبل التقريب والحد
    was_capped: bool = False        # هل طُبّق حد max_change_percent؟

    def to_dict(self) -> dict:
        return {
            "final_price": self.final_price,
            "base_price": self.base_price,
            "occupancy_factor": self.occupancy_factor,
            "lead_time_factor": self.lead_time_factor,
            "day_of_week_factor": self.day_of_week_factor,
            "season_factor": self.season_factor,
            "reason": self.reason,
            "confidence": self.confidence,
            "price_changed": self.price_changed,
            "previous_price": self.previous_price,
            "was_capped": self.was_capped,
        }
