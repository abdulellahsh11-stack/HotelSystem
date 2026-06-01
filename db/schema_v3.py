#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/schema_v3.py — مخطط قاعدة بيانات ضيوف الكامل v3.0
جميع الوحدات الـ 15 — يعمل مع نظام الـ migrations الحالي
"""

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
    for stmt in STAFF_APP_MIGRATIONS.split(";"):
        s = stmt.strip()
        if s:
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


def run_v3_migrations(db) -> None:
    import logging
    log = logging.getLogger("dheuof.db.migrations")
    log.info("🔄 تطبيق migrations v3 — جميع الوحدات الـ 15...")

    for statement in SCHEMA_V3_MODULES.split(";"):
        s = statement.strip()
        if s and not s.startswith("--"):
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
