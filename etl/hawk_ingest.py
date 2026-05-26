"""
HAWK Ingest - Step 1
Pulls DailyAnalystTransactions from LCY-SQL3 and writes to parquet.
Run manually to verify connection and data before scheduling.

Location: risk_dashboard_v2/etl/hawk_ingest.py
"""

import pyodbc
import pandas as pd
from pathlib import Path
from datetime import date

# ── Config ────────────────────────────────────────────────────────────────────

SERVER     = "LCY-SQL3"
DATABASE   = "OSTCRebates"
START_DATE = "2024-06-01"
TODAY      = date.today().strftime("%Y-%m-%d")

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "hawk" / "raw" / "analyst"

# ── Connection ─────────────────────────────────────────────────────────────────

print(f"Connecting to {SERVER}...")

conn = pyodbc.connect(
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"Trusted_Connection=yes;"
)

print("Connected.")

# ── Query ─────────────────────────────────────────────────────────────────────

query = f"""
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
  AND ReportDate <= '{TODAY}'
  AND ITM != 'ICHN'
ORDER BY ReportDate, PrimaryITM, ITM
"""

print(f"Pulling DailyAnalystTransactions from {START_DATE} to {TODAY}...")

df = pd.read_sql(query, conn)

conn.close()

# ── Summary ───────────────────────────────────────────────────────────────────

print(f"\nRows pulled:       {len(df):,}")
print(f"Date range:        {df['ReportDate'].min().date()} → {df['ReportDate'].max().date()}")
print(f"Unique analysts:   {df['PrimaryITM'].nunique()}")
print(f"Unique offices:    {df['Office'].nunique()}")
print(f"\nOffice breakdown:")
print(df.groupby('Office')['PrimaryITM'].nunique().sort_values(ascending=False).to_string())

# ── Write parquet ─────────────────────────────────────────────────────────────

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

output_path = OUTPUT_DIR / f"{TODAY}.parquet"

df.to_parquet(output_path, index=False)

print(f"\nWritten to: {output_path}")
print(f"File size:  {output_path.stat().st_size / 1024:.1f} KB")
print("\nDone.")
