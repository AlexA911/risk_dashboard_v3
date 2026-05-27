"""
HAWK Ingest - Step 3
Two modes:
  --backfill   One-off historical pull from 2024-06-01 → today.
               Writes a single history.parquet per table.
               Run once manually. Do not run again.

  --daily      Pulls yesterday's data only.
               Writes a dated parquet file alongside history.parquet.
               Scheduled to run at 5am every weekday.

Usage:
  python etl/hawk_ingest.py --backfill
  python etl/hawk_ingest.py --daily

Location: risk_dashboard_v3/etl/hawk_ingest.py
"""

import sys
import pyodbc
import pandas as pd
from pathlib import Path
from datetime import date, timedelta

# ── Config ────────────────────────────────────────────────────────────────────

SERVER     = "LCY-SQL3"
DATABASE   = "OSTCRebates"
BACKFILL_START = "2024-06-01"

BASE_DIR     = Path(__file__).resolve().parent.parent / "data" / "hawk" / "raw"
ANALYST_DIR  = BASE_DIR / "analyst"
PRODUCT_DIR  = BASE_DIR / "product"

# ── Mode ──────────────────────────────────────────────────────────────────────

if "--backfill" in sys.argv:
    MODE       = "backfill"
    START_DATE = BACKFILL_START
    END_DATE   = date.today().strftime("%Y-%m-%d")
    ANALYST_OUT = ANALYST_DIR / "history.parquet"
    PRODUCT_OUT = PRODUCT_DIR / "history.parquet"
elif "--daily" in sys.argv:
    MODE       = "daily"
    YESTERDAY  = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    START_DATE = YESTERDAY
    END_DATE   = YESTERDAY
    ANALYST_OUT = ANALYST_DIR / f"{YESTERDAY}.parquet"
    PRODUCT_OUT = PRODUCT_DIR / f"{YESTERDAY}.parquet"
else:
    print("ERROR: No mode specified.")
    print("Usage:")
    print("  python etl/hawk_ingest.py --backfill   (one-off historical pull)")
    print("  python etl/hawk_ingest.py --daily      (yesterday's data only)")
    sys.exit(1)

# ── Guards ────────────────────────────────────────────────────────────────────

if MODE == "backfill":
    if ANALYST_OUT.exists() or PRODUCT_OUT.exists():
        print("ERROR: history.parquet already exists.")
        print("Backfill has already been run. Use --daily for incremental updates.")
        sys.exit(1)

if MODE == "daily":
    if ANALYST_OUT.exists() or PRODUCT_OUT.exists():
        print(f"ERROR: {YESTERDAY}.parquet already exists.")
        print("Daily ingest for this date has already run.")
        sys.exit(1)

# ── Connection ─────────────────────────────────────────────────────────────────

print(f"Mode:     {MODE.upper()}")
print(f"Pulling:  {START_DATE} → {END_DATE}")
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
FROM [HAWK].[DailyAnalystTransactions]
WHERE ReportDate >= '{START_DATE}'
  AND ReportDate <= '{END_DATE}'
  AND ITM != 'ICHN'
ORDER BY ReportDate, PrimaryITM, ITM
"""

print(f"Pulling DailyAnalystTransactions...")

df_analyst = pd.read_sql(analyst_query, conn)

print(f"Rows pulled:       {len(df_analyst):,}")
print(f"Date range:        {df_analyst['ReportDate'].min().date()} → {df_analyst['ReportDate'].max().date()}")
print(f"Unique analysts:   {df_analyst['PrimaryITM'].nunique()}")

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
FROM [HAWK].[DailyProductTransactions]
WHERE ReportDate >= '{START_DATE}'
  AND ReportDate <= '{END_DATE}'
  AND ITM != 'ICHN'
ORDER BY ReportDate, PrimaryITM, ITM, Product
"""

print(f"\nPulling DailyProductTransactions...")

df_product = pd.read_sql(product_query, conn)

print(f"Rows pulled:       {len(df_product):,}")
print(f"Date range:        {df_product['ReportDate'].min().date()} → {df_product['ReportDate'].max().date()}")
print(f"Unique analysts:   {df_product['PrimaryITM'].nunique()}")
print(f"Unique products:   {df_product['Product'].nunique()}")

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