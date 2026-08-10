-- migrations/003_channels_pricing_api.sql
-- الشهر الثالث: Channel Manager + Dynamic Pricing + Open API
-- يُضاف لـ db/migrations.py


-- ─── Channel Manager ─────────────────────────────────────────

-- قنوات الحجز لكل منشأة
CREATE TABLE IF NOT EXISTS channel_configs (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    channel_name    VARCHAR(50) NOT NULL,   -- booking.com · mawasim · airbnb
    is_enabled      BOOLEAN DEFAULT FALSE,
    credentials     JSONB DEFAULT '{}',     -- مُشفَّرة في Railway Variables
    room_mapping    JSONB DEFAULT '{}',     -- room_type_local → room_type_channel
    last_sync       TIMESTAMPTZ,
    sync_errors     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, channel_name)
);

-- حجوزات واردة من القنوات
CREATE TABLE IF NOT EXISTS channel_reservations (
    id                      SERIAL PRIMARY KEY,
    client_id               VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    booking_id              VARCHAR(50) REFERENCES bookings(id),
    channel_name            VARCHAR(50) NOT NULL,
    channel_reservation_id  VARCHAR(100) NOT NULL,
    raw_data                JSONB,
    commission_amount       DECIMAL(10,2) DEFAULT 0,
    net_amount              DECIMAL(10,2) DEFAULT 0,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(channel_name, channel_reservation_id)
);
CREATE INDEX IF NOT EXISTS idx_ch_res_client ON channel_reservations(client_id);
CREATE INDEX IF NOT EXISTS idx_ch_res_booking ON channel_reservations(booking_id);

-- سجل مزامنة القنوات
CREATE TABLE IF NOT EXISTS channel_sync_log (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    channel_name    VARCHAR(50),
    sync_type       VARCHAR(30),    -- availability · rate · reservations · room_mapping
    status          VARCHAR(20),    -- success · failed · partial
    records_count   INTEGER DEFAULT 0,
    error_message   TEXT,
    duration_ms     INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sync_log_client ON channel_sync_log(client_id, created_at DESC);


-- ─── Dynamic Pricing ─────────────────────────────────────────

-- قواعد التسعير لكل غرفة
CREATE TABLE IF NOT EXISTS pricing_rules (
    id                  SERIAL PRIMARY KEY,
    client_id           VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    room_type           VARCHAR(100),           -- null = ينطبق على كل الغرف من هذا النوع
    room_id             INTEGER REFERENCES rooms(id),

    base_price          DECIMAL(10,2) NOT NULL,
    min_price           DECIMAL(10,2) NOT NULL,
    max_price           DECIMAL(10,2) NOT NULL,

    use_occupancy       BOOLEAN DEFAULT TRUE,
    use_lead_time       BOOLEAN DEFAULT TRUE,
    use_day_of_week     BOOLEAN DEFAULT TRUE,
    use_seasons         BOOLEAN DEFAULT TRUE,

    max_change_percent  DECIMAL(5,2) DEFAULT 20.0,
    round_to            DECIMAL(5,2) DEFAULT 5.0,

    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pricing_rules_client ON pricing_rules(client_id);

-- سجل تغييرات الأسعار
CREATE TABLE IF NOT EXISTS pricing_history (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    room_id         INTEGER REFERENCES rooms(id),
    target_date     DATE NOT NULL,

    old_price       DECIMAL(10,2),
    new_price       DECIMAL(10,2),

    occupancy_at_decision   DECIMAL(5,2),
    occupancy_factor        DECIMAL(5,2),
    lead_time_factor        DECIMAL(5,2),
    day_of_week_factor      DECIMAL(5,2),
    season_factor           DECIMAL(5,2),

    reason          TEXT,
    channels_updated JSONB DEFAULT '{}',

    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pricing_client_date ON pricing_history(client_id, target_date);

-- جدول الأسعار الحالية (يُحدَّث تلقائياً من Dynamic Pricing)
CREATE TABLE IF NOT EXISTS room_rates (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    room_id         INTEGER REFERENCES rooms(id),
    rate_date       DATE NOT NULL,
    current_rate    DECIMAL(10,2) NOT NULL,
    is_dynamic      BOOLEAN DEFAULT FALSE,
    last_updated    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(room_id, rate_date)
);
CREATE INDEX IF NOT EXISTS idx_rates_room_date ON room_rates(room_id, rate_date);
CREATE INDEX IF NOT EXISTS idx_rates_client ON room_rates(client_id, rate_date);


-- ─── Open API ─────────────────────────────────────────────────

-- مفاتيح API
CREATE TABLE IF NOT EXISTS api_keys (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    key_hash        VARCHAR(128) UNIQUE NOT NULL,    -- SHA256 للمفتاح
    key_prefix      VARCHAR(15) NOT NULL,             -- أول 12 حرف للتعريف
    name            VARCHAR(100) NOT NULL,
    permissions     TEXT[] DEFAULT '{}',
    is_active       BOOLEAN DEFAULT TRUE,
    last_used       TIMESTAMPTZ,
    request_count   INTEGER DEFAULT 0,
    rate_limit_rpm  INTEGER DEFAULT 60,              -- requests per hour
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_api_keys_client ON api_keys(client_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);

-- سجل استخدام API
CREATE TABLE IF NOT EXISTS api_usage_log (
    id              SERIAL PRIMARY KEY,
    key_id          INTEGER REFERENCES api_keys(id),
    client_id       VARCHAR(50),
    endpoint        VARCHAR(200),
    method          VARCHAR(10),
    status_code     INTEGER,
    ip_address      VARCHAR(45),
    duration_ms     INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_api_usage_key ON api_usage_log(key_id, created_at);
CREATE INDEX IF NOT EXISTS idx_api_usage_client ON api_usage_log(client_id, created_at);


-- ─── إضافة عمود source لـ bookings (إذا لم يكن موجوداً) ──────

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='bookings' AND column_name='source'
    ) THEN
        ALTER TABLE bookings ADD COLUMN source VARCHAR(50) DEFAULT 'direct';
    END IF;
END $$;

-- إضافة updated_at للجداول الأساسية
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='bookings' AND column_name='updated_at'
    ) THEN
        ALTER TABLE bookings ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
    END IF;
END $$;
