#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py — نقطة الدخول لـ uvicorn
يستورد app من main1 ويُسجّل جميع الـ routes عبر استيراد main2
"""
from main1 import app  # noqa: F401 — الهدف: uvicorn main:app
import main2           # noqa: F401 — يُسجّل جميع @app.get/post/put/delete

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 5050))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
