-- ================================================================
-- specs/db/04-isolation-hardening.sql
-- Security Isolation Hardening — النقاط العشر
-- يطبَّق من db/schema_v3.py عند بدء التشغيل
-- ================================================================

-- ──────────────────────────────────────────────────────────────
-- §1 — جلسات الإبطال (Finding #8: JWT/Session Revocation)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS revoked_sessions (
    token_hash  VARCHAR(128) PRIMARY KEY,
    client_id   VARCHAR(50),
    revoked_at  TIMESTAMPTZ DEFAULT NOW(),
    reason      VARCHAR(100) DEFAULT 'logout'
);
CREATE INDEX IF NOT EXISTS idx_revoked_client ON revoked_sessions(client_id);

-- تنظيف تلقائي للجلسات المبطَلة بعد 24 ساعة
CREATE OR REPLACE FUNCTION cleanup_revoked_sessions()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM revoked_sessions WHERE revoked_at < NOW() - INTERVAL '24 hours';
END;
$$;

-- ──────────────────────────────────────────────────────────────
-- §2 — أدوار الموظفين والصلاحيات (Finding #2: RBAC)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS staff_roles (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    role_code   VARCHAR(30) NOT NULL,
    name_ar     VARCHAR(100) NOT NULL,
    permissions JSONB DEFAULT '[]',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, role_code)
);

CREATE TABLE IF NOT EXISTS staff_role_assignments (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    employee_id INTEGER REFERENCES employees(id) ON DELETE CASCADE,
    role_code   VARCHAR(30) NOT NULL,
    branch_id   INTEGER,
    granted_by  VARCHAR(100),
    granted_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, employee_id, role_code)
);
CREATE INDEX IF NOT EXISTS idx_sra_client_emp ON staff_role_assignments(client_id, employee_id);

-- إدراج الأدوار الافتراضية دون تكرار
INSERT INTO staff_roles (client_id, role_code, name_ar, permissions)
SELECT 'system', 'owner',        'مالك المنشأة',    '["*"]'
WHERE NOT EXISTS (SELECT 1 FROM staff_roles WHERE client_id='system' AND role_code='owner');

INSERT INTO staff_roles (client_id, role_code, name_ar, permissions)
SELECT 'system', 'gm',           'مدير عام',        '["rooms","housekeeping","bookings","guests","hr","pos","reports"]'
WHERE NOT EXISTS (SELECT 1 FROM staff_roles WHERE client_id='system' AND role_code='gm');

INSERT INTO staff_roles (client_id, role_code, name_ar, permissions)
SELECT 'system', 'receptionist', 'موظف استقبال',    '["rooms","bookings","guests","pos","checkout"]'
WHERE NOT EXISTS (SELECT 1 FROM staff_roles WHERE client_id='system' AND role_code='receptionist');

INSERT INTO staff_roles (client_id, role_code, name_ar, permissions)
SELECT 'system', 'housekeeper',  'موظف نظافة',      '["housekeeping","rooms.read"]'
WHERE NOT EXISTS (SELECT 1 FROM staff_roles WHERE client_id='system' AND role_code='housekeeper');

INSERT INTO staff_roles (client_id, role_code, name_ar, permissions)
SELECT 'system', 'maintenance',  'موظف صيانة',      '["maintenance","rooms.read"]'
WHERE NOT EXISTS (SELECT 1 FROM staff_roles WHERE client_id='system' AND role_code='maintenance');

INSERT INTO staff_roles (client_id, role_code, name_ar, permissions)
SELECT 'system', 'accountant',   'محاسب',            '["pos","reports","invoices"]'
WHERE NOT EXISTS (SELECT 1 FROM staff_roles WHERE client_id='system' AND role_code='accountant');

-- دالة التحقق من الصلاحية (Finding #2: row-level RBAC guard)
CREATE OR REPLACE FUNCTION app_has_perm(
    p_client_id  TEXT,
    p_employee_id INTEGER,
    p_permission TEXT
)
RETURNS BOOLEAN LANGUAGE plpgsql STABLE SET search_path = public AS $$
DECLARE
    v_perms JSONB;
BEGIN
    -- owner/gm لهم كل الصلاحيات
    SELECT r.permissions INTO v_perms
    FROM staff_role_assignments a
    JOIN staff_roles r ON r.role_code = a.role_code AND r.client_id IN (a.client_id, 'system')
    WHERE a.client_id = p_client_id
      AND a.employee_id = p_employee_id
    LIMIT 1;

    IF v_perms IS NULL THEN RETURN FALSE; END IF;
    IF v_perms ? '*' THEN RETURN TRUE; END IF;
    RETURN v_perms ? p_permission;
END;
$$;

-- ──────────────────────────────────────────────────────────────
-- §3 — عزل الفروع في قاعدة البيانات (Finding #1: Branch RLS)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS branches (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    branch_code VARCHAR(30) NOT NULL,
    name_ar     VARCHAR(150) NOT NULL,
    city        VARCHAR(100),
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, branch_code)
);
CREATE INDEX IF NOT EXISTS idx_branches_client ON branches(client_id, is_active);

-- إضافة branch_id لجداول التشغيل الرئيسية (لا خطأ إن كان موجوداً)
ALTER TABLE rooms             ADD COLUMN IF NOT EXISTS branch_id INTEGER REFERENCES branches(id);
ALTER TABLE bookings          ADD COLUMN IF NOT EXISTS branch_id INTEGER REFERENCES branches(id);
ALTER TABLE housekeeping_tasks ADD COLUMN IF NOT EXISTS branch_id INTEGER REFERENCES branches(id);
ALTER TABLE maintenance_orders ADD COLUMN IF NOT EXISTS branch_id INTEGER REFERENCES branches(id);
ALTER TABLE employees         ADD COLUMN IF NOT EXISTS branch_id INTEGER REFERENCES branches(id);
ALTER TABLE payroll           ADD COLUMN IF NOT EXISTS branch_id INTEGER REFERENCES branches(id);
ALTER TABLE pos_transactions  ADD COLUMN IF NOT EXISTS branch_id INTEGER REFERENCES branches(id);

-- دالة التحقق من أن المستخدم ينتمي للفرع (Finding #1)
CREATE OR REPLACE FUNCTION app_branch_ok(
    p_session_branch_ids INTEGER[],
    p_row_branch_id      INTEGER
)
RETURNS BOOLEAN LANGUAGE sql IMMUTABLE SET search_path = public AS $$
    SELECT p_row_branch_id IS NULL                    -- سجل غير مرتبط بفرع: مرئي للجميع
        OR p_session_branch_ids IS NULL               -- مدير عام: يرى كل شيء
        OR p_row_branch_id = ANY(p_session_branch_ids);
$$;

-- ──────────────────────────────────────────────────────────────
-- §4 — عزل الضيوف (Finding #4: Guest Session Isolation)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS guest_sessions (
    token_hash  VARCHAR(128) PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    guest_id    INTEGER REFERENCES guests(id) ON DELETE CASCADE,
    booking_id  VARCHAR(50) REFERENCES bookings(id) ON DELETE CASCADE,
    actor_type  VARCHAR(20) DEFAULT 'guest',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ DEFAULT NOW() + INTERVAL '48 hours'
);
CREATE INDEX IF NOT EXISTS idx_gs_client_guest ON guest_sessions(client_id, guest_id);
CREATE INDEX IF NOT EXISTS idx_gs_expires ON guest_sessions(expires_at);

-- دالة التحقق من هوية الضيف (Finding #4)
CREATE OR REPLACE FUNCTION app_actor_is_guest(p_token_hash TEXT, p_guest_id INTEGER)
RETURNS BOOLEAN LANGUAGE plpgsql STABLE SET search_path = public AS $$
DECLARE v_gid INTEGER;
BEGIN
    SELECT guest_id INTO v_gid FROM guest_sessions
    WHERE token_hash = p_token_hash
      AND actor_type = 'guest'
      AND expires_at > NOW();
    RETURN v_gid IS NOT NULL AND v_gid = p_guest_id;
END;
$$;

-- ──────────────────────────────────────────────────────────────
-- §5 — نمط مفاتيح الكاش (Finding #5: Cache Key Prefix)
-- ──────────────────────────────────────────────────────────────
-- توثيق: كل مفتاح Redis يجب أن يتبع النمط:
--   {tenant_id}:{resource}:{id}
-- مثال: dheuof001:rooms:active  |  dheuof001:session:abc123
-- لا يوجد وصول للبيانات دون البادئة — مطبَّق في db/security.py
COMMENT ON TABLE revoked_sessions IS
    'Finding #5: Redis key pattern {tid}:{resource}:{id} enforced in db/security.py';

-- ──────────────────────────────────────────────────────────────
-- §6 — سياق المستأجر الآمن (Finding #3: NULL-safe tenant)
-- ──────────────────────────────────────────────────────────────
-- دالة تفشل بصوت إذا لم يُضبط client_id في سياق الجلسة
CREATE OR REPLACE FUNCTION app_tenant(fail_if_missing BOOLEAN DEFAULT TRUE)
RETURNS TEXT LANGUAGE plpgsql STABLE SET search_path = public AS $$
DECLARE v_tid TEXT;
BEGIN
    v_tid := current_setting('app.tenant_id', true);
    IF (v_tid IS NULL OR v_tid = '') AND fail_if_missing THEN
        RAISE EXCEPTION 'app.tenant_id غير مضبوط في السياق الحالي — رفض الاستعلام';
    END IF;
    RETURN v_tid;
END;
$$;

-- ──────────────────────────────────────────────────────────────
-- §7 — مسارات الملفات الآمنة (Finding #7: File Path Security)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS secure_file_links (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    branch_id   INTEGER REFERENCES branches(id),
    guest_id    INTEGER REFERENCES guests(id),
    file_path   TEXT NOT NULL,          -- tenant/branch/guest/filename
    link_token  VARCHAR(128) UNIQUE NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_by  VARCHAR(100),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sfl_token   ON secure_file_links(link_token, expires_at);
CREATE INDEX IF NOT EXISTS idx_sfl_client  ON secure_file_links(client_id, guest_id);

-- ──────────────────────────────────────────────────────────────
-- §8 — دوال SECURITY DEFINER آمنة (Finding #9)
-- ──────────────────────────────────────────────────────────────
-- جرد كل دوال SECURITY DEFINER — يُراجَع دورياً
CREATE OR REPLACE VIEW v_security_definer_audit AS
SELECT  n.nspname          AS schema_name,
        p.proname          AS function_name,
        p.prosecdef        AS is_security_definer,
        pg_get_userbyid(p.proowner) AS owner,
        obj_description(p.oid, 'pg_proc') AS description
FROM    pg_proc p
JOIN    pg_namespace n ON n.oid = p.pronamespace
WHERE   p.prosecdef = TRUE
ORDER BY n.nspname, p.proname;

COMMENT ON VIEW v_security_definer_audit IS
    'Finding #9: قائمة كل دوال SECURITY DEFINER للمراجعة الدورية';

-- ──────────────────────────────────────────────────────────────
-- §9 — سجل المراجعة غير القابل للتعديل (Audit Log)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    client_id   VARCHAR(50) NOT NULL,
    actor_type  VARCHAR(20) DEFAULT 'staff',   -- staff | guest | system | admin
    actor_id    VARCHAR(100),
    action      VARCHAR(100) NOT NULL,
    table_name  VARCHAR(100),
    record_uuid TEXT,                           -- UUID فقط — لا serial IDs للعموم
    old_data    JSONB,
    new_data    JSONB,
    ip_address  INET,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_client_time ON audit_log(client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor       ON audit_log(actor_id, created_at DESC);

-- منع الحذف والتعديل على سجل المراجعة (Finding #10 + immutability)
CREATE OR REPLACE FUNCTION audit_log_immutable()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    RAISE EXCEPTION 'سجل المراجعة غير قابل للتعديل أو الحذف';
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.triggers
        WHERE trigger_name = 'trg_audit_no_update' AND event_object_table = 'audit_log'
    ) THEN
        CREATE TRIGGER trg_audit_no_update
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
    END IF;
END;
$$;

-- ──────────────────────────────────────────────────────────────
-- §10 — إخفاء معرّفات BIGSERIAL من الـ API (Finding #10)
-- ──────────────────────────────────────────────────────────────
-- دالة لتحويل BIGSERIAL إلى token آمن قبل إرساله للعميل
CREATE OR REPLACE FUNCTION mask_serial_id(p_id BIGINT, p_salt TEXT DEFAULT 'dheuof')
RETURNS TEXT LANGUAGE sql IMMUTABLE SET search_path = public AS $$
    SELECT encode(
        digest(p_salt || '::' || p_id::TEXT, 'sha256'),
        'hex'
    );
$$;

COMMENT ON FUNCTION mask_serial_id IS
    'Finding #10: يُحوّل BIGSERIAL إلى hash آمن قبل كشفه في الـ API العام';
