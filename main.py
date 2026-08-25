#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py — نقطة الدخول لـ uvicorn

`app_core.py` يُنشئ التطبيق ويُركّب كل وحدات `routes/` في آخره.
يُعاد تصدير `require_client` و`_client_sessions` هنا لأن وحدات
`routes/*.py` تستوردهما عبر «from main import …» كنقطة دخول موحَّدة.
"""
from app_core import (  # noqa: F401 — الهدف: uvicorn main:app
    app,
    require_client,
    _client_sessions,
)

if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 5050)), reload=False)
