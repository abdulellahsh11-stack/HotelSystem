#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/backup_monitor.py — Backup Monitor
يُراقب عمليات backup اليومية ويُنبّه عند الفشل.
يعمل كـ thread كل 6 ساعات عبر CronManager.
"""
import time
import logging
import urllib.request
import urllib.error
import json
from datetime import datetime, timedelta

from utils.monitoring import log_error, log_event
from utils.date_utils import sa_now

log = logging.getLogger("dheuof.backup_monitor")

_6H = 6 * 3600
_MAX_BACKUP_AGE_H = 25   # تنبيه إذا لم يكن هناك backup منذ أكثر من 25 ساعة


class BackupMonitor:
    """
    يُراقب:
    1. آخر commit في GitHub backup repo
    2. حالة Railway PostgreSQL (عبر logs)
    يُنبّه المالك عبر واتساب إذا فشل الـ backup
    """

    def __init__(self, config, whatsapp_service=None):
        self._cfg = config
        self._wa = whatsapp_service
        self._last_alert_time = None

    def run(self) -> None:
        """Loop رئيسي — يعمل كـ daemon thread"""
        log.info("BackupMonitor بدأ")
        while True:
            try:
                self._check_github_backup()
            except Exception as e:
                log_error(e, context={"service": "backup_monitor"})
            time.sleep(_6H)

    def _check_github_backup(self) -> None:
        """يتحقق من آخر commit في repo الـ backup"""
        token = self._cfg.github_backup_token or self._cfg.github_token
        repo = self._cfg.github_backup_repo or self._cfg.github_repo

        if not token or not repo:
            return  # GitHub غير مُفعَّل

        try:
            url = f"https://api.github.com/repos/{repo}/commits?per_page=1"
            req = urllib.request.Request(url, headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                commits = json.loads(resp.read().decode())

            if not commits:
                self._alert_owner("⚠️ لا توجد commits في GitHub backup repo!")
                return

            last_commit_time_str = commits[0]["commit"]["committer"]["date"]
            last_commit_time = datetime.fromisoformat(
                last_commit_time_str.replace("Z", "+00:00")
            )
            age_hours = (sa_now() - last_commit_time).total_seconds() / 3600

            if age_hours > _MAX_BACKUP_AGE_H:
                msg = (
                    f"⚠️ آخر backup منذ {int(age_hours)} ساعة!\n"
                    f"Repo: {repo}\n"
                    f"آخر commit: {last_commit_time_str}"
                )
                self._alert_owner(msg)
                log_event("backup_overdue", {
                    "repo": repo, "age_hours": round(age_hours, 1)
                })
            else:
                log.info(f"✅ GitHub backup سليم — آخر backup منذ {int(age_hours)}h")

        except urllib.error.URLError as e:
            log.warning(f"فشل التحقق من GitHub backup: {e}")
        except Exception as e:
            log_error(e, context={"service": "backup_monitor", "step": "github_check"})

    def _alert_owner(self, message: str) -> None:
        """يُرسل واتساب للمالك إذا فشل الـ backup"""
        # تجنب إرسال نفس التنبيه أكثر من مرة كل 12 ساعة
        now = sa_now()
        if self._last_alert_time:
            hours_since = (now - self._last_alert_time).total_seconds() / 3600
            if hours_since < 12:
                return

        self._last_alert_time = now
        log.warning(f"BACKUP ALERT: {message}")

        if self._wa:
            try:
                owner_phone = getattr(self._cfg, "owner_phone", "")
                if owner_phone:
                    self._wa.send_text(owner_phone, f"🔴 تنبيه نظام ضيوف:\n{message}")
            except Exception as e:
                log.error(f"فشل إرسال تنبيه backup: {e}")
