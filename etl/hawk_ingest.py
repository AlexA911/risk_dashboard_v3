"""
HAWK Ingest
Four modes:
  --backfill     One-off historical pull from 2024-06-01 → today.
                 Writes a single history.parquet per table.
                 Errors if history.parquet already exists.

  --rebackfill   Re-pulls full history, overwriting history.parquet.
                 Use when LCY-SQL3 corrections have been applied to
                 historical data and the cache needs refreshing.

  --daily        Pulls the last trading day's data.
                 Skips weekends — Mon morning pulls Friday, not Sunday.
                 Writes a dated parquet file alongside history.parquet.
                 Scheduled to run at 5am every weekday.

  --date YYYY-MM-DD
                 Pulls a specific date's data. Use to backfill a missed
                 day or re-pull a single date. Errors if a file for that
                 date already exists — delete it first to overwrite.

Usage:
  python etl/hawk_ingest.py --backfill
  python etl/hawk_ingest.py --rebackfill
  python etl/hawk_ingest.py --daily
  python etl/hawk_ingest.py --date 2026-05-29

Notes:
  - All queries use (NOLOCK) to match HAWK frontend figures.
    HAWK frontend reads from parquets built from LCY-SQL3 using NOLOCK.
  - Nullable columns are explicitly cast to float64 before writing parquet
    to avoid pyarrow schema conflicts when all values are NULL on a given day.
  - LCY-SQL3 is the primary/authoritative source. Corrections applied to
    historical rows require --rebackfill to refresh the cache.
  - Bank holidays are not handled — a --daily run on a Tuesday after a
    Monday bank holiday will pull an empty Monday. Use --date to fetch
    the previous Friday explicitly if needed.

Location: risk_dashboard_v3/etl/hawk_ingest.py
"""

import sys
import pyodbc
import pandas as pd
from pathlib import Path
from datetime import date, timedelta

# ── Config ────────────────────────────────────────────────────────────────────

SERVER         = "LCY-SQL3"
DATABASE       = "OSTCRebates"
BACKFILL_START = "2024-06-01"

BASE_DIR     = Path(__file__).resolve().parent.parent / "data" / "hawk" / "raw"
ANALYST_DIR  = BASE_DIR / "analyst"
PRODUCT_DIR  = BASE_DIR / "product"

# Columns that can be entirely NULL on some days — cast to float64 to avoid
# pyarrow schema conflicts when concatenating parquet files
ANALYST_NULLABLE_COLS = [
    "Bonuses", "InactiveAccAdj", "CommissionFxDiff",
    "VolumeRebates", "ExchangeRebates",
]
PRODUCT_NULLABLE_COLS = [
    "InitialMargin", "SODPosition",
    "VolumeRebates", "ExchangeRebates",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def last_trading_day(reference: date) -> date:
    """
    Return the last weekday strictly before `reference`.
    Mon → previous Friday. Tue–Fri → previous day. Weekends → previous Friday.
    Does not account for bank holidays.
    """
    d = reference - timedelta(days=1)
    while d.weekday() >= 5:   # 5 = Sat, 6 = Sun
        d -= timedelta(days=1)
    return d


# ── Mode ──────────────────────────────────────────────────────────────────────

if "--rebackfill" in sys.argv:
    MODE        = "rebackfill"
    START_DATE  = BACKFILL_START
    END_DATE    = date.today().strftime("%Y-%m-%d")
    ANALYST_OUT = ANALYST_DIR / "history.parquet"
    PRODUCT_OUT = PRODUCT_DIR / "history.parquet"

elif "--backfill" in sys.argv:
    MODE        = "backfill"
    START_DATE  = BACKFILL_START
    END_DATE    = date.today().strftime("%Y-%m-%d")
    ANALYST_OUT = ANALYST_DIR / "history.parquet"
    PRODUCT_OUT = PRODUCT_DIR / "history.parquet"

elif "--daily" in sys.argv:
    MODE        = "daily"
    TARGET      = last_trading_day(date.today()).strftime("%Y-%m-%d")
    START_DATE  = TARGET
    END_DATE    = TARGET
    ANALYST_OUT = ANALYST_DIR / f"{TARGET}.parquet"
    PRODUCT_OUT = PRODUCT_DIR / f"{TARGET}.parquet"

elif "--date" in sys.argv:
    MODE        = "date"
    idx         = sys.argv.index("--date")
    if idx + 1 >= len(sys.argv):
        print("ERROR: --date requires a YYYY-MM-DD argument.")
        sys.exit(1)
    TARGET = sys.argv[idx + 1]
    try:
        date.fromisoformat(TARGET)
    except ValueError:
        print(f"ERROR: '{TARGET}' is not a valid YYYY-MM-DD date.")
        sys.exit(1)
    START_DATE  = TARGET
    END_DATE    = TARGET
    ANALYST_OUT = ANALYST_DIR / f"{TARGET}.parquet"
    PRODUCT_OUT = PRODUCT_DIR / f"{TARGET}.parquet"

else:
    print("ERROR: No mode specified.")
    print("Usage:")
    print("  python etl/hawk_ingest.py --backfill            (one-off historical pull)")
    print("  python etl/hawk_ingest.py --rebackfill          (re-pull full history, overwrites)")
    print("  python etl/hawk_ingest.py --daily               (last trading day's data)")
    print("  python etl/hawk_ingest.py --date YYYY-MM-DD     (specific date)")
    sys.exit(1)


# ── Guards ────────────────────────────────────────────────────────────────────

if MODE == "backfill":
    if ANALYST_OUT.exists() or PRODUCT_OUT.exists():
        print("ERROR: history.parquet already exists.")
        print("Use --rebackfill to overwrite, or --daily for incremental updates.")
        sys.exit(1)

if MODE in ("daily", "date"):
    if ANALYST_OUT.exists() or PRODUCT_OUT.exists():
        print(f"ERROR: {ANALYST_OUT.name} already exists.")
        print(f"Delete the file(s) manually if you intend to re-pull this date.")
        sys.exit(1)

# rebackfill has no guard — intentionally overwrites


# ── Connection ────────────────────────────────────────────────────────────────

print(f"Mode:     {MODE.upper()}")
print(f"Pulling:  {START_DATE} → {END_DATE}")
if MODE == "rebackfill":
    print("WARNING:  history.parquet will be overwritten.")
print(f"Connecting to {SERVER}...")

conn = pyodbc.connect(
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"Trusted_Connection=yes;"
)

print("Connected.\n")


# ── Pull analyst transactions ─────────────────────────────────────────────────

analyst_query = f"""
SELECT
    ReportDate,
    ITM,
    PrimaryITM,
    Office,
    Name,
    GrossPnL,
    NetPnL,
    Commissions,
    GrossPnL_WO_RF,
    NetPnL_WO_RF,
    RoundTurn,
    Margins,
    OpeningBalance,
    ClosingBalance,
    VolumeRebates,
    ExchangeRebates,
    FacilityCosts,
    HousekeepingCharges,
    InternalTransferCharges,
    OtherCharges,
    CashPostings,
    BalanceFxDiff,
    CommissionFxDiff,
    Bonuses,
    InactiveAccAdj,
    ClosingAccount,
    HireDate,
    FirstHireDate
FROM [HAWK].[DailyAnalystTransactions] (NOLOCK)
WHERE ReportDate >= '{START_DATE}'
  AND ReportDate <= '{END_DATE}'
  AND ITM != 'ICHN'
ORDER BY ReportDate, PrimaryITM, ITM
"""

print("Pulling DailyAnalystTransactions...")
df_analyst = pd.read_sql(analyst_query, conn)

# Cast nullable columns to float64 to avoid pyarrow schema conflicts
for col in ANALYST_NULLABLE_COLS:
    if col in df_analyst.columns:
        df_analyst[col] = df_analyst[col].astype("float64")

print(f"Rows pulled:       {len(df_analyst):,}")
if len(df_analyst) > 0:
    print(f"Date range:        {df_analyst['ReportDate'].min().date()} → {df_analyst['ReportDate'].max().date()}")
    print(f"Unique analysts:   {df_analyst['PrimaryITM'].nunique()}")
    print(f"GrossPnL total:    {df_analyst['GrossPnL'].sum():,.0f}")
else:
    print("WARNING: No rows returned for this date range.")


# ── Pull product transactions ─────────────────────────────────────────────────

product_query = f"""
SELECT
    ReportDate,
    ITM,
    PrimaryITM,
    Office,
    Product,
    ProductDesc,
    Exchange,
    ProductGroup,
    ProductType,
    SubAssetClass,
    AssetClass,
    ProductComplex,
    XTPContractCode,
    XTPExchange,
    ReportingSymbol,
    HGProductID,
    VolumeDTD,
    VolumeMTD,
    VolumeYTD,
    CombinedCode,
    InitialMargin,
    MarginCalcMethod,
    MarginProductGroup,
    SODPosition,
    PnL,
    VariationMargin,
    Commission,
    Fees,
    ExecCharges,
    OtherCharges,
    NetPnL,
    NetPnL_WO_RF,
    VolumeRebates,
    ExchangeRebates
FROM [HAWK].[DailyProductTransactions] (NOLOCK)
WHERE ReportDate >= '{START_DATE}'
  AND ReportDate <= '{END_DATE}'
  AND ITM != 'ICHN'
ORDER BY ReportDate, PrimaryITM, ITM, Product
"""

print(f"\nPulling DailyProductTransactions...")
df_product = pd.read_sql(product_query, conn)

# Cast nullable columns to float64
for col in PRODUCT_NULLABLE_COLS:
    if col in df_product.columns:
        df_product[col] = df_product[col].astype("float64")

print(f"Rows pulled:       {len(df_product):,}")
if len(df_product) > 0:
    print(f"Date range:        {df_product['ReportDate'].min().date()} → {df_product['ReportDate'].max().date()}")
    print(f"Unique analysts:   {df_product['PrimaryITM'].nunique()}")
    print(f"Unique products:   {df_product['Product'].nunique()}")
else:
    print("WARNING: No rows returned for this date range.")

conn.close()


# ── Write parquet ─────────────────────────────────────────────────────────────

ANALYST_DIR.mkdir(parents=True, exist_ok=True)

PRODUCT_DIR.mkdir(parents=True, exist_ok=True)

print(f"\nWriting analyst parquet  → {ANALYST_OUT.name}...")
df_analyst.to_parquet(ANALYST_OUT, index=False)
print(f"Written:  {ANALYST_OUT}")
print(f"Size:     {ANALYST_OUT.stat().st_size / 1024:.1f} KB")

print(f"\nWriting product parquet  → {PRODUCT_OUT.name}...")
df_product.to_parquet(PRODUCT_OUT, index=False)
print(f"Written:  {PRODUCT_OUT}")
print(f"Size:     {PRODUCT_OUT.stat().st_size / 1024:.1f} KB")

print(f"\n[{MODE.upper()}] Done.")