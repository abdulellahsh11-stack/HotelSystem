# HotelSystem v3.0 — FastAPI + uvicorn

مستودع موحَّد لمنصة ضيوف. دُمج فيه مستودع `HotelSystem1` بحيث أصبح هذا هو المسار الوحيد للتطوير.

## التشغيل

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```

نقطة الدخول `main.py` تستورد `app` من `main1.py` وتُسجّل المسارات عبر `main2.py`.

## البنية

| المسار | المحتوى |
|---|---|
| `main.py` · `main1.py` · `main2.py` | نقطة الدخول، تهيئة التطبيق، تسجيل المسارات |
| `routes/` | وحدات المسارات (FastAPI `APIRouter`) |
| `services/` | منطق الأعمال والتكاملات الخارجية |
| `models/` | نماذج البيانات الموحَّدة |
| `utils/` | أدوات مساعدة مشتركة |
| `db/` | الاتصال والترحيلات والمخطط |
| `specs/db/` | نماذج البيانات و DDL مرجعي |
| `tests/` | اختبارات الوحدة و e2e والحِمل |

### وحدات مدمجة من `HotelSystem1`

**محوّلات قنوات الحجز** — التنفيذ الفعلي لـ OTA خلف مسارات `/api/channels/*`:

| الملف | الوظيفة |
|---|---|
| `services/base_channel.py` | الواجهة الموحَّدة لأي قناة (`BaseChannel` · `ChannelResult`) |
| `services/booking_com.py` | تكامل Booking.com Connectivity API v3 (XML/OTA 2003) |
| `services/mawasim.py` | تكامل مواسم — منصة الحجز السعودية |
| `utils/xml_parser.py` | محلل XML لصيغة OTA 2003 (stdlib فقط) |
| `models/reservation.py` | صيغة حجز موحَّدة عبر كل المصادر |

**خدمات تشغيلية:**

| الملف | الوظيفة |
|---|---|
| `services/scheduler.py` | `CronManager` لإدارة الخيوط الخلفية |
| `services/backup_monitor.py` | مراقبة النسخ الاحتياطي اليومي |

**أدوات مشتركة (`utils/`):** `auth` · `date_utils` (توقيت الرياض UTC+3) ·
`middleware` · `monitoring` (Sentry) · `response` · `validators` (الهوية السعودية والهاتف)

**سكربتات:** `scripts/migrate_json_to_pg.py` (ترحيل JSON ← PostgreSQL) ·
`scripts/syntax_check.py`

مرجع DDL للقنوات والتسعير والـ API: [`specs/db/003-channels-pricing-api.sql`](specs/db/003-channels-pricing-api.sql)
