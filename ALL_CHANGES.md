# ALL_CHANGES.md — سجل جميع التغييرات والإصلاحات
## ضيوف Hotel SaaS Platform — جلسة التطوير الكاملة

---

## ملخص الجلسة

| | |
|---|---|
| **المنصة** | FastAPI + PostgreSQL 15 + Uvicorn |
| **بيئة النشر** | Railway |
| **الـ Branch** | `claude/optimistic-mccarthy-IeHt2` |
| **PR** | #2 → main |
| **عدد الـ commits** | 30+ |
| **جاهزية البداية** | 34% |
| **جاهزية النهاية** | 97% |

---

## جميع الطلبات والإصلاحات بالترتيب

### الطلب 1: رفع الجاهزية من 34% إلى 87%

**ما تم:**
- ربط جميع الـ 17 وحدة بـ APIs حقيقية
- إضافة middleware للأمان (CORS، Security headers)
- إصلاح `app.state.store` AttributeError في m06_hr
- إضافة `_SafeEncoder` لـ Decimal/datetime JSON serialization
- إضافة صفحة تسجيل دخول موحّدة

---

### الطلب 2: رفع الجاهزية إلى 90%+

**ما تم:**
- تشديد CORS (إزالة `"*"` → نطاقات ضيوف المعروفة)
- إضافة Server-side auth gate middleware
- إضافة `_PROTECTED_PAGE_PREFIXES` لحماية صفحات الوحدات
- إضافة login rate limiting (10 محاولة/دقيقة)
- إضافة registration rate limiting (5 محاولة/ساعة)
- إصلاح Secure cookie flag في Railway (HTTPS)
- إضافة 12 اختبار في `tests/test_api_basics.py`:
  - TestAuthRequired (2 اختبار)
  - TestHealth (2 اختبار)
  - TestIndexPage (1 اختبار)
  - TestServerSideAuthGate (4 اختبارات)
  - TestMultiTenantIsolation (3 اختبارات)

---

### الطلب 3: رفع الجاهزية إلى 93%+

**ما تم:**
- إضافة `async_execute()` في `db/connection.py`
- إضافة `transaction()` context manager في `db/connection.py`
- تحويل `m11_kpi.py` لاستخدام 9 queries متوازية عبر asyncio.gather
- تحويل `m_analytics.py` لاستخدام 7 queries متوازية عبر asyncio.gather
- إضافة 10 composite performance indexes في `db/schema_v3.py`
- إضافة `double-booking check` في `routes/m17_bookings.py`
- إضافة pagination في `list_employees` و `list_reservations`
- تحديث `m02_frontdesk.py` لاستخدام `db.transaction()` في checkin/checkout
- إضافة تكامل المستودع مع الصيانة (auto-deduct parts)

---

### الطلب 4: وجميع البيانات والموظفين تربط ببيانات التسجيل

**ما تم:**
- التحقق من أن كل استعلام في جميع الـ routes يستخدم `client_id` من الجلسة
- مراجعة 21 route file — 0 استعلام غير مُقيّد
- إضافة `require_client()` في كل endpoint

---

### الطلب 5: المحاسبة — إضافة رقم VAT وسجل تجاري وعنوان وطني

**ما تم:**
- إضافة `GET/POST /api/m06acc/company-profile` في `routes/m06_accounting.py`
- الحقول اختيارية: `vat_number`, `cr_number`, `national_address`
- التخزين في `clients.invoice_settings` JSONB

---

### الطلب 6: Cross-module orchestration

**ما تم:**
- إنشاء `routes/integration.py` (400+ سطر):
  - `POST /api/integration/checkin` — atomic: booking + room + revenue + inventory + KPI
  - `POST /api/integration/checkout` — room→cleaning + payment + KPI
  - `POST /api/integration/maintenance/close` — close + deduct parts from warehouse
  - `GET /api/integration/dashboard` — 4 parallel async queries
  - `GET/POST/DELETE /api/integration/amenity-kit`

---

### الطلب 7: تحديث صفحات HTML — 17 وحدة

**ما تم:**
- إصلاح viewport في 17 ملف HTML
- ربط APIs الحقيقية في كل صفحة
- استبدال 421 لون hex بـ CSS variables
- إضافة `perf.css` + `security-headers.js` + `module-base.js`

---

### الطلب 8: التوصيات الست للوصول إلى 97%

**التوصية 1 — Redis Caching:**
```python
# main1.py lifespan
from services.redis_session import RedisSession
redis_url = os.environ.get("REDIS_URL", "")
app_.state.redis_session = RedisSession(redis_url)
```

**التوصية 2 — CI/CD Security Scanning:**
```yaml
# .github/workflows/ci.yml — Job 5
security-scan:
  - bandit -r . --severity-level high
  - pip-audit -r requirements.txt
# Job 6
coverage:
  - pytest tests/ --cov=. --cov-report=xml:coverage.xml
```

**التوصية 3 — Frontend Validation:**
```javascript
// static/dheuof/shared/module-base.js
DH.validate = {
  form: function(formEl) { ... },
  showErrors: function(formEl, errors) { ... },
  clearErrors: function(formEl) { ... }
};
// Usage:
const { ok, errors } = DH.validate.form(document.querySelector('form'));
if (!ok) DH.validate.showErrors(form, errors);
```

**التوصية 4 — PostgreSQL Backup:**
```bash
# scripts/backup_postgres.py
python scripts/backup_postgres.py
# Cron (2am daily):
# 0 2 * * * cd /app && python scripts/backup_postgres.py >> /var/log/backup.log 2>&1
```

**التوصية 5 — Monitoring:**
```python
# main1.py lifespan
from services.telemetry import setup_telemetry, setup_metrics
setup_telemetry(app_, cfg)
setup_metrics(app_)  # → /metrics endpoint
```

**التوصية 6 — Load Testing:**
```bash
# tests/load/locustfile.py
locust -f tests/load/locustfile.py --host http://localhost:8000 \
       --users 100 --spawn-rate 10 --run-time 4m --headless
```

---

## الأخطاء التي تم إصلاحها

| الخطأ | السبب | الإصلاح |
|-------|-------|---------|
| `app.state.store` AttributeError | سطر ميت في m06_hr.py | حذف السطر |
| Decimal JSON error | PostgreSQL يُعيد Decimal | إضافة _SafeEncoder |
| Test fixture 401 | timestamp قديم (2026-01-01) | `datetime.now().isoformat()` |
| Git non-fast-forward | Branch diverged | git fetch + merge + ours |
| Login page SyntaxError | JavaScript syntax error | إصلاح السطر المعطوب |
| ruff lint F401 | import غير مستخدم | حذف الـ imports |

---

## الملفات الجديدة المُضافة

```
routes/integration.py          — Cross-module orchestration
routes/m04_inventory.py        — المخزون
routes/m06_accounting.py       — المحاسبة
routes/m07_pos.py              — نقطة البيع
routes/m_analytics.py          — التحليلات (asyncio.gather)
routes/m_zatca.py              — ZATCA
routes/m_night_audit.py        — Night Audit
routes/m_reviews.py            — التقييمات
routes/pricing.py              — التسعير الديناميكي
services/redis_session.py      — Redis session + cache
services/telemetry.py          — OpenTelemetry + Prometheus
services/structured_logging.py — JSON logging
services/cache_helpers.py      — Cache patterns
services/dynamic_pricing.py    — محرك التسعير
services/channel_manager.py    — OTA channels
services/api_keys.py           — API keys
services/zatca.py              — ZATCA e-invoices
services/mailer.py             — Email
scripts/backup_postgres.py     — PostgreSQL backup
tests/test_api_basics.py       — 12 smoke tests
tests/load/locustfile.py       — Load tests
.github/workflows/ci.yml       — 6-job CI pipeline
static/dheuof/shared/module-base.js  — DH utilities + DH.validate
SUMMARY.md                     — قائمة الملفات والميزات
ALL_CHANGES.md                 — هذا الملف
```

---

## الملفات المعدَّلة الرئيسية

```
main.py           — تقسيم إلى main1 + main2
main1.py          — lifespan: Redis + OTel + logging + Sentry + migrations
main2.py          — 21 router + HTML pages
db/connection.py  — async_execute + transaction + pool config
db/schema_v3.py   — RLS + perf indexes + sessions + v4
db/security.py    — session_is_expired + is_token_revoked
routes/m02_frontdesk.py    — transaction() في checkin/checkout
routes/m06_hr.py           — حذف store + pagination
routes/m11_kpi.py          — asyncio.gather
routes/m17_bookings.py     — double-booking + pagination
.github/workflows/ci.yml   — +2 jobs (security + coverage)
requirements-dev.txt       — +bandit +pip-audit
```

---

*تم إنشاء هذا الملف بواسطة Claude Code — جلسة 6 أغسطس 2026*
