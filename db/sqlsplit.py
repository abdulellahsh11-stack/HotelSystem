#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/sqlsplit.py — تقسيم نصوص SQL إلى عبارات مفردة بشكل صحيح.

لماذا هذا الملف موجود
─────────────────────
كانت الـ migrations تُقسّم SQL بـ `sql.split(";")`، وهذا يُمزّق أي دالة
مكتوبة بـ dollar-quoting:

    CREATE OR REPLACE FUNCTION f() RETURNS TRIGGER AS $$
    BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
    $$ LANGUAGE plpgsql;

فالفاصلة المنقوطة داخل جسم الدالة تُقسّمها إلى أربع قطع غير صالحة، وكل
واحدة تفشل بـ «unterminated dollar-quoted string».

الوحدة هنا تمسح النص حرفاً حرفاً وتتجاهل الفواصل المنقوطة الواقعة داخل:
  • dollar-quotes بأي وسم:  $$ ... $$  و  $tag$ ... $tag$
  • نصوص مفردة الاقتباس:     'it''s'
  • معرّفات مزدوجة الاقتباس:  "column;name"
  • تعليقات سطرية:            -- ...
  • تعليقات كتلية متداخلة:    /* ... /* ... */ ... */

كما توفّر has_executable_sql() لتمييز العبارة التي تحمل SQL حقيقياً عن
الكتلة التي لا تحوي إلا تعليقات — لأن الفحص الساذج `s.startswith("--")`
كان يُسقط كل عبارة مسبوقة بتعليق، أي معظم الملف الأمني.
"""
from __future__ import annotations

__all__ = ["split_sql", "has_executable_sql", "strip_sql_comments"]


def _dollar_tag_at(sql: str, i: int) -> str | None:
    """يُعيد وسم dollar-quote الذي يبدأ عند الموضع i، أو None.

    الوسم الصالح هو `$$` أو `$identifier$` حيث identifier يبدأ بحرف أو
    شرطة سفلية ويتكوّن من حروف/أرقام/شرطات سفلية. هذا يمنع الخلط مع
    معاملات psycopg2 مثل `$1` أو مع `$` المنفردة داخل نص.
    """
    if sql[i] != "$":
        return None
    j = i + 1
    if j < len(sql) and sql[j] == "$":
        return "$$"
    start = j
    while j < len(sql) and (sql[j].isalnum() or sql[j] == "_"):
        j += 1
    # لا بد أن يبدأ المعرّف بحرف أو شرطة سفلية (لا برقم)
    if j == start or sql[start].isdigit():
        return None
    if j < len(sql) and sql[j] == "$":
        return sql[i : j + 1]
    return None


def split_sql(sql: str) -> list[str]:
    """يُقسّم نص SQL إلى عبارات، مع احترام الاقتباسات والتعليقات.

    التعليقات السابقة لعبارة تبقى ملتصقة بها — وهذا مقصود كي تظل رسائل
    الخطأ مفهومة. استخدم has_executable_sql() قبل التنفيذ لتخطّي الكتل
    التعليقية البحتة.
    """
    statements: list[str] = []
    buf: list[str] = []
    i, n = 0, len(sql)
    block_depth = 0  # عمق تعليقات /* */ المتداخلة

    while i < n:
        ch = sql[i]

        # ── داخل تعليق كتلي ───────────────────────────────────────
        if block_depth:
            if sql.startswith("/*", i):
                block_depth += 1
                buf.append("/*")
                i += 2
                continue
            if sql.startswith("*/", i):
                block_depth -= 1
                buf.append("*/")
                i += 2
                continue
            buf.append(ch)
            i += 1
            continue

        # ── بداية تعليق كتلي ──────────────────────────────────────
        if sql.startswith("/*", i):
            block_depth = 1
            buf.append("/*")
            i += 2
            continue

        # ── تعليق سطري: ابتلع حتى نهاية السطر ─────────────────────
        if sql.startswith("--", i):
            eol = sql.find("\n", i)
            if eol == -1:
                buf.append(sql[i:])
                i = n
            else:
                buf.append(sql[i : eol + 1])
                i = eol + 1
            continue

        # ── نص مفرد الاقتباس (مع دعم '' المضاعفة) ─────────────────
        if ch == "'":
            j = i + 1
            while j < n:
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            buf.append(sql[i:j])
            i = j
            continue

        # ── معرّف مزدوج الاقتباس (مع دعم "" المضاعفة) ─────────────
        if ch == '"':
            j = i + 1
            while j < n:
                if sql[j] == '"':
                    if j + 1 < n and sql[j + 1] == '"':
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            buf.append(sql[i:j])
            i = j
            continue

        # ── dollar-quote: ابتلع حتى الوسم المطابق ─────────────────
        tag = _dollar_tag_at(sql, i)
        if tag:
            end = sql.find(tag, i + len(tag))
            if end == -1:
                # وسم غير مغلق — خُذ الباقي كما هو ودع PostgreSQL يشتكي
                buf.append(sql[i:])
                i = n
            else:
                stop = end + len(tag)
                buf.append(sql[i:stop])
                i = stop
            continue

        # ── فاصلة منقوطة على المستوى الأعلى = نهاية عبارة ─────────
        if ch == ";":
            statements.append("".join(buf))
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf)
    if tail.strip():
        statements.append(tail)

    return [s for s in statements if s.strip()]


def strip_sql_comments(sql: str) -> str:
    """يُزيل التعليقات السطرية والكتلية مع الإبقاء على محتوى النصوص."""
    out: list[str] = []
    i, n = 0, len(sql)
    block_depth = 0

    while i < n:
        if block_depth:
            if sql.startswith("/*", i):
                block_depth += 1
                i += 2
            elif sql.startswith("*/", i):
                block_depth -= 1
                i += 2
            else:
                i += 1
            continue

        if sql.startswith("/*", i):
            block_depth = 1
            i += 2
            continue

        if sql.startswith("--", i):
            eol = sql.find("\n", i)
            i = n if eol == -1 else eol + 1
            continue

        ch = sql[i]

        if ch in "'\"":
            j = i + 1
            while j < n:
                if sql[j] == ch:
                    if j + 1 < n and sql[j + 1] == ch:
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            out.append(sql[i:j])
            i = j
            continue

        tag = _dollar_tag_at(sql, i)
        if tag:
            end = sql.find(tag, i + len(tag))
            stop = n if end == -1 else end + len(tag)
            out.append(sql[i:stop])
            i = stop
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def has_executable_sql(statement: str) -> bool:
    """هل تحتوي العبارة على SQL حقيقي بعد نزع التعليقات؟

    يحلّ محل الفحص الخاطئ `s.startswith("--")` الذي كان يُسقط كل عبارة
    مسبوقة بتعليق توضيحي.
    """
    return bool(strip_sql_comments(statement).strip())
