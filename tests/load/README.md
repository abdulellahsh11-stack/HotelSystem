# اختبارات الحمل — Dheuof Load Tests

**المنصة / Platform:** dheuof.com (FastAPI)  
**الأدوات / Tools:** [Locust](https://locust.io) · [k6](https://k6.io)

---

## 1. Locust

### التثبيت / Installation

```bash
pip install locust
```

### متغيرات البيئة / Environment variables

| المتغير / Variable | الوصف / Description | الافتراضي / Default |
|---|---|---|
| `HOST` | عنوان الخادم / Server URL | `http://localhost:8000` |
| `ADMIN_PASSWORD` | كلمة مرور المدير / Admin password | `admin123` |
| `STAFF_CLIENT_ID` | معرّف الفندق / Hotel client ID | `test-hotel` |
| `STAFF_PASSWORD` | كلمة مرور الموظف / Staff password | `hotel123` |

### تشغيل واجهة الويب / Run with web UI

```bash
cd tests/load
locust -f locustfile.py --host http://localhost:8000
# ثم افتح / then open: http://localhost:8089
```

### تشغيل بدون واجهة (headless) / Headless run

```bash
# اختبار سريع — 10 مستخدمين لمدة دقيقتين
# Quick smoke — 10 users for 2 minutes
locust -f locustfile.py \
  --host http://localhost:8000 \
  --users 10 --spawn-rate 2 \
  --run-time 2m --headless

# الأمر الكامل مع متغيرات البيئة
# Full command with env vars
HOST=https://staging.dheuof.com \
ADMIN_PASSWORD=myadminpass \
STAFF_CLIENT_ID=hotel-001 \
STAFF_PASSWORD=hotelpass \
locust -f locustfile.py \
  --host https://staging.dheuof.com \
  --headless --run-time 4m
```

### مراحل الحمل المدمجة / Built-in load shape (DheuofLoadShape)

تستخدم `DheuofLoadShape` تلقائياً عند عدم تحديد `--users`:

Uses `DheuofLoadShape` automatically when `--users` is not specified:

| المرحلة / Stage | المدة / Duration | المستخدمون / Users |
|---|---|---|
| تسخين / Warm-up | 0 – 60 ث/s | 10 |
| متوسط / Moderate | 60 – 120 ث/s | 50 |
| ذروة / Peak | 120 – 180 ث/s | 100 |
| تبريد / Cool-down | 180 – 240 ث/s | 50 |

```bash
locust -f locustfile.py --host http://localhost:8000 --headless --run-time 4m
```

### فئات المستخدمين / User classes

| الفئة / Class | نوع المستخدم / User type | wait_time | المهام الرئيسية / Key tasks |
|---|---|---|---|
| `AdminUser` | مدير المنصة / Platform admin | 1 – 3 ث/s | KPI, حجوزات/bookings, وصول/arrivals, مخازن/warehouses |
| `StaffUser` | موظف الفندق / Hotel staff | 2 – 5 ث/s | وصول/arrivals, مغادرات/departures, صيانة/maintenance |
| `GuestUser` | زائر مجهول / Anonymous visitor | 3 – 8 ث/s | `/api/health`, الصفحة الرئيسية / home page |

---

## 2. k6

### التثبيت / Installation

```bash
# macOS
brew install k6

# Linux (Debian/Ubuntu)
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6

# Docker
docker pull grafana/k6
```

### متغيرات البيئة / Environment variables

| المتغير / Variable | الوصف / Description | الافتراضي / Default |
|---|---|---|
| `BASE_URL` | عنوان الخادم / Server URL | `http://localhost:8000` |
| `ADMIN_PASSWORD` | كلمة مرور المدير / Admin password | `admin123` |
| `CLIENT_ID` | معرّف الفندق / Hotel client ID | `test-hotel` |
| `CLIENT_PASSWORD` | كلمة مرور الموظف / Staff password | `hotel123` |

### تشغيل الاختبار / Run the test

```bash
cd tests/load

# تشغيل أساسي / Basic run
k6 run k6_script.js

# مع متغيرات مخصصة / With custom variables
k6 run \
  -e BASE_URL=https://staging.dheuof.com \
  -e ADMIN_PASSWORD=secretpass \
  -e CLIENT_ID=hotel-001 \
  -e CLIENT_PASSWORD=hotelpass \
  k6_script.js

# تشغيل داخل Docker / Run in Docker
docker run --rm -i grafana/k6 run \
  -e BASE_URL=http://host.docker.internal:8000 \
  - < k6_script.js

# تصدير النتائج إلى InfluxDB + Grafana
# Export results to InfluxDB + Grafana
k6 run --out influxdb=http://localhost:8086/k6 k6_script.js
```

### مراحل الحمل / Load stages

| المرحلة / Stage | المدة / Duration | VUs المستهدفة / Target VUs |
|---|---|---|
| تسخين / Warm-up | 1 دقيقة / 1 min | 0 → 10 |
| بناء / Build-up | 2 دقيقتان / 2 min | 10 → 50 |
| ذروة / Peak soak | 4 دقائق / 4 min | 50 → 100 |
| تبريد / Ramp-down | 2 دقيقتان / 2 min | 100 → 0 |

### حدود القبول / Acceptance thresholds

| المقياس / Metric | الحد / Threshold |
|---|---|
| `http_req_duration` p(95) | < 500 مللي ثانية / ms |
| `error_rate` | < 1% |
| تسجيل الدخول p(95) / Login p(95) | < 800 مللي ثانية / ms |

---

## 3. تشغيل كلا الأداتين معاً / Running both tools together

```bash
# نافذة 1 — Locust
cd tests/load
HOST=http://localhost:8000 locust -f locustfile.py --headless --run-time 4m

# نافذة 2 — k6 (توقيت مختلف أو بيئة مختلفة)
k6 run -e BASE_URL=http://localhost:8000 k6_script.js
```

> **تحذير / Warning:** تشغيل كلا الأداتين في نفس الوقت على نفس الخادم يُضاعف الحمل.  
> Running both tools simultaneously against the same server doubles the load.

---

## 4. تفسير النتائج / Interpreting results

### Locust
- **RPS** (طلبات/ثانية / requests per second): يجب ألا تنخفض تحت 50% عند الذروة.
- **Failures**: يجب أن تبقى أقل من 1% في كل نقطة زمنية.
- **Response time (median/p95)**: احرص على أن p95 < 500ms للمسارات الحرجة.

### k6
- **http_req_duration**: راقب p(50), p(90), p(95), p(99).
- **error_rate**: تحقق من `check_rate` — يجب أن يكون 1.0 (100% نجاح).
- **vus / vus_max**: يُظهر توزيع الجلسات عبر الزمن.

---

## 5. ملاحظات الإنتاج / Production notes

1. **بيانات الاختبار / Test data**: تأكد من وجود حساب `test-hotel` في قاعدة البيانات قبل تشغيل الاختبارات.
2. **معدل الطلبات / Rate limits**: الخادم يفرض حدوداً على تسجيل الحسابات (`REG_MAX_PER_HOUR`). اختبارات الحمل لا تُسجّل حسابات جديدة.
3. **البيئة المستهدفة / Target environment**: شغّل الاختبارات على بيئة staging منعزلة — لا تستخدم الإنتاج مباشرة.
4. **CORS**: إذا شغّلت الاختبارات من خارج النطاقات المسموحة، أضف عنوان الاختبار إلى `CORS_ORIGINS`.
5. **الجلسات / Sessions**: تنتهي الجلسات الإدارية بعد 8 ساعات. الاختبارات المطوّلة تحتاج إلى إعادة المصادقة.
6. **قاعدة البيانات / Database**: راقب بطء الاستعلامات (`slow query log`) خلال اختبارات الذروة.

---

## 6. البنية الدليلية / Directory structure

```
tests/
└── load/
    ├── locustfile.py   # Locust load test (Python)
    ├── k6_script.js    # k6 load test (JavaScript)
    └── README.md       # هذا الملف / this file
```
