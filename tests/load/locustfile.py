#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dheuof Hotel SaaS — Locust Load Test
=====================================
Platform : dheuof.com (FastAPI)
Auth     : POST /api/admin/login  →  cookie: admin_token
           POST /api/login        →  cookie: client_token

Environment variables
---------------------
HOST               Base URL (default: http://localhost:8000)
ADMIN_PASSWORD     Admin panel password  (default: admin123)
STAFF_CLIENT_ID    Hotel client_id for staff login  (default: test-hotel)
STAFF_PASSWORD     Staff password  (default: hotel123)

Run examples
------------
# Quick smoke (10 users, 2 min)
locust -f locustfile.py --host http://localhost:8000 \
       --users 10 --spawn-rate 2 --run-time 2m --headless

# Interactive UI
locust -f locustfile.py --host http://localhost:8000

# Shaped ramp-up (built-in stages, no --users flag needed)
locust -f locustfile.py --host http://localhost:8000 \
       --headless --run-time 4m
"""

import os
import logging

from locust import HttpUser, task, between, events
from locust import LoadTestShape

log = logging.getLogger("dheuof.load")

# ── Environment ──────────────────────────────────────────────────────────────

HOST = os.environ.get("HOST", "http://localhost:8000")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
STAFF_CLIENT_ID = os.environ.get("STAFF_CLIENT_ID", "test-hotel")
STAFF_PASSWORD = os.environ.get("STAFF_PASSWORD", "hotel123")


# ── Lifecycle hook ────────────────────────────────────────────────────────────

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Fires once when the test begins — useful for pre-flight checks."""
    log.info("=== Dheuof load test starting ===")
    log.info("Target host  : %s", environment.host or HOST)
    log.info("Admin user   : (password from ADMIN_PASSWORD env)")
    log.info("Staff client : %s", STAFF_CLIENT_ID)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    log.info("=== Dheuof load test finished ===")


# ── Helper: login utilities ───────────────────────────────────────────────────

def _admin_login(client) -> bool:
    """
    POST /api/admin/login with form-encoded password.
    Returns True on success; the session cookie is stored automatically
    in the Locust HttpSession cookie jar.
    """
    with client.post(
        "/api/admin/login",
        data={"password": ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        allow_redirects=False,
        catch_response=True,
        name="[auth] admin login",
    ) as resp:
        # 303 redirect on success; 200 means login page was returned (bad creds)
        if resp.status_code in (200, 303):
            if resp.status_code == 303 or "admin_token" in resp.cookies:
                resp.success()
                return True
            resp.failure(
                f"Admin login failed — HTTP {resp.status_code}, "
                "no redirect / no admin_token cookie"
            )
            return False
        resp.failure(f"Admin login unexpected status: {resp.status_code}")
        return False


def _staff_login(client) -> bool:
    """
    POST /api/login with form-encoded client_id + password.
    Returns True on success.
    """
    with client.post(
        "/api/login",
        data={
            "client_id": STAFF_CLIENT_ID,
            "password": STAFF_PASSWORD,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        allow_redirects=False,
        catch_response=True,
        name="[auth] staff login",
    ) as resp:
        if resp.status_code in (200, 303):
            if resp.status_code == 303 or "client_token" in resp.cookies:
                resp.success()
                return True
            resp.failure(
                f"Staff login failed — HTTP {resp.status_code}, "
                "no redirect / no client_token cookie"
            )
            return False
        resp.failure(f"Staff login unexpected status: {resp.status_code}")
        return False


# ── User classes ──────────────────────────────────────────────────────────────

class AdminUser(HttpUser):
    """
    Simulates a hotel administrator browsing the management dashboard.
    Authenticated via /api/admin/login → admin_token cookie.
    """

    wait_time = between(1, 3)

    def on_start(self):
        """Login once; subsequent requests carry the session cookie automatically."""
        _admin_login(self.client)

    # weight 3 — most frequent: KPI dashboard overview
    @task(3)
    def view_kpi_dashboard(self):
        with self.client.get(
            "/api/m11/dashboard",
            catch_response=True,
            name="[admin] GET /api/m11/dashboard",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 401:
                resp.failure("KPI dashboard — session expired, re-logging in")
                _admin_login(self.client)
            else:
                resp.failure(f"KPI dashboard HTTP {resp.status_code}")

    # weight 2 — list bookings
    @task(2)
    def list_bookings(self):
        with self.client.get(
            "/api/bookings",
            catch_response=True,
            name="[admin] GET /api/bookings",
        ) as resp:
            if resp.status_code in (200, 401):
                if resp.status_code == 401:
                    resp.failure("Bookings — session expired")
                    _admin_login(self.client)
                else:
                    resp.success()
            else:
                resp.failure(f"Bookings HTTP {resp.status_code}")

    # weight 2 — today's arrivals
    @task(2)
    def view_arrivals(self):
        with self.client.get(
            "/api/m02/arrivals",
            catch_response=True,
            name="[admin] GET /api/m02/arrivals",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 401:
                resp.failure("Arrivals — session expired")
                _admin_login(self.client)
            else:
                resp.failure(f"Arrivals HTTP {resp.status_code}")

    # weight 1 — warehouse overview (less frequent)
    @task(1)
    def view_warehouses(self):
        with self.client.get(
            "/api/m13/items",
            catch_response=True,
            name="[admin] GET /api/m13/warehouses",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 401:
                resp.failure("Warehouses — session expired")
                _admin_login(self.client)
            else:
                resp.failure(f"Warehouses HTTP {resp.status_code}")


class StaffUser(HttpUser):
    """
    Simulates a front-desk or maintenance staff member.
    Authenticated via /api/login → client_token cookie.
    """

    wait_time = between(2, 5)

    def on_start(self):
        _staff_login(self.client)

    # weight 3 — checking arrivals is the primary front-desk task
    @task(3)
    def view_arrivals(self):
        with self.client.get(
            "/api/m02/arrivals",
            catch_response=True,
            name="[staff] GET /api/m02/arrivals",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 401:
                resp.failure("Staff arrivals — session expired")
                _staff_login(self.client)
            else:
                resp.failure(f"Staff arrivals HTTP {resp.status_code}")

    # weight 2 — departures list
    @task(2)
    def view_departures(self):
        with self.client.get(
            "/api/m02/departures",
            catch_response=True,
            name="[staff] GET /api/m02/departures",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 401:
                resp.failure("Staff departures — session expired")
                _staff_login(self.client)
            else:
                resp.failure(f"Departures HTTP {resp.status_code}")

    # weight 2 — open maintenance orders
    @task(2)
    def view_maintenance_tickets(self):
        with self.client.get(
            "/api/m08/orders",
            catch_response=True,
            name="[staff] GET /api/m08/tickets",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 401:
                resp.failure("Maintenance tickets — session expired")
                _staff_login(self.client)
            else:
                resp.failure(f"Maintenance tickets HTTP {resp.status_code}")

    # weight 1 — periodic health check (background polling pattern)
    @task(1)
    def health_check(self):
        with self.client.get(
            "/api/health",
            catch_response=True,
            name="[staff] GET /health",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Health check HTTP {resp.status_code}")


class GuestUser(HttpUser):
    """
    Simulates an anonymous visitor / prospective guest browsing the
    public-facing site. No authentication required.
    """

    wait_time = between(3, 8)

    # weight 5 — health / status endpoint (CDN probes, uptime monitors)
    @task(5)
    def health_check(self):
        with self.client.get(
            "/api/health",
            catch_response=True,
            name="[guest] GET /health",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Health HTTP {resp.status_code}")

    # weight 3 — landing / home page
    @task(3)
    def home_page(self):
        with self.client.get(
            "/",
            catch_response=True,
            name="[guest] GET /",
        ) as resp:
            # Accept redirect (302/303 → /login) as valid for unauthenticated visitors
            if resp.status_code in (200, 302, 303):
                resp.success()
            else:
                resp.failure(f"Home page HTTP {resp.status_code}")


# ── Load shape: realistic ramp-up / soak / ramp-down ─────────────────────────

class DheuofLoadShape(LoadTestShape):
    """
    Staged load profile for the Dheuof platform:

      0 – 60 s  :  ramp to  10 users (warm-up / smoke)
     60 – 120 s :  ramp to  50 users (moderate load)
    120 – 180 s :  ramp to 100 users (peak soak)
    180 – 240 s :  ramp down to 50 users (cool-down)
    > 240 s     :  test ends

    The spawn_rate column controls how fast Locust adds/removes users per
    second during each transition.
    """

    # (duration_seconds, target_users, spawn_rate)
    stages = [
        (60,  10,   2),   # 0-60s  : warm-up, gentle ramp
        (120, 50,   5),   # 60-120s: moderate, ramp 5/s
        (180, 100,  10),  # 120-180s: peak soak
        (240, 50,   5),   # 180-240s: cool-down
    ]

    def tick(self):
        run_time = self.get_run_time()

        for duration, users, spawn_rate in self.stages:
            if run_time < duration:
                return (users, spawn_rate)

        return None  # signal Locust to stop after all stages
