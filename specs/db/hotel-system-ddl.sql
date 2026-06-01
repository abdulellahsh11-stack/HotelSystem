-- ================================================================
-- منصة ضيوف — Hotel System Complete DDL
-- PostgreSQL 15+  |  Multi-tenant SaaS
-- ================================================================
-- هذا الملف يحتوي على الجداول الجديدة المقترحة فقط.
-- الجداول الموجودة في migrations.py + schema_v3.py تُبقى كما هي.
-- ================================================================

-- ──────────────────────────────────────────────────────────────
-- جدول خطط الاشتراك
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subscription_plans (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL,
    price_monthly   NUMERIC(10,2)   NOT NULL DEFAULT 0,
    price_yearly    NUMERIC(10,2),
    max_rooms       INTEGER,
    max_users       INTEGER,
    allowed_modules JSONB           DEFAULT '[]',
    features        JSONB           DEFAULT '{}',
    is_active       BOOLEAN         DEFAULT TRUE,
    created_at      TIMESTAMPTZ     DEFAULT NOW()
);

-- ──────────────────────────────────────────────────────────────
-- جدول الوحدات الوظيفية
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS modules (
    id          SERIAL PRIMARY KEY,
    code        VARCHAR(10)  NOT NULL UNIQUE,
    name_ar     VARCHAR(100) NOT NULL,
    name_en     VARCHAR(100) NOT NULL,
    description TEXT,
    is_core     BOOLEAN DEFAULT FALSE,
    sort_order  SMALLINT DEFAULT 0
);

INSERT INTO modules (code, name_ar, name_en, is_core, sort_order) VALUES
  ('M01', 'إدارة الضيوف',         'Guest Management',      TRUE,  1),
  ('M02', 'الاستقبال',            'Front Desk',            TRUE,  2),
  ('M03', 'الحجوزات',             'Reservations',          TRUE,  3),
  ('M04', 'الفواتير',             'Invoices & Finance',    TRUE,  4),
  ('M05', 'نقطة البيع',           'Point of Sale',         FALSE, 5),
  ('M06', 'الموارد البشرية',      'HR & Payroll',          FALSE, 6),
  ('M07', 'التدبير المنزلي',      'Housekeeping',          TRUE,  7),
  ('M08', 'الصيانة',              'Maintenance',           FALSE, 8),
  ('M09', 'المخزن والمشتريات',    'Warehouse & Procurement',FALSE,9),
  ('M10', 'CRM والولاء',          'CRM & Loyalty',         FALSE, 10),
  ('M11', 'مؤشرات الأداء',        'KPI Analytics',         FALSE, 11),
  ('M12', 'iCal والقنوات',        'Channel Manager',       FALSE, 12),
  ('M13', 'واتساب والشات',        'WhatsApp & Chatbot',    FALSE, 13),
  ('M14', 'الجولات السياحية',     'Tourism Tours',         FALSE, 14),
  ('M15', 'الوجهات السياحية',     'Tourist Destinations',  FALSE, 15),
  ('M16', 'التقارير المتقدمة',    'Advanced Reports',      FALSE, 16),
  ('M17', 'التسويق والإحالات',    'Marketing & Referrals', FALSE, 17)
ON CONFLICT (code) DO NOTHING;

-- ──────────────────────────────────────────────────────────────
-- جدول المستخدمين (users)
-- NEW — يحل محل الجلسات في الذاكرة
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    public_id       UUID            DEFAULT gen_random_uuid() UNIQUE,
    client_id       VARCHAR(50)     REFERENCES clients(id) ON DELETE CASCADE,
    branch_id       INTEGER,        -- REFERENCES branches(id)
    email           VARCHAR(255)    NOT NULL UNIQUE,
    phone           VARCHAR(20),
    full_name       VARCHAR(200)    NOT NULL,
    password_hash   VARCHAR(255)    NOT NULL,
    role            VARCHAR(50)     NOT NULL DEFAULT 'receptionist',
    is_active       BOOLEAN         DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     DEFAULT NOW(),
    created_by      INTEGER         REFERENCES users(id),
    updated_at      TIMESTAMPTZ     DEFAULT NOW(),
    CONSTRAINT chk_users_role CHECK (
        role IN ('super_admin','facility_manager','receptionist',
                 'housekeeping_staff','pos_cashier','warehouse_staff','accountant')
    )
);
CREATE INDEX IF NOT EXISTS idx_users_client   ON users(client_id, role, is_active);
CREATE INDEX IF NOT EXISTS idx_users_email    ON users(email);

-- ──────────────────────────────────────────────────────────────
-- جدول صلاحيات الأدوار
-- NEW — RBAC matrix
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS role_permissions (
    id          SERIAL PRIMARY KEY,
    role        VARCHAR(50)  NOT NULL,
    resource    VARCHAR(100) NOT NULL,
    can_create  BOOLEAN DEFAULT FALSE,
    can_read    BOOLEAN DEFAULT FALSE,
    can_update  BOOLEAN DEFAULT FALSE,
    can_delete  BOOLEAN DEFAULT FALSE,
    can_approve BOOLEAN DEFAULT FALSE,
    can_export  BOOLEAN DEFAULT FALSE,
    UNIQUE(role, resource)
);

INSERT INTO role_permissions (role, resource, can_create, can_read, can_update, can_delete, can_approve, can_export) VALUES
-- facility_manager
('facility_manager','bookings',     TRUE, TRUE, TRUE, TRUE,  TRUE,  TRUE),
('facility_manager','guests',       TRUE, TRUE, TRUE, TRUE,  FALSE, TRUE),
('facility_manager','invoices',     TRUE, TRUE, TRUE, FALSE, TRUE,  TRUE),
('facility_manager','payments',     TRUE, TRUE, TRUE, FALSE, FALSE, TRUE),
('facility_manager','rooms',        TRUE, TRUE, TRUE, TRUE,  FALSE, FALSE),
('facility_manager','users',        TRUE, TRUE, TRUE, TRUE,  FALSE, FALSE),
('facility_manager','reports',      FALSE, TRUE, FALSE, FALSE, FALSE, TRUE),
-- receptionist
('receptionist','bookings',         TRUE,  TRUE, TRUE, FALSE, FALSE, FALSE),
('receptionist','guests',           TRUE,  TRUE, TRUE, FALSE, FALSE, FALSE),
('receptionist','invoices',         TRUE,  TRUE, FALSE, FALSE, FALSE, FALSE),
('receptionist','payments',         TRUE,  TRUE, FALSE, FALSE, FALSE, FALSE),
('receptionist','rooms',            FALSE, TRUE, TRUE, FALSE, FALSE, FALSE),
-- housekeeping_staff
('housekeeping_staff','housekeeping_tasks', FALSE, TRUE, TRUE, FALSE, FALSE, FALSE),
('housekeeping_staff','rooms',              FALSE, TRUE, TRUE, FALSE, FALSE, FALSE),
-- pos_cashier
('pos_cashier','pos_orders',       TRUE, TRUE, TRUE, FALSE, FALSE, FALSE),
('pos_cashier','pos_items',        FALSE, TRUE, FALSE, FALSE, FALSE, FALSE),
-- warehouse_staff
('warehouse_staff','inventory_items',       FALSE, TRUE, TRUE, FALSE, FALSE, FALSE),
('warehouse_staff','inventory_transactions',TRUE,  TRUE, FALSE, FALSE, FALSE, FALSE),
('warehouse_staff','purchase_orders',       TRUE,  TRUE, FALSE, FALSE, FALSE, FALSE),
-- accountant
('accountant','invoices',       FALSE, TRUE, TRUE, FALSE, TRUE, TRUE),
('accountant','payments',       FALSE, TRUE, TRUE, FALSE, FALSE, TRUE),
('accountant','reports',        FALSE, TRUE, FALSE, FALSE, FALSE, TRUE),
('accountant','purchase_orders',FALSE, TRUE, FALSE, FALSE, TRUE, TRUE)
ON CONFLICT (role, resource) DO NOTHING;

-- ──────────────────────────────────────────────────────────────
-- جدول الفروع
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS branches (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50)  NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name        VARCHAR(150) NOT NULL,
    address     TEXT,
    phone       VARCHAR(20),
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_branches_client ON branches(client_id);

-- ──────────────────────────────────────────────────────────────
-- جدول المرافق والخدمات في الغرف
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS amenities (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50)  NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name_ar     VARCHAR(100) NOT NULL,
    name_en     VARCHAR(100),
    icon        VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS room_amenities (
    room_id     INTEGER NOT NULL REFERENCES rooms(id)     ON DELETE CASCADE,
    amenity_id  INTEGER NOT NULL REFERENCES amenities(id) ON DELETE CASCADE,
    PRIMARY KEY (room_id, amenity_id)
);

-- ──────────────────────────────────────────────────────────────
-- تحسينات جدول guests
-- ──────────────────────────────────────────────────────────────
ALTER TABLE guests ADD COLUMN IF NOT EXISTS vip_level    VARCHAR(20) DEFAULT 'regular';
ALTER TABLE guests ADD COLUMN IF NOT EXISTS blacklisted  BOOLEAN     DEFAULT FALSE;
ALTER TABLE guests ADD COLUMN IF NOT EXISTS blacklist_reason TEXT;
ALTER TABLE guests ADD COLUMN IF NOT EXISTS full_name_en VARCHAR(200);
ALTER TABLE guests ADD COLUMN IF NOT EXISTS email        VARCHAR(255);
ALTER TABLE guests ADD COLUMN IF NOT EXISTS address      TEXT;
ALTER TABLE guests ADD COLUMN IF NOT EXISTS id_expiry    DATE;

CREATE TABLE IF NOT EXISTS guest_documents (
    id          SERIAL PRIMARY KEY,
    guest_id    INTEGER     NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
    client_id   VARCHAR(50) NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    doc_type    VARCHAR(30) NOT NULL,  -- front_id/back_id/passport/visa
    file_url    TEXT        NOT NULL,
    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    uploaded_by INTEGER     REFERENCES users(id),
    CONSTRAINT chk_doc_type CHECK (doc_type IN ('front_id','back_id','passport','visa','iqama','other'))
);
CREATE INDEX IF NOT EXISTS idx_gdoc_guest   ON guest_documents(guest_id);
CREATE INDEX IF NOT EXISTS idx_gdoc_client  ON guest_documents(client_id);

-- ──────────────────────────────────────────────────────────────
-- تحسينات جدول bookings
-- ──────────────────────────────────────────────────────────────
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS booking_type  VARCHAR(20) DEFAULT 'nightly';
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS num_adults    SMALLINT    DEFAULT 1;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS num_children  SMALLINT    DEFAULT 0;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS total_nights  SMALLINT    DEFAULT 1;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(10,2) DEFAULT 0;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS tax_amount    NUMERIC(10,2) DEFAULT 0;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS net_amount    NUMERIC(12,2) DEFAULT 0;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS created_by    INTEGER     REFERENCES users(id);
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS updated_by    INTEGER     REFERENCES users(id);

-- جدول ضيوف الحجز (يحل محل companions JSONB)
CREATE TABLE IF NOT EXISTS booking_guests (
    booking_id  VARCHAR(50) NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    guest_id    INTEGER     NOT NULL REFERENCES guests(id)   ON DELETE CASCADE,
    is_primary  BOOLEAN     DEFAULT FALSE,
    added_at    TIMESTAMPTZ DEFAULT NOW(),
    added_by    INTEGER     REFERENCES users(id),
    PRIMARY KEY (booking_id, guest_id)
);
CREATE INDEX IF NOT EXISTS idx_bg_guest   ON booking_guests(guest_id);
CREATE INDEX IF NOT EXISTS idx_bg_booking ON booking_guests(booking_id);

-- الخدمات الإضافية للحجز
CREATE TABLE IF NOT EXISTS booking_services (
    id          SERIAL PRIMARY KEY,
    booking_id  VARCHAR(50)  NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    client_id   VARCHAR(50)  NOT NULL REFERENCES clients(id)  ON DELETE CASCADE,
    service_name VARCHAR(200) NOT NULL,
    quantity    NUMERIC(8,2) DEFAULT 1,
    unit_price  NUMERIC(10,2) NOT NULL,
    total_price NUMERIC(12,2) NOT NULL,
    service_date DATE,
    added_by    INTEGER      REFERENCES users(id),
    added_at    TIMESTAMPTZ  DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bsvc_booking ON booking_services(booking_id);

-- ──────────────────────────────────────────────────────────────
-- تحسينات جدول invoices — إضافة invoice_items منفصل
-- ──────────────────────────────────────────────────────────────
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS invoice_number VARCHAR(30);
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS due_date       DATE;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(10,2) DEFAULT 0;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS tax_rate       NUMERIC(5,2)  DEFAULT 0;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS balance_due    NUMERIC(12,2) DEFAULT 0;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS issued_by      INTEGER REFERENCES users(id);

-- بنود الفاتورة (يحل محل line_items JSONB)
CREATE TABLE IF NOT EXISTS invoice_items (
    id          SERIAL PRIMARY KEY,
    invoice_id  VARCHAR(50)   NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description VARCHAR(500)  NOT NULL,
    item_type   VARCHAR(30)   NOT NULL DEFAULT 'room',
    quantity    NUMERIC(8,2)  NOT NULL DEFAULT 1,
    unit_price  NUMERIC(10,2) NOT NULL,
    discount_pct NUMERIC(5,2) DEFAULT 0,
    total_price NUMERIC(12,2) NOT NULL,
    CONSTRAINT chk_item_type CHECK (item_type IN ('room','service','pos','extra','other'))
);
CREATE INDEX IF NOT EXISTS idx_inv_items ON invoice_items(invoice_id);

-- ──────────────────────────────────────────────────────────────
-- نظام POS منظم (يكمل pos_transactions الحالي)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pos_categories (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50)  NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    sort_order  SMALLINT     DEFAULT 0,
    is_active   BOOLEAN      DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS pos_items (
    id                  SERIAL PRIMARY KEY,
    client_id           VARCHAR(50)    NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    category_id         INTEGER        REFERENCES pos_categories(id),
    name                VARCHAR(200)   NOT NULL,
    sku                 VARCHAR(50),
    price               NUMERIC(10,2)  NOT NULL,
    tax_rate            NUMERIC(5,2)   DEFAULT 0,
    is_active           BOOLEAN        DEFAULT TRUE,
    deduct_inventory    BOOLEAN        DEFAULT FALSE,
    inventory_item_id   INTEGER,       -- REFERENCES inventory_items(id)
    created_at          TIMESTAMPTZ    DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pos_items_client ON pos_items(client_id, is_active);

CREATE TABLE IF NOT EXISTS pos_orders (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50)    NOT NULL REFERENCES clients(id)   ON DELETE CASCADE,
    order_number    VARCHAR(30)    NOT NULL,
    booking_id      VARCHAR(50)    REFERENCES bookings(id),
    guest_id        INTEGER        REFERENCES guests(id),
    table_number    VARCHAR(20),
    order_type      VARCHAR(30)    NOT NULL DEFAULT 'dine_in',
    status          VARCHAR(20)    NOT NULL DEFAULT 'open',
    subtotal        NUMERIC(12,2)  DEFAULT 0,
    discount        NUMERIC(10,2)  DEFAULT 0,
    tax_amount      NUMERIC(10,2)  DEFAULT 0,
    total           NUMERIC(12,2)  DEFAULT 0,
    payment_method  VARCHAR(30),
    bill_to_room    BOOLEAN        DEFAULT FALSE,
    cashier_id      INTEGER        REFERENCES users(id),
    created_at      TIMESTAMPTZ    DEFAULT NOW(),
    UNIQUE(client_id, order_number),
    CONSTRAINT chk_pos_status CHECK (
        status IN ('open','preparing','ready','served','paid','cancelled')
    ),
    CONSTRAINT chk_pos_type CHECK (
        order_type IN ('dine_in','room_service','takeaway','delivery')
    )
);
CREATE INDEX IF NOT EXISTS idx_pos_orders_client ON pos_orders(client_id, status, created_at);

CREATE TABLE IF NOT EXISTS pos_order_items (
    id          SERIAL PRIMARY KEY,
    order_id    INTEGER        NOT NULL REFERENCES pos_orders(id) ON DELETE CASCADE,
    item_id     INTEGER        NOT NULL REFERENCES pos_items(id),
    item_name   VARCHAR(200)   NOT NULL,
    quantity    NUMERIC(8,2)   NOT NULL DEFAULT 1,
    unit_price  NUMERIC(10,2)  NOT NULL,
    total_price NUMERIC(12,2)  NOT NULL,
    notes       TEXT
);
CREATE INDEX IF NOT EXISTS idx_poi_order ON pos_order_items(order_id);

-- ──────────────────────────────────────────────────────────────
-- المخزن المنظم (يكمل warehouse_items الحالي)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inventory_categories (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50)  NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS inventory_items (
    id                      SERIAL PRIMARY KEY,
    client_id               VARCHAR(50)    NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    category_id             INTEGER        REFERENCES inventory_categories(id),
    name                    VARCHAR(200)   NOT NULL,
    sku                     VARCHAR(50),
    unit                    VARCHAR(30)    NOT NULL DEFAULT 'قطعة',
    current_stock           NUMERIC(12,2)  DEFAULT 0,
    min_stock               NUMERIC(12,2)  DEFAULT 0,
    unit_cost               NUMERIC(10,2),
    preferred_supplier_id   INTEGER        REFERENCES suppliers(id),
    is_active               BOOLEAN        DEFAULT TRUE,
    created_at              TIMESTAMPTZ    DEFAULT NOW(),
    UNIQUE(client_id, sku)
);
CREATE INDEX IF NOT EXISTS idx_inv_items_client ON inventory_items(client_id, is_active);
CREATE INDEX IF NOT EXISTS idx_inv_items_stock  ON inventory_items(client_id, current_stock);

CREATE TABLE IF NOT EXISTS inventory_transactions (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50)    NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    item_id         INTEGER        NOT NULL REFERENCES inventory_items(id),
    transaction_type VARCHAR(20)   NOT NULL,
    quantity        NUMERIC(12,2)  NOT NULL,
    unit_cost       NUMERIC(10,2),
    total_cost      NUMERIC(12,2),
    reference_type  VARCHAR(30),
    reference_id    INTEGER,
    notes           TEXT,
    performed_by    INTEGER        REFERENCES users(id),
    transaction_date TIMESTAMPTZ   DEFAULT NOW(),
    CONSTRAINT chk_inv_type CHECK (
        transaction_type IN ('in','out','adjustment','waste','return')
    )
);
CREATE INDEX IF NOT EXISTS idx_inv_tx_client ON inventory_transactions(client_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_inv_tx_item   ON inventory_transactions(item_id);

-- ──────────────────────────────────────────────────────────────
-- سجل التدقيق الشامل (append-only)
-- NEW — يحل محل السجل المحدود الحالي
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGSERIAL PRIMARY KEY,
    client_id       VARCHAR(50),
    user_id         INTEGER,
    user_email      VARCHAR(255),
    action          VARCHAR(100)  NOT NULL,
    resource_type   VARCHAR(100)  NOT NULL,
    resource_id     TEXT,
    old_values      JSONB,
    new_values      JSONB,
    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ   DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_client   ON audit_log(client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user     ON audit_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource_type, resource_id);

-- Trigger: يمنع تعديل أو حذف سجلات التدقيق
CREATE OR REPLACE FUNCTION audit_log_immutable()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only — UPDATE/DELETE not allowed';
END; $$;

DROP TRIGGER IF EXISTS trg_audit_immutable ON audit_log;
CREATE TRIGGER trg_audit_immutable
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();

-- ──────────────────────────────────────────────────────────────
-- تحسينات marketers (إضافة حقول مكملة)
-- ──────────────────────────────────────────────────────────────
ALTER TABLE marketers ADD COLUMN IF NOT EXISTS commission_type VARCHAR(20) DEFAULT 'percentage';
ALTER TABLE marketers ADD COLUMN IF NOT EXISTS total_referrals INTEGER     DEFAULT 0;
ALTER TABLE marketers ADD COLUMN IF NOT EXISTS bank_details    JSONB       DEFAULT '{}';

-- ──────────────────────────────────────────────────────────────
-- دالة تحديث updated_at (shared)
-- ──────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated ON users;
CREATE TRIGGER trg_users_updated
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ──────────────────────────────────────────────────────────────
-- فهارس أداء إضافية على الجداول الحالية
-- ──────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_rooms_checkout_due  ON rooms(client_id, checkout_due)
    WHERE status = 'occupied';
CREATE INDEX IF NOT EXISTS idx_bookings_checkin    ON bookings(client_id, check_in);
CREATE INDEX IF NOT EXISTS idx_bookings_checkout   ON bookings(client_id, check_out, status);
CREATE INDEX IF NOT EXISTS idx_guests_phone        ON guests(client_id, absher_phone);
CREATE INDEX IF NOT EXISTS idx_guests_idnum        ON guests(client_id, id_number);

-- ================================================================
-- الانتهاء
-- ================================================================
-- ملاحظة: هذا الملف يُضاف فوق الجداول الموجودة في migrations.py
-- جميع التعليمات IF NOT EXISTS تجعله آمنًا للتشغيل أكثر من مرة
-- ================================================================
