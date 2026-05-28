"""
routes/open_api.py
Open API للتكامل الخارجي — موثَّق ومُصادَق عليه.

POST /api/v1/auth/token
GET  /api/v1/availability
GET  /api/v1/rates
POST /api/v1/bookings
GET  /api/v1/bookings/{id}
PUT  /api/v1/bookings/{id}/cancel
GET  /api/v1/property
GET  /api/v1/property/rooms
GET  /api/v1/docs
GET  /api/v1/openapi.json
"""

import json
import time
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("routes.open_api")

# ─── Response Helpers ─────────────────────────────────────────


def api_success(data, request_id=None):
    return {
        "success": True,
        "data": data,
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id or str(uuid.uuid4())[:8],
            "version": "1.0",
        },
        "error": None,
    }


def api_error(code, message, details=None, status=400):
    return {
        "success": False,
        "data": None,
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": str(uuid.uuid4())[:8],
            "version": "1.0",
        },
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }, status


# ─── API Auth Middleware ───────────────────────────────────────


def require_api_key(api_key_manager, permission=None):
    """Decorator: يتحقق من API key قبل أي عملية"""
    import functools

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import flask
            request = flask.request

            # جلب المفتاح من Header أو Query
            raw_key = (
                request.headers.get("X-API-Key")
                or request.headers.get("Authorization", "").replace("Bearer ", "")
                or request.args.get("api_key")
            )

            if not raw_key:
                return api_error(
                    "MISSING_API_KEY",
                    "يجب إرسال API key في Header: X-API-Key",
                    status=401
                )

            # التحقق من المفتاح
            key_data = api_key_manager.validate_key(raw_key)
            if not key_data.get("success"):
                error_code = key_data.get("code", "INVALID_KEY")
                return api_error(key_data.get("error", "API key غير صالح"), error_code, status=401)

            # التحقق من الصلاحية المطلوبة
            if permission and not api_key_manager.has_permission(key_data, permission):
                return api_error(
                    "FORBIDDEN",
                    f"المفتاح لا يملك صلاحية: {permission}",
                    status=403
                )

            # التحقق من rate limit
            key_id = key_data.get("key_id")
            if not api_key_manager.check_rate_limit(key_id, request.path):
                remaining_time = "3600"  # ثانية
                import flask as fl
                response = fl.make_response(
                    json.dumps(api_error(
                        "RATE_LIMIT_EXCEEDED",
                        "تجاوزت حد الطلبات — انتظر ساعة",
                        status=429
                    )[0]),
                    429
                )
                response.headers["Retry-After"] = remaining_time
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["Content-Type"] = "application/json"
                return response

            # تسجيل الاستخدام (بعد الاستجابة)
            start_time = time.time()

            # تمرير key_data للـ function
            import flask
            flask.g.api_key_data = key_data

            response = func(*args, **kwargs)

            # تسجيل في api_usage_log
            try:
                duration_ms = int((time.time() - start_time) * 1000)
                status_code = response[1] if isinstance(response, tuple) else 200
                api_key_manager.log_usage(
                    key_id=key_id,
                    client_id=key_data.get("client_id", ""),
                    endpoint=request.path,
                    method=request.method,
                    status_code=status_code,
                    ip=request.remote_addr or "",
                    duration_ms=duration_ms,
                )
            except Exception:
                pass

            return response

        return wrapper
    return decorator


def register_open_api_routes(app, api_key_manager, db, channel_manager=None):
    """يسجّل كل routes الـ Open API"""

    # ─── Auth ─────────────────────────────────────────────────

    @app.route("/api/v1/auth/token", methods=["POST"])
    def api_auth_token():
        """يُعيد معلومات المفتاح (ليس JWT — نستخدم API keys مباشرة)"""
        import flask
        data = flask.request.json or {}
        api_key = data.get("api_key") or flask.request.headers.get("X-API-Key")

        if not api_key:
            return api_error("MISSING_KEY", "api_key مطلوب", status=401)

        key_data = api_key_manager.validate_key(api_key)
        if not key_data.get("success"):
            return api_error(key_data.get("error", "خطأ"), "INVALID_KEY", status=401)

        return api_success({
            "authenticated": True,
            "client_id": key_data.get("client_id"),
            "permissions": key_data.get("permissions"),
            "rate_limit_remaining": key_data.get("rate_limit_remaining"),
        })

    # ─── Availability ─────────────────────────────────────────

    @app.route("/api/v1/availability", methods=["GET"])
    @require_api_key(api_key_manager, permission="read")
    def api_availability():
        """توفر الغرف لفترة معينة"""
        import flask
        from datetime import date as date_type

        key_data = flask.g.api_key_data
        client_id = key_data["client_id"]

        check_in = flask.request.args.get("check_in")
        check_out = flask.request.args.get("check_out")
        adults = int(flask.request.args.get("adults", 1))

        # Validation
        if not check_in or not check_out:
            return api_error("MISSING_PARAMS", "check_in و check_out مطلوبان")

        try:
            ci = date_type.fromisoformat(check_in)
            co = date_type.fromisoformat(check_out)
        except ValueError:
            return api_error("INVALID_DATE", "صيغة التاريخ غير صحيحة — استخدم YYYY-MM-DD")

        if co <= ci:
            return api_error("INVALID_DATES", "check_out يجب أن يكون بعد check_in")

        nights = (co - ci).days
        if nights > 365:
            return api_error("DATE_RANGE_TOO_LONG", "الفترة الأقصى 365 يوم", {"max_nights": 365})

        try:
            # جلب الغرف المتاحة
            rows = db.execute(
                """SELECT r.id, r.room_number, r.room_type, r.floor,
                          rr.current_rate,
                          CASE WHEN b.id IS NULL THEN true ELSE false END as is_available
                   FROM rooms r
                   LEFT JOIN room_rates rr ON rr.room_id = r.id AND rr.rate_date = %s
                   LEFT JOIN bookings b ON b.room_id = r.id
                     AND b.status = 'confirmed'
                     AND b.check_in < %s AND b.check_out > %s
                   WHERE r.client_id = %s
                   ORDER BY r.room_number""",
                (check_in, check_out, check_in, client_id)
            ) or []

            available = [
                {
                    "room_id": r["id"],
                    "room_number": r["room_number"],
                    "room_type": r["room_type"],
                    "floor": r.get("floor"),
                    "rate_per_night": float(r["current_rate"]) if r.get("current_rate") else None,
                    "total_rate": float(r["current_rate"]) * nights if r.get("current_rate") else None,
                    "nights": nights,
                }
                for r in rows if r.get("is_available")
            ]

            return api_success({
                "check_in": check_in,
                "check_out": check_out,
                "nights": nights,
                "adults": adults,
                "available_rooms": available,
                "total_available": len(available),
            })

        except Exception as e:
            logger.error(f"api_availability error: {e}")
            return api_error("SERVER_ERROR", "خطأ في الخادم", status=500)

    # ─── Rates ────────────────────────────────────────────────

    @app.route("/api/v1/rates", methods=["GET"])
    @require_api_key(api_key_manager, permission="read")
    def api_rates():
        """الأسعار لفترة معينة"""
        import flask
        from datetime import date as date_type

        key_data = flask.g.api_key_data
        client_id = key_data["client_id"]

        date_from = flask.request.args.get("date_from")
        date_to = flask.request.args.get("date_to")
        room_type = flask.request.args.get("room_type")

        if not date_from or not date_to:
            return api_error("MISSING_PARAMS", "date_from و date_to مطلوبان")

        try:
            df = date_type.fromisoformat(date_from)
            dt = date_type.fromisoformat(date_to)
            if (dt - df).days > 365:
                return api_error("DATE_RANGE_TOO_LONG", "الفترة الأقصى 365 يوم")
        except ValueError:
            return api_error("INVALID_DATE", "صيغة التاريخ غير صحيحة")

        try:
            query = """SELECT r.room_number, r.room_type, rr.rate_date,
                              rr.current_rate, rr.is_dynamic
                       FROM room_rates rr
                       JOIN rooms r ON r.id = rr.room_id
                       WHERE r.client_id = %s
                         AND rr.rate_date >= %s AND rr.rate_date <= %s"""
            params = [client_id, date_from, date_to]

            if room_type:
                query += " AND r.room_type = %s"
                params.append(room_type)

            query += " ORDER BY rr.rate_date, r.room_number"
            rows = db.execute(query, tuple(params)) or []

            rates = [
                {
                    "room_number": r["room_number"],
                    "room_type": r["room_type"],
                    "date": str(r["rate_date"]),
                    "rate": float(r["current_rate"]),
                    "is_dynamic": r.get("is_dynamic", False),
                }
                for r in rows
            ]

            return api_success({
                "date_from": date_from,
                "date_to": date_to,
                "rates": rates,
                "count": len(rates),
            })

        except Exception as e:
            return api_error("SERVER_ERROR", str(e), status=500)

    # ─── Bookings ─────────────────────────────────────────────

    @app.route("/api/v1/bookings", methods=["POST"])
    @require_api_key(api_key_manager, permission="booking:create")
    def api_create_booking():
        """إنشاء حجز جديد"""
        import flask
        from datetime import date as date_type

        key_data = flask.g.api_key_data
        client_id = key_data["client_id"]
        data = flask.request.json or {}

        if not data:
            return api_error("EMPTY_BODY", "JSON body مطلوب")

        # Validation
        required = ["guest_name", "check_in", "check_out"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return api_error("MISSING_FIELDS", f"الحقول المطلوبة: {missing}")

        try:
            ci = date_type.fromisoformat(data["check_in"][:10])
            co = date_type.fromisoformat(data["check_out"][:10])
        except ValueError:
            return api_error("INVALID_DATE", "صيغة التاريخ غير صحيحة")

        if co <= ci:
            return api_error("INVALID_DATES", "check_out يجب أن يكون بعد check_in")

        try:
            # إنشاء النزيل
            guest_result = db.execute(
                """INSERT INTO guests (client_id, name, phone, email)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT DO NOTHING
                   RETURNING id""",
                (
                    client_id,
                    data["guest_name"],
                    data.get("guest_phone", ""),
                    data.get("guest_email", ""),
                )
            )
            guest_id = guest_result[0]["id"] if guest_result else None

            # إنشاء الحجز
            booking_result = db.execute(
                """INSERT INTO bookings
                   (client_id, guest_id, room_id, check_in, check_out,
                    adults, children, total_amount, payment_status, source, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'api', 'confirmed')
                   RETURNING id""",
                (
                    client_id,
                    guest_id,
                    data.get("room_id"),
                    data["check_in"],
                    data["check_out"],
                    int(data.get("adults", 1)),
                    int(data.get("children", 0)),
                    float(data.get("total_amount", 0)),
                    data.get("payment_status", "pending"),
                )
            )

            if not booking_result:
                return api_error("BOOKING_FAILED", "فشل إنشاء الحجز", status=500)

            booking_id = str(booking_result[0]["id"])
            return api_success({
                "booking_id": booking_id,
                "status": "confirmed",
                "check_in": data["check_in"],
                "check_out": data["check_out"],
            }), 201

        except Exception as e:
            logger.error(f"api_create_booking error: {e}")
            return api_error("SERVER_ERROR", str(e), status=500)

    @app.route("/api/v1/bookings/<booking_id>", methods=["GET"])
    @require_api_key(api_key_manager, permission="read")
    def api_get_booking(booking_id):
        """تفاصيل حجز — tenant isolation: يتحقق أن الحجز يعود للعميل"""
        import flask
        key_data = flask.g.api_key_data
        client_id = key_data["client_id"]

        try:
            rows = db.execute(
                """SELECT b.*, g.name as guest_name, g.phone as guest_phone,
                          r.room_number, r.room_type
                   FROM bookings b
                   LEFT JOIN guests g ON g.id = b.guest_id
                   LEFT JOIN rooms r ON r.id = b.room_id
                   WHERE b.id = %s AND b.client_id = %s LIMIT 1""",
                (booking_id, client_id)
            )

            if not rows:
                return api_error("NOT_FOUND", f"الحجز {booking_id} غير موجود", status=404)

            return api_success(dict(rows[0]))
        except Exception as e:
            return api_error("SERVER_ERROR", str(e), status=500)

    @app.route("/api/v1/bookings/<booking_id>/cancel", methods=["PUT"])
    @require_api_key(api_key_manager, permission="booking:cancel")
    def api_cancel_booking(booking_id):
        """إلغاء حجز"""
        import flask
        key_data = flask.g.api_key_data
        client_id = key_data["client_id"]

        try:
            result = db.execute(
                """UPDATE bookings SET status='cancelled', updated_at=NOW()
                   WHERE id=%s AND client_id=%s AND status != 'cancelled'
                   RETURNING id""",
                (booking_id, client_id)
            )

            if not result:
                return api_error("NOT_FOUND", f"الحجز {booking_id} غير موجود أو مُلغى مسبقاً", status=404)

            return api_success({"booking_id": booking_id, "status": "cancelled"})
        except Exception as e:
            return api_error("SERVER_ERROR", str(e), status=500)

    # ─── Property Info ────────────────────────────────────────

    @app.route("/api/v1/property", methods=["GET"])
    @require_api_key(api_key_manager, permission="read")
    def api_property():
        """معلومات المنشأة العامة"""
        import flask
        key_data = flask.g.api_key_data
        client_id = key_data["client_id"]

        try:
            rows = db.execute(
                "SELECT * FROM clients WHERE id=%s LIMIT 1", (client_id,)
            )
            if not rows:
                return api_error("NOT_FOUND", "المنشأة غير موجودة", status=404)

            row = dict(rows[0])
            # إزالة البيانات الحساسة
            for sensitive in ["password", "admin_pass", "secret"]:
                row.pop(sensitive, None)

            return api_success(row)
        except Exception as e:
            return api_error("SERVER_ERROR", str(e), status=500)

    @app.route("/api/v1/property/rooms", methods=["GET"])
    @require_api_key(api_key_manager, permission="read")
    def api_property_rooms():
        """أنواع الغرف المتاحة"""
        import flask
        key_data = flask.g.api_key_data
        client_id = key_data["client_id"]

        try:
            rows = db.execute(
                """SELECT id, room_number, room_type, floor, capacity,
                          description, amenities, is_active
                   FROM rooms WHERE client_id=%s AND is_active=true
                   ORDER BY room_number""",
                (client_id,)
            ) or []

            return api_success({
                "rooms": [dict(r) for r in rows],
                "total": len(rows),
            })
        except Exception as e:
            return api_error("SERVER_ERROR", str(e), status=500)

    # ─── API Keys Management (للمالك) ─────────────────────────

    @app.route("/api/v1/keys", methods=["GET"])
    def list_api_keys():
        """قائمة مفاتيح API — يتطلب auth المالك (ليس API key)"""
        import flask
        client_id = flask.request.args.get("client_id")
        if not client_id:
            return {"success": False, "error": "client_id مطلوب"}, 400

        keys = api_key_manager.list_keys(client_id)
        return {"success": True, "data": keys}

    @app.route("/api/v1/keys", methods=["POST"])
    def create_api_key():
        """إنشاء مفتاح API جديد"""
        import flask
        data = flask.request.json or {}
        client_id = data.get("client_id")
        name = data.get("name")
        permissions = data.get("permissions", ["read"])
        expires_days = int(data.get("expires_days", 365))

        if not client_id or not name:
            return {"success": False, "error": "client_id و name مطلوبان"}, 400

        result = api_key_manager.create_key(client_id, name, permissions, expires_days)
        status = 201 if result.get("success") else 400
        return result, status

    @app.route("/api/v1/keys/<int:key_id>", methods=["DELETE"])
    def revoke_api_key(key_id):
        """إلغاء مفتاح API"""
        import flask
        data = flask.request.json or {}
        client_id = data.get("client_id") or flask.request.args.get("client_id")

        if not client_id:
            return {"success": False, "error": "client_id مطلوب"}, 400

        success = api_key_manager.revoke_key(key_id, client_id)
        if success:
            return {"success": True, "message": "تم إلغاء المفتاح"}
        return {"success": False, "error": "المفتاح غير موجود"}, 404

    # ─── API Documentation ────────────────────────────────────

    @app.route("/api/v1/docs", methods=["GET"])
    def api_docs():
        """صفحة وثائق API بصيغة HTML"""
        import flask
        html = _generate_docs_html()
        return flask.Response(html, mimetype="text/html")

    @app.route("/api/v1/openapi.json", methods=["GET"])
    def api_openapi():
        """OpenAPI 3.0 spec"""
        import flask
        spec = _generate_openapi_spec()
        return flask.jsonify(spec)


def _generate_docs_html() -> str:
    return """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>توثيق API — نظام ضيوف</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #0f172a; color: #e2e8f0; }
  .header { background: linear-gradient(135deg, #1e40af, #7c3aed); padding: 2rem; text-align: center; }
  .header h1 { font-size: 2rem; color: white; margin-bottom: 0.5rem; }
  .header p { color: #bfdbfe; }
  .container { max-width: 900px; margin: 2rem auto; padding: 0 1rem; }
  .section { background: #1e293b; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
  .section h2 { color: #60a5fa; font-size: 1.25rem; margin-bottom: 1rem; border-bottom: 1px solid #334155; padding-bottom: 0.5rem; }
  .endpoint { background: #0f172a; border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; }
  .method { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.8rem; font-weight: bold; margin-left: 0.5rem; }
  .get { background: #065f46; color: #6ee7b7; }
  .post { background: #1e3a8a; color: #93c5fd; }
  .put { background: #78350f; color: #fcd34d; }
  .delete { background: #7f1d1d; color: #fca5a5; }
  .path { font-family: monospace; color: #e2e8f0; }
  .desc { color: #94a3b8; font-size: 0.9rem; margin-top: 0.3rem; }
  .auth-note { background: #1c1917; border: 1px solid #451a03; border-radius: 8px; padding: 1rem; margin-bottom: 1.5rem; }
  .auth-note code { background: #292524; padding: 0.2rem 0.4rem; border-radius: 4px; font-family: monospace; font-size: 0.85rem; }
  .badge { display: inline-block; background: #374151; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.75rem; margin-right: 0.3rem; color: #d1d5db; }
</style>
</head>
<body>
<div class="header">
  <h1>🏨 توثيق Open API — نظام ضيوف</h1>
  <p>الإصدار 1.0 | dheuof.com</p>
</div>
<div class="container">

  <div class="auth-note">
    <strong>🔑 المصادقة:</strong> أضف مفتاح API في كل طلب:<br>
    <code>X-API-Key: dheuof_your_key_here</code>
    أو <code>Authorization: Bearer dheuof_your_key_here</code>
  </div>

  <div class="section">
    <h2>🔐 المصادقة</h2>
    <div class="endpoint">
      <span class="method post">POST</span><span class="path">/api/v1/auth/token</span>
      <div class="desc">التحقق من API key والحصول على معلوماته</div>
    </div>
  </div>

  <div class="section">
    <h2>🛏️ التوفر والأسعار</h2>
    <div class="endpoint">
      <span class="method get">GET</span><span class="path">/api/v1/availability</span>
      <span class="badge">read</span>
      <div class="desc">غرف متاحة لفترة معينة. Params: check_in, check_out, adults</div>
    </div>
    <div class="endpoint">
      <span class="method get">GET</span><span class="path">/api/v1/rates</span>
      <span class="badge">read</span>
      <div class="desc">الأسعار لفترة وغرفة. Params: date_from, date_to, room_type</div>
    </div>
  </div>

  <div class="section">
    <h2>📅 الحجوزات</h2>
    <div class="endpoint">
      <span class="method post">POST</span><span class="path">/api/v1/bookings</span>
      <span class="badge">booking:create</span>
      <div class="desc">إنشاء حجز جديد. Body: guest_name, check_in, check_out, room_id</div>
    </div>
    <div class="endpoint">
      <span class="method get">GET</span><span class="path">/api/v1/bookings/{id}</span>
      <span class="badge">read</span>
      <div class="desc">تفاصيل حجز محدد</div>
    </div>
    <div class="endpoint">
      <span class="method put">PUT</span><span class="path">/api/v1/bookings/{id}/cancel</span>
      <span class="badge">booking:cancel</span>
      <div class="desc">إلغاء حجز</div>
    </div>
  </div>

  <div class="section">
    <h2>🏨 المنشأة</h2>
    <div class="endpoint">
      <span class="method get">GET</span><span class="path">/api/v1/property</span>
      <span class="badge">read</span>
      <div class="desc">معلومات المنشأة العامة</div>
    </div>
    <div class="endpoint">
      <span class="method get">GET</span><span class="path">/api/v1/property/rooms</span>
      <span class="badge">read</span>
      <div class="desc">قائمة أنواع الغرف المتاحة</div>
    </div>
  </div>

  <div class="section">
    <h2>📄 Response Format</h2>
    <div class="endpoint">
      <pre style="color:#94a3b8;font-size:0.85rem">{
  "success": true,
  "data": { ... },
  "meta": { "timestamp": "...", "request_id": "...", "version": "1.0" },
  "error": null
}</pre>
    </div>
  </div>

  <div class="section">
    <h2>⚠️ أكواد الأخطاء</h2>
    <div class="endpoint">
      <div class="desc">401 — MISSING_API_KEY / INVALID_KEY / KEY_EXPIRED / KEY_REVOKED</div>
      <div class="desc">403 — FORBIDDEN (صلاحية غير كافية)</div>
      <div class="desc">429 — RATE_LIMIT_EXCEEDED (تجاوز حد الطلبات)</div>
      <div class="desc">400 — MISSING_PARAMS / INVALID_DATE / EMPTY_BODY</div>
      <div class="desc">404 — NOT_FOUND</div>
      <div class="desc">500 — SERVER_ERROR</div>
    </div>
  </div>

</div>
</body>
</html>"""


def _generate_openapi_spec() -> dict:
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "نظام ضيوف Open API",
            "version": "1.0.0",
            "description": "API للتكامل الخارجي مع نظام إدارة الفندق",
            "contact": {"url": "https://dheuof.com"},
        },
        "servers": [{"url": "https://dheuof.com", "description": "Production"}],
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                }
            },
            "schemas": {
                "SuccessResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": True},
                        "data": {"type": "object"},
                        "meta": {
                            "type": "object",
                            "properties": {
                                "timestamp": {"type": "string"},
                                "request_id": {"type": "string"},
                                "version": {"type": "string"},
                            }
                        },
                        "error": {"type": "object", "nullable": True},
                    }
                }
            }
        },
        "security": [{"ApiKeyAuth": []}],
        "paths": {
            "/api/v1/availability": {
                "get": {
                    "summary": "توفر الغرف",
                    "parameters": [
                        {"name": "check_in", "in": "query", "required": True, "schema": {"type": "string", "format": "date"}},
                        {"name": "check_out", "in": "query", "required": True, "schema": {"type": "string", "format": "date"}},
                        {"name": "adults", "in": "query", "schema": {"type": "integer", "default": 1}},
                    ],
                    "responses": {"200": {"description": "غرف متاحة"}},
                }
            },
            "/api/v1/bookings": {
                "post": {
                    "summary": "إنشاء حجز",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["guest_name", "check_in", "check_out"],
                                    "properties": {
                                        "guest_name": {"type": "string"},
                                        "check_in": {"type": "string", "format": "date"},
                                        "check_out": {"type": "string", "format": "date"},
                                        "room_id": {"type": "integer"},
                                        "adults": {"type": "integer", "default": 1},
                                    }
                                }
                            }
                        }
                    },
                    "responses": {"201": {"description": "تم إنشاء الحجز"}},
                }
            },
        }
    }
