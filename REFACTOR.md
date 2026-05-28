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