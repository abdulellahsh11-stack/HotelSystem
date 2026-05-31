# HR — الموارد البشرية

Maps to module #9 in the spec: payroll, advances, Iqama, work permits, housing, living allowance, tickets, visas, Qiwa, contracts, medical insurance, GOSI.

## Components

- `Staff.jsx` — `StaffTable` (employee list with nationality, Iqama, expiry timeline, salary, Qiwa status) + `IqamaTimeline` (color-coded bar that turns gold ≤90 days, red ≤30).

## Tabs

The 8 tabs across the top mirror the brief's HR sub-modules — only the first ("الموظفون") is wired; the others are placeholder stubs ready to receive their own list components.

## Saudi-specific integrations

- **قوى (Qiwa)** — staff status pill (متصل قوى / بانتظار). Sync button in page header.
- **GOSI / التأمينات** — dedicated tab.
- **هوية وطنية vs إقامة** — distinguished in the table (Saudi nationals show their National ID, others show their Iqama).
