# Inventory & Warehouse — المخزون والمستودع

Combined surface for modules **4 (المخزون)** and **5 (المستودع)** — both share the same data model (item + qty + location + par level + reorder threshold), so they live in one kit with a category rail to switch between groups (linens/amenities vs MEP/maintenance).

## Components

- `Items.jsx` — `CategoryRail` (left nav by group + custom-category slot), `ItemsTable` (item list with avatar/SKU/location/movement/status), and `StockBar` (par-level bar with reorder tick).

## Data shape

```js
{ sku, ic, name, loc, zone, qty, par, reorder, dir: "in"|"out", move, when }
```

Status thresholds are computed in `ItemsTable`:
- `qty <= reorder` → **danger** ("تحت الحد")
- `qty < par*0.5`  → **warning** ("منخفض")
- else             → **ok** ("متوفر")

## Custom categories

The "+ تخصيص فئة جديدة" tile at the bottom of the rail is the placeholder for user-defined categories (mentioned in the brief as "+ تخصيص"). Wire to your taxonomy service.
