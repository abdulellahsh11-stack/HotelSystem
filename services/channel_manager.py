"""
services/channels/channel_manager.py
يُدير كل قنوات الحجز في مكان واحد.

المبدأ: أي تغيير في التوفر أو السعر يصل لكل القنوات
المُفعَّلة في نفس الوقت (parallel threads).
يعمل كـ cron كل 15 دقيقة لجلب الحجوزات الجديدة.
"""

import threading
import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from services.base_channel import BaseChannel, ChannelResult

logger = logging.getLogger("channel_manager")


class ChannelManager:
    """
    يُدير كل قنوات الحجز.
    thread-safe: يستخدم قفل لمنع race conditions.
    """

    def __init__(self, db, whatsapp_service=None):
        self.db = db
        self.whatsapp = whatsapp_service
        self.channels: dict = {}            # name → BaseChannel
        self._lock = threading.Lock()
        self._enabled = True

    # ─── Channel Registration ─────────────────────────────────

    def register_channel(self, channel: BaseChannel) -> None:
        """يُسجّل قناة جديدة"""
        with self._lock:
            self.channels[channel.channel_name] = channel
            logger.info(f"Channel registered: {channel.channel_name}")

    def get_channel(self, name: str) -> Optional[BaseChannel]:
        return self.channels.get(name)

    def get_active_channels(self) -> dict:
        """يُعيد القنوات المُفعَّلة فقط"""
        return {
            name: ch for name, ch in self.channels.items()
            if ch.is_configured()
        }

    # ─── Push: Availability ───────────────────────────────────

    def push_availability_all(
        self,
        client_id: str,
        room_type_id: str,
        date_from: str,
        date_to: str,
        available_rooms: int
    ) -> dict:
        """
        يُرسل تحديث التوفر لكل القنوات المُفعَّلة بشكل parallel.
        يُعيد نتيجة كل قناة.
        لا يُوقف النظام إذا فشلت قناة.
        """
        results = {}
        threads = []
        results_lock = threading.Lock()

        active = self.get_active_channels()
        if not active:
            return {}

        def push(ch_name: str, ch: BaseChannel):
            try:
                result = ch.update_availability(
                    room_type_id, date_from, date_to, available_rooms
                )
                with results_lock:
                    results[ch_name] = result.to_dict()

                self._log_sync(
                    client_id, ch_name, "availability",
                    "success" if result.success else "failed",
                    message=result.message
                )
            except Exception as e:
                with results_lock:
                    results[ch_name] = {"success": False, "error": str(e)}
                self._log_sync(client_id, ch_name, "availability", "failed", message=str(e))
                logger.error(f"Channel {ch_name} availability push failed: {e}")

        for name, channel in active.items():
            t = threading.Thread(target=push, args=(name, channel), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=15)  # لا ينتظر أكثر من 15 ثانية لأي قناة

        return results

    def push_rate_all(
        self,
        client_id: str,
        room_type_id: str,
        date_from: str,
        date_to: str,
        rate: float,
        currency: str = "SAR"
    ) -> dict:
        """يُرسل تحديث السعر لكل القنوات بشكل parallel"""
        results = {}
        threads = []
        results_lock = threading.Lock()

        active = self.get_active_channels()
        if not active:
            return {}

        def push_rate(ch_name: str, ch: BaseChannel):
            try:
                result = ch.update_rate(room_type_id, date_from, date_to, rate, currency)
                with results_lock:
                    results[ch_name] = result.to_dict()
                self._log_sync(
                    client_id, ch_name, "rate",
                    "success" if result.success else "failed",
                    message=result.message
                )
            except Exception as e:
                with results_lock:
                    results[ch_name] = {"success": False, "error": str(e)}
                self._log_sync(client_id, ch_name, "rate", "failed", message=str(e))
                logger.error(f"Channel {ch_name} rate push failed: {e}")

        for name, channel in active.items():
            t = threading.Thread(target=push_rate, args=(name, channel), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=15)

        return results

    # ─── Pull: Reservations ───────────────────────────────────

    def pull_all_reservations(self, client_id: str) -> dict:
        """
        يجلب الحجوزات الجديدة من كل القنوات.
        يُشغَّل كل 15 دقيقة من CronManager.
        يُعيد: {channel_name: [reservations_processed]}
        """
        summary = {}
        active = self.get_active_channels()

        for name, channel in active.items():
            try:
                raw_reservations = channel.fetch_new_reservations()
                processed = []

                for raw in raw_reservations:
                    result = self._process_reservation(client_id, name, raw)
                    processed.append(result)

                summary[name] = {
                    "fetched": len(raw_reservations),
                    "processed": len([r for r in processed if r.get("success")]),
                    "errors": len([r for r in processed if not r.get("success")]),
                }

                self._log_sync(
                    client_id, name, "reservations", "success",
                    records=len(raw_reservations)
                )

            except Exception as e:
                summary[name] = {"error": str(e)}
                self._log_sync(client_id, name, "reservations", "failed", message=str(e))
                logger.error(f"Pull reservations from {name} failed: {e}")

        return summary

    def _process_reservation(
        self,
        client_id: str,
        channel_name: str,
        raw: dict
    ) -> dict:
        """
        يُعالج حجزاً واحداً من أي قناة:
        1. فحص الـ duplicate
        2. إنشاء/تحديث النزيل
        3. إنشاء الحجز
        4. تحديث التوفر في القنوات الأخرى
        5. إرسال إشعارات
        """
        channel_res_id = raw.get("channel_reservation_id", "")
        if not channel_res_id:
            return {"success": False, "reason": "no_reservation_id"}

        # 1. فحص duplicate
        if self._is_duplicate(channel_name, channel_res_id):
            return {
                "success": True,
                "action": "skipped_duplicate",
                "channel_reservation_id": channel_res_id
            }

        # 2. التحقق من الغرفة
        room_type = raw.get("room_type", "")
        room_mapping = self._get_room_mapping(client_id, channel_name, room_type)

        if not room_mapping and room_type:
            # الغرفة غير مربوطة — نُنبّه المالك
            self._notify_unmapped_room(client_id, channel_name, room_type, raw)

        # 3. إنشاء/إيجاد النزيل
        guest_id = self._upsert_guest(client_id, raw)

        # 4. إنشاء الحجز
        booking_id = self._create_booking(client_id, raw, guest_id, room_mapping)

        if not booking_id:
            return {"success": False, "reason": "booking_creation_failed"}

        # 5. حفظ في channel_reservations
        self._save_channel_reservation(
            client_id, booking_id, channel_name, channel_res_id,
            raw, raw.get("commission", 0), raw.get("net_amount", 0)
        )

        # 6. تأكيد الاستلام للقناة
        channel = self.channels.get(channel_name)
        if channel:
            try:
                channel.confirm_reservation(channel_res_id)
            except Exception:
                pass  # لا نوقف العملية إذا فشل التأكيد

        # 7. إرسال إشعارات (في خيط منفصل لا يؤثر على الأداء)
        threading.Thread(
            target=self._send_notifications,
            args=(client_id, raw, booking_id),
            daemon=True
        ).start()

        return {
            "success": True,
            "action": "created",
            "booking_id": booking_id,
            "channel_reservation_id": channel_res_id,
        }

    # ─── Database Helpers ─────────────────────────────────────

    def _is_duplicate(self, channel_name: str, channel_res_id: str) -> bool:
        """يتحقق من وجود الحجز مسبقاً"""
        try:
            rows = self.db.execute(
                "SELECT id FROM channel_reservations WHERE channel_name=%s AND channel_reservation_id=%s LIMIT 1",
                (channel_name, channel_res_id)
            )
            return len(rows) > 0
        except Exception:
            return False

    def _get_room_mapping(self, client_id: str, channel_name: str, room_type: str) -> Optional[str]:
        """يجلب الغرفة المحلية المرتبطة بنوع غرفة القناة"""
        if not room_type:
            return None
        try:
            rows = self.db.execute(
                "SELECT room_mapping FROM channel_configs WHERE client_id=%s AND channel_name=%s LIMIT 1",
                (client_id, channel_name)
            )
            if rows:
                mapping = rows[0].get("room_mapping", {})
                if isinstance(mapping, str):
                    mapping = json.loads(mapping)
                return mapping.get(room_type)
        except Exception:
            pass
        return None

    def _upsert_guest(self, client_id: str, raw: dict) -> Optional[str]:
        """ينشئ نزيلاً جديداً أو يجد الموجود"""
        try:
            name = raw.get("guest_name", "")
            phone = raw.get("guest_phone", "")
            email = raw.get("guest_email", "")

            # ابحث بالهاتف أو الإيميل
            existing = None
            if phone:
                rows = self.db.execute(
                    "SELECT id FROM guests WHERE client_id=%s AND phone=%s LIMIT 1",
                    (client_id, phone)
                )
                if rows:
                    existing = rows[0]["id"]

            if not existing and email:
                rows = self.db.execute(
                    "SELECT id FROM guests WHERE client_id=%s AND email=%s LIMIT 1",
                    (client_id, email)
                )
                if rows:
                    existing = rows[0]["id"]

            if existing:
                return str(existing)

            # إنشاء جديد
            result = self.db.execute(
                """INSERT INTO guests (client_id, name, phone, email, nationality)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (client_id, name, phone, email, raw.get("guest_nationality", ""))
            )
            return str(result[0]["id"]) if result else None

        except Exception as e:
            logger.error(f"upsert_guest failed: {e}")
            return None

    def _create_booking(
        self, client_id: str, raw: dict,
        guest_id: Optional[str], room_id: Optional[str]
    ) -> Optional[str]:
        """ينشئ حجزاً في النظام"""
        try:
            result = self.db.execute(
                """INSERT INTO bookings
                   (client_id, guest_id, room_id, check_in, check_out,
                    adults, children, total_amount, payment_status,
                    source, special_requests, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'confirmed')
                   RETURNING id""",
                (
                    client_id,
                    guest_id,
                    room_id,
                    raw.get("check_in"),
                    raw.get("check_out"),
                    raw.get("adults", 1),
                    raw.get("children", 0),
                    raw.get("total_amount", 0),
                    raw.get("payment_status", "pending"),
                    raw.get("channel", "channel"),
                    raw.get("special_requests", ""),
                )
            )
            return str(result[0]["id"]) if result else None
        except Exception as e:
            logger.error(f"create_booking failed: {e}")
            return None

    def _save_channel_reservation(
        self, client_id: str, booking_id: str,
        channel_name: str, channel_res_id: str,
        raw: dict, commission: float, net_amount: float
    ) -> None:
        """يحفظ في channel_reservations"""
        try:
            self.db.execute(
                """INSERT INTO channel_reservations
                   (client_id, booking_id, channel_name, channel_reservation_id,
                    raw_data, commission_amount, net_amount)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (channel_name, channel_reservation_id) DO NOTHING""",
                (
                    client_id, booking_id, channel_name, channel_res_id,
                    json.dumps(raw), commission, net_amount
                )
            )
        except Exception as e:
            logger.error(f"save_channel_reservation failed: {e}")

    def _log_sync(
        self, client_id: str, channel: str,
        sync_type: str, status: str,
        records: int = 0, message: str = ""
    ) -> None:
        """يسجّل عملية مزامنة في channel_sync_log"""
        try:
            self.db.execute(
                """INSERT INTO channel_sync_log
                   (client_id, channel_name, sync_type, status, records_count, error_message)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (client_id, channel, sync_type, status, records, message[:500] if message else "")
            )
        except Exception as e:
            logger.error(f"log_sync failed: {e}")

    # ─── Notifications ────────────────────────────────────────

    def _send_notifications(self, client_id: str, raw: dict, booking_id: str) -> None:
        """يُرسل إشعارات واتساب (في خيط منفصل)"""
        if not self.whatsapp:
            return

        try:
            guest_phone = raw.get("guest_phone", "")
            guest_name = raw.get("guest_name", "")
            channel = raw.get("channel", "")
            check_in = raw.get("check_in", "")
            check_out = raw.get("check_out", "")

            # إشعار المالك دائماً
            self.whatsapp.send_owner_notification(
                client_id=client_id,
                message=f"🏨 حجز جديد من {channel}\n"
                        f"النزيل: {guest_name}\n"
                        f"الوصول: {check_in}\n"
                        f"المغادرة: {check_out}\n"
                        f"رقم الحجز: {booking_id}"
            )

            # إشعار النزيل فقط إذا كان الجوال متاحاً
            if guest_phone and guest_phone.strip():
                self.whatsapp.send_booking_confirmation(
                    phone=guest_phone,
                    guest_name=guest_name,
                    check_in=check_in,
                    check_out=check_out,
                    booking_id=booking_id,
                )

        except Exception as e:
            logger.error(f"send_notifications failed: {e}")

    def _notify_unmapped_room(
        self, client_id: str, channel: str,
        room_type: str, raw: dict
    ) -> None:
        """يُنبّه المالك عند وصول حجز بغرفة غير مربوطة"""
        logger.warning(
            f"Unmapped room type: channel={channel}, room_type={room_type}, "
            f"client_id={client_id}"
        )
        try:
            self._log_sync(
                client_id, channel, "room_mapping", "partial",
                message=f"غرفة غير مربوطة: {room_type} — يرجى الربط من لوحة التحكم"
            )
        except Exception:
            pass

    # ─── Status ───────────────────────────────────────────────

    def get_status(self, client_id: str) -> dict:
        """يُعيد حالة كل القنوات للـ health endpoint"""
        status = {}
        for name, channel in self.channels.items():
            configured = channel.is_configured()
            status[name] = {
                "configured": configured,
                "channel_name": name,
            }
        return status

    def get_revenue_split(self, client_id: str, days: int = 30) -> dict:
        """توزيع الإيرادات حسب القناة"""
        try:
            rows = self.db.execute(
                """SELECT cr.channel_name,
                          COUNT(*) as bookings_count,
                          COALESCE(SUM(b.total_amount), 0) as total_revenue,
                          COALESCE(SUM(cr.commission_amount), 0) as total_commission
                   FROM channel_reservations cr
                   JOIN bookings b ON b.id = cr.booking_id
                   WHERE cr.client_id = %s
                     AND b.created_at >= NOW() - INTERVAL '%s days'
                   GROUP BY cr.channel_name""",
                (client_id, days)
            )
            return {r["channel_name"]: dict(r) for r in (rows or [])}
        except Exception as e:
            logger.error(f"get_revenue_split failed: {e}")
            return {}
