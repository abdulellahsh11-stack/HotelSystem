"""
services/channels/booking_com.py
تكامل مع Booking.com Connectivity API v3 (XML/OTA 2003).

وثائق: https://connect.booking.com/
نوع الاتصال: Basic Auth + XML over HTTPS
Booking.com يستخدم XML API في الـ supply side (ليس JSON).
"""

import urllib.request
import urllib.error
import base64
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from services.base_channel import BaseChannel, ChannelResult
from utils.xml_parser import BookingXMLParser


@dataclass
class BookingComConfig:
    """إعدادات الاتصال بـ Booking.com"""
    hotel_id: str
    api_key: str            # username:password بصيغة base64 أو API key
    username: str = ""      # من Connectivity Partner account
    password: str = ""
    timeout: int = 30       # ثانية

    @classmethod
    def from_env(cls) -> "BookingComConfig":
        """يقرأ الإعدادات من Environment Variables"""
        return cls(
            hotel_id=os.environ.get("BOOKING_COM_HOTEL_ID", ""),
            api_key=os.environ.get("BOOKING_COM_API_KEY", ""),
            username=os.environ.get("BOOKING_COM_USERNAME", ""),
            password=os.environ.get("BOOKING_COM_PASSWORD", ""),
        )

    def is_valid(self) -> bool:
        return bool(self.hotel_id) and (
            bool(self.api_key) or (bool(self.username) and bool(self.password))
        )


class BookingComChannel(BaseChannel):
    """
    تكامل مع Booking.com Connectivity XML API.

    متطلبات التفعيل:
    1. التسجيل كـ Connectivity Partner على connect.booking.com
    2. الحصول على Username/Password أو API Key
    3. إعداد Webhook URL في لوحة Booking.com:
       POST https://your-domain.com/api/channels/booking-com/webhook
    4. ربط الغرف (Room Mapping) من لوحة التحكم
    """

    BASE_URL = "https://supply-xml.booking.com/hotels/xml"
    # ملاحظة: sandbox للاختبار
    SANDBOX_URL = "https://supply-xml.booking.com/hotels/xml"

    def __init__(self, config: BookingComConfig):
        self.config = config
        self.parser = BookingXMLParser()
        self._auth_header = self._build_auth_header()

    @property
    def channel_name(self) -> str:
        return "booking.com"

    def _build_auth_header(self) -> str:
        """يبني Authorization header"""
        if self.config.username and self.config.password:
            creds = f"{self.config.username}:{self.config.password}"
            encoded = base64.b64encode(creds.encode()).decode()
            return f"Basic {encoded}"
        elif self.config.api_key:
            # بعض Connectivity Partners يستخدمون API Key مباشرة
            return f"Basic {self.config.api_key}"
        return ""

    def _post_xml(self, xml_body: str, endpoint: str = "") -> tuple:
        """
        يرسل XML request لـ Booking.com.
        يُعيد (response_text, error_message)
        """
        url = self.BASE_URL + (f"/{endpoint}" if endpoint else "")

        try:
            data = xml_body.encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                method="POST",
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "Authorization": self._auth_header,
                    "User-Agent": "dheuof/3.0 BookingConnector",
                    "Content-Length": str(len(data)),
                }
            )

            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                return resp.read().decode("utf-8"), None

        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")
            except Exception:
                pass
            return None, f"HTTP {e.code}: {e.reason} — {body[:200]}"

        except urllib.error.URLError as e:
            return None, f"Connection error: {e.reason}"

        except TimeoutError:
            return None, "Timeout: لم يرد Booking.com خلال 30 ثانية"

        except Exception as e:
            return None, f"Unexpected error: {e}"

    # ─── BaseChannel Implementation ───────────────────────────

    def is_configured(self) -> bool:
        return self.config.is_valid()

    def test_connection(self) -> ChannelResult:
        """يختبر الاتصال بـ Booking.com"""
        if not self.is_configured():
            return ChannelResult(
                success=False,
                message="إعدادات Booking.com غير مكتملة — أضف BOOKING_COM_HOTEL_ID و BOOKING_COM_API_KEY",
                error_code="NOT_CONFIGURED"
            )

        # نرسل طلب availability بسيط للاختبار
        test_xml = self.parser.build_availability_request({
            "hotel_id": self.config.hotel_id,
            "room_type_id": "TEST",
            "date_from": datetime.now().strftime("%Y-%m-%d"),
            "date_to": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "available_rooms": 0,
        })

        response_text, error = self._post_xml(test_xml)

        if error:
            # تحقق: قد يكون خطأ 401 يعني credentials خاطئة
            if "401" in str(error):
                return ChannelResult(
                    success=False,
                    message="فشل المصادقة — تحقق من API credentials",
                    error_code="AUTH_FAILED"
                )
            if "404" in str(error):
                return ChannelResult(
                    success=False,
                    message=f"Hotel ID غير صحيح: {self.config.hotel_id}",
                    error_code="HOTEL_NOT_FOUND"
                )
            return ChannelResult(success=False, message=error, error_code="CONNECTION_FAILED")

        return ChannelResult(
            success=True,
            message=f"متصل بـ Booking.com — Hotel ID: {self.config.hotel_id}",
            data={"hotel_id": self.config.hotel_id}
        )

    def update_availability(
        self,
        room_type_id: str,
        date_from: str,
        date_to: str,
        available_rooms: int
    ) -> ChannelResult:
        """يحدّث توفر الغرف في Booking.com"""
        if not self.is_configured():
            return ChannelResult(success=False, message="Booking.com غير مُفعَّل", error_code="NOT_CONFIGURED")

        xml_body = self.parser.build_availability_request({
            "hotel_id": self.config.hotel_id,
            "room_type_id": room_type_id,
            "date_from": date_from,
            "date_to": date_to,
            "available_rooms": available_rooms,
        })

        response_text, error = self._post_xml(xml_body)
        if error:
            return ChannelResult(success=False, message=error, error_code="API_ERROR")

        result = self.parser.parse_availability_response(response_text)
        return ChannelResult(
            success=result.get("success", False),
            message=result.get("error", "تم تحديث التوفر"),
            data={"room_type_id": room_type_id, "available": available_rooms}
        )

    def update_rate(
        self,
        room_type_id: str,
        date_from: str,
        date_to: str,
        rate: float,
        currency: str = "SAR"
    ) -> ChannelResult:
        """يحدّث السعر في Booking.com"""
        if not self.is_configured():
            return ChannelResult(success=False, message="Booking.com غير مُفعَّل", error_code="NOT_CONFIGURED")

        xml_body = self.parser.build_rate_request({
            "hotel_id": self.config.hotel_id,
            "room_type_id": room_type_id,
            "date_from": date_from,
            "date_to": date_to,
            "rate": rate,
            "currency": currency,
        })

        response_text, error = self._post_xml(xml_body)
        if error:
            return ChannelResult(success=False, message=error, error_code="API_ERROR")

        result = self.parser.parse_rate_response(response_text)
        return ChannelResult(
            success=result.get("success", False),
            message=result.get("error", "تم تحديث السعر"),
            data={"room_type_id": room_type_id, "rate": rate, "currency": currency}
        )

    def fetch_new_reservations(self, date_from: Optional[str] = None) -> list:
        """
        يجلب الحجوزات الجديدة من Booking.com.
        يُشغَّل كل 15 دقيقة من CronManager.
        """
        if not self.is_configured():
            return []

        if not date_from:
            # جلب آخر 24 ساعة افتراضياً
            date_from = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        xml_body = self.parser.build_reservation_pull_request({
            "hotel_id": self.config.hotel_id,
            "date_from": date_from,
        })

        response_text, error = self._post_xml(xml_body)
        if error or not response_text:
            return []

        return self.parser.parse_reservations_list(response_text)

    def confirm_reservation(self, reservation_id: str) -> ChannelResult:
        """يؤكّد لـ Booking.com أننا استلمنا الحجز"""
        if not self.is_configured():
            return ChannelResult(success=False, message="Booking.com غير مُفعَّل", error_code="NOT_CONFIGURED")

        xml_body = self.parser.build_confirm_request({
            "hotel_id": self.config.hotel_id,
            "reservation_id": reservation_id,
        })

        response_text, error = self._post_xml(xml_body)
        if error:
            return ChannelResult(success=False, message=error, error_code="API_ERROR")

        return ChannelResult(
            success=True,
            message=f"تم تأكيد الحجز {reservation_id}",
            data={"reservation_id": reservation_id}
        )

    def cancel_reservation(self, reservation_id: str, reason: str = "") -> ChannelResult:
        """يُلغي حجزاً — يستخدم نادراً"""
        # Booking.com لا يسمح عادةً بإلغاء من طرف الفندق عبر API
        # الإلغاء يتم عبر extranet يدوياً
        return ChannelResult(
            success=False,
            message="إلغاء الحجوزات يتم عبر Booking.com Extranet يدوياً",
            error_code="NOT_SUPPORTED"
        )

    # ─── Webhook Processing ───────────────────────────────────

    def process_webhook(self, xml_body: str, source_ip: str = "") -> dict:
        """
        يعالج إشعار webhook وارد من Booking.com.
        يُعيد dict يصف الإجراء المطلوب.

        Booking.com IPs: 62.183.80.0/24 (تحقق من الوثائق الرسمية)
        """
        # تحديد نوع الإشعار
        notification_type = self.parser.detect_notification_type(xml_body)

        if notification_type == "CreditCardDetails":
            # نتجاهل بيانات البطاقة — لا نحفظها
            return {"action": "ignore", "reason": "credit_card_details"}

        if notification_type == "Unknown":
            return {"action": "ignore", "reason": "unknown_notification_type"}

        # تحليل الحجز
        reservation_data = self.parser.parse_reservation(xml_body)

        if "error" in reservation_data:
            return {
                "action": "error",
                "reason": reservation_data["error"],
                "raw": xml_body[:500]
            }

        return {
            "action": notification_type,          # NewReservation · ModifiedReservation · CancelledReservation
            "reservation": reservation_data,
            "notification_type": notification_type,
        }

    def get_room_types(self) -> ChannelResult:
        """
        يجلب أنواع الغرف من Booking.com للـ Room Mapping UI.
        مفيد عند إعداد الربط لأول مرة.
        """
        if not self.is_configured():
            return ChannelResult(success=False, message="Booking.com غير مُفعَّل", error_code="NOT_CONFIGURED")

        # OTA_HotelDescriptiveInfoRQ
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        xml_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<OTA_HotelDescriptiveInfoRQ xmlns="http://www.opentravel.org/OTA/2003/05"
    Version="1.0" TimeStamp="{timestamp}">
  <HotelDescriptiveInfos>
    <HotelDescriptiveInfo HotelCode="{self.config.hotel_id}">
      <ContentInfos>
        <ContentInfo Name="Facility"/>
      </ContentInfos>
    </HotelDescriptiveInfo>
  </HotelDescriptiveInfos>
</OTA_HotelDescriptiveInfoRQ>"""

        response_text, error = self._post_xml(xml_body)
        if error:
            return ChannelResult(success=False, message=error, error_code="API_ERROR")

        # نُعيد النص الخام — يُحلَّل في route handler
        return ChannelResult(
            success=True,
            message="تم جلب بيانات الفندق",
            data={"raw_response": response_text}
        )
