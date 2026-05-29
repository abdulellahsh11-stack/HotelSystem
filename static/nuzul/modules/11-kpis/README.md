# Reports & Analytics — التقارير والتحليلات

Maps to modules **11 (مؤشرات الأداء)** and **12 (تحليل البيانات و نقاط القوه ونقاط الضعف)**.

## Components

- `Charts.jsx` — `LineChart` (SVG daily revenue trend) + `ChannelBars` (stacked channel mix bar + legend).
- `Insights.jsx` — `InsightCard` (strengths vs weaknesses cards with recommendations) + `ReportsList` (scheduled report subscriptions).

## KPI ladder

5 hotel-industry KPIs presented as a strip: **RevPAR · ADR · OCC · GOPPAR · ALOS**. Each card mirrors the same template (label-en + label-ar + value + change).

## Strengths / Weaknesses framing

Each InsightCard has a recommendation — the system positions itself as inspirational AND actionable, per the brief ("مؤشرات الاداء احترافيه وملهمه" + "نقاط القوه ونقاط الضعف"). The recommendation panel is in the warm paper-tint with gold "TOIVOMUS / التوصية" eyebrow.

## Scheduled reports

The schedule list ties to: daily / weekly / monthly cadence from the brief, plus ZATCA-ready VAT export for Saudi compliance.
