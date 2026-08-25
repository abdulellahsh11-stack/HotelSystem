"""
utils/xml_parser.py
محلل XML لـ Booking.com OTA 2003 format
stdlib فقط — لا lxml
"""

import xml.etree.ElementTree as ET
from datetime import datetime


# Namespaces المستخدمة في Booking.com
OTA_NS = "http://www.opentravel.org/OTA/2003/05"
NS = {"ota": OTA_NS}


class BookingXMLParser:
    """
    يحوّل XML responses من Booking.com إلى Python dicts.
    يحوّل Python dicts إلى XML requests لـ Booking.com.
    متوافق مع OTA 2003 format.
    """

    # ─── Parse ────────────────────────────────────────────────

    def parse_reservation(self, xml_string: str) -> dict:
        """
        يحوّل XML حجز (OTA_HotelResNotifRQ) لـ dict
        يتوافق مع UnifiedReservation.
        """
        try:
            root = ET.fromstring(xml_string.strip())
        except ET.ParseError as e:
            return {"error": f"XML parse error: {e}", "raw": xml_string}

        # دعم namespace أو بدونه
        def find(node, path):
            # جرب مع namespace أولاً
            result = node.find(path, NS)
            if result is None:
                # جرب بدون namespace (Booking.com أحياناً يرسل بدونه)
                path_no_ns = path.replace("ota:", "")
                result = node.find(path_no_ns)
            return result

        def findtext(node, path, default=""):
            el = find(node, path)
            return (el.text or default).strip() if el is not None else default

        def findattr(node, path, attr, default=""):
            el = find(node, path)
            return el.get(attr, default) if el is not None else default

        # جذر الحجز — قد يكون مباشراً أو داخل HotelReservations
        res_node = (
            find(root, ".//ota:HotelReservation")
            or find(root, ".//HotelReservation")
            or root
        )

        # رقم الحجز في Booking.com
        channel_res_id = (
            findattr(res_node, "ota:UniqueID", "ID")
            or findattr(res_node, "UniqueID", "ID")
            or ""
        )
        if not channel_res_id:
            # محاولة من ResGlobalInfo
            channel_res_id = findattr(
                res_node, ".//ota:ResGlobalInfo/ota:HotelReservationIDs/ota:HotelReservationID",
                "ResID_Value", ""
            )

        # بيانات النزيل
        profile = (
            find(res_node, ".//ota:Profile")
            or find(res_node, ".//Profile")
        )
        given_name = ""
        family_name = ""
        phone = ""
        email = ""
        if profile is not None:
            given_name = findtext(profile, ".//ota:GivenName") or findtext(profile, ".//GivenName")
            family_name = findtext(profile, ".//ota:Surname") or findtext(profile, ".//Surname")
            phone = findtext(profile, ".//ota:PhoneNumber") or findtext(profile, ".//PhoneNumber")
            email = findtext(profile, ".//ota:Email") or findtext(profile, ".//Email")

        guest_name = f"{given_name} {family_name}".strip() or "ضيف Booking.com"

        # بيانات الغرفة والتواريخ
        room_stay = find(res_node, ".//ota:RoomStay") or find(res_node, ".//RoomStay")
        check_in = ""
        check_out = ""
        room_type = ""
        adults = 1
        children = 0
        total_amount = 0.0
        currency = "SAR"
        commission = 0.0

        if room_stay is not None:
            # التواريخ
            time_span = find(room_stay, "ota:TimeSpan") or find(room_stay, "TimeSpan")
            if time_span is not None:
                check_in = time_span.get("Start", "")
                check_out = time_span.get("End", "")

            # نوع الغرفة
            room_type_node = (
                find(room_stay, ".//ota:RoomTypes/ota:RoomType")
                or find(room_stay, ".//RoomTypes/RoomType")
            )
            if room_type_node is not None:
                room_type = room_type_node.get("RoomTypeCode", "")

            # عدد الأشخاص
            guest_count = find(room_stay, ".//ota:GuestCount") or find(room_stay, ".//GuestCount")
            if guest_count is not None:
                age_code = guest_count.get("AgeQualifyingCode", "10")
                count = int(guest_count.get("Count", "1"))
                if age_code == "10":
                    adults = count
                elif age_code == "8":
                    children = count

            # المبلغ
            total_node = (
                find(room_stay, ".//ota:Total")
                or find(room_stay, ".//Total")
            )
            if total_node is not None:
                try:
                    total_amount = float(total_node.get("AmountAfterTax", 0))
                    currency = total_node.get("CurrencyCode", "SAR")
                except (ValueError, TypeError):
                    total_amount = 0.0

            # العمولة (Booking.com يرسلها أحياناً)
            commission_node = (
                find(room_stay, ".//ota:Commission")
                or find(room_stay, ".//Commission")
            )
            if commission_node is not None:
                try:
                    commission = float(commission_node.get("Percent", 0)) / 100 * total_amount
                except (ValueError, TypeError):
                    commission = 0.0

        net_amount = total_amount - commission

        # طلبات خاصة
        special_requests = findtext(res_node, ".//ota:SpecialRequest/ota:Text")

        return {
            "channel": "booking.com",
            "channel_reservation_id": channel_res_id,
            "guest_name": guest_name,
            "guest_phone": phone,
            "guest_email": email,
            "guest_nationality": "",
            "room_type": room_type,
            "check_in": check_in,
            "check_out": check_out,
            "adults": adults,
            "children": children,
            "total_amount": total_amount,
            "currency": currency,
            "commission": round(commission, 2),
            "net_amount": round(net_amount, 2),
            "payment_status": "pending",
            "special_requests": special_requests,
        }

    def parse_availability_response(self, xml_string: str) -> dict:
        """يحلل رد Booking.com على طلب تحديث التوفر"""
        try:
            root = ET.fromstring(xml_string.strip())
        except ET.ParseError as e:
            return {"success": False, "error": str(e)}

        # Booking.com يرد بـ OTA_HotelAvailNotifRS
        errors = root.findall(".//Error") + root.findall(f".//{{{OTA_NS}}}Error")
        if errors:
            return {
                "success": False,
                "error": errors[0].get("ShortText", "Unknown error"),
                "code": errors[0].get("Code", ""),
            }

        success_el = root.find("Success") or root.find(f"{{{OTA_NS}}}Success")
        return {"success": success_el is not None}

    def parse_rate_response(self, xml_string: str) -> dict:
        """يحلل رد Booking.com على طلب تحديث السعر"""
        return self.parse_availability_response(xml_string)  # نفس الصيغة

    def parse_reservations_list(self, xml_string: str) -> list:
        """يحلل قائمة الحجوزات من Booking.com pull"""
        try:
            root = ET.fromstring(xml_string.strip())
        except ET.ParseError:
            return []

        reservations = []
        for res_node in (
            root.findall(".//HotelReservation")
            + root.findall(f".//{{{OTA_NS}}}HotelReservation")
        ):
            # نبني XML مؤقت لكل حجز ونحلله
            res_xml = ET.tostring(res_node, encoding="unicode")
            parsed = self.parse_reservation(res_xml)
            if "error" not in parsed:
                reservations.append(parsed)

        return reservations

    # ─── Build Requests ───────────────────────────────────────

    def build_availability_request(self, params: dict) -> str:
        """
        يبني OTA_HotelAvailNotifRQ XML
        params: {hotel_id, room_type_id, date_from, date_to, available_rooms}
        """
        hotel_id = params["hotel_id"]
        room_type_id = params["room_type_id"]
        date_from = params["date_from"]
        date_to = params["date_to"]
        available = int(params.get("available_rooms", 0))
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<OTA_HotelAvailNotifRQ xmlns="http://www.opentravel.org/OTA/2003/05"
    Version="1.0"
    TimeStamp="{timestamp}"
    EchoToken="dheuof_{hotel_id}_{timestamp[:10]}">
  <AvailStatusMessages HotelCode="{hotel_id}">
    <AvailStatusMessage>
      <StatusApplicationControl
          Start="{date_from}"
          End="{date_to}"
          InvTypeCode="{room_type_id}"
          IsRoom="true"/>
      <RestrictionStatus Status="Open"/>
      <InvCountList>
        <InvCount CountType="2" Count="{available}"/>
      </InvCountList>
    </AvailStatusMessage>
  </AvailStatusMessages>
</OTA_HotelAvailNotifRQ>"""

    def build_rate_request(self, params: dict) -> str:
        """
        يبني OTA_HotelRateAmountNotifRQ XML
        params: {hotel_id, room_type_id, rate_plan_id, date_from, date_to, rate, currency}
        """
        hotel_id = params["hotel_id"]
        room_type_id = params["room_type_id"]
        rate_plan_id = params.get("rate_plan_id", "BAR")
        date_from = params["date_from"]
        date_to = params["date_to"]
        rate = float(params["rate"])
        currency = params.get("currency", "SAR")
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<OTA_HotelRateAmountNotifRQ xmlns="http://www.opentravel.org/OTA/2003/05"
    Version="1.0"
    TimeStamp="{timestamp}"
    EchoToken="dheuof_rate_{hotel_id}_{timestamp[:10]}">
  <RateAmountMessages HotelCode="{hotel_id}">
    <RateAmountMessage>
      <StatusApplicationControl
          Start="{date_from}"
          End="{date_to}"
          InvTypeCode="{room_type_id}"
          RatePlanCode="{rate_plan_id}"/>
      <Rates>
        <Rate>
          <BaseByGuestAmts>
            <BaseByGuestAmt AmountBeforeTax="{rate:.2f}"
                            CurrencyCode="{currency}"
                            NumberOfGuests="1"/>
          </BaseByGuestAmts>
        </Rate>
      </Rates>
    </RateAmountMessage>
  </RateAmountMessages>
</OTA_HotelRateAmountNotifRQ>"""

    def build_reservation_pull_request(self, params: dict) -> str:
        """
        يبني OTA_ReadRQ لجلب الحجوزات الجديدة
        params: {hotel_id, date_from (optional)}
        """
        hotel_id = params["hotel_id"]
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        date_from = params.get("date_from", timestamp[:10])

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<OTA_ReadRQ xmlns="http://www.opentravel.org/OTA/2003/05"
    Version="1.0"
    TimeStamp="{timestamp}"
    EchoToken="dheuof_pull_{hotel_id}">
  <ReadRequests>
    <HotelReadRequest HotelCode="{hotel_id}">
      <SelectionCriteria Start="{date_from}" End="{timestamp[:10]}"
                         SelectionType="Creation"/>
    </HotelReadRequest>
  </ReadRequests>
</OTA_ReadRQ>"""

    def build_confirm_request(self, params: dict) -> str:
        """يبني طلب تأكيد استلام الحجز"""
        hotel_id = params["hotel_id"]
        reservation_id = params["reservation_id"]
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<OTA_HotelResModifyRQ xmlns="http://www.opentravel.org/OTA/2003/05"
    Version="1.0"
    TimeStamp="{timestamp}">
  <HotelResModifies>
    <HotelResModify>
      <UniqueID Type="14" ID="{reservation_id}"/>
      <ResGlobalInfo>
        <HotelReservationIDs>
          <HotelReservationID ResID_Type="14" ResID_Value="{reservation_id}"
                              ResID_Source="{hotel_id}"/>
        </HotelReservationIDs>
      </ResGlobalInfo>
    </HotelResModify>
  </HotelResModifies>
</OTA_HotelResModifyRQ>"""

    def detect_notification_type(self, xml_string: str) -> str:
        """
        يحدد نوع الإشعار الوارد من Booking.com webhook:
        NewReservation | ModifiedReservation | CancelledReservation | CreditCardDetails | Unknown
        """
        try:
            root = ET.fromstring(xml_string.strip())
        except ET.ParseError:
            return "Unknown"

        tag = root.tag.replace(f"{{{OTA_NS}}}", "")

        if "HotelResNotif" in tag:
            # فحص نوع العملية
            res_status = root.get("ResStatus", "")
            if res_status == "Commit":
                return "NewReservation"
            elif res_status == "Modify":
                return "ModifiedReservation"
            elif res_status == "Cancel":
                return "CancelledReservation"
            return "NewReservation"  # افتراضي

        if "CreditCard" in tag or "PaymentCard" in tag:
            return "CreditCardDetails"

        # فحص محتوى الـ tag
        if "Cancel" in tag:
            return "CancelledReservation"
        if "Modify" in tag:
            return "ModifiedReservation"

        return "NewReservation"
