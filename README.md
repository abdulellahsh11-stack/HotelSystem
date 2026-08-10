# HotelSystem v3.0 — FastAPI + uvicorn

مستودع موحَّد لمنصة ضيوف. دُمج فيه مستودع `HotelSystem1` بحيث أصبح هذا هو المسار الوحيد للتطوير.

## التشغيل

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```

## البنية

| المسار | المحتوى |
|---|---|
| `main.py` | نقطة الدخول لـ uvicorn — يُعيد تصدير `app` |
| `app_core.py` | إنشاء التطبيق · الوسائط · المصادقة · سجل الوحدات |
| `routes/` | وحدات المسارات — وحدة لكل مجال |
| `services/` | منطق الأعمال والتكاملات الخارجية |
| `models/` | نماذج البيانات الموحَّدة |
| `utils/` | أدوات مساعدة مشتركة |
| `db/` | الاتصال والترحيلات والمخطط |
| `specs/db/` | نموذج البيانات و DDL مرجعي |
| `tests/` | اختبارات الوحدة و e2e والحِمل |
| `static/` | الواجهة |

### تسجيل الوحدات

كل وحدات `routes/` مُدرَجة في جدول واحد `ROUTE_MODULES` في آخر `app_core.py`،
ويُركّبها `_register_route_modules()`. لإضافة وحدة: أنشئ `routes/<اسم>.py`
فيه `router = APIRouter(prefix=…)` ثم أضف سطراً للجدول.

فشل وحدة لا يُسقط التطبيق، ويظهر في سجل الإقلاع:

```
✓ وحدات المسارات: 28/28 محمَّلة
```

إن نقص العدد فهناك وحدة لم تُحمَّل — يسجّلها السطر `✗` مع سبب الفشل.

### وحدات المسارات

| المجال | الملف | البادئة |
|---|---|---|
| الاستقبال | `routes/frontdesk.py` | `/api/m02` |
| الحجوزات | `routes/bookings.py` | `/api/m17` |
| التدبير الفندقي | `routes/housekeeping.py` | `/api/m07` |
| نقاط البيع | `routes/pos.py` | `/api/m07` |
| الصيانة | `routes/maintenance.py` | `/api/m08` |
| المخزون | `routes/inventory.py` | `/api/m04` |
| المستودعات | `routes/warehouses.py` | `/api/m13` |
| المحاسبة | `routes/accounting.py` | `/api/m06acc` |
| الموارد البشرية | `routes/hr.py` | `/api/m06` |
| علاقات العملاء | `routes/crm.py` | `/api/m10` |
| مؤشرات الأداء | `routes/kpi.py` | `/api/m11` |
| التحليلات | `routes/analytics.py` | `/api/analytics` |
| التقييمات | `routes/reviews.py` | `/api/reviews` |
| تدقيق الليل | `routes/night_audit.py` | `/api/night-audit` |
| الفوترة الإلكترونية | `routes/zatca.py` | `/api/zatca` |
| الرحلات السياحية | `routes/tourism.py` | `/api/m14` |
| الوجهات السياحية | `routes/destinations.py` | `/api/m14b` |
| قنوات التوزيع | `routes/channels.py` | `/api/channels` |
| التسعير الديناميكي | `routes/pricing.py` | `/api/pricing` |
| التنسيق عبر الوحدات | `routes/integration.py` | `/api/integration` |
| الـ Open API | `routes/open_api.py` | `/api/open/v1` |
| الصفحات و PWA و SEO | `routes/pages.py` | مسارات جذرية |
| الصحة والنسخ الاحتياطي | `routes/system.py` | `/api` |
| لوحة مالك المنصة | `routes/admin.py` | `/api/admin` |
| دخول المنشأة | `routes/auth.py` | `/api` |
| العمليات الفندقية | `routes/hotel_ops.py` | `/api` |
| المؤشرات والاشتراك | `routes/insights.py` | `/api` |
| الباقات والتذاكر | `routes/commerce.py` | `/api` |

> بادئات `/api/mNN` عقدٌ عام تعتمد عليه الواجهة في ١٠٢ موضع — لم تُغيَّر.
> `/api/m07` مشتركة بين التدبير ونقاط البيع بمسارات فرعية مختلفة (لا تعارض).

### وحدات مدمجة من `HotelSystem1`

**محوّلات قنوات الحجز** — التنفيذ الفعلي لـ OTA خلف مسارات `/api/channels/*`:

| الملف | الوظيفة |
|---|---|
| `services/base_channel.py` | الواجهة الموحَّدة (`BaseChannel` · `ChannelResult`) |
| `services/booking_com.py` | Booking.com Connectivity API v3 (XML/OTA 2003) |
| `services/mawasim.py` | تكامل مواسم |
| `utils/xml_parser.py` | محلل OTA 2003 (stdlib فقط) |
| `models/reservation.py` | صيغة حجز موحَّدة عبر المصادر |

**خدمات تشغيلية:** `services/scheduler.py` (`CronManager`) · `services/backup_monitor.py`

**أدوات (`utils/`):** `auth` · `date_utils` (توقيت الرياض UTC+3) · `middleware` ·
`monitoring` (Sentry) · `response` · `validators` (الهوية السعودية والهاتف)

**سكربتات:** `scripts/migrate_json_to_pg.py` · `scripts/syntax_check.py`

مرجع DDL: [`specs/db/003-channels-pricing-api.sql`](specs/db/003-channels-pricing-api.sql)
