/**
 * Dheuof Hotel SaaS — k6 Load Test Script
 * ==========================================
 * Platform : dheuof.com (FastAPI)
 * Tool     : k6 (https://k6.io)
 *
 * Auth endpoints
 * --------------
 *   Admin  : POST /api/admin/login  → sets cookie admin_token
 *   Client : POST /api/login        → sets cookie client_token
 *
 * Environment variables (pass with -e / --env)
 * --------------------------------------------
 *   BASE_URL         Base URL of the platform  (default: http://localhost:8000)
 *   ADMIN_PASSWORD   Admin password            (default: admin123)
 *   CLIENT_ID        Hotel client identifier   (default: test-hotel)
 *   CLIENT_PASSWORD  Hotel client password     (default: hotel123)
 *
 * Run examples
 * ------------
 *   # Against local dev server
 *   k6 run k6_script.js
 *
 *   # Against staging, custom credentials
 *   k6 run \
 *     -e BASE_URL=https://staging.dheuof.com \
 *     -e ADMIN_PASSWORD=secretpass \
 *     -e CLIENT_ID=hotel-001 \
 *     -e CLIENT_PASSWORD=hotelpass \
 *     k6_script.js
 *
 *   # Output to InfluxDB for Grafana dashboards
 *   k6 run --out influxdb=http://localhost:8086/k6 k6_script.js
 *
 * Stages (ramp-up → soak → ramp-down)
 * ------------------------------------
 *   0 – 1 min  : ramp  0 → 10 VUs  (warm-up)
 *   1 – 3 min  : ramp 10 → 50 VUs  (build-up)
 *   3 – 7 min  : hold 100 VUs      (peak soak — sustained load)
 *   7 – 9 min  : ramp 100 → 0 VUs  (cool-down)
 */

import http from "k6/http";
import { check, group, sleep } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";
import { CookieJar } from "k6/http";

// ── Configuration ─────────────────────────────────────────────────────────────

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const ADMIN_PASSWORD = __ENV.ADMIN_PASSWORD || "admin123";
const CLIENT_ID = __ENV.CLIENT_ID || "test-hotel";
const CLIENT_PASSWORD = __ENV.CLIENT_PASSWORD || "hotel123";

// ── Custom metrics ────────────────────────────────────────────────────────────

const loginErrors = new Counter("login_errors_total");
const apiErrors = new Counter("api_errors_total");
const sessionExpired = new Counter("session_expired_total");

const kpiDashboardDuration = new Trend("kpi_dashboard_duration", true);
const bookingsDuration = new Trend("bookings_duration", true);
const arrivalsDuration = new Trend("arrivals_duration", true);

const errorRate = new Rate("error_rate");

// ── Thresholds ────────────────────────────────────────────────────────────────

export const options = {
  /**
   * Staged load profile:
   *   Stage 1 (0-60s)   : ramp up to 10 VUs  — smoke / baseline
   *   Stage 2 (1-3min)  : ramp up to 50 VUs  — normal load
   *   Stage 3 (3-7min)  : hold 100 VUs       — peak soak
   *   Stage 4 (7-9min)  : ramp down to 0     — cool-down
   */
  stages: [
    { duration: "1m",  target: 10  },  // warm-up
    { duration: "2m",  target: 50  },  // build up to moderate load
    { duration: "4m",  target: 100 },  // peak soak (sustain 100 VUs)
    { duration: "2m",  target: 0   },  // graceful ramp-down
  ],

  thresholds: {
    // 95th percentile response time must stay under 500 ms
    "http_req_duration": ["p(95)<500"],

    // Overall HTTP error rate (non-2xx/3xx) must stay below 1%
    "error_rate": ["rate<0.01"],

    // Login path must be fast — p(95) under 800 ms
    "http_req_duration{name:admin_login}": ["p(95)<800"],
    "http_req_duration{name:staff_login}": ["p(95)<800"],

    // KPI dashboard latency budget
    "kpi_dashboard_duration": ["p(95)<500"],

    // Bookings list latency budget
    "bookings_duration": ["p(95)<500"],
  },
};

// ── Helper: parse Set-Cookie header ──────────────────────────────────────────

/**
 * Extract a named cookie value from the Set-Cookie response header.
 * k6's http module stores cookies automatically in the jar but we
 * sometimes need to inspect the value directly.
 *
 * @param {import("k6/http").Response} response
 * @param {string} name  Cookie name to find
 * @returns {string|null}
 */
function extractCookie(response, name) {
  const headers = response.headers["Set-Cookie"] || "";
  const entries = Array.isArray(headers) ? headers : [headers];
  for (const entry of entries) {
    const match = entry.match(new RegExp(`(?:^|;\\s*)${name}=([^;]+)`));
    if (match) return match[1];
  }
  return null;
}

// ── Scenario: Admin login ─────────────────────────────────────────────────────

/**
 * Authenticate as the platform admin.
 * Uses a dedicated CookieJar so each VU has isolated session state.
 *
 * @returns {{ jar: CookieJar, token: string|null }}
 */
function adminLogin() {
  const jar = new CookieJar();
  const params = {
    cookieJar: jar,
    tags: { name: "admin_login" },
    redirects: 0, // capture the redirect manually to check status
  };

  const resp = http.post(
    `${BASE_URL}/api/admin/login`,
    `password=${encodeURIComponent(ADMIN_PASSWORD)}`,
    {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      ...params,
    }
  );

  const ok = check(resp, {
    "admin login: status 2xx or 303 redirect": (r) =>
      r.status === 200 || r.status === 303,
  });

  if (!ok) {
    loginErrors.add(1);
    errorRate.add(1);
    console.warn(`Admin login failed — HTTP ${resp.status}: ${resp.body}`);
    return { jar, token: null };
  }

  errorRate.add(0);
  return { jar, token: extractCookie(resp, "admin_token") };
}

// ── Scenario: Staff / client login ────────────────────────────────────────────

/**
 * Authenticate as a hotel staff member (client account).
 *
 * @returns {{ jar: CookieJar, token: string|null }}
 */
function staffLogin() {
  const jar = new CookieJar();

  const resp = http.post(
    `${BASE_URL}/api/login`,
    `client_id=${encodeURIComponent(CLIENT_ID)}&password=${encodeURIComponent(CLIENT_PASSWORD)}`,
    {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      cookieJar: jar,
      tags: { name: "staff_login" },
      redirects: 0,
    }
  );

  const ok = check(resp, {
    "staff login: status 2xx or 303 redirect": (r) =>
      r.status === 200 || r.status === 303,
  });

  if (!ok) {
    loginErrors.add(1);
    errorRate.add(1);
    console.warn(`Staff login failed — HTTP ${resp.status}`);
    return { jar, token: null };
  }

  errorRate.add(0);
  return { jar, token: extractCookie(resp, "client_token") };
}

// ── Scenario: Browse admin dashboard ─────────────────────────────────────────

function scenarioAdminDashboard(jar) {
  group("Admin — KPI Dashboard", () => {
    const start = Date.now();
    const resp = http.get(`${BASE_URL}/api/m11/dashboard`, {
      cookieJar: jar,
      tags: { name: "kpi_dashboard" },
    });

    kpiDashboardDuration.add(Date.now() - start);

    const ok = check(resp, {
      "kpi dashboard: status 200": (r) => r.status === 200,
      "kpi dashboard: has success field": (r) => {
        try { return JSON.parse(r.body).success === true; } catch { return false; }
      },
    });

    if (!ok) {
      if (resp.status === 401) sessionExpired.add(1);
      apiErrors.add(1);
      errorRate.add(1);
    } else {
      errorRate.add(0);
    }
  });

  sleep(1); // think time between KPI and next action

  group("Admin — Bookings List", () => {
    const start = Date.now();
    const resp = http.get(`${BASE_URL}/api/bookings`, {
      cookieJar: jar,
      tags: { name: "bookings_list" },
    });

    bookingsDuration.add(Date.now() - start);

    const ok = check(resp, {
      "bookings list: status 200": (r) => r.status === 200,
    });

    if (!ok) {
      if (resp.status === 401) sessionExpired.add(1);
      apiErrors.add(1);
      errorRate.add(1);
    } else {
      errorRate.add(0);
    }
  });

  sleep(1.5); // think time

  group("Admin — Today Arrivals", () => {
    const start = Date.now();
    const resp = http.get(`${BASE_URL}/api/m02/arrivals`, {
      cookieJar: jar,
      tags: { name: "admin_arrivals" },
    });

    arrivalsDuration.add(Date.now() - start);

    const ok = check(resp, {
      "arrivals: status 200": (r) => r.status === 200,
    });

    if (!ok) {
      if (resp.status === 401) sessionExpired.add(1);
      apiErrors.add(1);
      errorRate.add(1);
    } else {
      errorRate.add(0);
    }
  });
}

// ── Scenario: Browse staff views ──────────────────────────────────────────────

function scenarioStaffBrowse(jar) {
  group("Staff — Arrivals", () => {
    const resp = http.get(`${BASE_URL}/api/m02/arrivals`, {
      cookieJar: jar,
      tags: { name: "staff_arrivals" },
    });

    const ok = check(resp, {
      "staff arrivals: status 200": (r) => r.status === 200,
    });

    if (!ok) {
      if (resp.status === 401) sessionExpired.add(1);
      apiErrors.add(1);
      errorRate.add(1);
    } else {
      errorRate.add(0);
    }
  });

  sleep(2); // think time

  group("Staff — Departures", () => {
    const resp = http.get(`${BASE_URL}/api/m02/departures`, {
      cookieJar: jar,
      tags: { name: "staff_departures" },
    });

    const ok = check(resp, {
      "departures: status 200": (r) => r.status === 200,
    });

    if (!ok) {
      if (resp.status === 401) sessionExpired.add(1);
      apiErrors.add(1);
      errorRate.add(1);
    } else {
      errorRate.add(0);
    }
  });

  sleep(1.5); // think time

  group("Staff — Maintenance Tickets", () => {
    const resp = http.get(`${BASE_URL}/api/m08/orders`, {
      cookieJar: jar,
      tags: { name: "maintenance_tickets" },
    });

    const ok = check(resp, {
      "maintenance tickets: status 200": (r) => r.status === 200,
    });

    if (!ok) {
      if (resp.status === 401) sessionExpired.add(1);
      apiErrors.add(1);
      errorRate.add(1);
    } else {
      errorRate.add(0);
    }
  });
}

// ── Scenario: Guest / public page ────────────────────────────────────────────

function scenarioGuest() {
  group("Guest — Health Check", () => {
    const resp = http.get(`${BASE_URL}/api/health`, {
      tags: { name: "health_check" },
    });

    const ok = check(resp, {
      "health: status 200": (r) => r.status === 200,
    });

    if (!ok) {
      apiErrors.add(1);
      errorRate.add(1);
    } else {
      errorRate.add(0);
    }
  });

  sleep(2); // think time

  group("Guest — Home Page", () => {
    const resp = http.get(`${BASE_URL}/`, {
      redirects: 5,
      tags: { name: "home_page" },
    });

    // Redirect to /login is expected for unauthenticated visitors
    const ok = check(resp, {
      "home page: status 200 or redirect": (r) =>
        r.status === 200 || r.status === 302 || r.status === 303,
    });

    if (!ok) {
      apiErrors.add(1);
      errorRate.add(1);
    } else {
      errorRate.add(0);
    }
  });
}

// ── Default function (VU entrypoint) ─────────────────────────────────────────

/**
 * Each VU executes this function repeatedly.
 *
 * Distribution across scenarios (probabilistic):
 *   30% Admin journey  — login + KPI dashboard + bookings + arrivals
 *   50% Staff journey  — login + arrivals + departures + maintenance
 *   20% Guest journey  — health check + home page (no auth)
 */
export default function () {
  const roll = Math.random();

  if (roll < 0.30) {
    // ── Admin journey ──────────────────────────────────────────────
    const { jar, token } = adminLogin();
    if (!token) {
      sleep(2);
      return;
    }

    sleep(0.5); // brief pause after login (simulates page load)

    scenarioAdminDashboard(jar);

    // Occasional warehouse check (20% of admin sessions)
    if (Math.random() < 0.2) {
      group("Admin — Warehouses", () => {
        const resp = http.get(`${BASE_URL}/api/m13/items`, {
          cookieJar: jar,
          tags: { name: "warehouses" },
        });
        check(resp, { "warehouses: status 200": (r) => r.status === 200 });
        errorRate.add(resp.status !== 200 ? 1 : 0);
      });
      sleep(1);
    }

    sleep(2); // think time before session ends

  } else if (roll < 0.80) {
    // ── Staff journey ──────────────────────────────────────────────
    const { jar, token } = staffLogin();
    if (!token) {
      sleep(2);
      return;
    }

    sleep(0.5);

    scenarioStaffBrowse(jar);

    // Periodic health check (35% of staff sessions)
    if (Math.random() < 0.35) {
      group("Staff — Health Ping", () => {
        const resp = http.get(`${BASE_URL}/api/health`, {
          cookieJar: jar,
          tags: { name: "staff_health" },
        });
        check(resp, { "staff health: 200": (r) => r.status === 200 });
        errorRate.add(resp.status !== 200 ? 1 : 0);
      });
    }

    sleep(2);

  } else {
    // ── Guest / anonymous journey ──────────────────────────────────
    scenarioGuest();
    sleep(3); // guests linger longer before next action
  }
}

// ── Teardown (runs once after all VUs finish) ─────────────────────────────────

export function teardown() {
  console.log("=== Dheuof k6 load test complete ===");
}
