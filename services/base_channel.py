"""
services/channels/base_channel.py
واجهة موحدة لكل قنوات الحجز.
أي قناة جديدة (Airbnb · Expedia · Agoda) تطبّق هذه الواجهة.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChannelResult:
    """نتيجة موحدة من أي عملية قناة"""
    success: bool
    message: str = ""
    data: dict = field(default_factory=dict)
    error_code: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "error_code": self.error_code,
        }


class BaseChannel(ABC):
    """
    واجهة موحدة لكل قنوات الحجز.
    كل قناة تُطبّق هذه الـ abstract methods.
    """

    @abstractmethod
    def update_availability(
        self,
        room_type_id: str,
        date_from: str,
        date_to: str,
        available_rooms: int
    ) -> ChannelResult:
        """
        يحدّث توفر الغرف في القناة.
        يُستدعى عند: حجز جديد · Check-out · إلغاء · صيانة.
        """

    @abstractmethod
    def update_rate(
        self,
        room_type_id: str,
        date_from: str,
        date_to: str,
        rate: float,
        currency: str = "SAR"
    ) -> ChannelResult:
        """يحدّث السعر في القناة — يُستدعى من Dynamic Pricing"""

    @abstractmethod
    def fetch_new_reservations(self, date_from: Optional[str] = None) -> list:
        """
        يجلب الحجوزات الجديدة من القناة.
        يُشغَّل كل 15 دقيقة من CronManager.
        يُعيد قائمة UnifiedReservation dicts.
        """

    @abstractmethod
    def confirm_reservation(self, reservation_id: str) -> ChannelResult:
        """يؤكّد للقناة أننا استلمنا الحجز"""

    @abstractmethod
    def cancel_reservation(self, reservation_id: str, reason: str = "") -> ChannelResult:
        """يُلغي حجزاً في القناة"""

    @abstractmethod
    def is_configured(self) -> bool:
        """يتحقق من اكتمال الإعدادات — إذا False لا تُحاول المزامنة"""

    @abstractmethod
    def test_connection(self) -> ChannelResult:
        """
        يختبر الاتصال ويُعيد:
        ChannelResult(success=True/False, message=..., data={hotel_name, rooms_count, ...})
        """

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """اسم القناة: booking.com · mawasim · airbnb"""

    # ─── Helper Methods مشتركة ────────────────────────────────

    def _safe_call(self, func, *args, **kwargs) -> ChannelResult:
        """
        يُنفّذ أي دالة بأمان مع timeout.
        يُعيد ChannelResult(success=False) عند أي خطأ.
        """
        try:
            return func(*args, **kwargs)
        except TimeoutError:
            return ChannelResult(
                success=False,
                message=f"انتهى وقت الاتصال بـ {self.channel_name}",
                error_code="TIMEOUT"
            )
        except Exception as e:
            return ChannelResult(
                success=False,
                message=str(e),
                error_code="UNKNOWN_ERROR"
            )
