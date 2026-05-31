# Front Desk — الاستقبال

Reception screen for daily check-in/out flow.

## Components

- `ArrivalDepart.jsx` — `ArrivalCard` (today's arrival row with one-click check-in) + `DepartureRow` (departure with balance check).
- `CheckInPanel.jsx` — 3-step quick check-in:
  1. ID/Iqama scanner (Smart Key reader — see Smart Key module)
  2. Guest summary with verification badge
  3. Available rooms grid with selection

## Smart Key integration

Step 1's scanner is the visible surface for the **المفتاح الذكي** module: ID/passport/Iqama is read via the connected device, identity is verified against the anti-fraud database, the guest's profile loads, and on completion a digital key is issued. The placeholder element is `.fd-scan` — wire it to your hardware bridge.
