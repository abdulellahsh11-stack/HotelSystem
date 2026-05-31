# Admin Dashboard — لوحة التحكم

The main hotel control panel. Senior staff land here.

## Screens / components included

- `Sidebar.jsx` — primary nav (dark forest, gold accent) — bilingual labels, RTL.
- `TopBar.jsx` — search, lang switch, notifications, user menu.
- `KpiGrid.jsx` — 6 stat cards (Occupancy, ADR, RevPAR, today's revenue, upcoming, maintenance).
- `OccupancyHeatmap.jsx` — 14-day forecast across room types.
- `BookingsTable.jsx` — recent reservations with status pills, channel, VIP markers.
- `RevenueChart.jsx` — daily revenue bar chart (SVG, peaks in gold).
- `Panels.jsx` — channel-mix donut + live activity feed.

## Notes

- Numerics in Arabic UI use Eastern Arabic-Indic digits (٠–٩) for body; **the type stack uses Latin family on numerics** to enable `tabular-nums`. If you want pure Arabic-Indic with tabular alignment, swap to a font that ships Arabic tabular figures (Boutros AdsBold, IBM Plex Sans Arabic with `font-feature-settings: "tnum"`).
- Heatmap colors go sand → gold → green → deep-forest. Tweak `cellColor()` in `OccupancyHeatmap.jsx` to shift thresholds.
- VIP guests get a gold ring on the avatar + a `VIP` tag in the name.
