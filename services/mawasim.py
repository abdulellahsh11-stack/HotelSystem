"""
services/channels/mawasim.py
تكامل مع موزن (Mawasim) — منصة سعودية للحجز.

الواقع الحالي لـ API موزن:
- موزن لا توفر REST API عام للتكامل الخارجي حتى الآن
- التكامل المتاح: iCal export/import
- الخطة: iCal sync (مرحلة 1) + انتظار API رسمي (مرحلة 2)

استراتيجية المرحلة 1:
1. موزن يوفر رابط iCal لكل منشأة
2. نقرأ هذا الرابط كل 30 دقيقة
3. نحوّل الحجوزات القادمة لـ UnifiedReservation
4. نكتشف الحجوزات الجديدة والملغية بمقارنة مع آخر قراءة
"""

import urllib.request
import urllib.error
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import Optional

from services.base_channel import BaseChannel, ChannelResult


@dataclass
class MawasimConfig:
    """إعدادات التكامل مع موزن"""
    ical_url: str = ""              # رابط iCal من لوحة موزن
    property_id: str = ""           # رقم المنشأة في موزن
    api_key: str = ""               # للمستقبل — عند توفر REST API
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "MawasimConfig":
        return cls(
            ical_url=os.environ.get("MAWASIM_ICAL_URL", ""),
            property_id=os.environ.get("MAWASIM_PROPERTY_ID", ""),
            api_key=os.environ.get("MAWASIM_API_KEY", ""),
        )

    def is_valid(self) -> bool:
        return bool(self.ical_url) or bool(self.api_key)


class ICalParser:
    """
    يحلل ملفات iCal (.ics) ويستخرج الحجوزات.
    يستخدم stdlib فقط — لا icalendar library.
    """

    def parse(self, ical_text: str) -> list:
        """
        يحلل iCal text ويُعيد قائمة events كـ dicts.
        كل event: {uid, summary, dtstart, dtend, description, status}
        """
        events = []
        current = {}
        in_vevent = False
        lines = self._unfold_lines(ical_text.splitlines())

        for line in lines:
            if line.strip() == "BEGIN:VEVENT":
                in_vevent = True
                current = {}
                continue
            if line.strip() == "END:VEVENT":
                if current:
                    events.append(current)
                in_vevent = False
                current = {}
                continue

            if not in_vevent:
                continue

            # تحليل السطر: KEY;params:VALUE أو KEY:VALUE
            if ":" not in line:
                continue

            colon_idx = line.index(":")
            key_part = line[:colon_idx].strip()
            value = line[colon_idx + 1:].strip()

            # تجاهل الـ params (مثل DTSTART;TZID=...)
            key = key_part.split(";")[0].upper()

            if key == "UID":
                current["uid"] = value
            elif key == "SUMMARY":
                current["summary"] = self._unescape(value)
            elif key == "DTSTART":
                current["dtstart"] = self._parse_date(value)
            elif key == "DTEND":
                current["dtend"] = self._parse_date(value)
            elif key == "DESCRIPTION":
                current["description"] = self._unescape(value)
            elif key == "STATUS":
                current["status"] = value.upper()
            elif key == "ORGANIZER":
                # قد يحتوي على بريد إلكتروني
                current["organizer"] = value.replace("MAILTO:", "")
            elif key == "ATTENDEE":
                attendees = current.get("attendees", [])
                attendees.append(value.replace("MAILTO:", ""))
                current["attendees"] = attendees

        return events

    def _unfold_lines(self, lines: list) -> list:
        """
        iCal يطوي الأسطر الطويلة بمسافة في البداية.
        نجمعها في سطر واحد.
        """
        result = []
        for line in lines:
            if line.startswith((" ", "\t")) and result:
                result[-1] += line[1:]
            else:
                result.append(line)
        return result

    def _parse_date(self, value: str) -> Optional[date]:
        """يحوّل DTSTART/DTEND قيمة لـ date"""
        value = value.strip()
        # صيغة: 20260601 أو 20260601T000000Z أو 20260601T000000
        try:
            if "T" in value:
                dt = datetime.strptime(value[:15].replace("Z", ""), "%Y%m%dT%H%M%S")
                return dt.date()
            else:
                return datetime.strptime(value[:8], "%Y%m%d").date()
        except ValueError:
            return None

    def _unescape(self, text: str) -> str:
        """يُعالج escape sequences في iCal"""
        return (
            text.replace("\\n", "\n")
                .replace("\\,", ",")
                .replace("\\;", ";")
                .replace("\\\\", "\\")
        )

    def events_to_reservations(self, events: list) -> list:
        """
        يحوّل iCal events لـ UnifiedReservation dicts.
        موزن يضع اسم النزيل في SUMMARY والتفاصيل في DESCRIPTION.
        """
        reservations = []
        for ev in events:
            # تجاهل المحجوزات الملغية
            if ev.get("status") == "CANCELLED":
                continue

            uid = ev.get("uid", "")
            if not uid:
                continue

            dtstart = ev.get("dtstart")
            dtend = ev.get("dtend")
            if not dtstart or not dtend:
                continue

            # اسم النزيل من SUMMARY (موزن يضعه هنا)
            summary = ev.get("summary", "")
            guest_name = summary if summary else "ضيف موزن"

            # استخراج تفاصيل من DESCRIPTION إن وُجدت
            desc = ev.get("description", "")
            phone = self._extract_phone(desc)
            email = next(iter(ev.get("attendees", [])), "")

            reservations.append({
                "channel": "mawasim",
                "channel_reservation_id": uid,
                "guest_name": guest_name,
                "guest_phone": phone,
                "guest_email": email,
                "check_in": str(dtstart),
                "check_out": str(dtend),
                "adults": 1,
                "children": 0,
                "total_amount": 0.0,    # موزن لا يرسل المبلغ في iCal
                "currency": "SAR",
                "payment_status": "pending",
                "commission": 0.0,
                "net_amount": 0.0,
                "special_requests": desc[:200] if desc else "",
            })

        return reservations

    def _extract_phone(self, text: str) -> str:
        """يستخرج رقم الهاتف من النص"""
        import re
        # أنماط الجوال السعودي
        patterns = [
            r'05\d{8}',
            r'\+9665\d{8}',
            r'009665\d{8}',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group()
        return ""


class MawasimChannel(BaseChannel):
    """
    قناة موزن — المرحلة 1: iCal sync.
    المرحلة 2: REST API (عند توفره من موزن).
    """

    def __init__(self, config: MawasimConfig):
        self.config = config
        self.ical_parser = ICalParser()
        self._last_known_uids: set = set()  # لاكتشاف الحجوزات الجديدة

    @property
    def channel_name(self) -> str:
        return "mawasim"

    def is_configured(self) -> bool:
        return self.config.is_valid()

    def test_connection(self) -> ChannelResult:
        """يختبر الاتصال بموزن عبر iCal"""
        if not self.is_configured():
            return ChannelResult(
                success=False,
                message="رابط iCal موزن غير مُضاف — أضف MAWASIM_ICAL_URL في Railway Variables",
                error_code="NOT_CONFIGURED"
            )

        ical_text, error = self._fetch_ical()
        if error:
            return ChannelResult(
                success=False,
                message=f"فشل جلب iCal موزن: {error}",
                error_code="CONNECTION_FAILED"
            )

        events = self.ical_parser.parse(ical_text)
        return ChannelResult(
            success=True,
            message=f"متصل بـ موزن — {len(events)} حجز في iCal",
            data={"events_count": len(events), "property_id": self.config.property_id}
        )

    def fetch_new_reservations(self, date_from: Optional[str] = None) -> list:
        """يجلب الحجوزات الجديدة من iCal موزن"""
        if not self.is_configured():
            return []

        ical_text, error = self._fetch_ical()
        if error or not ical_text:
            return []

        events = self.ical_parser.parse(ical_text)
        all_reservations = self.ical_parser.events_to_reservations(events)

        # اكتشاف الحجوزات الجديدة فقط
        new_reservations = []
        current_uids = set()

        for res in all_reservations:
            uid = res.get("channel_reservation_id", "")
            current_uids.add(uid)
            if uid and uid not in self._last_known_uids:
                new_reservations.append(res)

        # تحديث الـ UIDs المعروفة
        self._last_known_uids = current_uids

        return new_reservations

    def update_availability(
        self,
        room_type_id: str,
        date_from: str,
        date_to: str,
        available_rooms: int
    ) -> ChannelResult:
        """
        موزن لا يدعم Push للتوفر في المرحلة الحالية.
        iCal هو read-only — النزلاء يحجزون على موزن مباشرة.
        """
        return ChannelResult(
            success=True,
            message="موزن (iCal mode): تحديث التوفر يدوي عبر لوحة موزن",
            error_code="MANUAL_REQUIRED"
        )

    def update_rate(
        self,
        room_type_id: str,
        date_from: str,
        date_to: str,
        rate: float,
        currency: str = "SAR"
    ) -> ChannelResult:
        """موزن لا يدعم Push للأسعار في المرحلة الحالية"""
        return ChannelResult(
            success=True,
            message="موزن (iCal mode): تحديث الأسعار يدوي عبر لوحة موزن",
            error_code="MANUAL_REQUIRED"
        )

    def confirm_reservation(self, reservation_id: str) -> ChannelResult:
        """iCal لا يحتاج تأكيد — الحجز يظهر تلقائياً"""
        return ChannelResult(
            success=True,
            message="iCal: لا يلزم تأكيد",
        )

    def cancel_reservation(self, reservation_id: str, reason: str = "") -> ChannelResult:
        """الإلغاء يتم في لوحة موزن يدوياً"""
        return ChannelResult(
            success=False,
            message="إلغاء حجوزات موزن يتم عبر لوحة موزن يدوياً",
            error_code="NOT_SUPPORTED"
        )

    # ─── Internal ─────────────────────────────────────────────

    def _fetch_ical(self) -> tuple:
        """
        يجلب ملف iCal من موزن.
        يُعيد (ical_text, error_message)
        """
        try:
            req = urllib.request.Request(
                self.config.ical_url,
                headers={"User-Agent": "dheuof/3.0 MawasimConnector"}
            )
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                content_bytes = resp.read()
                # iCal يكون UTF-8 عادةً
                try:
                    return content_bytes.decode("utf-8"), None
                except UnicodeDecodeError:
                    return content_bytes.decode("latin-1"), None

        except urllib.error.HTTPError as e:
            return None, f"HTTP {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            return None, f"URL Error: {e.reason}"
        except TimeoutError:
            return None, "Timeout: لم يرد موزن خلال 30 ثانية"
        except Exception as e:
            return None, str(e)
