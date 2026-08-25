#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/migrate_json_to_pg.py — Migration من JSON إلى PostgreSQL
يُشغَّل مرة واحدة فقط بعد إضافة PostgreSQL plugin في Railway.
آمن للتشغيل أكثر من مرة (idempotent).

الاستخدام:
    python scripts/migrate_json_to_pg.py
    python scripts/migrate_json_to_pg.py --dry-run    (فحص بدون كتابة)
    python scripts/migrate_json_to_pg.py --json-path /path/to/admin_store.json
"""
import sys
import os
import json
import argparse
import logging
from datetime import datetime

# إضافة الـ root directory للـ path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("migration")


def _safe_str(v, max_len=200) -> str:
    return str(v or "")[:max_len]


def _safe_float(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


# ── Migrate Functions ──────────────────────────────────────────

def migrate_clients(data: dict, db, dry_run: bool) -> dict:
    """ينقل المنشآت (العملاء) من JSON"""
    stats = {"migrated": 0, "skipped": 0, "errors": []}
    clients = data.get("clients", [])
    log.info(f"  📋 {len(clients)} منشأة في JSON")

    for client in clients:
        client_id = _safe_str(client.get("id", ""), 50)
        if not client_id:
            stats["errors"].append({"item": "client_no_id", "error": "لا يوجد ID"})
            continue

        try:
            # تحقق من الوجود
            existing = db.execute(
                "SELECT id FROM clients WHERE id = %s", (client_id,), fetch="one"
            )
            if existing:
                stats["skipped"] += 1
                continue

            if dry_run:
                log.info(f"    [DRY-RUN] سيُنقل: {client_id}")
                stats["migrated"] += 1
                continue

            name = _safe_str(
                client.get("name") or client.get("hotel_name") or
                client.get("facility_name") or "", 200
            )
            if not name:
                name = f"منشأة {client_id}"

            settings = {k: v for k, v in client.items()
                        if k not in {"id", "name", "hotel_name", "type", "city",
                                     "region", "phone", "email", "units_count",
                                     "settings_locked", "guests", "bookings",
                                     "invoices", "pos_transactions"}}

            db.execute("""
                INSERT INTO clients
                    (id, name, type, city, region, phone, email,
                     units_count, settings_locked, settings)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                client_id, name,
                _safe_str(client.get("type") or client.get("hotel_type") or
                           client.get("facility_type"), 50),
                _safe_str(client.get("city"), 100),
                _safe_str(client.get("region"), 100),
                _safe_str(client.get("phone"), 20),
                _safe_str(client.get("email"), 200),
                _safe_int(client.get("units_count") or client.get("rooms")),
                bool(client.get("settings_locked", False)),
                json.dumps(settings, ensure_ascii=False),
            ))
            stats["migrated"] += 1
            log.info(f"    ✓ {client_id}: {name}")

        except Exception as e:
            stats["errors"].append({"client": client_id, "error": str(e)})
            log.error(f"    ❌ {client_id}: {e}")

    return stats


def migrate_guests(data: dict, db, dry_run: bool) -> dict:
    """ينقل النزلاء — يبحث داخل كل عميل"""
    stats = {"migrated": 0, "skipped": 0, "errors": []}
    clients = data.get("clients", [])

    for client in clients:
        client_id = _safe_str(client.get("id", ""), 50)
        guests = client.get("guests", [])

        for guest in guests:
            guest_id = _safe_int(guest.get("id"))
            if not guest_id:
                continue

            try:
                existing = db.execute(
                    "SELECT id FROM guests WHERE client_id=%s AND id=%s",
                    (client_id, guest_id), fetch="one"
                )
                if existing:
                    stats["skipped"] += 1
                    continue

                if dry_run:
                    stats["migrated"] += 1
                    continue

                db.execute("""
                    INSERT INTO guests
                        (id, client_id, id_type, id_number, full_name,
                         absher_phone, nationality, data_status, source, notes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    guest_id, client_id,
                    _safe_str(guest.get("id_type"), 20),
                    _safe_str(guest.get("id_number"), 20),
                    _safe_str(guest.get("full_name") or guest.get("name"), 200) or "مجهول",
                    _safe_str(guest.get("absher_phone") or guest.get("phone"), 20),
                    _safe_str(guest.get("nationality"), 100),
                    _safe_str(guest.get("data_status", "incomplete"), 20),
                    _safe_str(guest.get("source"), 50),
                    _safe_str(guest.get("notes"), 1000),
                ))
                stats["migrated"] += 1

            except Exception as e:
                stats["errors"].append({"guest": guest_id, "client": client_id, "error": str(e)})

    return stats


def migrate_bookings(data: dict, db, dry_run: bool) -> dict:
    """ينقل الحجوزات"""
    stats = {"migrated": 0, "skipped": 0, "errors": []}
    clients = data.get("clients", [])

    for client in clients:
        client_id = _safe_str(client.get("id", ""), 50)
        bookings = client.get("bookings", [])

        for booking in bookings:
            booking_id = _safe_str(booking.get("id", ""), 50)
            if not booking_id:
                continue

            check_in = booking.get("check_in") or booking.get("checkin")
            check_out = booking.get("check_out") or booking.get("checkout")
            if not check_in or not check_out:
                continue

            try:
                existing = db.execute(
                    "SELECT id FROM bookings WHERE id=%s", (booking_id,), fetch="one"
                )
                if existing:
                    stats["skipped"] += 1
                    continue

                if dry_run:
                    stats["migrated"] += 1
                    continue

                companions = json.dumps(booking.get("companions", []), ensure_ascii=False)
                pre_data = json.dumps(booking.get("pre_arrival_data", {}), ensure_ascii=False)

                db.execute("""
                    INSERT INTO bookings
                        (id, client_id, guest_id, check_in, check_out,
                         nightly_rate, total_room, status, source,
                         company_name, companions, pre_arrival_status, pre_arrival_data, notes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    booking_id, client_id,
                    _safe_int(booking.get("guest_id")) or None,
                    str(check_in)[:10],
                    str(check_out)[:10],
                    _safe_float(booking.get("nightly_rate") or booking.get("price_per_night")),
                    _safe_float(booking.get("total_room") or booking.get("total")),
                    _safe_str(booking.get("status", "confirmed"), 30),
                    _safe_str(booking.get("source", "reception"), 50),
                    _safe_str(booking.get("company_name"), 200),
                    companions,
                    _safe_str(booking.get("pre_arrival_status", "pending"), 20),
                    pre_data,
                    _safe_str(booking.get("notes"), 1000),
                ))
                stats["migrated"] += 1

            except Exception as e:
                stats["errors"].append({"booking": booking_id, "error": str(e)})

    return stats


def migrate_invoices(data: dict, db, dry_run: bool) -> dict:
    """ينقل الفواتير"""
    stats = {"migrated": 0, "skipped": 0, "errors": []}
    clients = data.get("clients", [])

    for client in clients:
        client_id = _safe_str(client.get("id", ""), 50)
        invoices = client.get("invoices", [])

        for inv in invoices:
            inv_id = _safe_str(
                inv.get("id") or inv.get("invoice_number") or inv.get("invoice_id"), 50
            )
            if not inv_id:
                continue

            try:
                existing = db.execute(
                    "SELECT id FROM invoices WHERE id=%s", (inv_id,), fetch="one"
                )
                if existing:
                    stats["skipped"] += 1
                    continue

                if dry_run:
                    stats["migrated"] += 1
                    continue

                line_items = json.dumps(inv.get("line_items", []), ensure_ascii=False)
                total = _safe_float(inv.get("total_amount") or inv.get("total"))
                vat = _safe_float(inv.get("vat_amount") or inv.get("vat"))
                sub = _safe_float(inv.get("subtotal") or (total - vat))

                db.execute("""
                    INSERT INTO invoices
                        (id, client_id, issue_date, subtotal, vat_amount,
                         total_amount, payment_method, payment_status, line_items)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    inv_id, client_id,
                    str(inv.get("issue_date") or inv.get("date", str(datetime.now().date())))[:10],
                    sub, vat, total,
                    _safe_str(inv.get("payment_method", "cash"), 30),
                    _safe_str(inv.get("payment_status", "paid"), 20),
                    line_items,
                ))
                stats["migrated"] += 1

            except Exception as e:
                stats["errors"].append({"invoice": inv_id, "error": str(e)})

    return stats


def migrate_pos(data: dict, db, dry_run: bool) -> dict:
    """ينقل عمليات POS"""
    stats = {"migrated": 0, "skipped": 0, "errors": []}
    clients = data.get("clients", [])

    for client in clients:
        client_id = _safe_str(client.get("id", ""), 50)
        txs = client.get("pos_transactions", client.get("pos", []))

        for tx in txs:
            try:
                if dry_run:
                    stats["migrated"] += 1
                    continue

                db.execute("""
                    INSERT INTO pos_transactions
                        (client_id, date, payment_method, amount,
                         vat_amount, category, description, cashier)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    client_id,
                    str(tx.get("date", str(datetime.now().date())))[:10],
                    _safe_str(tx.get("payment_method", "cash"), 30),
                    _safe_float(tx.get("amount")),
                    _safe_float(tx.get("vat_amount")),
                    _safe_str(tx.get("category"), 100),
                    _safe_str(tx.get("description"), 500),
                    _safe_str(tx.get("cashier"), 100),
                ))
                stats["migrated"] += 1

            except Exception as e:
                stats["errors"].append({"tx": str(tx.get("id", "?")), "error": str(e)})

    return stats


# ── Main ───────────────────────────────────────────────────────

def run_migration(json_path: str, dry_run: bool = False) -> None:
    """نقطة الدخول الرئيسية للـ migration"""
    print("=" * 60)
    print("  DHEUOF — Migration من JSON إلى PostgreSQL")
    print("=" * 60)
    print(f"  JSON: {json_path}")
    print(f"  Mode: {'🔍 DRY-RUN (لا كتابة)' if dry_run else '✍️  LIVE'}")
    print("=" * 60)

    # 1. تحقق من DATABASE_URL
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("❌ DATABASE_URL غير موجود في environment variables")
        print("   أضفه: export DATABASE_URL=postgresql://...")
        sys.exit(1)

    # 2. قراءة JSON
    if not os.path.exists(json_path):
        print(f"❌ الملف غير موجود: {json_path}")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    clients_count = len(data.get("clients", []))
    print(f"📂 تم قراءة JSON: {clients_count} عميل")

    # 3. اتصال قاعدة البيانات
    from db.connection import DatabasePool
    db = DatabasePool(database_url=db_url)

    if not db.use_postgres:
        print("❌ فشل الاتصال بـ PostgreSQL — تحقق من DATABASE_URL")
        sys.exit(1)

    # 4. تشغيل migrations
    if not dry_run:
        print("\n🔧 تطبيق database schema...")
        db.run_migrations()
        print("✅ Schema جاهز\n")

    # 5. نقل البيانات بالترتيب
    results = {}

    print("📋 نقل المنشآت...")
    results["clients"] = migrate_clients(data, db, dry_run)

    print("👥 نقل النزلاء...")
    results["guests"] = migrate_guests(data, db, dry_run)

    print("📅 نقل الحجوزات...")
    results["bookings"] = migrate_bookings(data, db, dry_run)

    print("💰 نقل POS...")
    results["pos"] = migrate_pos(data, db, dry_run)

    print("📄 نقل الفواتير...")
    results["invoices"] = migrate_invoices(data, db, dry_run)

    # 6. تقرير النتائج
    print("\n" + "=" * 60)
    print("  📊 تقرير Migration")
    print("=" * 60)

    total_migrated = 0
    total_skipped = 0
    total_errors = []

    for key, stats in results.items():
        m = stats["migrated"]
        s = stats["skipped"]
        e = len(stats["errors"])
        total_migrated += m
        total_skipped += s
        total_errors.extend(stats["errors"])
        status = "✅" if e == 0 else "⚠️"
        print(f"  {status} {key}: {m} منقول، {s} موجود مسبقاً، {e} خطأ")

    print("=" * 60)
    print(f"  الإجمالي: {total_migrated} منقول، {total_skipped} تخطّى")

    if total_errors:
        print(f"\n⚠️  {len(total_errors)} أخطاء:")
        for err in total_errors[:20]:  # اعرض أول 20 خطأ فقط
            print(f"  ❌ {err}")
        if len(total_errors) > 20:
            print(f"  ... و{len(total_errors) - 20} خطأ إضافي")

    if dry_run:
        print("\n🔍 DRY-RUN انتهى — لم تُكتب أي بيانات")
        print("   شغّل بدون --dry-run للتنفيذ الفعلي")
    else:
        print("\n✅ Migration اكتمل!")
        print("   الخطوات التالية:")
        print("   1. تحقق من /api/health → database.status = ok")
        print("   2. بعد 48 ساعة من التأكيد: أضف DUAL_WRITE=false في Railway Variables")
        print("   3. احتفظ بـ admin_store.json شهراً كاملاً كـ backup")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migration من JSON إلى PostgreSQL لنظام ضيوف"
    )
    parser.add_argument(
        "--json-path",
        default="admin_store.json",
        help="مسار ملف admin_store.json (افتراضي: admin_store.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="فحص بدون كتابة — لرؤية ما سيحدث",
    )
    args = parser.parse_args()
    run_migration(args.json_path, args.dry_run)
