#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/schema_v3.py — مخطط قاعدة بيانات ضيوف الكامل v3.0
جميع الوحدات الـ 15 — يعمل مع نظام الـ migrations الحالي
"""
from db.sqlsplit import has_executable_sql, split_sql

SCHEMA_V3_MODULES = """
-- ================================================================
-- ضيوف Dheuof — Module Tables v3.0
-- ================================================================

-- ──────────────────────────────────────────────────────────────
-- M01: إدارة الضيوف — Guest Management
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS guest_profiles (
    id            SERIAL PRIMARY KEY,
    client_id     VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    guest_id      INTEGER REFERENCES guests(id) ON DELETE CASCADE,
    vip_level     VARCHAR(20) DEFAULT 'standard',
    preferred_room_type VARCHAR(50),
    dietary_notes TEXT,
    loyalty_points INTEGER DEFAULT 0,
    total_stays   INTEGER DEFAULT 0,
    total_revenue DECIMAL(12,2) DEFAULT 0,
    tags          JSONB DEFAULT '[]',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_gp_client ON guest_profiles(client_id);
CREATE INDEX IF NOT EXISTS idx_gp_guest  ON guest_profiles(guest_id);

CREATE TABLE IF NOT EXISTS room_types (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    code        VARCHAR(20) NOT NULL,
    name_ar     VARCHAR(100) NOT NULL,
    name_en     VARCHAR(100),
    capacity    INTEGER DEFAULT 2,
    base_price  DECIMAL(10,2) DEFAULT 0,
    amenities   JSONB DEFAULT '[]',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, code)
);

CREATE TABLE IF NOT EXISTS rate_plans (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    code        VARCHAR(20) NOT NULL,
    name_ar     VARCHAR(100) NOT NULL,
    rate_type   VARCHAR(30) DEFAULT 'daily',
    base_amount DECIMAL(10,2) NOT NULL,
    min_stay    INTEGER DEFAULT 1,
    max_stay    INTEGER,
    valid_from  DATE,
    valid_to    DATE,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, code)
);

-- ──────────────────────────────────────────────────────────────
-- M02: الاستقبال — Front Desk
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS front_desk_shifts (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    employee_name   VARCHAR(100) NOT NULL,
    shift_type      VARCHAR(20) DEFAULT 'morning',
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,
    opening_cash    DECIMAL(10,2) DEFAULT 0,
    closing_cash    DECIMAL(10,2),
    notes           TEXT,
    status          VARCHAR(20) DEFAULT 'open'
);
CREATE INDEX IF NOT EXISTS idx_shifts_client ON front_desk_shifts(client_id, started_at);

CREATE TABLE IF NOT EXISTS check_in_log (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    booking_id      VARCHAR(50) REFERENCES bookings(id),
    room_id         INTEGER REFERENCES rooms(id),
    guest_id        INTEGER REFERENCES guests(id),
    checkin_by      VARCHAR(100),
    id_verified     BOOLEAN DEFAULT FALSE,
    key_issued      BOOLEAN DEFAULT FALSE,
    notes           TEXT,
    checked_in_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS check_out_log (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    booking_id      VARCHAR(50) REFERENCES bookings(id),
    checkout_by     VARCHAR(100),
    final_amount    DECIMAL(10,2),
    payment_method  VARCHAR(30),
    notes           TEXT,
    checked_out_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────────────────────
-- M06: الموارد البشرية — HR & Payroll
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS employees (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    employee_id     VARCHAR(30) NOT NULL,
    full_name_ar    VARCHAR(150) NOT NULL,
    full_name_en    VARCHAR(150),
    national_id     VARCHAR(20),
    iqama_number    VARCHAR(20),
    nationality     VARCHAR(50),
    position        VARCHAR(100),
    department      VARCHAR(100),
    phone           VARCHAR(20),
    email           VARCHAR(100),
    hire_date       DATE,
    basic_salary    DECIMAL(10,2) DEFAULT 0,
    housing_allow   DECIMAL(10,2) DEFAULT 0,
    transport_allow DECIMAL(10,2) DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'active',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, employee_id)
);
CREATE INDEX IF NOT EXISTS idx_emp_client ON employees(client_id, status);

CREATE TABLE IF NOT EXISTS attendance (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    employee_id     INTEGER REFERENCES employees(id) ON DELETE CASCADE,
    work_date       DATE NOT NULL,
    check_in_time   TIME,
    check_out_time  TIME,
    hours_worked    DECIMAL(5,2),
    overtime_hours  DECIMAL(5,2) DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'present',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, employee_id, work_date)
);
CREATE INDEX IF NOT EXISTS idx_att_client_date ON attendance(client_id, work_date);

CREATE TABLE IF NOT EXISTS payroll (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    employee_id     INTEGER REFERENCES employees(id) ON DELETE CASCADE,
    period_month    INTEGER NOT NULL,
    period_year     INTEGER NOT NULL,
    basic_salary    DECIMAL(10,2) DEFAULT 0,
    allowances      DECIMAL(10,2) DEFAULT 0,
    overtime_pay    DECIMAL(10,2) DEFAULT 0,
    deductions      DECIMAL(10,2) DEFAULT 0,
    gosi_employee   DECIMAL(10,2) DEFAULT 0,
    gosi_employer   DECIMAL(10,2) DEFAULT 0,
    net_salary      DECIMAL(10,2) DEFAULT 0,
    paid_at         DATE,
    status          VARCHAR(20) DEFAULT 'pending',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, employee_id, period_month, period_year)
);
CREATE INDEX IF NOT EXISTS idx_payroll_client ON payroll(client_id, period_year, period_month);

-- ──────────────────────────────────────────────────────────────
-- M07: الإشراف الداخلي — Housekeeping
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS housekeeping_tasks (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    room_id         INTEGER REFERENCES rooms(id),
    task_type       VARCHAR(30) DEFAULT 'cleaning',
    priority        VARCHAR(20) DEFAULT 'normal',
    assigned_to     VARCHAR(100),
    status          VARCHAR(20) DEFAULT 'pending',
    notes           TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_hk_client_status ON housekeeping_tasks(client_id, status);

CREATE TABLE IF NOT EXISTS housekeeping_checklist (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    task_id         INTEGER REFERENCES housekeeping_tasks(id) ON DELETE CASCADE,
    item            VARCHAR(200) NOT NULL,
    checked         BOOLEAN DEFAULT FALSE,
    checked_by      VARCHAR(100),
    checked_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS lost_and_found (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    room_id         INTEGER REFERENCES rooms(id),
    item_description TEXT NOT NULL,
    found_date      DATE DEFAULT CURRENT_DATE,
    found_by        VARCHAR(100),
    status          VARCHAR(20) DEFAULT 'stored',
    claimed_by      VARCHAR(100),
    claimed_date    DATE,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────────────────────
-- M08: الصيانة — Maintenance
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS maintenance_orders (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    room_id         INTEGER REFERENCES rooms(id),
    order_number    VARCHAR(30),
    issue_type      VARCHAR(50),
    description     TEXT NOT NULL,
    priority        VARCHAR(20) DEFAULT 'normal',
    assigned_to     VARCHAR(100),
    status          VARCHAR(20) DEFAULT 'open',
    estimated_cost  DECIMAL(10,2),
    actual_cost     DECIMAL(10,2),
    parts_used      JSONB DEFAULT '[]',
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_mo_client_status ON maintenance_orders(client_id, status);

CREATE TABLE IF NOT EXISTS assets (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    asset_code      VARCHAR(30) NOT NULL,
    name_ar         VARCHAR(150) NOT NULL,
    category        VARCHAR(50),
    location        VARCHAR(100),
    purchase_date   DATE,
    purchase_cost   DECIMAL(10,2),
    warranty_expiry DATE,
    status          VARCHAR(20) DEFAULT 'operational',
    last_service_at DATE,
    next_service_at DATE,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, asset_code)
);
CREATE INDEX IF NOT EXISTS idx_assets_client ON assets(client_id, status);

-- ──────────────────────────────────────────────────────────────
-- M10: CRM والولاء — CRM & Loyalty
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS crm_contacts (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    guest_id        INTEGER REFERENCES guests(id),
    segment         VARCHAR(50) DEFAULT 'regular',
    lifecycle_stage VARCHAR(30) DEFAULT 'active',
    lifetime_value  DECIMAL(12,2) DEFAULT 0,
    total_bookings  INTEGER DEFAULT 0,
    last_stay_date  DATE,
    nps_score       INTEGER,
    tags            JSONB DEFAULT '[]',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_crm_client ON crm_contacts(client_id, segment);

CREATE TABLE IF NOT EXISTS loyalty_transactions (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    guest_id        INTEGER REFERENCES guests(id),
    transaction_type VARCHAR(30),
    points          INTEGER NOT NULL,
    booking_id      VARCHAR(50) REFERENCES bookings(id),
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_loyalty_guest ON loyalty_transactions(client_id, guest_id);

CREATE TABLE IF NOT EXISTS campaigns (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    name            VARCHAR(150) NOT NULL,
    campaign_type   VARCHAR(30) DEFAULT 'email',
    target_segment  VARCHAR(50),
    message_ar      TEXT,
    subject         VARCHAR(200),
    send_date       DATE,
    status          VARCHAR(20) DEFAULT 'draft',
    sent_count      INTEGER DEFAULT 0,
    opened_count    INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────────────────────
-- M11: مؤشرات الأداء — KPI Analytics
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS daily_kpis (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    kpi_date        DATE NOT NULL,
    total_rooms     INTEGER DEFAULT 0,
    occupied_rooms  INTEGER DEFAULT 0,
    occupancy_rate  DECIMAL(5,2) DEFAULT 0,
    adr             DECIMAL(10,2) DEFAULT 0,
    revpar          DECIMAL(10,2) DEFAULT 0,
    trevpar         DECIMAL(10,2) DEFAULT 0,
    revenue_rooms   DECIMAL(12,2) DEFAULT 0,
    revenue_fb      DECIMAL(12,2) DEFAULT 0,
    revenue_other   DECIMAL(12,2) DEFAULT 0,
    revenue_total   DECIMAL(12,2) DEFAULT 0,
    check_ins       INTEGER DEFAULT 0,
    check_outs      INTEGER DEFAULT 0,
    no_shows        INTEGER DEFAULT 0,
    cancellations   INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, kpi_date)
);
CREATE INDEX IF NOT EXISTS idx_kpi_client_date ON daily_kpis(client_id, kpi_date);

-- ──────────────────────────────────────────────────────────────
-- M13: المستودعات والمشتريات — Warehouses & Procurement
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS warehouse_items (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    warehouse_type  VARCHAR(30) DEFAULT 'general',
    name            VARCHAR(200) NOT NULL,
    unit            VARCHAR(20) DEFAULT 'قطعة',
    quantity        DECIMAL(10,2) DEFAULT 0,
    reorder_level   DECIMAL(10,2) DEFAULT 0,
    price_per_unit  DECIMAL(10,2) DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_wi_client ON warehouse_items(client_id);

CREATE TABLE IF NOT EXISTS warehouse_movements (
    id              SERIAL PRIMARY KEY,
    item_id         INTEGER REFERENCES warehouse_items(id) ON DELETE CASCADE,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    movement_type   VARCHAR(10) DEFAULT 'in',
    quantity        DECIMAL(10,2) NOT NULL,
    notes           TEXT,
    created_by      VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS suppliers (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    supplier_code   VARCHAR(30),
    name_ar         VARCHAR(150) NOT NULL,
    name_en         VARCHAR(150),
    vat_number      VARCHAR(20),
    contact_phone   VARCHAR(20),
    contact_email   VARCHAR(100),
    payment_terms   INTEGER DEFAULT 30,
    status          VARCHAR(20) DEFAULT 'active',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sup_client ON suppliers(client_id, status);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    po_number       VARCHAR(30) NOT NULL,
    supplier_id     INTEGER REFERENCES suppliers(id),
    order_date      DATE DEFAULT CURRENT_DATE,
    expected_date   DATE,
    status          VARCHAR(20) DEFAULT 'draft',
    subtotal        DECIMAL(12,2) DEFAULT 0,
    vat_amount      DECIMAL(12,2) DEFAULT 0,
    total_amount    DECIMAL(12,2) DEFAULT 0,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, po_number)
);
CREATE INDEX IF NOT EXISTS idx_po_client ON purchase_orders(client_id, status);

CREATE TABLE IF NOT EXISTS po_items (
    id              SERIAL PRIMARY KEY,
    po_id           INTEGER REFERENCES purchase_orders(id) ON DELETE CASCADE,
    item_id         INTEGER REFERENCES warehouse_items(id),
    item_name       VARCHAR(200) NOT NULL,
    quantity        DECIMAL(10,2) NOT NULL,
    unit_price      DECIMAL(10,2) NOT NULL,
    total_price     DECIMAL(10,2) NOT NULL,
    received_qty    DECIMAL(10,2) DEFAULT 0
);

-- ──────────────────────────────────────────────────────────────
-- M14: الجولات السياحية — Tourism Tours
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tour_catalog (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    tour_code       VARCHAR(30) NOT NULL,
    name_ar         VARCHAR(200) NOT NULL,
    name_en         VARCHAR(200),
    description_ar  TEXT,
    tour_type       VARCHAR(30) DEFAULT 'city',
    duration_hours  DECIMAL(5,1),
    price_adult     DECIMAL(10,2) DEFAULT 0,
    price_child     DECIMAL(10,2) DEFAULT 0,
    max_capacity    INTEGER DEFAULT 10,
    includes_ar     TEXT,
    status          VARCHAR(20) DEFAULT 'active',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, tour_code)
);
CREATE INDEX IF NOT EXISTS idx_tour_client ON tour_catalog(client_id, status);

CREATE TABLE IF NOT EXISTS tour_bookings (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    tour_id         INTEGER REFERENCES tour_catalog(id),
    guest_id        INTEGER REFERENCES guests(id),
    booking_id      VARCHAR(50) REFERENCES bookings(id),
    tour_date       DATE NOT NULL,
    tour_time       TIME,
    adults_count    INTEGER DEFAULT 1,
    children_count  INTEGER DEFAULT 0,
    guide_name      VARCHAR(100),
    total_price     DECIMAL(10,2) DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'confirmed',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tb_client_date ON tour_bookings(client_id, tour_date);

-- ──────────────────────────────────────────────────────────────
-- م14ب: وجهات سياحية — Tourist Destinations
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tourist_destinations (
    id                  SERIAL PRIMARY KEY,
    client_id           VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    dest_code           VARCHAR(30) NOT NULL,
    name_ar             VARCHAR(200) NOT NULL,
    name_en             VARCHAR(200),
    description_ar      TEXT,
    city                VARCHAR(100),
    category            VARCHAR(50) DEFAULT 'heritage',
    latitude            DECIMAL(10,7),
    longitude           DECIMAL(10,7),
    entry_fee_adult     DECIMAL(10,2) DEFAULT 0,
    entry_fee_child     DECIMAL(10,2) DEFAULT 0,
    opening_hours       VARCHAR(200),
    website_url         TEXT,
    visit_duration_hours DECIMAL(5,1) DEFAULT 2,
    max_group_size      INTEGER DEFAULT 20,
    avg_rating          DECIMAL(3,2) DEFAULT 0,
    reviews_count       INTEGER DEFAULT 0,
    status              VARCHAR(20) DEFAULT 'active',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, dest_code)
);
CREATE INDEX IF NOT EXISTS idx_dest_client ON tourist_destinations(client_id, status);

CREATE TABLE IF NOT EXISTS destination_pois (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    destination_id  INTEGER REFERENCES tourist_destinations(id) ON DELETE CASCADE,
    name_ar         VARCHAR(200) NOT NULL,
    poi_type        VARCHAR(50) DEFAULT 'attraction',
    description_ar  TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS destination_bookings (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    destination_id  INTEGER REFERENCES tourist_destinations(id),
    guest_id        INTEGER REFERENCES guests(id),
    booking_id      VARCHAR(50) REFERENCES bookings(id),
    visit_date      DATE NOT NULL,
    visit_time      TIME,
    adults_count    INTEGER DEFAULT 1,
    children_count  INTEGER DEFAULT 0,
    guide_required  BOOLEAN DEFAULT FALSE,
    guide_name      VARCHAR(100),
    total_price     DECIMAL(10,2) DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'confirmed',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_db_client_date ON destination_bookings(client_id, visit_date);

CREATE TABLE IF NOT EXISTS destination_reviews (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    destination_id  INTEGER REFERENCES tourist_destinations(id) ON DELETE CASCADE,
    guest_id        INTEGER REFERENCES guests(id),
    rating          INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text     TEXT,
    visit_date      DATE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rev_dest ON destination_reviews(destination_id);

-- ──────────────────────────────────────────────────────────────
-- نظام الإشعارات — Notifications
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notifications (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    type            VARCHAR(30) DEFAULT 'info',
    title_ar        VARCHAR(200) NOT NULL,
    body_ar         TEXT,
    is_read         BOOLEAN DEFAULT FALSE,
    ref_type        VARCHAR(50),
    ref_id          VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_notif_client ON notifications(client_id, is_read, created_at DESC);

-- ──────────────────────────────────────────────────────────────
-- Triggers للوحدات الجديدة
-- ──────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;
"""

# ── Staff App migrations — room accountability ────────────────────────────────
STAFF_APP_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS room_actions (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50),
    room_number     VARCHAR(20) NOT NULL,
    action_type     VARCHAR(40) NOT NULL,
    performed_by    VARCHAR(100) NOT NULL,
    previous_status VARCHAR(30),
    new_status      VARCHAR(30),
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_room_actions_client ON room_actions(client_id, room_number);
CREATE INDEX IF NOT EXISTS idx_room_actions_staff  ON room_actions(performed_by)
"""

STAFF_APP_ALTER = [
    "ALTER TABLE rooms ADD COLUMN IF NOT EXISTS last_action_by  VARCHAR(100)",
    "ALTER TABLE rooms ADD COLUMN IF NOT EXISTS last_action_at  TIMESTAMPTZ",
    "ALTER TABLE rooms ADD COLUMN IF NOT EXISTS current_guest   VARCHAR(200)",
    "ALTER TABLE rooms ADD COLUMN IF NOT EXISTS checkout_due    VARCHAR(10)",
]


def run_staff_app_migrations(db) -> None:
    import logging
    log = logging.getLogger("dheuof.db.staff_app")
    if not db.use_postgres:
        return
    for stmt in split_sql(STAFF_APP_MIGRATIONS):
        s = stmt.strip()
        if has_executable_sql(s):
            try:
                db.execute(s)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    log.warning(f"staff_app migration: {e}")
    for stmt in STAFF_APP_ALTER:
        try:
            db.execute(stmt)
        except Exception as e:
            if "already exists" not in str(e).lower():
                log.warning(f"ALTER rooms: {e}")
    log.info("✅ Staff App migrations — room_actions + accountability columns")


NEW_TRIGGERS = [
    ("trg_gp_updated",   "guest_profiles"),
    ("trg_emp_updated",  "employees"),
]

# ── Sessions table migration ────────────────────────────────────────────────
SESSIONS_MIGRATION = """
CREATE TABLE IF NOT EXISTS client_sessions (
    token       VARCHAR(64) PRIMARY KEY,
    client_id   VARCHAR(50) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL,
    user_agent  TEXT,
    ip_address  VARCHAR(50)
);
CREATE INDEX IF NOT EXISTS idx_csess_client ON client_sessions(client_id);
CREATE INDEX IF NOT EXISTS idx_csess_exp    ON client_sessions(expires_at)
"""


def run_sessions_migration(db) -> None:
    import logging
    log = logging.getLogger("dheuof.db.sessions")
    if not db.use_postgres:
        return
    for stmt in split_sql(SESSIONS_MIGRATION):
        s = stmt.strip()
        if has_executable_sql(s):
            try:
                db.execute(s)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    log.warning(f"sessions migration: {e}")
    log.info("✅ client_sessions table ready")


# ── Row Level Security — عزل المستأجرين على مستوى قاعدة البيانات ───────────

# الدور المُقيَّد الذي يسري عليه RLS. المالك يتجاوز السياسات دائماً ما لم
# تُفرَض بـ FORCE، لذلك التطبيق في الإنتاج يجب أن يتصل بهذا الدور.
APP_ROLE = "dheuof_app"

# جداول لا تحمل client_id ولا تخضع للعزل الصفّي
_RLS_EXEMPT = {"po_items", "marketers"}

# جداول يجوز أن يكون client_id فيها NULL بمعنى «قالب عام مقروء للجميع»
_RLS_GLOBAL_TEMPLATE = {"staff_roles"}

# سجل المراجعة: القراءة مقصورة على صفوف المنشأة، أما الإضافة فمسموحة
# دائماً. سياسة القراءة وحدها كانت ستمنع تسجيل عمليات مالك المنصة —
# فهي بلا سياق مستأجر، فيفشل شرط WITH CHECK ويضيع أثر أخطر العمليات.
_RLS_APPEND_ONLY = {"audit_log"}


def _tenant_tables(db) -> list:
    """يستخرج من الكتالوج كل جدول يحمل عمود client_id.

    الاستخراج من الكتالوج لا من قائمة ثابتة: أي جدول جديد يُضاف لاحقاً
    يُحمى تلقائياً بدل أن يُنسى. القائمة الثابتة القديمة كانت تغطي 7
    جداول من أصل 67.
    """
    rows = db.execute(
        """
        SELECT c.relname AS t
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
          AND EXISTS (
              SELECT 1 FROM information_schema.columns col
              WHERE col.table_schema = 'public'
                AND col.table_name   = c.relname
                AND col.column_name  = 'client_id'
          )
        ORDER BY c.relname
        """,
        fetch="all",
    ) or []
    return [r["t"] for r in rows if r["t"] not in _RLS_EXEMPT]


def run_reporting_views(db) -> None:
    """يُنشئ طرق العرض التقريرية من specs/db/05-reporting-views.sql.

    كان في المشروع كله طريقة عرض واحدة (v_security_definer_audit) رغم
    أن القسم العاشر من وثيقة التصميم يسرد أكثر من عشرين تقريراً — كلها
    استعلامات في Markdown لا كائنات في قاعدة البيانات.
    """
    if not db.use_postgres:
        return
    import logging
    import os
    log = logging.getLogger("dheuof.db.views")

    path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "specs", "db", "05-reporting-views.sql")
    )
    if not os.path.exists(path):
        log.warning(f"⚠️  ملف طرق العرض غير موجود: {path}")
        return

    with open(path, encoding="utf-8") as f:
        raw = f.read()

    ok = fail = 0
    for stmt in split_sql(raw):
        s = stmt.strip()
        if not has_executable_sql(s):
            continue
        try:
            db.execute(s)
            ok += 1
        except Exception as e:
            log.warning(f"view stmt failed: {e} | SQL: {s[:80]}")
            fail += 1

    log.info(f"✅ طرق العرض التقريرية — {ok} عبارة، {fail} فشل")

    # التحقق من security_invoker: طريقة عرض بدونه تتجاوز سياسات RLS،
    # فتُظهر لكل منشأة أرقامَ المنشآت الأخرى.
    try:
        leaky = db.execute(
            """
            SELECT c.relname AS v
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'v'
              AND c.relname LIKE 'v_%'
              AND NOT COALESCE(
                  (SELECT option_value = 'true' FROM pg_options_to_table(c.reloptions)
                   WHERE option_name = 'security_invoker'), FALSE)
            """,
            fetch="all",
        ) or []
        if leaky:
            log.error(
                "❌ طرق عرض بلا security_invoker (تتجاوز عزل المستأجرين): "
                f"{[r['v'] for r in leaky]}"
            )
    except Exception as e:
        log.warning(f"فحص security_invoker: {e}")


# ── توثيق داخل قاعدة البيانات — COMMENT ON ─────────────────────────────────
#
# لم يكن في قاعدة البيانات ولا تعليق واحد. التوثيق كان كله في ملف
# Markdown منفصل يسهل أن ينحرف عن الواقع — كما حدث فعلاً مع ادّعاء
# bcrypt. التعليق داخل الكتالوج يظهر في \d+ وفي أدوات العرض ويرافق
# المخطط أينما ذهب.
_TABLE_COMMENTS = {
    "clients":              "المنشآت المشتركة — الجذر الذي يتفرّع منه كل شيء عبر client_id",
    "subscriptions":        "اشتراكات المنشآت وخططها ومددها",
    "rooms":                "الغرف والوحدات السكنية",
    "guests":               "النزلاء. رقم الهوية مشفَّر في id_number_enc والبحث عبر id_number_bidx",
    "bookings":             "الحجوزات — من التأكيد حتى المغادرة",
    "invoices":             "الفواتير الضريبية المتوافقة مع هيئة الزكاة والضريبة",
    "pos_transactions":     "حركات نقاط البيع",
    "pos_sales":            "مبيعات نقاط البيع بتفصيل الضريبة",
    "employees":            "الموظفون. الهوية والإقامة مشفّرتان في الأعمدة المنتهية بـ _enc",
    "payroll":              "مسيّرات الرواتب الشهرية",
    "warehouse_items":      "أصناف المستودعات وحدود إعادة الطلب",
    "warehouse_movements":  "حركات دخول وخروج المخزون",
    "housekeeping_tasks":   "مهام التدبير المنزلي",
    "maintenance_orders":   "أوامر الصيانة",
    "audit_log":            "سجل المراجعة — إضافة فقط: UPDATE و DELETE ممنوعان بمُشغّل ودون امتياز",
    "staff_roles":          "أدوار الموظفين. client_id فارغ يعني قالباً عاماً لكل المنشآت",
    "staff_role_assignments": "إسناد الأدوار للموظفين — يُقرأ عبر app_has_perm()",
    "branches":             "فروع المنشأة الواحدة",
    "revoked_sessions":     "الجلسات المُبطَلة — تُنظَّف بـ cleanup_revoked_sessions()",
    "guest_sessions":       "جلسات النزلاء المعزولة عن جلسات الموظفين",
    "secure_file_links":    "روابط ملفات قصيرة العمر بمسار tenant/branch/guest",
    "client_sessions":      "جلسات المنشآت النشطة",
    "zatca_invoices":       "فواتير هيئة الزكاة والضريبة والجمارك",
    "marketers":            "المسوّقون بالعمولة — على مستوى المنصة لا المنشأة",
    "marketer_referrals":   "إحالات المسوّقين إلى المنشآت",
    "notifications":        "إشعارات داخل المنصة",
    "channel_configs":      "إعدادات قنوات التوزيع الخارجية",
    "api_keys":             "مفاتيح الـ API — يُخزَّن هاش المفتاح لا المفتاح",
}

_COLUMN_COMMENTS = {
    ("guests", "id_number"):
        "متروك فارغاً في الصفوف الجديدة — القيمة في id_number_enc مشفّرة",
    ("guests", "id_number_enc"):
        "رقم الهوية مشفَّراً بـ AES-256-GCM (بادئة enc:v1:)",
    ("guests", "id_number_bidx"):
        "فهرس أعمى HMAC-SHA256 للبحث بالمساواة دون فكّ التشفير",
    ("employees", "national_id_enc"):
        "الهوية الوطنية مشفَّرة بـ AES-256-GCM",
    ("employees", "iqama_number_enc"):
        "رقم الإقامة مشفَّراً بـ AES-256-GCM",
    ("staff_roles", "client_id"):
        "NULL يعني قالب دور عام متاح لكل المنشآت",
    ("bookings", "tax_mode"):
        "MODE_A: الضريبة على الضيف — MODE_B: تتحمّلها المنشأة",
}


def run_table_comments(db) -> None:
    """يكتب توثيق الجداول والأعمدة داخل كتالوج قاعدة البيانات."""
    if not db.use_postgres:
        return
    import logging
    log = logging.getLogger("dheuof.db.comments")
    done = 0

    for table, comment in _TABLE_COMMENTS.items():
        try:
            exists = db.execute(
                "SELECT to_regclass(%s) IS NOT NULL AS ok", (f"public.{table}",), fetch="one"
            )
            if not exists or not exists["ok"]:
                continue
            db.execute(f"COMMENT ON TABLE {table} IS %s", (comment,))
            done += 1
        except Exception as e:
            log.warning(f"COMMENT ON TABLE {table}: {e}")

    for (table, column), comment in _COLUMN_COMMENTS.items():
        try:
            exists = db.execute(
                "SELECT COUNT(*) AS n FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=%s AND column_name=%s",
                (table, column), fetch="one",
            )
            if not exists or not exists["n"]:
                continue
            db.execute(f"COMMENT ON COLUMN {table}.{column} IS %s", (comment,))
            done += 1
        except Exception as e:
            log.warning(f"COMMENT ON COLUMN {table}.{column}: {e}")

    log.info(f"✅ توثيق قاعدة البيانات — {done} تعليقاً")


def apply_tenant_rls(db, table: str, key: str = "client_id") -> bool:
    """يُطبّق سياسة العزل على جدول واحد — للجداول التي تُنشأ بعد الإقلاع.

    عدة جداول تُنشأ كسولاً عند أول استخدام (api_keys، channel_connections،
    channel_reservations). لو انتظرنا ترحيل الإقلاع التالي لبقيت بلا
    سياسة طوال عمر العملية الحالية. يُستدعى هذا مباشرة بعد CREATE TABLE.

    يُعيد True عند النجاح.
    """
    if not db or not db.use_postgres:
        return False
    import logging
    import os
    log = logging.getLogger("dheuof.db.rls")
    enforce = os.environ.get("RLS_ENFORCE", "").strip().lower() in ("1", "true", "yes")
    predicate = f"{key} = current_setting('app.tenant_id', true)"
    try:
        db.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        db.execute(
            f"ALTER TABLE {table} {'FORCE' if enforce else 'NO FORCE'} ROW LEVEL SECURITY"
        )
        db.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        db.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({predicate}) WITH CHECK ({predicate})"
        )
        return True
    except Exception as e:
        log.warning(f"apply_tenant_rls({table}): {e}")
        return False


def run_rls_migration(db) -> None:
    """يُنشئ سياسات عزل حقيقية لكل جدول مستأجر.

    الحالة السابقة: RLS مُفعَّل على 7 جداول بصفر سياسات، والسياسة الوحيدة
    مكتوبة كتعليق. تفعيل RLS بلا سياسة يعني في PostgreSQL منع كل الصفوف
    عن غير المالك — لكن التطبيق يتصل بالمالك، والمالك يتجاوز RLS. أي أن
    العزل الفعلي كان صفراً بينما يبدو الجدول «مؤمَّناً».

    التطبيق هنا:
      • سياسة tenant_isolation على كل جدول يحمل client_id (67 جدولاً)
      • سياسة على clients نفسه عبر عمود id
      • FORCE ROW LEVEL SECURITY حين RLS_ENFORCE=1 — يجعل السياسات تسري
        على المالك أيضاً، وهو ما يلزم لأن التطبيق يتصل بالمالك حالياً
    """
    if not db.use_postgres:
        return
    import logging
    import os
    log = logging.getLogger("dheuof.db.rls")

    enforce = os.environ.get("RLS_ENFORCE", "").strip().lower() in ("1", "true", "yes")
    tables = _tenant_tables(db)
    applied = 0

    for table in tables:
        key = "client_id"
        predicate = f"{key} = current_setting('app.tenant_id', true)"
        if table in _RLS_GLOBAL_TEMPLATE:
            # القوالب العامة (client_id IS NULL) مقروءة للجميع
            predicate = f"({predicate} OR {key} IS NULL)"
        try:
            db.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            db.execute(
                f"ALTER TABLE {table} "
                f"{'FORCE' if enforce else 'NO FORCE'} ROW LEVEL SECURITY"
            )
            db.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
            db.execute(f"DROP POLICY IF EXISTS audit_append ON {table}")

            if table in _RLS_APPEND_ONLY:
                # القراءة مقصورة على صفوف المنشأة، والإضافة مسموحة دائماً.
                # لولا ذلك لتعذّر تسجيل عمليات مالك المنصة — فهي بلا سياق
                # مستأجر، فيفشل شرط WITH CHECK ويضيع أثر أخطر العمليات.
                db.execute(
                    f"CREATE POLICY tenant_isolation ON {table} "
                    f"FOR SELECT USING ({predicate})"
                )
                db.execute(
                    f"CREATE POLICY audit_append ON {table} "
                    f"FOR INSERT WITH CHECK (true)"
                )
            else:
                db.execute(
                    f"CREATE POLICY tenant_isolation ON {table} "
                    f"USING ({predicate}) WITH CHECK ({predicate})"
                )
            applied += 1
        except Exception as e:
            log.warning(f"RLS {table}: {e}")

    # جدول clients يستخدم id لا client_id
    try:
        db.execute("ALTER TABLE clients ENABLE ROW LEVEL SECURITY")
        db.execute(
            f"ALTER TABLE clients {'FORCE' if enforce else 'NO FORCE'} ROW LEVEL SECURITY"
        )
        db.execute("DROP POLICY IF EXISTS tenant_isolation ON clients")
        db.execute(
            "CREATE POLICY tenant_isolation ON clients "
            "USING (id = current_setting('app.tenant_id', true)) "
            "WITH CHECK (id = current_setting('app.tenant_id', true))"
        )
        applied += 1
    except Exception as e:
        log.warning(f"RLS clients: {e}")

    mode = "مفروضة على المالك (FORCE)" if enforce else "غير مفروضة على المالك"
    log.info(f"✅ RLS — {applied} جدولاً بسياسة عزل، {mode}")
    if not enforce:
        log.warning(
            "⚠️  RLS_ENFORCE غير مضبوط: التطبيق يتصل بمالك الجداول فيتجاوز "
            "السياسات. العزل يعتمد حالياً على طبقة التطبيق وحدها."
        )


def run_app_role_migration(db) -> None:
    """يُنشئ الدور المُقيَّد dheuof_app بأقل امتيازات ممكنة.

    لم يكن في المستودع أي CREATE ROLE أو GRANT قابل للتنفيذ — القسم 13.8
    من وثيقة التصميم يعرضها كمثال في Markdown فقط. هذا الدور هو ما يجب
    أن يتصل به التطبيق في الإنتاج كي تسري عليه سياسات RLS.
    """
    if not db.use_postgres:
        return
    import logging
    log = logging.getLogger("dheuof.db.roles")

    try:
        db.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                    CREATE ROLE {APP_ROLE} NOLOGIN;
                END IF;
            END
            $$
        """)
        # قراءة/كتابة البيانات فقط — لا DDL ولا حذف جداول
        db.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
        db.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"
        )
        db.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")
        # الجداول المستقبلية ترث نفس الامتيازات تلقائياً
        db.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}"
        )
        db.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE}"
        )
        # سجل المراجعة لا يُعدَّل ولا يُحذف — إضافة فقط
        db.execute(f"REVOKE UPDATE, DELETE ON audit_log FROM {APP_ROLE}")
        log.info(f"✅ الدور {APP_ROLE} جاهز بأقل الامتيازات")
    except Exception as e:
        log.warning(f"app role migration: {e}")


# ── Performance indexes for hot multi-tenant query paths ────────────────────
PERF_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_bookings_client_status   ON bookings(client_id, status);
CREATE INDEX IF NOT EXISTS idx_bookings_client_checkin  ON bookings(client_id, check_in);
CREATE INDEX IF NOT EXISTS idx_bookings_client_checkout ON bookings(client_id, check_out);
CREATE INDEX IF NOT EXISTS idx_bookings_client_room     ON bookings(client_id, room_id);
CREATE INDEX IF NOT EXISTS idx_rooms_client_status      ON rooms(client_id, status);
CREATE INDEX IF NOT EXISTS idx_guests_client_created    ON guests(client_id, created_at);
CREATE INDEX IF NOT EXISTS idx_employees_client_status  ON employees(client_id, status);
CREATE INDEX IF NOT EXISTS idx_maint_client_status      ON maintenance_orders(client_id, status);
CREATE INDEX IF NOT EXISTS idx_checkin_client_date      ON check_in_log(client_id, checked_in_at);
CREATE INDEX IF NOT EXISTS idx_wmov_client              ON warehouse_movements(client_id, created_at);
"""


def run_perf_indexes(db) -> None:
    """Create composite indexes on (client_id, hot_column) for fast tenant queries.

    Idempotent — every statement is CREATE INDEX IF NOT EXISTS. Failures on a
    not-yet-created table are ignored (the table's own migration runs elsewhere).
    """
    if not db.use_postgres:
        return
    import logging
    log = logging.getLogger("dheuof")
    for stmt in split_sql(PERF_INDEXES):
        s = stmt.strip()
        if has_executable_sql(s):
            try:
                db.execute(s)
            except Exception as e:
                err = str(e).lower()
                if "does not exist" not in err and "already exists" not in err:
                    log.warning(f"perf index: {e}")


def run_v3_migrations(db) -> None:
    import logging
    log = logging.getLogger("dheuof.db.migrations")
    log.info("🔄 تطبيق migrations v3 — جميع الوحدات الـ 15...")

    for statement in split_sql(SCHEMA_V3_MODULES):
        s = statement.strip()
        if has_executable_sql(s):
            try:
                db.execute(s)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    log.error(f"خطأ v3: {e}\nSQL: {s[:80]}")

    for trigger_name, table_name in NEW_TRIGGERS:
        try:
            existing = db.execute(
                "SELECT 1 FROM information_schema.triggers WHERE trigger_name = %s",
                (trigger_name,), fetch="one"
            )
            if not existing:
                db.execute(f"""
                    CREATE TRIGGER {trigger_name}
                    BEFORE UPDATE ON {table_name}
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at()
                """)
        except Exception as e:
            log.warning(f"Trigger {trigger_name}: {e}")

    log.info("✅ v3 migrations اكتملت")


# ── Security Hardening migrations (Isolation Audit — 10 findings) ──────────

def run_security_hardening(db) -> None:
    """
    تطبيق ملف SQL الأمني — specs/db/04-isolation-hardening.sql
    يعالج النقاط العشر من تقرير فحص أمن العزل.
    """
    import logging
    import os
    log = logging.getLogger("dheuof.db.security")

    if not db.use_postgres:
        log.info("⏭  Security hardening skipped — JSON fallback mode")
        return

    sql_path = os.path.join(os.path.dirname(__file__), "..", "specs", "db", "04-isolation-hardening.sql")
    sql_path = os.path.normpath(sql_path)

    if not os.path.exists(sql_path):
        log.warning(f"⚠️  Security hardening SQL not found: {sql_path}")
        return

    with open(sql_path, "r", encoding="utf-8") as f:
        raw_sql = f.read()

    # تقسيم على ';' مع تجاهل الـ DO $$ blocks بشكل صحيح
    statements = _split_sql_safe(raw_sql)
    ok = fail = skipped = 0
    for stmt in statements:
        s = stmt.strip()
        # تخطَّ الكتل التعليقية البحتة فقط — لا كل عبارة مسبوقة بتعليق.
        # الفحص القديم `s.startswith("--")` كان يُسقط 19 من 24 عبارة أمنية.
        if not has_executable_sql(s):
            skipped += 1
            continue
        try:
            db.execute(s)
            ok += 1
        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ("already exists", "duplicate", "42p07", "42710")):
                ok += 1
            else:
                log.warning(f"hardening stmt failed: {e} | SQL: {s[:80]}")
                fail += 1

    # تشغيل audit على SECURITY DEFINER functions
    try:
        from db.security import audit_security_definer_functions
        funcs = audit_security_definer_functions(db)
        if funcs:
            log.warning(f"⚠️  SECURITY DEFINER functions detected ({len(funcs)}): "
                        f"{[f['function_name'] for f in funcs]}")
    except Exception as e:
        log.warning(f"SECURITY DEFINER audit: {e}")

    if fail:
        log.error(f"❌ Security hardening — {ok} OK, {fail} FAILED, {skipped} comment-only")
        raise RuntimeError(
            f"فشل تطبيق التحصين الأمني: {fail} عبارة لم تُنفَّذ. "
            "لا يجوز تشغيل المنصة بعزل مستأجرين ناقص — راجع السجل أعلاه."
        )
    log.info(f"✅ Security hardening — {ok} statements OK, {skipped} comment-only")


def _split_sql_safe(sql: str) -> list:
    """تقسيم SQL بشكل آمن — غلاف حول db.sqlsplit.split_sql.

    محفوظ بهذا الاسم لأن وحدات أخرى تستورده. المنطق الحقيقي في
    db/sqlsplit.py، والذي يتعامل مع $tag$ والنصوص والتعليقات المتداخلة.
    """
    return split_sql(sql)


# ══════════════════════════════════════════════════════════════
#  v4 migrations — ZATCA + Night Audit + Reviews + Payments
# ══════════════════════════════════════════════════════════════

_SCHEMA_V4 = """
-- ──────────────────────────────────────────────────────────────
-- ZATCA — الفواتير الإلكترونية
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS zatca_invoices (
    id               SERIAL PRIMARY KEY,
    client_id        VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    invoice_number   VARCHAR(50) UNIQUE NOT NULL,
    booking_id       VARCHAR(100),
    guest_id         VARCHAR(100),
    invoice_type     VARCHAR(20)  DEFAULT 'SIMPLIFIED',
    issue_date       TIMESTAMPTZ  DEFAULT NOW(),
    supply_date      TIMESTAMPTZ  DEFAULT NOW(),
    subtotal         DECIMAL(12,2) DEFAULT 0,
    discount         DECIMAL(12,2) DEFAULT 0,
    vat_rate         DECIMAL(5,4)  DEFAULT 0.15,
    vat_amount       DECIMAL(12,2) DEFAULT 0,
    total            DECIMAL(12,2) DEFAULT 0,
    vat_number       VARCHAR(20),
    buyer_name       VARCHAR(200),
    buyer_vat        VARCHAR(20),
    zatca_uuid       VARCHAR(100),
    zatca_hash       VARCHAR(200),
    zatca_status     VARCHAR(20)  DEFAULT 'PENDING',
    qr_tlv_base64    TEXT,
    qr_image_base64  TEXT,
    xml_signed       TEXT,
    pdf_url          VARCHAR(500),
    is_deleted       BOOLEAN DEFAULT FALSE,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_zatca_client ON zatca_invoices(client_id);
CREATE INDEX IF NOT EXISTS idx_zatca_booking ON zatca_invoices(booking_id);
CREATE INDEX IF NOT EXISTS idx_zatca_status ON zatca_invoices(zatca_status);

-- ──────────────────────────────────────────────────────────────
-- Night Audit — إعدادات وسجل الإغلاق اليومي
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS night_audit_settings (
    id                      SERIAL PRIMARY KEY,
    client_id               VARCHAR(50) UNIQUE REFERENCES clients(id) ON DELETE CASCADE,
    auto_run                BOOLEAN DEFAULT FALSE,
    scheduled_time          VARCHAR(5)  DEFAULT '23:59',
    default_check_in_time   VARCHAR(5)  DEFAULT '14:00',
    default_check_out_time  VARCHAR(5)  DEFAULT '12:00',
    grace_period_minutes    INTEGER DEFAULT 30,
    require_payment_close   BOOLEAN DEFAULT TRUE,
    updated_by              VARCHAR(100),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS night_audit_log (
    id                  SERIAL PRIMARY KEY,
    client_id           VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    audit_date          DATE NOT NULL,
    status              VARCHAR(20)  DEFAULT 'PENDING',
    trigger_type        VARCHAR(20)  DEFAULT 'MANUAL',
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    performed_by        VARCHAR(100),
    rooms_audited       INTEGER DEFAULT 0,
    payments_verified   INTEGER DEFAULT 0,
    unsettled_payments  INTEGER DEFAULT 0,
    total_revenue       DECIMAL(12,2) DEFAULT 0,
    errors_count        INTEGER DEFAULT 0,
    report_data         JSONB DEFAULT '{}',
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_log_client ON night_audit_log(client_id, audit_date);

-- ──────────────────────────────────────────────────────────────
-- أجهزة الدفع
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS payment_devices (
    id               SERIAL PRIMARY KEY,
    client_id        VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    device_name      VARCHAR(100) NOT NULL,
    device_type      VARCHAR(30)  DEFAULT 'POS',
    serial_number    VARCHAR(100),
    is_active        BOOLEAN DEFAULT TRUE,
    last_settled_at  TIMESTAMPTZ,
    daily_total      DECIMAL(12,2) DEFAULT 0,
    is_deleted       BOOLEAN DEFAULT FALSE,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_devices_client ON payment_devices(client_id);

-- ──────────────────────────────────────────────────────────────
-- تقييمات الحجوزات
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS booking_reviews (
    id               SERIAL PRIMARY KEY,
    client_id        VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    booking_id       VARCHAR(100) NOT NULL,
    guest_id         VARCHAR(100),
    recorded_by      VARCHAR(100),
    overall_rating   SMALLINT CHECK (overall_rating BETWEEN 1 AND 5),
    cleanliness      SMALLINT CHECK (cleanliness    BETWEEN 1 AND 5),
    service          SMALLINT CHECK (service        BETWEEN 1 AND 5),
    location         SMALLINT CHECK (location       BETWEEN 1 AND 5),
    value_for_money  SMALLINT CHECK (value_for_money BETWEEN 1 AND 5),
    comment          TEXT,
    is_public        BOOLEAN DEFAULT TRUE,
    management_reply TEXT,
    replied_by       VARCHAR(100),
    replied_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, booking_id)
);
CREATE INDEX IF NOT EXISTS idx_reviews_client ON booking_reviews(client_id);
"""


def run_v4_migrations(db) -> None:
    """تشغيل migrations الوحدات الجديدة — ZATCA + Night Audit + Reviews"""
    import logging
    log = logging.getLogger("dheuof.db.migrations")
    if not db.use_postgres:
        log.info("v4 migrations: JSON mode — skip")
        return
    ok = fail = 0
    for s in _split_sql_safe(_SCHEMA_V4):
        s = s.strip()
        if not s:
            continue
        try:
            db.execute(s)
            ok += 1
        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ("already exists", "duplicate", "42p07", "42710")):
                ok += 1
            else:
                log.warning(f"v4 migration failed: {e} | SQL: {s[:80]}")
                fail += 1
    log.info(f"✅ v4 migrations — {ok} OK, {fail} failed")

    # ── ضريبة السياحة (Tourism Tax 2.5%) — أعمدة zatca_invoices ─
    _tourism_cols = [
        "tourism_tax_rate   DECIMAL(5,4) DEFAULT 0.025",
        "tourism_tax_amount DECIMAL(12,2) DEFAULT 0",
        "tax_absorbed_by    VARCHAR(20)   DEFAULT 'guest'",
    ]
    for col_def in _tourism_cols:
        col_name = col_def.split()[0]
        try:
            db.execute(
                f"ALTER TABLE zatca_invoices ADD COLUMN IF NOT EXISTS {col_def}"
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                log.warning(f"tourism tax col {col_name}: {e}")

    # ── أعمدة الضريبة المركزية — bookings ────────────────────────
    _booking_tax_cols = [
        "tax_mode            VARCHAR(10)   DEFAULT 'MODE_A'",
        "vat_amount          DECIMAL(12,2) DEFAULT 0",
        "tourism_tax_amount  DECIMAL(12,2) DEFAULT 0",
    ]
    for col_def in _booking_tax_cols:
        col_name = col_def.split()[0]
        try:
            db.execute(
                f"ALTER TABLE bookings ADD COLUMN IF NOT EXISTS {col_def}"
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                log.warning(f"bookings tax col {col_name}: {e}")

    # ── employees.updated_at ─────────────────────────────────────
    # المُشغّل trg_emp_updated يُنفّذ update_updated_at() التي تُسنِد
    # NEW.updated_at، والعمود غير موجود في employees. النتيجة أن كل
    # UPDATE على جدول الموظفين يفشل بـ «record "new" has no field
    # updated_at» — أي أن تعديل بيانات موظف وإنهاء خدمته كانا معطَّلين.
    try:
        db.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()")
    except Exception as e:
        if "already exists" not in str(e).lower():
            log.warning(f"employees.updated_at: {e}")

    # حارس عام: أي جدول عليه مُشغّل التحديث ولا يحمل العمود سيفشل عند
    # أول UPDATE. الفحص هنا يكشفه عند الإقلاع بدل أن يكتشفه مستخدم.
    try:
        mismatched = db.execute(
            """
            SELECT DISTINCT t.event_object_table AS t
            FROM information_schema.triggers t
            WHERE t.action_statement LIKE '%%update_updated_at%%'
              AND NOT EXISTS (
                  SELECT 1 FROM information_schema.columns c
                  WHERE c.table_schema = 'public'
                    AND c.table_name = t.event_object_table
                    AND c.column_name = 'updated_at')
            """,
            fetch="all",
        ) or []
        for row in mismatched:
            try:
                db.execute(
                    f"ALTER TABLE {row['t']} ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()"
                )
                log.warning(f"أُضيف updated_at إلى {row['t']} — مُشغّل بلا عمود")
            except Exception as e:
                log.error(f"جدول {row['t']} عليه مُشغّل تحديث بلا عمود updated_at: {e}")
    except Exception as e:
        log.warning(f"فحص مُشغّلات updated_at: {e}")

    # ── دخول الموظفين ────────────────────────────────────────────
    # كانت هوية الموظف تُمرَّر كنص staff_name في جسم الطلب — أي أن أي
    # مستخدم للمنشأة ينسب أي عملية لأي موظف. لا مصادقة ولا مساءلة.
    _staff_auth_cols = [
        ("pass_hash",     "TEXT"),
        ("last_login_at", "TIMESTAMPTZ"),
        ("can_login",     "BOOLEAN DEFAULT FALSE"),
    ]
    for _col, _type in _staff_auth_cols:
        try:
            db.execute(f"ALTER TABLE employees ADD COLUMN IF NOT EXISTS {_col} {_type}")
        except Exception as e:
            if "already exists" not in str(e).lower():
                log.warning(f"employees.{_col}: {e}")
    try:
        # employee_id هو ما يكتبه الموظف عند الدخول، فيجب أن يكون فريداً
        # داخل المنشأة الواحدة
        db.execute("""
            DELETE FROM employees a USING employees b
            WHERE a.id > b.id AND a.client_id = b.client_id
              AND a.employee_id = b.employee_id
        """)
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_employees_client_empid "
            "ON employees(client_id, employee_id)"
        )
    except Exception as e:
        if "already exists" not in str(e).lower():
            log.warning(f"employees unique: {e}")

    # ── guest_profiles: قيد فريد لكل نزيل في كل منشأة ────────────
    # مسار منح نقاط الولاء ينفّذ ON CONFLICT (client_id, guest_id)
    # والقيد غير موجود، فيفشل الاستعلام دائماً بـ «there is no unique
    # or exclusion constraint matching the ON CONFLICT specification» —
    # أي أن منح النقاط كان معطَّلاً كلياً لا عند مدخل خاطئ فحسب.
    # القيد صحيح دلالياً: ملف تعريف واحد لكل نزيل في كل منشأة.
    try:
        db.execute("""
            DELETE FROM guest_profiles a USING guest_profiles b
            WHERE a.id > b.id
              AND a.client_id IS NOT DISTINCT FROM b.client_id
              AND a.guest_id  IS NOT DISTINCT FROM b.guest_id
        """)
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_guest_profiles_client_guest "
            "ON guest_profiles(client_id, guest_id)"
        )
    except Exception as e:
        if "already exists" not in str(e).lower():
            log.warning(f"guest_profiles unique: {e}")

    # ── rooms.is_deleted ─────────────────────────────────────────
    # محرك التسعير الديناميكي يُرشّح به في موضعين، والعمود غير موجود —
    # فكل استدعاء لـ _get_rooms_with_rules و count_rooms كان يفشل بـ
    # «column r.is_deleted does not exist». الحذف الناعم نمط قائم سلفاً
    # في zatca_invoices و payment_devices.
    try:
        db.execute("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE")
        db.execute("UPDATE rooms SET is_deleted = FALSE WHERE is_deleted IS NULL")
    except Exception as e:
        if "already exists" not in str(e).lower():
            log.warning(f"rooms.is_deleted: {e}")

    # ── bookings.booking_number ──────────────────────────────────
    # يشير إليه الكود في أربعة ملفات (m17_bookings، m06_accounting،
    # integration) لكنه لم يوجد قط في المخطط. النتيجة أن إنشاء الحجز
    # وتسجيل الوصول والمغادرة وقائمة حجوزات القنوات والفواتير
    # المحاسبية كانت كلها تفشل بـ «column b.booking_number does not
    # exist». رقم مقروء للبشر مستقل عن المفتاح الأساسي (BK-XXXXXXXX).
    try:
        db.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS booking_number VARCHAR(30)")
        # ملء الحجوزات القائمة برقم مشتق من معرّفها
        db.execute(
            "UPDATE bookings SET booking_number = 'BK-' || UPPER(LEFT(MD5(id), 8)) "
            "WHERE booking_number IS NULL"
        )
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_bookings_number "
            "ON bookings(client_id, booking_number)"
        )
    except Exception as e:
        if "already exists" not in str(e).lower():
            log.warning(f"bookings.booking_number: {e}")

    # ── أعمدة ZATCA على invoices ─────────────────────────────────
    # كانت تُضاف كسولاً من services/zatca.py عند أول استخدام، فلا توجد
    # عند الإقلاع — وطرق العرض التقريرية التي تشير إليها تفشل.
    _zatca_invoice_cols = [
        ("zatca_uuid",   "VARCHAR(40)"),
        ("company_name", "VARCHAR(200)"),
        ("seller_vat",   "VARCHAR(20)"),
        ("buyer_name",   "VARCHAR(200)"),
        ("buyer_vat",    "VARCHAR(20)"),
        ("zatca_qr",     "TEXT"),
        ("invoice_hash", "VARCHAR(64)"),
        ("invoice_type", "VARCHAR(20)"),
    ]
    for _col, _type in _zatca_invoice_cols:
        try:
            db.execute(f"ALTER TABLE invoices ADD COLUMN IF NOT EXISTS {_col} {_type}")
        except Exception as e:
            if "already exists" not in str(e).lower():
                log.warning(f"ZATCA col invoices.{_col}: {e}")

    # ── تشفير حقول الهوية — أعمدة النص المشفَّر والفهرس الأعمى ────
    # النص المشفَّر بـ AES-GCM يطول عن VARCHAR(20) فيحتاج عموداً خاصاً،
    # والفهرس الأعمى (HMAC-SHA256) يتيح البحث بالمساواة دون فكّ تشفير.
    _pii_cols = [
        ("guests",    "id_number_enc",       "TEXT"),
        ("guests",    "id_number_bidx",      "VARCHAR(64)"),
        ("employees", "national_id_enc",     "TEXT"),
        ("employees", "national_id_bidx",    "VARCHAR(64)"),
        ("employees", "iqama_number_enc",    "TEXT"),
        ("employees", "iqama_number_bidx",   "VARCHAR(64)"),
    ]
    for _tbl, _col, _type in _pii_cols:
        try:
            db.execute(f"ALTER TABLE {_tbl} ADD COLUMN IF NOT EXISTS {_col} {_type}")
        except Exception as e:
            if "already exists" not in str(e).lower():
                log.warning(f"PII col {_tbl}.{_col}: {e}")
    for _tbl, _col in (("guests", "id_number_bidx"),
                       ("employees", "national_id_bidx"),
                       ("employees", "iqama_number_bidx")):
        try:
            db.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{_tbl}_{_col} "
                f"ON {_tbl}(client_id, {_col})"
            )
        except Exception as e:
            log.warning(f"PII index {_tbl}.{_col}: {e}")

    # ── أعمدة الضريبة المركزية — pos_sales ───────────────────────
    # يُنشأ الجدول هنا لا في routes/m07_pos.py فقط: الإنشاء الكسول كان
    # يعني أن الجدول لا يوجد حتى يزور أحدهم مسار نقاط البيع، فتفشل
    # ترقيات الضريبة أدناه في كل إقلاع على قاعدة جديدة.
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS pos_sales (
                id                 SERIAL PRIMARY KEY,
                client_id          VARCHAR(50),
                sale_number        VARCHAR(30),
                guest_id           INTEGER,
                items              JSONB DEFAULT '[]',
                subtotal           DECIMAL(10,2) DEFAULT 0,
                vat_amount         DECIMAL(10,2) DEFAULT 0,
                tourism_tax_amount DECIMAL(10,2) DEFAULT 0,
                total              DECIMAL(10,2) DEFAULT 0,
                tax_mode           VARCHAR(10)   DEFAULT 'MODE_A',
                payment_method     VARCHAR(30)   DEFAULT 'cash',
                status             VARCHAR(20)   DEFAULT 'completed',
                created_by         VARCHAR(100),
                created_at         TIMESTAMPTZ   DEFAULT NOW()
            )
        """)
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_pos_client ON pos_sales(client_id, created_at)"
        )
    except Exception as e:
        if "already exists" not in str(e).lower():
            log.warning(f"pos_sales create: {e}")

    _pos_tax_cols = [
        "subtotal            DECIMAL(10,2) DEFAULT 0",
        "vat_amount          DECIMAL(10,2) DEFAULT 0",
        "tourism_tax_amount  DECIMAL(10,2) DEFAULT 0",
        "tax_mode            VARCHAR(10)   DEFAULT 'MODE_A'",
    ]
    for col_def in _pos_tax_cols:
        col_name = col_def.split()[0]
        try:
            db.execute(
                f"ALTER TABLE pos_sales ADD COLUMN IF NOT EXISTS {col_def}"
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                log.warning(f"pos_sales tax col {col_name}: {e}")

    # ── أعمدة الضريبة المركزية — purchase_orders ─────────────────
    _po_tax_cols = [
        "vat_amount          DECIMAL(12,2) DEFAULT 0",
        "tourism_tax_amount  DECIMAL(12,2) DEFAULT 0",
        "tax_mode            VARCHAR(10)   DEFAULT 'MODE_A'",
    ]
    for col_def in _po_tax_cols:
        col_name = col_def.split()[0]
        try:
            db.execute(
                f"ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS {col_def}"
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                log.warning(f"purchase_orders tax col {col_name}: {e}")

    # ── جدول القيود المحاسبية (API مفتوح) ────────────────────────
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS journal_entries (
                id          SERIAL PRIMARY KEY,
                client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
                reference   VARCHAR(100),
                entry_date  DATE DEFAULT CURRENT_DATE,
                description TEXT,
                lines       JSONB DEFAULT '[]',
                source      VARCHAR(30) DEFAULT 'external',
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    except Exception as e:
        if "already exists" not in str(e).lower():
            log.warning(f"journal_entries table: {e}")

    # ── مفتاح API للربط بالأنظمة الخارجية (clients.api_key) ─────
    try:
        db.execute(
            "ALTER TABLE clients ADD COLUMN IF NOT EXISTS api_key VARCHAR(80) UNIQUE"
        )
    except Exception as e:
        if "already exists" not in str(e).lower():
            log.warning(f"clients.api_key col: {e}")
