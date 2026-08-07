# نموذج قاعدة البيانات الكامل — منصة ضيوف المتكاملة
## لإدارة الفنادق والشقق المخدومة

> **نظام RDBMS المستخدم:** PostgreSQL 15+  
> **نمط الهيكل:** Multi-tenant SaaS مع عزل البيانات عبر `client_id`  
> **مستوى التطبيع:** 3NF مع استثناءات أداء مبررة  
> **تاريخ الإصدار:** 2026-06-01

---

## القسم الأول: وصف عام للنظام

### 1.1 الهدف الإداري

**منصة ضيوف** هي منصة SaaS متعددة المستأجرين (Multi-tenant) لإدارة الفنادق والشقق المخدومة. تتيح لكل منشأة فندقية امتلاك بيئة عمل مستقلة تمامًا، مع إدارة مركزية لجميع المنشآت من لوحة تحكم موحدة.

**الوظيفة الجوهرية:**
- إدارة الغرف والوحدات (تسجيل دخول/خروج، حالة الغرف)
- إدارة الضيوف والحجوزات (Bookings & Reservations)
- التسوية المالية (الفواتير، المدفوعات، الإيرادات)
- التدبير المنزلي / Housekeeping
- نقطة البيع (مطعم، كافيه، خدمات إضافية)
- المخزن والمشتريات
- التسويق والإحالات
- التقارير الإدارية ومؤشرات الأداء KPI

### 1.2 المستخدمون الرئيسيون

| الدور | الوصف |
|---|---|
| `super_admin` | مدير النظام (الشركة المطورة) — صلاحية كاملة على جميع المنشآت |
| `facility_manager` | مدير المنشأة — صلاحية كاملة داخل منشأته |
| `receptionist` | موظف استقبال — حجوزات، دخول/خروج، فواتير |
| `housekeeping_staff` | موظف التدبير المنزلي — مهام التنظيف والصيانة |
| `pos_cashier` | أمين الصندوق — طلبات POS والمدفوعات |
| `warehouse_staff` | أمين المخزن — استلام وصرف البضائع |
| `accountant` | المحاسب — تقارير مالية، مراجعة الفواتير |

### 1.3 الأقسام الإدارية المرتبطة

1. الاستقبال (Front Desk)
2. التدبير المنزلي (Housekeeping)
3. نقطة البيع - مطعم/كافيه (POS)
4. المخزن والمشتريات (Warehouse)
5. الحسابات والمالية (Finance)
6. التسويق والمبيعات (Marketing)
7. الصيانة (Maintenance)
8. الإدارة العليا (Management)

### 1.4 المشكلات التي يحلها النظام

- فوضى السجلات الورقية → سجلات رقمية مركزية بصلاحيات
- عدم معرفة حالة الغرف في الوقت الفعلي → لوحة حالة غرف لحظية
- ضياع بيانات الضيوف → ملف ضيف شامل مع تاريخ كامل
- صعوبة متابعة التدبير المنزلي → نظام مهام مع تتبع الموظف
- عدم ربط المبيعات بالفواتير → نظام POS مرتبط بالحجز
- ضعف الرقابة المالية → تقارير إيراد تفصيلية وسجل تدقيق

---

## القسم الثاني: الكيانات الرئيسية (Entities)

### الكيانات الأساسية:

| # | اسم الكيان | الوصف |
|---|---|---|
| 1 | **Clients** | المنشآت (فنادق/شقق) المشتركة في المنصة |
| 2 | **Subscription Plans** | خطط الاشتراك (شهري/سنوي/مخصص) |
| 3 | **Subscriptions** | اشتراك كل منشأة في خطة معينة |
| 4 | **Modules** | وحدات النظام M01–M17 |
| 5 | **Client Modules** | الوحدات المفعّلة لكل منشأة |
| 6 | **Users** | المستخدمون (مدراء + موظفون) |
| 7 | **User Roles** | أدوار المستخدمين |
| 8 | **Role Permissions** | صلاحيات كل دور |
| 9 | **Room Types** | أنواع الغرف (standard, suite, apartment…) |
| 10 | **Rooms** | الغرف والوحدات السكنية |
| 11 | **Amenities** | المرافق والخدمات المتاحة في الغرفة |
| 12 | **Guests** | الضيوف والنزلاء |
| 13 | **Guest Documents** | وثائق الضيوف (هوية، جواز) |
| 14 | **Bookings** | الحجوزات |
| 15 | **Booking Guests** | الضيوف في كل حجز (M:M) |
| 16 | **Booking Services** | خدمات إضافية مضافة للحجز |
| 17 | **Invoices** | الفواتير |
| 18 | **Invoice Items** | بنود الفاتورة |
| 19 | **Payments** | المدفوعات |
| 20 | **Housekeeping Tasks** | مهام التدبير المنزلي |
| 21 | **Room Inspections** | سجلات فحص الغرف |
| 22 | **Maintenance Requests** | طلبات الصيانة |
| 23 | **POS Categories** | تصنيفات منتجات POS |
| 24 | **POS Items** | منتجات/خدمات POS |
| 25 | **POS Orders** | طلبات POS |
| 26 | **POS Order Items** | بنود طلب POS |
| 27 | **Inventory Categories** | تصنيفات المخزن |
| 28 | **Inventory Items** | أصناف المخزن |
| 29 | **Inventory Transactions** | حركات الدخول/الخروج |
| 30 | **Suppliers** | الموردون |
| 31 | **Purchase Orders** | أوامر الشراء |
| 32 | **Purchase Order Items** | بنود أوامر الشراء |
| 33 | **Marketers** | المسوّقون والشركاء التجاريون |
| 34 | **Marketer Referrals** | عملاء جاءوا عبر إحالة مسوّق |
| 35 | **Referral Commissions** | عمولات الإحالة |
| 36 | **Audit Log** | سجل التدقيق والأنشطة الحساسة |
| 37 | **System Notifications** | الإشعارات الداخلية |
| 38 | **Branches** | الفروع (إن وجدت لكل منشأة) |

---

## القسم الثالث: بناء الجداول (Tables)

---

### 3.1 جدول: `clients` — المنشآت المشتركة

**الوصف:** يمثل كل منشأة فندقية أو شقق مخدومة مشتركة في المنصة.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف الداخلي |
| `public_id` | UUID DEFAULT gen_random_uuid() | ✓ | — | — | المعرف العلني |
| `name` | VARCHAR(200) | ✓ | — | — | اسم المنشأة |
| `name_en` | VARCHAR(200) | — | — | — | الاسم بالإنجليزية |
| `facility_type` | VARCHAR(50) | ✓ | — | — | hotel / serviced_apartment / resort |
| `email` | VARCHAR(255) | ✓ | — | — | البريد الإلكتروني (UNIQUE) |
| `phone` | VARCHAR(20) | ✓ | — | — | رقم الهاتف |
| `address` | TEXT | — | — | — | العنوان |
| `city` | VARCHAR(100) | — | — | — | المدينة |
| `country` | VARCHAR(100) | — | — | — | الدولة |
| `timezone` | VARCHAR(50) | — | — | — | المنطقة الزمنية |
| `logo_url` | TEXT | — | — | — | رابط الشعار |
| `tax_number` | VARCHAR(50) | — | — | — | الرقم الضريبي |
| `star_rating` | SMALLINT | — | — | — | تصنيف النجوم 1–5 |
| `enabled_modules` | JSONB | — | — | — | الوحدات المفعّلة |
| `plan_id` | INTEGER | — | — | `subscription_plans.id` | خطة الاشتراك الحالية |
| `status` | VARCHAR(20) DEFAULT 'active' | ✓ | — | — | active / suspended / cancelled |
| `registered_by_ref` | VARCHAR(20) | — | — | `marketers.ref_code` | كود الإحالة عند التسجيل |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | تاريخ الإنشاء |
| `updated_at` | TIMESTAMPTZ | — | — | — | آخر تحديث |

**القيود:**
- `UNIQUE(email)`
- `CHECK(star_rating BETWEEN 1 AND 5)`
- `CHECK(status IN ('active','suspended','cancelled','trial'))`
- `CHECK(facility_type IN ('hotel','serviced_apartment','resort','hostel','motel'))`

---

### 3.2 جدول: `subscription_plans` — خطط الاشتراك

**الوصف:** خطط الاشتراك المتاحة في المنصة.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `name` | VARCHAR(100) | ✓ | — | — | اسم الخطة (Starter, Pro, Enterprise) |
| `price_monthly` | NUMERIC(10,2) | ✓ | — | — | السعر الشهري |
| `price_yearly` | NUMERIC(10,2) | — | — | — | السعر السنوي |
| `max_rooms` | INTEGER | — | — | — | الحد الأقصى للغرف (NULL = غير محدود) |
| `max_users` | INTEGER | — | — | — | الحد الأقصى للمستخدمين |
| `allowed_modules` | JSONB | — | — | — | الوحدات المتاحة في هذه الخطة |
| `features` | JSONB | — | — | — | ميزات الخطة |
| `is_active` | BOOLEAN DEFAULT TRUE | ✓ | — | — | هل الخطة نشطة |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | تاريخ الإنشاء |

---

### 3.3 جدول: `subscriptions` — الاشتراكات

**الوصف:** سجل الاشتراكات لكل منشأة (التاريخ الكامل).

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `plan_id` | INTEGER | ✓ | — | `subscription_plans.id` | الخطة |
| `status` | VARCHAR(20) | ✓ | — | — | active / expired / cancelled / trial |
| `billing_cycle` | VARCHAR(10) | ✓ | — | — | monthly / yearly |
| `start_date` | DATE | ✓ | — | — | تاريخ بدء الاشتراك |
| `end_date` | DATE | ✓ | — | — | تاريخ انتهاء الاشتراك |
| `amount_paid` | NUMERIC(10,2) | — | — | — | المبلغ المدفوع |
| `payment_reference` | VARCHAR(100) | — | — | — | مرجع الدفع |
| `notes` | TEXT | — | — | — | ملاحظات |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | تاريخ الإنشاء |

---

### 3.4 جدول: `modules` — وحدات النظام

**الوصف:** تعريف الوحدات الوظيفية المتاحة في المنصة M01–M17.

| الحقل | النوع | إلزامي | PK | وصف |
|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | المعرف |
| `code` | VARCHAR(10) | ✓ | — | M01, M02… |
| `name_ar` | VARCHAR(100) | ✓ | — | الاسم بالعربية |
| `name_en` | VARCHAR(100) | ✓ | — | الاسم بالإنجليزية |
| `description` | TEXT | — | — | وصف الوحدة |
| `is_core` | BOOLEAN DEFAULT FALSE | ✓ | — | وحدة أساسية لا يمكن إيقافها |
| `sort_order` | SMALLINT | — | — | ترتيب العرض |

**القيود:** `UNIQUE(code)`

---

### 3.5 جدول: `users` — المستخدمون

**الوصف:** جميع مستخدمي النظام (super admins + مدراء منشآت + موظفون).

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `public_id` | UUID DEFAULT gen_random_uuid() | ✓ | — | — | المعرف العلني |
| `client_id` | INTEGER | — | — | `clients.id` | المنشأة (NULL للـ super_admin) |
| `branch_id` | INTEGER | — | — | `branches.id` | الفرع (اختياري) |
| `email` | VARCHAR(255) | ✓ | — | — | البريد (UNIQUE) |
| `phone` | VARCHAR(20) | — | — | — | الهاتف |
| `full_name` | VARCHAR(200) | ✓ | — | — | الاسم الكامل |
| `password_hash` | VARCHAR(255) | ✓ | — | — | كلمة المرور المُجزّأة (Argon2id) |
| `role` | VARCHAR(50) | ✓ | — | — | super_admin / facility_manager / receptionist… |
| `is_active` | BOOLEAN DEFAULT TRUE | ✓ | — | — | هل الحساب نشط |
| `last_login_at` | TIMESTAMPTZ | — | — | — | آخر تسجيل دخول |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | تاريخ الإنشاء |
| `created_by` | INTEGER | — | — | `users.id` | أنشأه |
| `updated_at` | TIMESTAMPTZ | — | — | — | آخر تعديل |

**القيود:**
- `UNIQUE(email)`
- `CHECK(role IN ('super_admin','facility_manager','receptionist','housekeeping_staff','pos_cashier','warehouse_staff','accountant'))`

**ملاحظة أمنية:** تُجزَّأ كلمات المرور بـ Argon2id (ذاكرة 19 ميبي، جولتان، تفرّع 1 — توصية OWASP) بملح عشوائي فريد مضمَّن في الهاش. لا تُخزَّن أبدًا كنص صريح. التنفيذ في `db/passwords.py`، والهاش موسوم بخوارزميته فتتم الترقية مستقبلاً دون إجبار المستخدمين على تغيير كلمات مرورهم.

---

### 3.6 جدول: `role_permissions` — صلاحيات الأدوار

**الوصف:** تحديد ما يستطيع كل دور فعله لكل موارد النظام.

| الحقل | النوع | إلزامي | PK | وصف |
|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | المعرف |
| `role` | VARCHAR(50) | ✓ | — | اسم الدور |
| `resource` | VARCHAR(100) | ✓ | — | المورد (bookings, invoices, rooms…) |
| `can_create` | BOOLEAN DEFAULT FALSE | ✓ | — | صلاحية الإنشاء |
| `can_read` | BOOLEAN DEFAULT FALSE | ✓ | — | صلاحية الاطلاع |
| `can_update` | BOOLEAN DEFAULT FALSE | ✓ | — | صلاحية التعديل |
| `can_delete` | BOOLEAN DEFAULT FALSE | ✓ | — | صلاحية الحذف |
| `can_approve` | BOOLEAN DEFAULT FALSE | ✓ | — | صلاحية الاعتماد |
| `can_export` | BOOLEAN DEFAULT FALSE | ✓ | — | صلاحية التصدير |

**القيود:** `UNIQUE(role, resource)`

---

### 3.7 جدول: `branches` — الفروع

**الوصف:** الفروع أو المباني المنفصلة لنفس المنشأة.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `name` | VARCHAR(150) | ✓ | — | — | اسم الفرع |
| `address` | TEXT | — | — | — | العنوان |
| `phone` | VARCHAR(20) | — | — | — | الهاتف |
| `is_active` | BOOLEAN DEFAULT TRUE | ✓ | — | — | نشط |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | تاريخ الإنشاء |

---

### 3.8 جدول: `room_types` — أنواع الغرف

**الوصف:** تصنيف أنواع الغرف مع التسعير الأساسي.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `name` | VARCHAR(100) | ✓ | — | — | الاسم (غرفة مفردة، جناح…) |
| `code` | VARCHAR(20) | ✓ | — | — | الكود المختصر |
| `description` | TEXT | — | — | — | الوصف |
| `base_price_night` | NUMERIC(10,2) | ✓ | — | — | السعر الأساسي لليلة |
| `base_price_month` | NUMERIC(10,2) | — | — | — | السعر الشهري (للشقق) |
| `max_occupancy` | SMALLINT | — | — | — | الحد الأقصى للأشخاص |
| `bed_type` | VARCHAR(50) | — | — | — | نوع السرير |
| `size_sqm` | NUMERIC(6,2) | — | — | — | المساحة بالمتر المربع |
| `is_active` | BOOLEAN DEFAULT TRUE | ✓ | — | — | نشط |

---

### 3.9 جدول: `rooms` — الغرف والوحدات

**الوصف:** سجل كل غرفة أو وحدة سكنية في المنشأة.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `branch_id` | INTEGER | — | — | `branches.id` | الفرع |
| `room_number` | VARCHAR(20) | ✓ | — | — | رقم الغرفة |
| `room_type_id` | INTEGER | ✓ | — | `room_types.id` | نوع الغرفة |
| `floor` | SMALLINT | — | — | — | رقم الطابق |
| `building` | VARCHAR(50) | — | — | — | المبنى |
| `status` | VARCHAR(30) DEFAULT 'available' | ✓ | — | — | available/occupied/cleaning/maintenance/blocked |
| `is_active` | BOOLEAN DEFAULT TRUE | ✓ | — | — | نشط |
| `current_booking_id` | INTEGER | — | — | `bookings.id` | الحجز الحالي |
| `current_guest` | VARCHAR(200) | — | — | — | اسم الضيف الحالي (للعرض السريع) |
| `checkout_due` | DATE | — | — | — | موعد تسليم الغرفة |
| `last_action_by` | VARCHAR(200) | — | — | — | آخر موظف أجرى عملية |
| `last_action_at` | TIMESTAMPTZ | — | — | — | توقيت آخر عملية |
| `notes` | TEXT | — | — | — | ملاحظات |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | تاريخ الإنشاء |

**القيود:**
- `UNIQUE(client_id, room_number)`
- `CHECK(status IN ('available','occupied','cleaning','maintenance','blocked','reserved'))`

**فهارس:** `(client_id, status)`, `(client_id, room_number)`

---

### 3.10 جدول: `amenities` — المرافق والخدمات

**الوصف:** قائمة المرافق المتاحة في الغرف (واي فاي، جاكوزي، شرفة…).

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `name_ar` | VARCHAR(100) | ✓ | — | — | الاسم بالعربية |
| `name_en` | VARCHAR(100) | — | — | — | الاسم بالإنجليزية |
| `icon` | VARCHAR(50) | — | — | — | أيقونة CSS/SVG |

---

### 3.11 جدول: `room_amenities` — مرافق الغرف (M:M)

**الوصف:** جدول وسيط يربط الغرف بمرافقها.

| الحقل | النوع | إلزامي | PK | FK |
|---|---|---|---|---|
| `room_id` | INTEGER | ✓ | (PK) | `rooms.id` |
| `amenity_id` | INTEGER | ✓ | (PK) | `amenities.id` |

---

### 3.12 جدول: `guests` — الضيوف والنزلاء

**الوصف:** ملف الضيف الشامل مع تاريخ كامل.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `full_name` | VARCHAR(200) | ✓ | — | — | الاسم الكامل |
| `full_name_en` | VARCHAR(200) | — | — | — | الاسم بالإنجليزية |
| `nationality` | VARCHAR(100) | — | — | — | الجنسية |
| `id_type` | VARCHAR(30) | — | — | — | national_id / passport / iqama |
| `id_number` | VARCHAR(50) | — | — | — | رقم الهوية |
| `id_expiry` | DATE | — | — | — | تاريخ انتهاء الوثيقة |
| `gender` | VARCHAR(10) | — | — | — | male / female |
| `birth_date` | DATE | — | — | — | تاريخ الميلاد |
| `phone` | VARCHAR(20) | — | — | — | رقم الهاتف |
| `email` | VARCHAR(255) | — | — | — | البريد الإلكتروني |
| `address` | TEXT | — | — | — | العنوان |
| `vip_level` | VARCHAR(20) DEFAULT 'regular' | — | — | — | regular / silver / gold / platinum |
| `notes` | TEXT | — | — | — | ملاحظات خاصة |
| `blacklisted` | BOOLEAN DEFAULT FALSE | ✓ | — | — | مدرج في القائمة السوداء |
| `blacklist_reason` | TEXT | — | — | — | سبب الإدراج |
| `total_stays` | INTEGER DEFAULT 0 | — | — | — | إجمالي الإقامات (مُحسَّب) |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | تاريخ الإنشاء |
| `created_by` | INTEGER | — | — | `users.id` | موظف الإدخال |

**القيود:**
- `UNIQUE(client_id, id_type, id_number)` (لا يتكرر رقم الهوية لنفس النوع)
- `CHECK(vip_level IN ('regular','silver','gold','platinum'))`
- `CHECK(gender IN ('male','female','other'))`

**فهارس:** `(client_id, id_number)`, `(client_id, phone)`

---

### 3.13 جدول: `guest_documents` — وثائق الضيوف

**الوصف:** صور وثائق الهوية والجواز.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `guest_id` | INTEGER | ✓ | — | `guests.id` | الضيف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `doc_type` | VARCHAR(30) | ✓ | — | — | front_id / back_id / passport / visa |
| `file_url` | TEXT | ✓ | — | — | رابط الملف |
| `uploaded_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | وقت الرفع |
| `uploaded_by` | INTEGER | — | — | `users.id` | موظف الرفع |

---

### 3.14 جدول: `bookings` — الحجوزات

**الوصف:** سجل الحجوزات الرئيسي — قلب النظام.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `booking_ref` | VARCHAR(30) | ✓ | — | — | رقم الحجز (UNIQUE, مُولَّد) |
| `room_id` | INTEGER | ✓ | — | `rooms.id` | الغرفة |
| `primary_guest_id` | INTEGER | ✓ | — | `guests.id` | الضيف الرئيسي |
| `check_in_date` | DATE | ✓ | — | — | تاريخ الدخول المخطط |
| `check_out_date` | DATE | ✓ | — | — | تاريخ الخروج المخطط |
| `actual_check_in` | TIMESTAMPTZ | — | — | — | وقت الدخول الفعلي |
| `actual_check_out` | TIMESTAMPTZ | — | — | — | وقت الخروج الفعلي |
| `num_adults` | SMALLINT DEFAULT 1 | ✓ | — | — | عدد البالغين |
| `num_children` | SMALLINT DEFAULT 0 | — | — | — | عدد الأطفال |
| `booking_type` | VARCHAR(20) | ✓ | — | — | nightly / monthly / extended |
| `booking_source` | VARCHAR(50) | — | — | — | direct / phone / website / airbnb / booking.com |
| `status` | VARCHAR(30) DEFAULT 'reserved' | ✓ | — | — | reserved/confirmed/checked_in/checked_out/cancelled/no_show |
| `rate_per_night` | NUMERIC(10,2) | ✓ | — | — | السعر المتفق عليه لليلة |
| `total_nights` | SMALLINT | ✓ | — | — | عدد الليالي |
| `total_amount` | NUMERIC(12,2) | ✓ | — | — | الإجمالي |
| `discount_amount` | NUMERIC(10,2) DEFAULT 0 | — | — | — | قيمة الخصم |
| `tax_amount` | NUMERIC(10,2) DEFAULT 0 | — | — | — | قيمة الضريبة |
| `net_amount` | NUMERIC(12,2) | ✓ | — | — | الصافي بعد الخصم والضريبة |
| `special_requests` | TEXT | — | — | — | طلبات خاصة |
| `internal_notes` | TEXT | — | — | — | ملاحظات داخلية |
| `created_by` | INTEGER | — | — | `users.id` | موظف الإنشاء |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | وقت الإنشاء |
| `updated_by` | INTEGER | — | — | `users.id` | آخر محدِّث |
| `updated_at` | TIMESTAMPTZ | — | — | — | وقت التحديث |

**القيود:**
- `UNIQUE(booking_ref)`
- `CHECK(check_out_date > check_in_date)`
- `CHECK(status IN ('reserved','confirmed','checked_in','checked_out','cancelled','no_show'))`
- `CHECK(booking_type IN ('nightly','monthly','extended','hourly'))`

**فهارس:** `(client_id, status)`, `(client_id, room_id, check_in_date)`, `(client_id, primary_guest_id)`

---

### 3.15 جدول: `booking_guests` — ضيوف الحجز (M:M)

**الوصف:** جدول وسيط — حجز واحد يمكن أن يضم ضيوفًا متعددين.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `booking_id` | INTEGER | ✓ | (PK) | `bookings.id` | الحجز |
| `guest_id` | INTEGER | ✓ | (PK) | `guests.id` | الضيف |
| `is_primary` | BOOLEAN DEFAULT FALSE | ✓ | — | — | الضيف الرئيسي |
| `added_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | وقت الإضافة |
| `added_by` | INTEGER | — | — | `users.id` | موظف الإضافة |

---

### 3.16 جدول: `booking_services` — الخدمات الإضافية للحجز

**الوصف:** خدمات إضافية تضاف على الحجز (إفطار، نقل مطار، غسيل…).

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `booking_id` | INTEGER | ✓ | — | `bookings.id` | الحجز |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `service_name` | VARCHAR(200) | ✓ | — | — | اسم الخدمة |
| `quantity` | NUMERIC(8,2) DEFAULT 1 | ✓ | — | — | الكمية |
| `unit_price` | NUMERIC(10,2) | ✓ | — | — | سعر الوحدة |
| `total_price` | NUMERIC(12,2) | ✓ | — | — | الإجمالي |
| `service_date` | DATE | — | — | — | تاريخ الخدمة |
| `added_by` | INTEGER | — | — | `users.id` | موظف الإضافة |
| `added_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | وقت الإضافة |

---

### 3.17 جدول: `invoices` — الفواتير

**الوصف:** فاتورة لكل حجز أو خدمة مستقلة.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `invoice_number` | VARCHAR(30) | ✓ | — | — | رقم الفاتورة (UNIQUE) |
| `booking_id` | INTEGER | — | — | `bookings.id` | الحجز المرتبط |
| `guest_id` | INTEGER | ✓ | — | `guests.id` | الضيف |
| `invoice_date` | DATE | ✓ | — | — | تاريخ الفاتورة |
| `due_date` | DATE | — | — | — | تاريخ الاستحقاق |
| `subtotal` | NUMERIC(12,2) | ✓ | — | — | المجموع قبل الضريبة |
| `discount_amount` | NUMERIC(10,2) DEFAULT 0 | ✓ | — | — | الخصم |
| `tax_rate` | NUMERIC(5,2) DEFAULT 0 | — | — | — | نسبة الضريبة % |
| `tax_amount` | NUMERIC(10,2) DEFAULT 0 | ✓ | — | — | قيمة الضريبة |
| `total_amount` | NUMERIC(12,2) | ✓ | — | — | الإجمالي |
| `amount_paid` | NUMERIC(12,2) DEFAULT 0 | ✓ | — | — | المبلغ المدفوع |
| `balance_due` | NUMERIC(12,2) | ✓ | — | — | الرصيد المستحق |
| `status` | VARCHAR(20) DEFAULT 'pending' | ✓ | — | — | pending/partial/paid/cancelled/refunded |
| `payment_method` | VARCHAR(50) | — | — | — | cash/card/transfer/online |
| `notes` | TEXT | — | — | — | ملاحظات |
| `issued_by` | INTEGER | — | — | `users.id` | موظف الإصدار |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | وقت الإنشاء |

**القيود:**
- `UNIQUE(client_id, invoice_number)`
- `CHECK(status IN ('pending','partial','paid','cancelled','refunded'))`
- `CHECK(total_amount >= 0)`

---

### 3.18 جدول: `invoice_items` — بنود الفاتورة

**الوصف:** تفاصيل بنود كل فاتورة.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `invoice_id` | INTEGER | ✓ | — | `invoices.id` | الفاتورة |
| `description` | VARCHAR(500) | ✓ | — | — | الوصف |
| `item_type` | VARCHAR(30) | ✓ | — | — | room / service / pos / other |
| `quantity` | NUMERIC(8,2) | ✓ | — | — | الكمية |
| `unit_price` | NUMERIC(10,2) | ✓ | — | — | سعر الوحدة |
| `discount_pct` | NUMERIC(5,2) DEFAULT 0 | — | — | — | نسبة خصم البند |
| `total_price` | NUMERIC(12,2) | ✓ | — | — | إجمالي البند |

---

### 3.19 جدول: `payments` — المدفوعات

**الوصف:** سجل كل دفعة مرتبطة بفاتورة.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `invoice_id` | INTEGER | ✓ | — | `invoices.id` | الفاتورة |
| `amount` | NUMERIC(12,2) | ✓ | — | — | قيمة الدفع |
| `payment_method` | VARCHAR(50) | ✓ | — | — | cash/card/bank_transfer/online |
| `payment_date` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | وقت الدفع |
| `reference_number` | VARCHAR(100) | — | — | — | رقم المرجع/الإيصال |
| `notes` | TEXT | — | — | — | ملاحظات |
| `received_by` | INTEGER | — | — | `users.id` | موظف الاستلام |

---

### 3.20 جدول: `housekeeping_tasks` — مهام التدبير المنزلي

**الوصف:** مهام التنظيف والإعداد المرتبطة بالغرف.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `room_id` | INTEGER | ✓ | — | `rooms.id` | الغرفة |
| `booking_id` | INTEGER | — | — | `bookings.id` | الحجز المرتبط |
| `task_type` | VARCHAR(50) | ✓ | — | — | checkout_clean/daily_clean/deep_clean/turndown/inspection |
| `status` | VARCHAR(20) DEFAULT 'pending' | ✓ | — | — | pending/in_progress/done/skipped |
| `priority` | VARCHAR(20) DEFAULT 'normal' | — | — | — | low/normal/high/urgent |
| `assigned_to` | INTEGER | — | — | `users.id` | الموظف المكلف |
| `assigned_at` | TIMESTAMPTZ | — | — | — | وقت التكليف |
| `started_at` | TIMESTAMPTZ | — | — | — | وقت البداية |
| `completed_at` | TIMESTAMPTZ | — | — | — | وقت الانتهاء |
| `notes` | TEXT | — | — | — | ملاحظات |
| `created_by` | VARCHAR(200) | — | — | — | اسم الموظف المنشئ |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | وقت الإنشاء |

**فهارس:** `(client_id, status)`, `(client_id, room_id, status)`

---

### 3.21 جدول: `room_actions` — سجل تصرفات الغرف

**الوصف:** تتبع كل عملية تُجرى على غرفة (checkout، تغيير حالة، تنظيف…).

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `room_id` | INTEGER | ✓ | — | `rooms.id` | الغرفة |
| `room_number` | VARCHAR(20) | ✓ | — | — | رقم الغرفة |
| `action_type` | VARCHAR(50) | ✓ | — | — | checkout/check_in/status_change/housekeeping_done |
| `old_status` | VARCHAR(30) | — | — | — | الحالة قبل العملية |
| `new_status` | VARCHAR(30) | — | — | — | الحالة بعد العملية |
| `staff_name` | VARCHAR(200) | ✓ | — | — | اسم الموظف المنفذ |
| `notes` | TEXT | — | — | — | تفاصيل العملية |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | وقت العملية |

---

### 3.22 جدول: `maintenance_requests` — طلبات الصيانة

**الوصف:** تتبع طلبات الصيانة وإصلاح الأعطال.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `room_id` | INTEGER | — | — | `rooms.id` | الغرفة (اختياري — قد يكون منطقة عامة) |
| `location` | VARCHAR(200) | — | — | — | الموقع (إذا لم تكن غرفة) |
| `issue_type` | VARCHAR(100) | ✓ | — | — | plumbing/electrical/ac/furniture/other |
| `description` | TEXT | ✓ | — | — | وصف المشكلة |
| `priority` | VARCHAR(20) DEFAULT 'normal' | ✓ | — | — | low/normal/high/urgent |
| `status` | VARCHAR(20) DEFAULT 'open' | ✓ | — | — | open/in_progress/resolved/closed |
| `reported_by` | INTEGER | — | — | `users.id` | من أبلغ |
| `assigned_to` | INTEGER | — | — | `users.id` | تكليف |
| `resolved_at` | TIMESTAMPTZ | — | — | — | وقت الإصلاح |
| `resolution_notes` | TEXT | — | — | — | تفاصيل الحل |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | وقت الإبلاغ |

---

### 3.23 جدول: `pos_categories` — تصنيفات POS

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `name` | VARCHAR(100) | ✓ | — | — | اسم التصنيف |
| `sort_order` | SMALLINT DEFAULT 0 | — | — | — | ترتيب العرض |
| `is_active` | BOOLEAN DEFAULT TRUE | ✓ | — | — | نشط |

---

### 3.24 جدول: `pos_items` — منتجات نقطة البيع

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `category_id` | INTEGER | — | — | `pos_categories.id` | التصنيف |
| `name` | VARCHAR(200) | ✓ | — | — | اسم المنتج/الخدمة |
| `sku` | VARCHAR(50) | — | — | — | رمز المنتج |
| `price` | NUMERIC(10,2) | ✓ | — | — | السعر |
| `tax_rate` | NUMERIC(5,2) DEFAULT 0 | — | — | — | نسبة الضريبة |
| `is_active` | BOOLEAN DEFAULT TRUE | ✓ | — | — | متاح |
| `deduct_inventory` | BOOLEAN DEFAULT FALSE | — | — | — | هل يُخصم من المخزن |
| `inventory_item_id` | INTEGER | — | — | `inventory_items.id` | الصنف المخزني المرتبط |

---

### 3.25 جدول: `pos_orders` — طلبات POS

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `order_number` | VARCHAR(30) | ✓ | — | — | رقم الطلب |
| `booking_id` | INTEGER | — | — | `bookings.id` | الحجز المرتبط |
| `guest_id` | INTEGER | — | — | `guests.id` | الضيف |
| `table_number` | VARCHAR(20) | — | — | — | رقم الطاولة |
| `order_type` | VARCHAR(30) | ✓ | — | — | dine_in/room_service/takeaway |
| `status` | VARCHAR(20) DEFAULT 'open' | ✓ | — | — | open/preparing/ready/served/paid/cancelled |
| `subtotal` | NUMERIC(12,2) | ✓ | — | — | المجموع |
| `discount` | NUMERIC(10,2) DEFAULT 0 | — | — | — | الخصم |
| `tax_amount` | NUMERIC(10,2) DEFAULT 0 | — | — | — | الضريبة |
| `total` | NUMERIC(12,2) | ✓ | — | — | الإجمالي |
| `payment_method` | VARCHAR(30) | — | — | — | طريقة الدفع |
| `bill_to_room` | BOOLEAN DEFAULT FALSE | — | — | — | يُضاف لفاتورة الغرفة |
| `cashier_id` | INTEGER | — | — | `users.id` | الكاشير |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | وقت الطلب |

---

### 3.26 جدول: `pos_order_items` — بنود طلب POS

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `order_id` | INTEGER | ✓ | — | `pos_orders.id` | الطلب |
| `item_id` | INTEGER | ✓ | — | `pos_items.id` | المنتج |
| `item_name` | VARCHAR(200) | ✓ | — | — | اسم المنتج (نسخة ثابتة) |
| `quantity` | NUMERIC(8,2) | ✓ | — | — | الكمية |
| `unit_price` | NUMERIC(10,2) | ✓ | — | — | سعر الوحدة وقت البيع |
| `total_price` | NUMERIC(12,2) | ✓ | — | — | الإجمالي |
| `notes` | TEXT | — | — | — | ملاحظات البند |

---

### 3.27 جدول: `suppliers` — الموردون

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `name` | VARCHAR(200) | ✓ | — | — | اسم المورد |
| `contact_name` | VARCHAR(150) | — | — | — | اسم جهة الاتصال |
| `phone` | VARCHAR(20) | — | — | — | الهاتف |
| `email` | VARCHAR(255) | — | — | — | البريد |
| `address` | TEXT | — | — | — | العنوان |
| `tax_number` | VARCHAR(50) | — | — | — | الرقم الضريبي |
| `category` | VARCHAR(100) | — | — | — | تصنيف المورد |
| `is_active` | BOOLEAN DEFAULT TRUE | ✓ | — | — | نشط |
| `notes` | TEXT | — | — | — | ملاحظات |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | تاريخ الإنشاء |

---

### 3.28 جدول: `inventory_categories` — تصنيفات المخزن

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `name` | VARCHAR(100) | ✓ | — | — | اسم التصنيف |
| `description` | TEXT | — | — | — | الوصف |

---

### 3.29 جدول: `inventory_items` — أصناف المخزن

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `category_id` | INTEGER | — | — | `inventory_categories.id` | التصنيف |
| `name` | VARCHAR(200) | ✓ | — | — | اسم الصنف |
| `sku` | VARCHAR(50) | — | — | — | الرمز |
| `unit` | VARCHAR(30) | ✓ | — | — | وحدة القياس (قطعة، كيلو، لتر…) |
| `current_stock` | NUMERIC(12,2) DEFAULT 0 | ✓ | — | — | الكمية الحالية |
| `min_stock` | NUMERIC(12,2) DEFAULT 0 | — | — | — | الحد الأدنى للتنبيه |
| `unit_cost` | NUMERIC(10,2) | — | — | — | تكلفة الوحدة |
| `preferred_supplier_id` | INTEGER | — | — | `suppliers.id` | المورد المفضل |
| `is_active` | BOOLEAN DEFAULT TRUE | ✓ | — | — | نشط |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | تاريخ الإنشاء |

**القيود:** `UNIQUE(client_id, sku)` (عند وجود SKU)

---

### 3.30 جدول: `inventory_transactions` — حركات المخزن

**الوصف:** كل عملية دخول أو خروج من المخزن.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `item_id` | INTEGER | ✓ | — | `inventory_items.id` | الصنف |
| `transaction_type` | VARCHAR(20) | ✓ | — | — | in/out/adjustment/waste |
| `quantity` | NUMERIC(12,2) | ✓ | — | — | الكمية |
| `unit_cost` | NUMERIC(10,2) | — | — | — | تكلفة الوحدة |
| `total_cost` | NUMERIC(12,2) | — | — | — | الإجمالي |
| `reference_type` | VARCHAR(30) | — | — | — | purchase_order/pos_order/manual |
| `reference_id` | INTEGER | — | — | — | مرجع العملية |
| `notes` | TEXT | — | — | — | ملاحظات |
| `performed_by` | INTEGER | — | — | `users.id` | المنفذ |
| `transaction_date` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | وقت العملية |

---

### 3.31 جدول: `purchase_orders` — أوامر الشراء

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | ✓ | — | `clients.id` | المنشأة |
| `po_number` | VARCHAR(30) | ✓ | — | — | رقم أمر الشراء |
| `supplier_id` | INTEGER | ✓ | — | `suppliers.id` | المورد |
| `status` | VARCHAR(20) DEFAULT 'draft' | ✓ | — | — | draft/sent/received/partial/cancelled |
| `order_date` | DATE | ✓ | — | — | تاريخ الأمر |
| `expected_date` | DATE | — | — | — | تاريخ الاستلام المتوقع |
| `total_amount` | NUMERIC(12,2) | — | — | — | الإجمالي |
| `notes` | TEXT | — | — | — | ملاحظات |
| `created_by` | INTEGER | — | — | `users.id` | المنشئ |
| `approved_by` | INTEGER | — | — | `users.id` | المعتمد |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | وقت الإنشاء |

---

### 3.32 جدول: `marketers` — المسوّقون

**الوصف:** الشركاء والمسوّقون الذين يحيلون عملاء جدد للمنصة.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `name` | VARCHAR(200) | ✓ | — | — | الاسم |
| `email` | VARCHAR(255) | ✓ | — | — | البريد (UNIQUE) |
| `phone` | VARCHAR(20) | — | — | — | الهاتف |
| `ref_code` | VARCHAR(20) | ✓ | — | — | كود الإحالة (UNIQUE) |
| `commission_rate` | NUMERIC(5,2) DEFAULT 10.0 | ✓ | — | — | نسبة العمولة % |
| `commission_type` | VARCHAR(20) DEFAULT 'percentage' | ✓ | — | — | percentage / fixed |
| `status` | VARCHAR(20) DEFAULT 'active' | ✓ | — | — | active/suspended/inactive |
| `total_referrals` | INTEGER DEFAULT 0 | — | — | — | عدد الإحالات (مُحسَّب) |
| `total_earnings` | NUMERIC(12,2) DEFAULT 0 | — | — | — | إجمالي الأرباح (مُحسَّب) |
| `bank_details` | JSONB | — | — | — | بيانات التحويل البنكي |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | تاريخ الإنشاء |

**القيود:** `UNIQUE(email)`, `UNIQUE(ref_code)`

---

### 3.33 جدول: `marketer_referrals` — إحالات المسوّقين

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | SERIAL | ✓ | ✓ | — | المعرف |
| `marketer_id` | INTEGER | ✓ | — | `marketers.id` | المسوّق |
| `client_id` | INTEGER | ✓ | — | `clients.id` | العميل المُحال |
| `ref_code_used` | VARCHAR(20) | ✓ | — | — | الكود المستخدم |
| `commission_earned` | NUMERIC(10,2) | — | — | — | العمولة المستحقة |
| `commission_paid` | BOOLEAN DEFAULT FALSE | ✓ | — | — | هل دُفعت |
| `paid_at` | TIMESTAMPTZ | — | — | — | وقت الدفع |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | وقت الإحالة |

**القيود:** `UNIQUE(client_id)` — كل عميل له إحالة واحدة فقط

---

### 3.34 جدول: `audit_log` — سجل التدقيق

**الوصف:** سجل غير قابل للتعديل لجميع العمليات الحساسة.

| الحقل | النوع | إلزامي | PK | FK | وصف |
|---|---|---|---|---|---|
| `id` | BIGSERIAL | ✓ | ✓ | — | المعرف |
| `client_id` | INTEGER | — | — | `clients.id` | المنشأة |
| `user_id` | INTEGER | — | — | `users.id` | المستخدم |
| `user_email` | VARCHAR(255) | — | — | — | البريد (نسخة ثابتة) |
| `action` | VARCHAR(100) | ✓ | — | — | CREATE/UPDATE/DELETE/LOGIN/LOGOUT |
| `resource_type` | VARCHAR(100) | ✓ | — | — | booking/invoice/user/room… |
| `resource_id` | TEXT | — | — | — | معرف المورد |
| `old_values` | JSONB | — | — | — | القيم القديمة |
| `new_values` | JSONB | — | — | — | القيم الجديدة |
| `ip_address` | INET | — | — | — | عنوان IP |
| `user_agent` | TEXT | — | — | — | معلومات المتصفح |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | ✓ | — | — | وقت الحدث |

**ملاحظة:** هذا الجدول محمي بـ trigger يمنع UPDATE و DELETE — للإضافة فقط (append-only).

---

## القسم الرابع: قاموس البيانات (Data Dictionary) — مختصر

| الجدول | الحقل | الوصف | النوع | الطول | إلزامي | PK | FK | القيم المسموحة |
|---|---|---|---|---|---|---|---|---|
| clients | id | المعرف الداخلي | SERIAL | — | ✓ | ✓ | — | — |
| clients | email | البريد الإلكتروني | VARCHAR | 255 | ✓ | — | — | UNIQUE، يقبل @ |
| clients | status | حالة الحساب | VARCHAR | 20 | ✓ | — | — | active/suspended/cancelled/trial |
| clients | facility_type | نوع المنشأة | VARCHAR | 50 | ✓ | — | — | hotel/serviced_apartment/resort |
| rooms | room_number | رقم الغرفة | VARCHAR | 20 | ✓ | — | — | UNIQUE per client |
| rooms | status | حالة الغرفة | VARCHAR | 30 | ✓ | — | — | available/occupied/cleaning/maintenance |
| bookings | booking_ref | رقم الحجز | VARCHAR | 30 | ✓ | — | — | UNIQUE، مُولَّد تلقائيًا |
| bookings | status | حالة الحجز | VARCHAR | 30 | ✓ | — | — | reserved/confirmed/checked_in/checked_out/cancelled |
| bookings | check_out_date | تاريخ الخروج | DATE | — | ✓ | — | — | > check_in_date |
| guests | id_number | رقم الهوية | VARCHAR | 50 | — | — | — | UNIQUE per client per id_type |
| guests | vip_level | مستوى VIP | VARCHAR | 20 | — | — | — | regular/silver/gold/platinum |
| invoices | status | حالة الفاتورة | VARCHAR | 20 | ✓ | — | — | pending/partial/paid/cancelled |
| invoices | total_amount | إجمالي الفاتورة | NUMERIC | 12,2 | ✓ | — | — | ≥ 0 |
| users | role | دور المستخدم | VARCHAR | 50 | ✓ | — | — | super_admin/facility_manager/receptionist… |
| users | password_hash | كلمة المرور | VARCHAR | 255 | ✓ | — | — | Argon2id hash موسوم |
| marketers | ref_code | كود الإحالة | VARCHAR | 20 | ✓ | — | — | UNIQUE، حروف+أرقام |
| inventory_transactions | transaction_type | نوع الحركة | VARCHAR | 20 | ✓ | — | — | in/out/adjustment/waste |
| audit_log | action | نوع الإجراء | VARCHAR | 100 | ✓ | — | — | CREATE/UPDATE/DELETE/LOGIN |

---

## القسم الخامس: العلاقات بين الجداول (Relationships)

### علاقات واحد إلى متعدد (1:M)

| الجدول الأب | الجدول الابن | الوصف |
|---|---|---|
| `clients` | `users` | كل منشأة لها عدة مستخدمين |
| `clients` | `rooms` | كل منشأة لها عدة غرف |
| `clients` | `bookings` | كل منشأة لها عدة حجوزات |
| `clients` | `guests` | كل منشأة لها عدة ضيوف |
| `clients` | `invoices` | كل منشأة لها عدة فواتير |
| `clients` | `housekeeping_tasks` | كل منشأة لها مهام تدبير |
| `clients` | `inventory_items` | كل منشأة لها مخزن |
| `clients` | `pos_orders` | كل منشأة لها طلبات POS |
| `clients` | `marketers` (عبر referrals) | ← كل عميل جاء من مسوّق |
| `rooms` | `bookings` | كل غرفة لها عدة حجوزات |
| `rooms` | `housekeeping_tasks` | كل غرفة لها مهام تنظيف |
| `rooms` | `room_actions` | كل غرفة لها سجل تصرفات |
| `room_types` | `rooms` | كل نوع غرفة لها عدة غرف |
| `guests` | `bookings` (primary) | ضيف رئيسي لعدة حجوزات |
| `guests` | `guest_documents` | كل ضيف له عدة وثائق |
| `bookings` | `invoice_items` (عبر invoices) | ← الحجز يولد فواتير |
| `bookings` | `booking_services` | كل حجز له خدمات إضافية |
| `bookings` | `housekeeping_tasks` | كل حجز ينتج مهام تنظيف |
| `invoices` | `invoice_items` | كل فاتورة لها بنود |
| `invoices` | `payments` | كل فاتورة لها مدفوعات |
| `pos_orders` | `pos_order_items` | كل طلب له بنود |
| `suppliers` | `purchase_orders` | كل مورد له أوامر شراء |
| `inventory_items` | `inventory_transactions` | كل صنف له حركات |
| `marketers` | `marketer_referrals` | كل مسوّق له إحالات |

### علاقات متعدد إلى متعدد (M:M) — مع الجداول الوسيطة

| الجدول أ | الجدول الوسيط | الجدول ب | الوصف |
|---|---|---|---|
| `bookings` | `booking_guests` | `guests` | حجز واحد = ضيوف متعددون |
| `rooms` | `room_amenities` | `amenities` | غرفة واحدة = مرافق متعددة |
| `subscription_plans` | (عبر client_modules) | `modules` | خطط الاشتراك تحدد الوحدات |

### علاقات واحد إلى واحد (1:1)

| الجدول أ | الجدول ب | الوصف |
|---|---|---|
| `clients` | `marketer_referrals` | كل عميل له إحالة واحدة فقط |
| `bookings` | `rooms` (current) | الغرفة المحجوزة حاليًا |

---

## القسم السادس: مخطط ERD النصي

```
[subscription_plans] 1 ——— * [subscriptions] * ——— 1 [clients]
                                                         |
                    ┌────────────────────────────────────┤
                    |             |              |        |
                    ↓             ↓              ↓        ↓
                [users]       [rooms]        [guests]  [marketers]
                    |             |              |          |
                    |         [room_types]       |     [marketer_referrals]
                    |             |              |
                    └──→[bookings]←─────────────┘
                              |
              ┌───────────────┼──────────────────┐
              ↓               ↓                  ↓
      [booking_guests]  [booking_services]  [invoices]
      (M:M via guests)                          |
                                        ┌───────┴───────┐
                                        ↓               ↓
                                 [invoice_items]   [payments]
                                 
[rooms] 1 ——— * [housekeeping_tasks]
[rooms] 1 ——— * [room_actions]
[rooms] 1 ——— * [maintenance_requests]
[rooms] * ——— * [amenities]  (via room_amenities)

[clients] 1 ——— * [pos_orders] 1 ——— * [pos_order_items] * ——— 1 [pos_items]
[pos_items] * ——— 1 [pos_categories]

[clients] 1 ——— * [inventory_items] 1 ——— * [inventory_transactions]
[inventory_items] * ——— 1 [suppliers]
[suppliers] 1 ——— * [purchase_orders] 1 ——— * [purchase_order_items]

[users] 1 ——— * [audit_log]
[clients] 1 ——— * [branches] 1 ——— * [rooms/users]
```

---

## القسم السابع: التطبيع (Normalization)

### 7.1 المراجعة وفق 1NF

**✅ محقق:** جميع الحقول تحتوي قيمًا ذرية (atomic values).  
**⚠️ ملاحظة:** `enabled_modules` في جدول `clients` من نوع JSONB — استثناء مبرر للأداء في بيئة SaaS متعددة الوحدات. الجدول الوسيط `client_modules` متاح إذا احتجنا استعلامات معقدة.

### 7.2 المراجعة وفق 2NF

**✅ محقق:** في جداول M:M الوسيطة (`booking_guests`, `room_amenities`) لا توجد تبعيات جزئية.  
**تعديل أُجري:** حقل `item_name` في `pos_order_items` مكرر عمدًا من `pos_items.name` — تبرير: حماية السجل التاريخي عند تغيير اسم المنتج.

### 7.3 المراجعة وفق 3NF

**✅ محقق:** لا تبعيات انتقالية.  
**تعديل أُجري:** `total_nights` في `bookings` مُحسَّب من `check_out_date - check_in_date` — استُبقي لأداء الاستعلامات وتأمين السجل التاريخي عند أي تعديل لاحق على التواريخ.  
**تعديل أُجري:** `total_stays` في `guests` و `total_referrals/total_earnings` في `marketers` — حقول مُحسَّبة مُخزَّنة للأداء، تُحدَّث بـ trigger.

### 7.4 التوازن بين التطبيع والأداء

| الحقل المخزَّن | المبرر |
|---|---|
| `rooms.current_guest` | عرض سريع في لوحة حالة الغرف دون JOIN |
| `rooms.checkout_due` | فلترة سريعة للغرف التي تستحق الخروج |
| `pos_order_items.unit_price` | تجميد السعر وقت البيع |
| `bookings.net_amount` | إجمالي محسوب + مخزن للتقارير السريعة |

---

## القسم الثامن: قواعد العمل (Business Rules)

```
BR-01: لا يمكن استخدام النظام دون تسجيل — كل منشأة يجب أن تكون مسجلة كـ client.
BR-02: لا يمكن إنشاء حجز لغرفة حالتها occupied أو maintenance أو blocked.
BR-03: لا يمكن إنشاء فاتورة دون حجز أو ضيف مسجل.
BR-04: لا يمكن تسجيل دخول ضيف مدرج في القائمة السوداء (blacklisted = TRUE).
BR-05: check_out_date يجب أن يكون أكبر من check_in_date بيوم على الأقل.
BR-06: لا يمكن تكرار رقم الغرفة (room_number) لنفس المنشأة.
BR-07: لا يمكن تكرار رقم الهوية من نفس النوع لنفس الضيف في المنشأة.
BR-08: لا يمكن تكرار البريد الإلكتروني للمستخدمين عبر النظام.
BR-09: لا يمكن لمستخدم الوصول لبيانات منشأة غير منشأته (عزل client_id).
BR-10: كلمات المرور تُخزَّن مشفرة فقط — لا يُسمح بتخزين نص صريح.
BR-11: لا يمكن صرف صنف من المخزن إذا كانت current_stock = 0.
BR-12: عند وصول current_stock ≤ min_stock يُرسَل تنبيه لمدير المنشأة.
BR-13: لا يمكن اعتماد أمر شراء إلا من مستخدم بدور facility_manager أو accountant.
BR-14: لا يمكن حذف فاتورة بعد دفعها (status = paid) — يُنشأ إشعار دائن بدلًا.
BR-15: لا يمكن لموظف استقبال حذف سجلات الضيوف — القراءة والتعديل فقط.
BR-16: كود الإحالة (ref_code) فريد لكل مسوّق ولا يمكن تكراره.
BR-17: كل عميل (منشأة) مرتبط بإحالة واحدة فقط — UNIQUE(client_id) في marketer_referrals.
BR-18: سجل التدقيق audit_log للإضافة فقط — لا يُسمح بالتعديل أو الحذف.
BR-19: لا يمكن تفعيل وحدة غير مدرجة في خطة الاشتراك الحالية.
BR-20: عند تسجيل checkout غرفة، يجب تحديد staff_name وتأكيد نظافة الغرفة.
BR-21: الغرفة تنتقل تلقائيًا لحالة cleaning عند checkout الضيف.
BR-22: لا يمكن اعتماد مهمة تدبير منزلي دون تحديد الموظف المكلف.
BR-23: فاتورة POS المضافة لحساب الغرفة (bill_to_room) تظهر تلقائيًا في فاتورة الحجز.
```

---

## القسم التاسع: الصلاحيات والأدوار (Roles & Permissions)

### مصفوفة الصلاحيات الكاملة

| المورد | super_admin | facility_manager | receptionist | housekeeping_staff | pos_cashier | warehouse_staff | accountant |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **clients (المنشآت)** | CRUD + A | R | — | — | — | — | R |
| **users (المستخدمون)** | CRUD | CRUD (منشأته) | R | — | — | — | R |
| **rooms (الغرف)** | CRUD | CRUD | R+U | R+U(status) | R | — | R |
| **guests (الضيوف)** | CRUD | CRUD | CRU | R | — | — | R |
| **bookings (الحجوزات)** | CRUD | CRUD | CRU | R | — | — | R |
| **invoices (الفواتير)** | CRUD | CRUD | CR | — | R | — | CRUD |
| **payments (المدفوعات)** | CRUD | CRUD | CR | — | CR | — | CRUD |
| **housekeeping_tasks** | CRUD | CRUD | CR | RU | — | — | — |
| **pos_orders** | CRUD | CRUD | R | — | CRUD | — | R |
| **inventory_items** | CRUD | CRUD | R | — | R | CRUD | R |
| **purchase_orders** | CRUD | CR+A | — | — | — | CR | CR+A |
| **reports** | ALL | منشأته | محدود | — | POS فقط | مخزن فقط | مالية |
| **audit_log** | R | R (منشأته) | — | — | — | — | R |
| **subscriptions** | CRUD | R | — | — | — | — | — |
| **marketers** | CRUD | — | — | — | — | — | — |
| **modules** | CRUD | R+U (منشأته) | — | — | — | — | — |

> **أسطورة:** C=إنشاء، R=قراءة، U=تعديل، D=حذف، A=اعتماد

---

## القسم العاشر: التقارير الإدارية المتوقعة

### 10.1 تقارير الضيوف والإشغال

| التقرير | الوصف | الجداول المصدر |
|---|---|---|
| تقرير الإشغال اليومي | نسبة الإشغال يوميًا | `rooms`, `bookings` |
| تقرير الوصول والمغادرة | قائمة check-in وcheck-out المتوقعة | `bookings`, `guests` |
| تقرير تاريخ الضيف | إجمالي إقامات ضيف محدد | `bookings`, `booking_guests` |
| تقرير الضيوف VIP | قائمة الضيوف VIP والنزلاء المميزين | `guests` |
| تقرير القائمة السوداء | الضيوف المقيدون | `guests` |
| تقرير أطول إقامة | الضيوف بأعلى فترات إقامة | `bookings` |

### 10.2 التقارير المالية

| التقرير | الوصف | الجداول المصدر |
|---|---|---|
| الإيراد اليومي | إجمالي مدفوعات اليوم | `payments`, `invoices` |
| الإيراد الشهري | إجمالي مدفوعات الشهر مع مقارنة | `payments`, `invoices` |
| الديون المستحقة | الفواتير غير المسددة | `invoices` (status=pending/partial) |
| إيراد POS | مبيعات نقطة البيع | `pos_orders` |
| تقرير الخصومات | إجمالي الخصومات الممنوحة | `invoices`, `bookings` |
| مؤشر RevPAR | الإيراد لكل غرفة متاحة | `bookings`, `rooms`, `invoices` |
| مؤشر ADR | متوسط سعر الليلة | `bookings` |

### 10.3 تقارير التدبير المنزلي

| التقرير | الوصف | الجداول المصدر |
|---|---|---|
| حالة الغرف اللحظية | لوحة حالة جميع الغرف | `rooms` |
| مهام التنظيف المعلقة | مهام لم تُنجز بعد | `housekeeping_tasks` |
| أداء موظفي التدبير | عدد المهام المنجزة لكل موظف | `housekeeping_tasks`, `users` |
| تاريخ الغرفة | جميع عمليات غرفة محددة | `room_actions` |

### 10.4 تقارير المخزن

| التقرير | الوصف | الجداول المصدر |
|---|---|---|
| مخزون منتهٍ أو ناقص | أصناف أقل من الحد الأدنى | `inventory_items` |
| حركة المخزن | دخول وخروج خلال فترة | `inventory_transactions` |
| قيمة المخزون | القيمة المالية الكاملة للمخزن | `inventory_items` |
| أوامر الشراء المعلقة | أوامر لم تستلم | `purchase_orders` |

### 10.5 تقارير التسويق والإحالات

| التقرير | الوصف | الجداول المصدر |
|---|---|---|
| أداء المسوّقين | عدد الإحالات والعمولات لكل مسوّق | `marketers`, `marketer_referrals` |
| العملاء المُحالون | قائمة المنشآت التي جاءت عبر إحالة | `clients`, `marketer_referrals` |
| العمولات المستحقة | عمولات لم تُدفع بعد | `marketer_referrals` |

### 10.6 مؤشرات الأداء KPI

| المؤشر | الصيغة | الجداول |
|---|---|---|
| معدل الإشغال OCC% | (غرف مشغولة / غرف متاحة) × 100 | `rooms`, `bookings` |
| متوسط سعر الليلة ADR | إجمالي إيراد الغرف / عدد الليالي | `bookings` |
| الإيراد لكل غرفة متاحة RevPAR | ADR × OCC% | `bookings`, `rooms` |
| معدل الإلغاء | (حجوزات ملغاة / إجمالي) × 100 | `bookings` |
| متوسط مدة الإقامة ALOS | إجمالي ليالي / عدد حجوزات | `bookings` |
| معدل تكرار الزيارة | ضيوف لهم أكثر من إقامة | `booking_guests`, `guests` |

---

## القسم الحادي عشر: الاستعلامات الأساسية (SQL Queries)

### 11.1 حالة الغرف اللحظية
```sql
SELECT 
    r.room_number,
    rt.name AS room_type,
    r.status,
    r.current_guest,
    r.checkout_due,
    r.last_action_by,
    r.last_action_at
FROM rooms r
JOIN room_types rt ON r.room_type_id = rt.id
WHERE r.client_id = :client_id
  AND r.is_active = TRUE
ORDER BY r.floor, r.room_number;
```

### 11.2 بحث عن ضيف
```sql
SELECT 
    g.id, g.full_name, g.phone, g.id_number, g.nationality,
    g.vip_level, g.total_stays, g.blacklisted,
    MAX(b.check_in_date) AS last_stay
FROM guests g
LEFT JOIN bookings b ON b.primary_guest_id = g.id
WHERE g.client_id = :client_id
  AND (
    g.full_name ILIKE '%' || :q || '%'
    OR g.phone LIKE '%' || :q || '%'
    OR g.id_number LIKE '%' || :q || '%'
  )
GROUP BY g.id
ORDER BY g.total_stays DESC
LIMIT 20;
```

### 11.3 الإيراد الشهري
```sql
SELECT 
    DATE_TRUNC('month', p.payment_date) AS month,
    COUNT(DISTINCT p.invoice_id) AS invoices_count,
    SUM(p.amount) AS total_revenue,
    AVG(p.amount) AS avg_payment,
    STRING_AGG(DISTINCT p.payment_method, ', ') AS payment_methods
FROM payments p
JOIN invoices i ON p.invoice_id = i.id
WHERE i.client_id = :client_id
  AND p.payment_date >= :start_date
  AND p.payment_date < :end_date
GROUP BY DATE_TRUNC('month', p.payment_date)
ORDER BY month;
```

### 11.4 مؤشرات الأداء KPI
```sql
WITH room_stats AS (
    SELECT 
        COUNT(*) FILTER (WHERE status = 'occupied') AS occupied_count,
        COUNT(*) FILTER (WHERE is_active = TRUE)     AS total_rooms
    FROM rooms
    WHERE client_id = :client_id
),
booking_stats AS (
    SELECT
        COUNT(*) AS bookings_count,
        SUM(total_nights) AS total_nights,
        SUM(net_amount) AS total_revenue,
        COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_count
    FROM bookings
    WHERE client_id = :client_id
      AND check_in_date BETWEEN :start_date AND :end_date
)
SELECT
    rs.occupied_count,
    rs.total_rooms,
    ROUND(rs.occupied_count::numeric / NULLIF(rs.total_rooms, 0) * 100, 1) AS occupancy_rate,
    ROUND(bs.total_revenue / NULLIF(bs.total_nights, 0), 2) AS adr,
    ROUND(bs.total_revenue / NULLIF(rs.total_rooms, 0), 2) AS revpar,
    ROUND(bs.cancelled_count::numeric / NULLIF(bs.bookings_count, 0) * 100, 1) AS cancellation_rate,
    ROUND(bs.total_nights::numeric / NULLIF(bs.bookings_count, 0), 1) AS avg_los
FROM room_stats rs, booking_stats bs;
```

### 11.5 الديون المستحقة
```sql
SELECT 
    i.invoice_number,
    g.full_name AS guest_name,
    g.phone,
    b.room_id,
    r.room_number,
    i.total_amount,
    i.amount_paid,
    i.balance_due,
    i.due_date,
    CURRENT_DATE - i.due_date AS days_overdue
FROM invoices i
JOIN guests g ON i.guest_id = g.id
JOIN bookings b ON i.booking_id = b.id
JOIN rooms r ON b.room_id = r.id
WHERE i.client_id = :client_id
  AND i.status IN ('pending', 'partial')
  AND i.balance_due > 0
ORDER BY days_overdue DESC NULLS LAST;
```

### 11.6 أداء المسوّقين
```sql
SELECT 
    m.name AS marketer_name,
    m.ref_code,
    m.commission_rate,
    COUNT(mr.id) AS total_referrals,
    COUNT(mr.id) FILTER (WHERE mr.commission_paid = TRUE) AS paid_referrals,
    SUM(mr.commission_earned) FILTER (WHERE mr.commission_paid = FALSE) AS unpaid_commissions,
    SUM(mr.commission_earned) AS total_earnings
FROM marketers m
LEFT JOIN marketer_referrals mr ON mr.marketer_id = m.id
GROUP BY m.id, m.name, m.ref_code, m.commission_rate
ORDER BY total_referrals DESC;
```

### 11.7 غرف تستحق الخروج اليوم
```sql
SELECT 
    r.room_number,
    g.full_name AS guest_name,
    g.phone,
    b.check_out_date,
    b.booking_ref,
    i.balance_due,
    r.status
FROM bookings b
JOIN rooms r ON b.room_id = r.id
JOIN guests g ON b.primary_guest_id = g.id
LEFT JOIN invoices i ON i.booking_id = b.id AND i.status != 'paid'
WHERE b.client_id = :client_id
  AND b.check_out_date = CURRENT_DATE
  AND b.status = 'checked_in'
ORDER BY r.room_number;
```

### 11.8 تقرير أداء موظفي التدبير
```sql
SELECT 
    u.full_name AS staff_name,
    COUNT(ht.id) AS total_tasks,
    COUNT(ht.id) FILTER (WHERE ht.status = 'done') AS completed_tasks,
    ROUND(COUNT(ht.id) FILTER (WHERE ht.status = 'done')::numeric / 
          NULLIF(COUNT(ht.id), 0) * 100, 1) AS completion_rate,
    ROUND(AVG(EXTRACT(EPOCH FROM (ht.completed_at - ht.started_at))/60) 
          FILTER (WHERE ht.status = 'done'), 0) AS avg_minutes_per_task
FROM housekeeping_tasks ht
JOIN users u ON ht.assigned_to = u.id
WHERE ht.client_id = :client_id
  AND ht.created_at >= :start_date
GROUP BY u.id, u.full_name
ORDER BY completion_rate DESC;
```

---

## القسم الثاني عشر: كود SQL لإنشاء الجداول (DDL)

> ملف DDL الكامل موجود في: `specs/db/hotel-system-ddl.sql`

---

## القسم الثالث عشر: اعتبارات الأمان وجودة البيانات

> 📎 **التفاصيل التشغيلية في [`06-security-and-scale.md`](06-security-and-scale.md):**
> التشفير أثناء النقل والسكون، إدارة المفاتيح وتدويرها، النسخ الاحتياطي
> واختبار الاستعادة، وقائمة ما قبل التسويق. هذا القسم يصف المبادئ،
> والملحق يصف التنفيذ وما لم يُنفَّذ بعد.

### 13.1 حماية كلمات المرور
- تُجزَّأ بـ Argon2id (m=19456 KiB، t=2، p=1 — الحد الأدنى الموصى به من OWASP)
- لا تُخزَّن أبدًا كنص صريح في قاعدة البيانات
- لا تُرسَّل في الاستجابات (API responses)
- بعد تسجيل الدخول تُصدَّر JWT فقط

### 13.2 عزل البيانات (Multi-tenant Isolation)
- كل استعلام يجب أن يحتوي `WHERE client_id = :client_id`
- دالة PostgreSQL `app_tenant()` تُعيد client_id الحالي من إعداد الجلسة
  `app.tenant_id`، ويربطه `DatabasePool` بكل اتصال يُستعار
- **سياسة Row Level Security ليست اختيارية بل الطبقة الحاسمة:** شرط
  `client_id` في الكود يحمي من الأخطاء العادية لا من الخطأ البرمجي نفسه.
  RLS هي ما يجعل استعلاماً نُسي فيه الشرط يُعيد صفراً بدل بيانات منشأة
  أخرى. مُطبَّقة على 65 جدولاً، وتُفرَض بـ `RLS_ENFORCE=1`
- استعلامات المستأجرين تُنفَّذ بالدور المُقيَّد `dheuof_app`؛ مالك
  الجداول يتجاوز RLS ما لم تُفرَض بـ FORCE
- كل طريقة عرض تحمل `security_invoker = true` — بدونها تتجاوز العزل

### 13.3 منع التكرار
- `UNIQUE` على email للمستخدمين والمنشآت
- `UNIQUE(client_id, room_number)` لأرقام الغرف
- `UNIQUE(client_id, id_type, id_number)` لوثائق الضيوف
- `UNIQUE(ref_code)` لكود الإحالة

### 13.4 سجل التدقيق (Audit Log)
```sql
-- trigger يمنع تعديل أو حذف سجلات التدقيق
CREATE OR REPLACE FUNCTION audit_log_immutable()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'سجل التدقيق للقراءة فقط';
END; $$;

CREATE TRIGGER trg_audit_immutable
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
```

### 13.5 تتبع المستخدم
- كل جدول رئيسي يحتوي: `created_by`, `updated_by`, `created_at`, `updated_at`
- جدول `room_actions` يسجل كل تصرف بالاسم والتوقيت
- جدول `audit_log` يسجل التغييرات الكاملة (old_values/new_values)

### 13.6 النسخ الاحتياطي
- نسخ احتياطي يومي تلقائي لقاعدة البيانات
- الاحتفاظ بـ 30 نسخة على الأقل
- اختبار الاستعادة أسبوعيًا

### 13.7 حماية البيانات الشخصية
- تشفير أرقام الهوية والجوازات في قاعدة البيانات (AES-256)
- الوصول لوثائق الضيوف عبر روابط موقتة (signed URLs)
- حذف البيانات الشخصية بعد انتهاء فترة الاحتفاظ القانونية

### 13.8 صلاحيات قاعدة البيانات
```sql
-- مستخدم التطبيق بصلاحيات محدودة
CREATE ROLE app_user NOLOGIN;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app_user;
REVOKE DELETE ON audit_log FROM app_user;
REVOKE ALL ON subscription_plans FROM app_user; -- يديرها super_admin فقط
```

---

## القسم الرابع عشر: قابلية التوسع (Future Scalability)

> 📎 **التوسّع على مستوى قاعدة البيانات في
> [`06-security-and-scale.md`](06-security-and-scale.md) §7:** نسخ القراءة،
> التقسيم الأفقي حسب المنشأة، أرشفة البيانات الباردة، والعتبات التي
> تُقاس قبل تغيير أي شيء. هذا القسم يغطّي التوسّع الوظيفي (تكاملات
> وقنوات)، والملحق يغطّي التوسّع البنيوي.

### 14.1 ربط بتطبيق جوال
- API endpoints موحدة (REST/GraphQL) تخدم تطبيق iOS/Android
- Push Notifications عبر Firebase عند أحداث مهمة
- بيانات الوقت الفعلي للغرف عبر WebSocket

### 14.2 ربط بنظام محاسبي
- تصدير/استيراد الفواتير بتنسيق XML/JSON لأنظمة Odoo, QuickBooks
- تحويل دوري تلقائي للقيود المحاسبية
- جدول `accounting_sync_log` لتتبع عمليات التزامن

### 14.3 ربط بالقنوات الإلكترونية (Channel Manager)
- iCal sync مع Airbnb, Booking.com, Agoda
- جدول `channel_reservations` لتتبع الحجوزات الواردة من كل قناة
- API integration لتحديث الأسعار والتوافر

### 14.4 إشعارات متقدمة
- WhatsApp API عند تأكيد الحجز والخروج
- إشعارات SMS للدفع المستحق
- إشعارات داخلية لموظفي التدبير المنزلي

### 14.5 ذكاء اصطناعي وتحليل البيانات
- توقع الإشغال بناء على البيانات التاريخية
- تسعير ديناميكي (Dynamic Pricing) حسب الطلب
- تحليل سلوك الضيوف VIP
- اكتشاف الأنماط الشاذة (fraud detection)

### 14.6 تكامل API خارجي
- RESTful API مع مصادقة OAuth 2.0
- Webhooks للأحداث المهمة (new_booking, checkout, payment)
- API Rate Limiting وإدارة المفاتيح `api_keys` table

### 14.7 لوحة مؤشرات متقدمة (BI Dashboard)
- بيانات مجمعة في جداول `reporting_*` محدثة دوريًا
- توافق مع أدوات BI مثل Power BI, Tableau عبر PostgreSQL connector
- مؤشرات مقارنة تاريخية (YoY, MoM)

### 14.8 توسع التقسيم (Partitioning)
- `bookings` و `audit_log` تتوسع بسرعة — يُوصى بـ Range Partitioning على `created_at`
- `inventory_transactions` مرشحة للأرشفة التلقائية بعد 3 سنوات

---

## القسم الخامس عشر: ملاحظات تحليلية نهائية

### 15.1 تقييم مدى ملاءمة النموذج

**نقاط القوة:**
- ✅ عزل كامل للبيانات بين المنشآت عبر `client_id`
- ✅ تغطية شاملة لدورة حياة الضيف: حجز → دخول → إقامة → خروج → فاتورة → دفع
- ✅ سجل تدقيق غير قابل للتعديل يضمن المساءلة
- ✅ نموذج صلاحيات مرن يدعم 7 أدوار مختلفة
- ✅ ربط كامل بين الأقسام: Housekeeping ↔ Rooms ↔ Bookings ↔ Finance
- ✅ نظام تسويق إحالة مدمج مع قيود تمنع التكرار

**تحفظات وافتراضات:**
- ⚠️ **افتراض:** نظام الدفع الإلكتروني (بطاقات، Stripe) سيحتاج `payment_gateway_log` لتتبع المعاملات
- ⚠️ **افتراض:** نظام التسعير الديناميكي (بالموسم، الحدث) غير مُنمذج — يتطلب جدول `pricing_rules`
- ⚠️ **افتراض:** الحجوزات الجماعية (مجموعة سياح) تحتاج كيان `group_bookings` وسيط
- ⚠️ **افتراض:** نظام الهدايا والنقاط (Loyalty Program) غير مُنمذج — يتطلب `loyalty_accounts` + `loyalty_transactions`

### 15.2 بيانات ستحسّن النموذج إذا توفرت

| البيانات الناقصة | الفائدة |
|---|---|
| بيانات المنافسين وأسعار السوق | تفعيل التسعير الديناميكي |
| تقييمات الضيوف (Reviews) | مؤشر رضا العملاء + توجيه VIP |
| ساعات الذروة وأنماط الحجز | تحسين جدولة موظفي التدبير |
| تكاليف المرافق (كهرباء، ماء) | حساب هامش الربح الصافي لكل غرفة |
| بيانات قناة الحجز التفصيلية | مقارنة الإيراد بين Booking.com و Airbnb |
| بيانات الوقت الفعلي للمباني IoT | أتمتة Housekeeping عبر أجهزة استشعار |

### 15.3 الأولويات المقترحة للتطبيق

```
المرحلة 1 (الأساسية):
  clients → users → rooms → room_types → guests → bookings → invoices → payments

المرحلة 2 (التشغيل الكامل):
  housekeeping_tasks → room_actions → pos_orders → inventory_items

المرحلة 3 (المالية والتقارير):
  purchase_orders → suppliers → audit_log → role_permissions

المرحلة 4 (التسويق والتوسع):
  marketers → marketer_referrals → subscriptions → modules
```

---

*نموذج قاعدة البيانات هذا مبني على معايير PostgreSQL 15+ وموصى به للتطبيق في بيئة SaaS متعددة المستأجرين مع عزل بيانات كامل.*
