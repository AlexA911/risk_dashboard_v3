# Refactor Log

A running record of structural changes to the codebase — what changed,
why, and when. For changes that are self-documenting in code, no entry
is needed here.

---

## 2026-05-27 — Pre-refactor cleanup (Stage 0)

**Deleted dead frontend files:**
- `frontend/src/components/LocationTable.jsx` — replaced by LocationTableAG
- `frontend/src/components/LocationTable_New.jsx` — replaced by LocationTableAG
- `frontend/src/App.css` — leftover Vite starter template, never used

**Deleted dead backend files:**
- `data/data_layer.py` — v1/v2 era file, still calling db_var which no longer exists
- `data/db_var_additions.py` — querying MarginDataTable (old Market_Risk schema),
  not imported anywhere in v3

---

## 2026-05-27 — Stage 1: Extract `today()` into shared module

**New file:** `data/dates.py`

**Reason:** `_today()` was defined identically in `db_office.py`, `db_analyst.py`,
and `db_rollview.py`. Single source of truth means one place to change if the
date format or timezone handling ever needs updating.

**Pattern established:** shared date helpers live in `data/dates.py`, imported
by all query modules. Private `_today()` → public `today()` (underscore dropped
because the function is now intentionally shared).

**Local variable rename:** any function that previously did `today = _today()`
now does `today_str = today()` to avoid shadowing the imported function name.

---

## 2026-05-27 — Stage 2: Extract `get_latest_eod_dates()` into shared module

**Updated file:** `data/dates.py`

**Reason:** `_get_latest_eod_dates()` was defined identically in all three query
modules. Same rationale as Stage 1 — one source of truth for a function that
all modules depend on equally.

**Note:** `dates.py` now imports `get_connection` from `db_connection.py` because
this function queries the database. A future split into `dates.py` (pure) and
`db_dates.py` (DB-backed) was considered and deferred — the project is small
enough that the mixed responsibility is acceptable for now.

---
## 2026-05-28 — Stage 3: Introduce DateContext

**Updated file:** `data/dates.py`

**Reason:** Every table function began with a 7-line block resolving five date
references (today, last_night_95, t1_95, last_night_100, t1_100). This block
was repeated across 8+ functions in db_office.py, db_analyst.py, and
db_rollview.py — identical logic, identical risk of drift.

**Change:** Added a `DateContext` dataclass and `date_context()` factory function
to dates.py. Every table function now calls `dc = date_context()` once at the
top and accesses dates via `dc.today_str`, `dc.last_night_95` etc.

**Also removed:** `_get_dates()` in db_rollview.py — it was doing exactly what
`date_context()` now does, so it was deleted rather than converted.

**Local variable rename:** `today_str` → `dc.today_str` throughout. Note that
`_get_ff_row()` in db_office.py still takes `today_str` as a parameter name —
this is intentional, callers pass `dc.today_str` as the argument.

## 2026-05-28 — Stage 4: Introduce build_var_table() helper

**New file:** `data/query_helpers.py`

**Reason:** Every table function contained an identical 35-line block —
6 fetches across two VaR configs and two EOD dates, SOD fallback,
column rename, outer merge, and 9-column delta computation. This block
appeared in 6 functions across 3 files (~210 lines total).

**Change:** `build_var_table(fetch_fn, keys, dc, var_col, margin_col)`
takes a caller-provided fetch function and a DateContext, and owns all
the structural assembly work. Each table function now provides only the
SQL (10-15 lines) and calls build_var_table() for the rest.

**Functions converted:**
- db_office.py: get_location_table, get_analyst_table,
  get_asset_class_table_grouped, get_product_table_by_sector
- db_analyst.py: (get_analyst_table_for_tab left as-is — per-row
  IsIntraday fallback logic doesn't fit the generic helper cleanly)
- db_rollview.py: _build_product_df deleted, both call sites replaced
  with local fetch_products + build_var_table

**Note:** var_col defaults to "VaR" for office/analyst queries,
set to "iVaR" for product-level queries.

## 2026-05-28 — Stage 5: Rename Roll Risk functions and fix ViewToggle bug

**Files changed:**
- `data/db_rollview.py` — function definitions and docstring comments
- `backend/main.py` — endpoint decorators, function names, cache keys, error labels
- `frontend/src/api/client.js` — export names and API URL strings
- `frontend/src/components/RollRiskTab.jsx` — import and 2 call sites

**Renamed:**

| Old | New |
|---|---|
| `get_roll_risk()` | `get_fi_group_risk()` |
| `get_roll_risk_rolls()` | `get_fi_roll_risk()` |
| `/api/roll-risk` | `/api/fi-group-risk` |
| `/api/roll-risk-rolls` | `/api/fi-roll-risk` |
| `getRollRisk` | `getFiGroupRisk` |
| `getRollRiskRolls` | `getFiRollRisk` |

**Reason:** The old names were ambiguous — "roll risk" could mean anything.
The new names make the distinction explicit:
- `get_fi_group_risk` — Fixed Income grouped by currency subgroup (USD, GBP,
  EUR, CAD, AUD, CHF) plus Equities. Section total = Cumulus netted Rates /
  Equity Indices. Shows the full offsetting STIRs effect.
- `get_fi_roll_risk` — Fixed Income roll positions only (bond futures, no
  STIRs) plus Equity Rolls. Section total = Cumulus netted from FI Rolls /
  Equity Rolls asset class. Flat list, no subgroups.

**Bug fixed:** `ViewToggle` in `RollRiskTab.jsx` had `value="Offset"` on the
Risk button (should be `"risk"`) and `value="Rolls"` (capital R) where the
view state check used lowercase `"rolls"`. Both corrected — Risk and Rolls
tabs now show different data as intended.

## 2026-05-28 — Stage 6: Normalise client.js

**Reason:** `getVixMargin` and `getLastSnapshot` used raw `fetch` while
every other export used axios. Inconsistent error handling and base URL
management — if BASE_URL ever changes, raw fetch calls wouldn't pick it up.

**Change:** Both converted to `api.get(...).then(r => r.data)` — same
response shape for callers, consistent with the rest of the file.