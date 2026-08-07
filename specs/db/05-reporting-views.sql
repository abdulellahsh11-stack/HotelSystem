-- ================================================================
-- specs/db/05-reporting-views.sql
-- طرق العرض التقريرية — القسم العاشر من وثيقة التصميم
-- يطبَّق من db/schema_v3.py عند بدء التشغيل
-- ================================================================
--
-- ⚠️  security_invoker = true على كل طريقة عرض — وهو جوهري لا تحسين.
--
-- طريقة العرض في PostgreSQL تُنفَّذ افتراضياً بصلاحيات مالكها لا
-- بصلاحيات من يستعلم عنها. وبما أن هذه الطرق يملكها مالك الجداول،
-- فإن سياسات RLS لا تسري عليها — وأي منشأة تستعلم عن v_kpi_daily
-- كانت سترى أرقام كل المنشآت الأخرى. security_invoker يجعل التنفيذ
-- بصلاحيات المستعلم، فتسري عليه سياساته. (متاح من PostgreSQL 15.)
--
-- كل طريقة عرض تُبقي client_id في مخرجاتها كي يعمل العزل ولتتمكّن
-- لوحة المالك من التجميع عبر المنشآت.

-- ──────────────────────────────────────────────────────────────
-- الإشغال ومؤشرات الأداء
-- ──────────────────────────────────────────────────────────────

-- الغرف المشغولة يومياً مقابل المتاحة
CREATE OR REPLACE VIEW v_daily_occupancy
WITH (security_invoker = true) AS
SELECT
    r.client_id,
    d.day::DATE                                   AS day,
    COUNT(DISTINCT r.id)                          AS rooms_total,
    COUNT(DISTINCT b.room_id)                     AS rooms_occupied,
    ROUND(
        COUNT(DISTINCT b.room_id)::NUMERIC
        / NULLIF(COUNT(DISTINCT r.id), 0) * 100, 2
    )                                             AS occupancy_pct
FROM rooms r
CROSS JOIN LATERAL (
    SELECT generate_series(CURRENT_DATE - INTERVAL '90 days', CURRENT_DATE, '1 day') AS day
) d
LEFT JOIN bookings b
       ON b.client_id = r.client_id
      AND b.room_id   = r.id
      AND b.status    IN ('confirmed', 'checked_in', 'checked_out')
      AND d.day >= b.check_in
      AND d.day <  b.check_out
GROUP BY r.client_id, d.day;

COMMENT ON VIEW v_daily_occupancy IS
    'نسبة الإشغال اليومية لآخر 90 يوماً — القسم 10.1';

-- ADR و RevPAR و OCC مجتمعة
CREATE OR REPLACE VIEW v_kpi_daily
WITH (security_invoker = true) AS
SELECT
    o.client_id,
    o.day,
    o.rooms_total,
    o.rooms_occupied,
    o.occupancy_pct,
    ROUND(COALESCE(rev.room_revenue, 0)
          / NULLIF(o.rooms_occupied, 0), 2)       AS adr,
    ROUND(COALESCE(rev.room_revenue, 0)
          / NULLIF(o.rooms_total, 0), 2)          AS revpar,
    COALESCE(rev.room_revenue, 0)                 AS room_revenue
FROM v_daily_occupancy o
LEFT JOIN LATERAL (
    SELECT SUM(b.nightly_rate) AS room_revenue
    FROM bookings b
    WHERE b.client_id = o.client_id
      AND b.status IN ('confirmed', 'checked_in', 'checked_out')
      AND o.day >= b.check_in
      AND o.day <  b.check_out
) rev ON TRUE;

COMMENT ON VIEW v_kpi_daily IS
    'OCC% و ADR و RevPAR يومياً — القسم 10.6. ADR = إيراد الغرف ÷ الغرف '
    'المشغولة، RevPAR = إيراد الغرف ÷ إجمالي الغرف';

-- ──────────────────────────────────────────────────────────────
-- الوصول والمغادرة
-- ──────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW v_arrivals_departures
WITH (security_invoker = true) AS
SELECT
    b.client_id,
    b.id                      AS booking_id,
    b.check_in,
    b.check_out,
    b.status,
    g.full_name               AS guest_name,
    g.absher_phone            AS guest_phone,
    r.room_number,
    CASE
        WHEN b.check_in  = CURRENT_DATE THEN 'arrival'
        WHEN b.check_out = CURRENT_DATE THEN 'departure'
    END                       AS movement
FROM bookings b
LEFT JOIN guests g ON g.id = b.guest_id
LEFT JOIN rooms  r ON r.id = b.room_id
WHERE b.status IN ('confirmed', 'checked_in')
  AND (b.check_in = CURRENT_DATE OR b.check_out = CURRENT_DATE);

COMMENT ON VIEW v_arrivals_departures IS
    'وصول ومغادرة اليوم — القسم 10.1. رقم الهوية مستبعَد عمداً: مشفَّر '
    'في id_number_enc ويُفكّ في طبقة التطبيق وحدها';

-- ──────────────────────────────────────────────────────────────
-- المالية
-- ──────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW v_revenue_daily
WITH (security_invoker = true) AS
SELECT
    client_id,
    day,
    SUM(rooms_revenue)  AS rooms_revenue,
    SUM(pos_revenue)    AS pos_revenue,
    SUM(vat_collected)  AS vat_collected,
    SUM(rooms_revenue) + SUM(pos_revenue) AS total_revenue
FROM (
    SELECT client_id, issue_date AS day,
           COALESCE(SUM(total_amount), 0) AS rooms_revenue,
           0::NUMERIC                     AS pos_revenue,
           COALESCE(SUM(vat_amount), 0)   AS vat_collected
    FROM invoices
    WHERE payment_status = 'paid'
    GROUP BY client_id, issue_date
    UNION ALL
    SELECT client_id, created_at::DATE,
           0::NUMERIC,
           COALESCE(SUM(total), 0),
           COALESCE(SUM(vat_amount), 0)
    FROM pos_sales
    WHERE status = 'completed'
    GROUP BY client_id, created_at::DATE
) src
GROUP BY client_id, day;

COMMENT ON VIEW v_revenue_daily IS
    'الإيراد اليومي: غرف + نقاط بيع + ضريبة محصَّلة — القسم 10.2';

CREATE OR REPLACE VIEW v_outstanding_invoices
WITH (security_invoker = true) AS
SELECT
    i.client_id,
    i.id                AS invoice_id,
    i.issue_date,
    i.total_amount,
    i.payment_status,
    CURRENT_DATE - i.issue_date AS days_outstanding,
    g.full_name         AS guest_name,
    i.company_name
FROM invoices i
LEFT JOIN guests g ON g.id = i.guest_id
WHERE i.payment_status IN ('pending', 'partial', 'unpaid');

COMMENT ON VIEW v_outstanding_invoices IS
    'الفواتير غير المسددة وعمر الدين بالأيام — القسم 10.2';

-- ──────────────────────────────────────────────────────────────
-- التشغيل
-- ──────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW v_housekeeping_pending
WITH (security_invoker = true) AS
SELECT
    h.client_id,
    h.id            AS task_id,
    h.task_type,
    h.priority,
    h.status,
    h.assigned_to,
    r.room_number,
    h.created_at,
    ROUND(EXTRACT(EPOCH FROM (NOW() - h.created_at)) / 3600, 1) AS hours_open
FROM housekeeping_tasks h
LEFT JOIN rooms r ON r.id = h.room_id
WHERE h.status IN ('pending', 'in_progress');

COMMENT ON VIEW v_housekeeping_pending IS
    'مهام التدبير المعلّقة وعمر كل مهمة بالساعات — القسم 10.3';

CREATE OR REPLACE VIEW v_low_stock
WITH (security_invoker = true) AS
SELECT
    client_id,
    id          AS item_id,
    name,
    warehouse_type,
    unit,
    quantity,
    reorder_level,
    reorder_level - quantity           AS shortfall,
    ROUND(quantity * price_per_unit, 2) AS current_value
FROM warehouse_items
WHERE reorder_level > 0
  AND quantity <= reorder_level;

COMMENT ON VIEW v_low_stock IS
    'أصناف بلغت حد إعادة الطلب أو دونه — القسم 10.4';

CREATE OR REPLACE VIEW v_inventory_value
WITH (security_invoker = true) AS
SELECT
    client_id,
    warehouse_type,
    COUNT(*)                                  AS items_count,
    ROUND(SUM(quantity * price_per_unit), 2)  AS total_value
FROM warehouse_items
GROUP BY client_id, warehouse_type;

COMMENT ON VIEW v_inventory_value IS
    'القيمة المالية للمخزون حسب نوع المستودع — القسم 10.4';

-- ──────────────────────────────────────────────────────────────
-- التسويق — على مستوى المنصة لا المنشأة
-- ──────────────────────────────────────────────────────────────

-- marketers لا يحمل client_id: المسوّقون تابعون للمنصة لا لمنشأة،
-- فلا تسري عليهم سياسات العزل وهذه الطريقة للوحة المالك وحدها.
CREATE OR REPLACE VIEW v_marketer_performance
WITH (security_invoker = true) AS
SELECT
    m.id                AS marketer_id,
    m.name,
    m.ref_code,
    m.status,
    m.commission_rate,
    COUNT(r.id)         AS referrals_count,
    COUNT(r.id) FILTER (WHERE r.converted_at >= CURRENT_DATE - INTERVAL '30 days')
                        AS referrals_30d,
    m.total_earnings
FROM marketers m
LEFT JOIN marketer_referrals r ON r.marketer_id = m.id
GROUP BY m.id, m.name, m.ref_code, m.status, m.commission_rate, m.total_earnings;

COMMENT ON VIEW v_marketer_performance IS
    'أداء المسوّقين وإحالاتهم — القسم 10.5. على مستوى المنصة: '
    'جدول marketers لا يحمل client_id';
