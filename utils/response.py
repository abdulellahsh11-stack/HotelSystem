#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils/response.py — JSON Response Helpers
"""
import json
from typing import Any


def ok(data: dict = None, **kwargs) -> dict:
    """response ناجح"""
    result = {"ok": True}
    if data:
        result.update(data)
    result.update(kwargs)
    return result


def err(message: str, status: int = 400, **kwargs) -> dict:
    """response خطأ"""
    result = {"ok": False, "error": message, "status": status}
    result.update(kwargs)
    return result


def json_response(data: Any, status: int = 200) -> tuple:
    """يُعيد (body_bytes, status, content_type)"""
    body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return body, status, "application/json; charset=utf-8"


def paginate(items: list, page: int = 1, per_page: int = 50) -> dict:
    """تقسيم القائمة لصفحات"""
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "has_next": end < total,
        "has_prev": page > 1,
    }
