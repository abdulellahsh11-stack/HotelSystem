# ضيوف — منصة إدارة الفنادق والشقق المخدومة

FastAPI + PostgreSQL. متعدّدة المستأجرين، بعزل مفروض على مستوى قاعدة البيانات.

---

## التشغيل السريع

```bash
pip install -r requirements.txt
export DATABASE_URL="postgresql://user:pass@host:5432/db?sslmode=require"
export SECRET_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
export ADMIN_PASS_HASH="$(python3 scripts/gen_admin_hash.py)"
uvicorn main:app --host 0.0.0.0 --port 5050
```

الترحيلات تُطبَّق تلقائياً عند الإقلاع وهي آمنة للتكرار.

---

## متغيّرات البيئة

### إلزامية

| المتغيّر | الغرض |
|---|---|
| `DATABASE_URL` | اتصال PostgreSQL. **أضف `?sslmode=require`** |
| `SECRET_KEY` | توقيع الجلسات — 32 محرفاً فأكثر |
| `ADMIN_PASS_HASH` | كلمة مرور المالك (`scripts/gen_admin_hash.py`) |

### أمنية — مطلوبة قبل الإنتاج

| المتغيّر | الغرض | التوليد |
|---|---|---|
| `RLS_ENFORCE` | `1` يفرض عزل المستأجرين في قاعدة البيانات | — |
| `PII_ENCRYPTION_KEY` | تشفير أرقام الهوية | `python3 -m db.crypto` |
| `PII_BLIND_INDEX_PEPPER` | البحث في الحقول المشفَّرة | نفس الأمر |

بغياب مفاتيح التشفير تُخزَّن أرقام الهوية نصاً صريحاً مع تحذير في السجل.
بغياب `RLS_ENFORCE` تبقى سياسات العزل موجودة لكن غير سارية.

### اختيارية

| المتغيّر | الغرض | الافتراضي |
|---|---|---|
| `STRICT_MIGRATIONS` | `1` يوقف الإقلاع عند فشل أي ترحيل | مطفأ |
| `REDIS_URL` | تخزين الجلسات | ذاكرة العملية |
| `SENTRY_DSN` | تتبّع الأخطاء | معطّل |
| `MAX_PG_CONN` | حجم مجمّع الاتصالات | `20` |
| `PORT` | منفذ الخادم | `5050` |

---

## الأمان — كيف يعمل العزل

خمس طبقات، الحاسمة منها الثالثة:

1. **التطبيق** — شرط `client_id` في كل استعلام
2. **سياق الجلسة** — `app.tenant_id` يُربط بكل اتصال يُستعار من المجمّع
3. **قاعدة البيانات** — سياسات RLS على 65 جدولاً
4. **الدور** — استعلامات المستأجرين تُنفَّذ بـ `dheuof_app` بأقل امتيازات
5. **طرق العرض** — `security_invoker = true` فلا تتجاوز السياسات

الطبقة الأولى تحمي من الأخطاء العادية لا من الخطأ البرمجي نفسه. RLS هي
ما يجعل استعلاماً نُسي فيه الشرط يُعيد صفراً بدل بيانات منشأة أخرى.

التفاصيل وإجراء التفعيل في
[`specs/db/06-security-and-scale.md`](specs/db/06-security-and-scale.md).

---

## الاختبارات

```bash
pytest tests/ --ignore=tests/e2e          # يحتاج DATABASE_URL
ruff check . --select=E,F,W --ignore=E501
```

يُشغَّل CI الاختبارات في وضعَي العزل معاً (`RLS_ENFORCE` مطفأ ومُفعَّل).

---

## بنية المشروع

```
main.py            نقطة الدخول لـ uvicorn
main1.py           التطبيق والجلسات وكلمات المرور والترحيلات
main2.py           مسارات الإدارة والمنشآت
routes/            وحدات المنصة (استقبال، تدبير، محاسبة، نقاط بيع…)
services/          خدمات مساندة (ZATCA، قنوات، تسعير، كاش)
db/
  connection.py    مجمّع الاتصالات + ربط سياق المستأجر
  tenant_context.py سياق المستأجر الحالي
  sqlsplit.py      تقسيم نصوص SQL بأمان
  passwords.py     Argon2id
  crypto.py        تشفير حقول الهوية + الفهرس الأعمى
  schema_v3.py     المخطط والترحيلات والعزل وطرق العرض
specs/db/          وثائق التصميم وملفات SQL
```

---

## الوثائق

| الملف | المحتوى |
|---|---|
| [`hotel-system-complete-model.md`](specs/db/hotel-system-complete-model.md) | نموذج البيانات الكامل — 15 قسماً |
| [`06-security-and-scale.md`](specs/db/06-security-and-scale.md) | الأمان والتشفير والتوسّع واصطلاحات التسمية |
| [`04-isolation-hardening.sql`](specs/db/04-isolation-hardening.sql) | دوال وجداول العزل |
| [`05-reporting-views.sql`](specs/db/05-reporting-views.sql) | طرق العرض التقريرية |
