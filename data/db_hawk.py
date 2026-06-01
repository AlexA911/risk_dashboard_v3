"""
data/db_hawk.py — HAWK P&L data from local parquet cache.

Source:  data/hawk/raw/analyst/   — DailyAnalystTransactions
         data/hawk/raw/product/   — DailyProductTransactions

Each directory contains:
  history.parquet       — 2024-06-01 → first run date (one-off backfill)
  YYYY-MM-DD.parquet    — daily incremental files

Key facts:
  - Always aggregate by PrimaryITM — sub-accounts carry independent P&L
  - ICHN excluded at ingest time (not present in parquet files)
  - Excluded offices filtered via reference.EXCLUDED_OFFICES
  - Sector mapping via reference.hawk_sector()
  - Currency: USD throughout
  - P&L field: GrossPnL (= GrossPnL ExcR on HAWK frontend)
    GrossPnL_WO_RF confirmed to behave differently on rebate days.
    GrossPnL matches the HAWK frontend figure.

Known data note:
  - ~1,121 gap vs HAWK frontend total (1,472,362 vs 1,473,483 on 2026-05-26)
  - Consistent and non-timing-related — likely LCY-SQL3 lagging the primary
    AWS RDS instance (TM-DBINST1.CTMLJWOTKQUZ.EU-WEST-1.RDS.AMAZONAWS.COM)
    by a small amount. Revisit if gap widens significantly.

Public functions:
  get_office_pnl()              → Office-level P&L for location table (1D, 5D)
  get_sector_pnl(location)      → Sector-level P&L for sector breakdown (1D, 5D)
  get_product_pnl(location)     → Product-level P&L for product drill-down (1D, 5D)
  get_analyst_pnl(location)     → Analyst-level P&L for analyst tab (1D, 5D, YTD)
  get_analyst_product_pnl(analyst) → Product-level P&L for analyst detail panel (YTD)
"""

import pandas as pd
from pathlib import Path
from datetime import date
from data.reference import (
    EXCLUDED_OFFICES,
    hawk_sector,
    HAWK_PRODUCT_PNL_MAP,
    HAWK_ANALYST_PNL_COL,
    HAWK_PRODUCT_PNL_COL,
)

# ── Paths ─────────────────────────────────────────────────────────────────────

_BASE        = Path(__file__).resolve().parent.parent / "data" / "hawk" / "raw"
ANALYST_DIR  = _BASE / "analyst"
PRODUCT_DIR  = _BASE / "product"


# ── Internal loaders ──────────────────────────────────────────────────────────

def _load_parquet(directory: Path) -> pd.DataFrame:
    """
    Load all parquet files in a directory into a single DataFrame.
    Files are read individually and concatenated to avoid pyarrow schema
    conflicts where all-NULL columns are stored as null type in some files
    but as double in others.
    """
    if not directory.exists():
        raise FileNotFoundError(f"Parquet directory not found: {directory}")

    files = sorted(directory.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files found in {directory}")

    frames = [pd.read_parquet(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    df["ReportDate"] = pd.to_datetime(df["ReportDate"]).dt.normalize()
    return df


def _last_n_dates(df: pd.DataFrame, n: int) -> list:
    """Return the n most recent distinct ReportDates in the dataset."""
    return sorted(df["ReportDate"].unique(), reverse=True)[:n]


def _ytd_start() -> pd.Timestamp:
    """Return January 1st of the current year."""
    return pd.Timestamp(date.today().year, 1, 1)


# ── Office P&L ────────────────────────────────────────────────────────────────

def get_office_pnl() -> pd.DataFrame:
    """
    Office-level P&L for the location table.

    Returns:
        Office    — office name + 'Futures First' for firm-wide total
        PnL_1D    — GrossPnL for most recent trading day
        PnL_5D    — cumulative GrossPnL over last 5 trading days
    """
    df = _load_parquet(ANALYST_DIR)
    df = df[~df["Office"].isin(EXCLUDED_OFFICES)]

    last_5 = _last_n_dates(df, 5)
    last_1  = last_5[:1]

    if not last_5:
        return pd.DataFrame(columns=["Office", "PnL_1D", "PnL_5D"])

    def _agg(date_filter: list) -> pd.DataFrame:
        subset = df[df["ReportDate"].isin(date_filter)]
        by_analyst = (
            subset
            .groupby(["ReportDate", "PrimaryITM", "Office"], as_index=False)
            .agg(PnL=(HAWK_ANALYST_PNL_COL, "sum"))
        )
        return (
            by_analyst
            .groupby("Office", as_index=False)
            .agg(PnL=("PnL", "sum"))
        )

    pnl_1d = _agg(last_1).rename(columns={"PnL": "PnL_1D"})
    pnl_5d = _agg(last_5).rename(columns={"PnL": "PnL_5D"})

    result = pnl_1d.merge(pnl_5d, on="Office", how="outer")

    ff_row = pd.DataFrame([{
        "Office": "Futures First",
        "PnL_1D": result["PnL_1D"].sum(),
        "PnL_5D": result["PnL_5D"].sum(),
    }])

    return pd.concat([ff_row, result], ignore_index=True)


# ── Sector P&L ────────────────────────────────────────────────────────────────

def get_sector_pnl(location: str = "Total") -> pd.DataFrame:
    """
    Sector-level P&L for the sector breakdown table.

    Args:
        location: office name or 'Total' for firm-wide

    Returns:
        Sector    — dashboard sector name
        PnL_1D    — GrossPnL for most recent trading day
        PnL_5D    — cumulative GrossPnL over last 5 trading days
    """
    df = _load_parquet(PRODUCT_DIR)
    df = df[~df["Office"].isin(EXCLUDED_OFFICES)]

    if location != "Total":
        df = df[df["Office"] == location]

    df["Sector"] = df.apply(
        lambda r: hawk_sector(
            r["AssetClass"] or "",
            r["SubAssetClass"] or "",
            r["Product"] or "",
        ),
        axis=1,
    )
    df = df[df["Sector"].notna()]

    last_5 = _last_n_dates(df, 5)
    last_1  = last_5[:1]

    if not last_5:
        return pd.DataFrame(columns=["Sector", "PnL_1D", "PnL_5D"])

    def _agg(date_filter: list) -> pd.DataFrame:
        subset = df[df["ReportDate"].isin(date_filter)]
        by_analyst = (
            subset
            .groupby(["ReportDate", "PrimaryITM", "Office", "Sector"], as_index=False)
            .agg(PnL=(HAWK_PRODUCT_PNL_COL, "sum"))
        )
        return (
            by_analyst
            .groupby("Sector", as_index=False)
            .agg(PnL=("PnL", "sum"))
        )

    pnl_1d = _agg(last_1).rename(columns={"PnL": "PnL_1D"})
    pnl_5d = _agg(last_5).rename(columns={"PnL": "PnL_5D"})

    return pnl_1d.merge(pnl_5d, on="Sector", how="outer")


# ── Product P&L ───────────────────────────────────────────────────────────────
def get_product_pnl(location: str = "Total", sector: str | None = None) -> pd.DataFrame:
    """
    Product-level P&L for the product drill-down table.

    Args:
        location: office name or 'Total' for firm-wide
        sector:   dashboard sector name to filter by, or None for all

    Returns:
        Product     — ProductRisk product name (joins to db_summary product rows)
        ProductDesc — full HAWK product description (where available)
        Sector      — dashboard sector
        PnL_1D      — GrossPnL for most recent trading day
        PnL_5D      — cumulative GrossPnL over last 5 trading days

    Translates HAWK exchange codes → ProductRisk product names via
    HAWK_PRODUCT_PNL_MAP so the frontend join works. Multiple HAWK codes
    mapping to the same product name (e.g. RB1 + ICENYH → 'RBOB Gasoline')
    are summed automatically by the groupby.
    """
    from data.reference import HAWK_PRODUCT_PNL_MAP

    df = _load_parquet(PRODUCT_DIR)
    df = df[~df["Office"].isin(EXCLUDED_OFFICES)]

    if location != "Total":
        df = df[df["Office"] == location]

    df["Sector"] = df.apply(
        lambda r: hawk_sector(
            r["AssetClass"] or "",
            r["SubAssetClass"] or "",
            r["Product"] or "",
        ),
        axis=1,
    )
    df = df[df["Sector"].notna()]

    if sector:
        df = df[df["Sector"] == sector]

    # Translate HAWK ticker → ProductRisk product name. Tickers absent from
    # the map are dropped (no ProductRisk row to join to anyway).
    df = df[df["Product"].isin(HAWK_PRODUCT_PNL_MAP)]
    if df.empty:
        return pd.DataFrame(columns=["Product", "ProductDesc", "Sector", "PnL_1D", "PnL_5D"])

    df = df.copy()
    # Capture HAWK ProductDesc before overwriting Product, so we can surface
    # the descriptive label alongside the canonical name.
    desc_map = (
        df[df["ProductDesc"].notna()]
        .groupby("Product")["ProductDesc"]
        .first()
        .to_dict()
    )
    df["ProductDesc_HAWK"] = df["Product"].map(desc_map)
    df["Product"]          = df["Product"].map(HAWK_PRODUCT_PNL_MAP)

    last_5 = _last_n_dates(df, 5)
    last_1 = last_5[:1]

    if not last_5:
        return pd.DataFrame(columns=["Product", "ProductDesc", "Sector", "PnL_1D", "PnL_5D"])

    def _agg(date_filter: list) -> pd.DataFrame:
        subset = df[df["ReportDate"].isin(date_filter)]
        by_analyst = (
            subset
            .groupby(["ReportDate", "PrimaryITM", "Office", "Product", "Sector"], as_index=False)
            .agg(PnL=(HAWK_PRODUCT_PNL_COL, "sum"))
        )
        return (
            by_analyst
            .groupby(["Product", "Sector"], as_index=False)
            .agg(PnL=("PnL", "sum"))
        )

    pnl_1d = _agg(last_1).rename(columns={"PnL": "PnL_1D"})
    pnl_5d = _agg(last_5).rename(columns={"PnL": "PnL_5D"})

    result = pnl_1d.merge(pnl_5d, on=["Product", "Sector"], how="outer")

    # One ProductRisk name may now correspond to several HAWK tickers; pick
    # the first non-null HAWK ProductDesc as the descriptor.
    rename_desc = (
        df[df["ProductDesc_HAWK"].notna()]
        .groupby("Product")["ProductDesc_HAWK"]
        .first()
        .to_dict()
    )
    result["ProductDesc"] = result["Product"].map(rename_desc)

    return result[["Product", "ProductDesc", "Sector", "PnL_1D", "PnL_5D"]]

# ── Analyst P&L ───────────────────────────────────────────────────────────────
# ── Analyst P&L ───────────────────────────────────────────────────────────────

def get_analyst_pnl(location: str = "Total") -> pd.DataFrame:
    """
    Analyst-level P&L for the analyst tab.

    Args:
        location: office name or 'Total' for firm-wide

    Returns:
        Analyst   — ITM (sub-account code, joins to AnalystRisk.Analyst)
        Office    — office name
        PnL_1D    — GrossPnL for most recent trading day
        PnL_5D    — cumulative GrossPnL over last 5 trading days
        PnL_YTD   — cumulative NetPnL from Jan 1st of current year to today

    Note: HAWK breaks P&L down per ITM (sub-account), not per PrimaryITM.
    Sub-accounts like FIL3, FIL9 etc. each carry their own P&L on the
    HAWK frontend, so we filter and group by ITM here. PrimaryITM is only
    used for office/sector/product aggregations where we deliberately want
    each trader counted once.

    1D/5D use GrossPnL (matches what traders watch intraday).
    YTD uses NetPnL — gross less commissions/fees/rebates — which is the
    figure that matters for performance review and compensation.
    """
    df = _load_parquet(ANALYST_DIR)
    df = df[~df["Office"].isin(EXCLUDED_OFFICES)]

    if location != "Total":
        df = df[df["Office"] == location]

    last_5  = _last_n_dates(df, 5)
    last_1  = last_5[:1]
    ytd_start = _ytd_start()

    if not last_5:
        return pd.DataFrame(columns=["Analyst", "Office", "PnL_1D", "PnL_5D", "PnL_YTD"])

    def _agg_analyst(date_filter=None, ytd=False, pnl_col=HAWK_ANALYST_PNL_COL) -> pd.DataFrame:
        if ytd:
            subset = df[df["ReportDate"] >= ytd_start]
        else:
            subset = df[df["ReportDate"].isin(date_filter)]

        # Group by ITM — each sub-account is a distinct analyst row in
        # the dashboard and joins to AnalystRisk.Analyst.
        return (
            subset
            .groupby(["ITM", "Office"], as_index=False)
            .agg(PnL=(pnl_col, "sum"))
        )

    pnl_1d  = _agg_analyst(date_filter=last_1).rename(columns={"PnL": "PnL_1D"})
    pnl_5d  = _agg_analyst(date_filter=last_5).rename(columns={"PnL": "PnL_5D"})
    pnl_ytd = _agg_analyst(ytd=True, pnl_col="NetPnL").rename(columns={"PnL": "PnL_YTD"})

    result = (
        pnl_1d
        .merge(pnl_5d,  on=["ITM", "Office"], how="outer")
        .merge(pnl_ytd, on=["ITM", "Office"], how="outer")
    )

    result = result.rename(columns={"ITM": "Analyst"})
    return result[["Analyst", "Office", "PnL_1D", "PnL_5D", "PnL_YTD"]]

# ── Analyst product P&L ───────────────────────────────────────────────────────
def get_analyst_product_pnl(analyst: str) -> pd.DataFrame:
    """
    Product-level YTD NetPnL for a single analyst's detail panel.

    Args:
        analyst: ITM code (e.g. 'FIL3', 'MRN')

    Returns:
        Product   — ProductRisk product name (joins to AnalystTab product rows)
        PnL_YTD   — cumulative NetPnL from Jan 1st of current year to today

    Note: filters by ITM, not PrimaryITM. Each sub-account (e.g. FIL3 vs FIL9)
    has its own distinct P&L in HAWK and should be queried independently.

    Uses NetPnL (gross less commissions/fees/rebates) for consistency with
    the YTD column on the analyst table — that's the figure that matters
    for performance review and compensation.

    Translates HAWK exchange codes → ProductRisk product names via
    HAWK_PRODUCT_PNL_MAP so the frontend join with the product breakdown
    table works. Multiple tickers mapping to the same name (e.g. BCO + BCOC
    + BCOP → 'ICE Brent Crude') are summed.
    """
    from data.reference import HAWK_PRODUCT_PNL_MAP

    df = _load_parquet(PRODUCT_DIR)

    # Filter to analyst by ITM — each sub-account has independent P&L.
    df = df[df["ITM"] == analyst]

    ytd_start = _ytd_start()
    df = df[df["ReportDate"] >= ytd_start]

    if df.empty:
        return pd.DataFrame(columns=["Product", "PnL_YTD"])

    # Translate HAWK ticker → ProductRisk product name. Tickers absent from
    # the map are dropped (no ProductRisk row to join to).
    df = df[df["Product"].isin(HAWK_PRODUCT_PNL_MAP)]
    if df.empty:
        return pd.DataFrame(columns=["Product", "PnL_YTD"])

    df = df.copy()
    df["Product"] = df["Product"].map(HAWK_PRODUCT_PNL_MAP)

    result = (
        df
        .groupby("Product", as_index=False)
        .agg(PnL_YTD=("NetPnL", "sum"))
        .sort_values("PnL_YTD", ascending=False, key=abs)
        .reset_index(drop=True)
    )

    return result[["Product", "PnL_YTD"]]

# ── Roll Risk product P&L ─────────────────────────────────────────────────────

def get_roll_product_pnl(location: str = "Total") -> pd.DataFrame:
    """
    Product-level P&L for the Roll Risk tab (Rates + Equities sectors).

    Maps HAWK exchange codes → ProductRisk product names via
    HAWK_ROLL_PRODUCT_MAP, then aggregates 1D and 5D P&L.
    Multiple HAWK codes mapping to the same product name (e.g. TB + UBE →
    'US Ultra Bond') are summed automatically by the groupby.

    Returns:
        Product  — ProductRisk product name (joins to db_rollview product rows)
        PnL_1D   — GrossPnL for most recent trading day
        PnL_5D   — cumulative GrossPnL over last 5 trading days
    """
    from data.reference import HAWK_ROLL_PRODUCT_MAP

    df = _load_parquet(PRODUCT_DIR)
    df = df[~df["Office"].isin(EXCLUDED_OFFICES)]

    if location != "Total":
        df = df[df["Office"] == location]

    df = df[df["Product"].isin(HAWK_ROLL_PRODUCT_MAP)]
    if df.empty:
        return pd.DataFrame(columns=["Product", "PnL_1D", "PnL_5D"])

    df = df.copy()
    df["Product"] = df["Product"].map(HAWK_ROLL_PRODUCT_MAP)

    last_5 = _last_n_dates(df, 5)
    last_1 = last_5[:1]

    if not last_5:
        return pd.DataFrame(columns=["Product", "PnL_1D", "PnL_5D"])

    def _agg(date_filter: list) -> pd.DataFrame:
        subset = df[df["ReportDate"].isin(date_filter)]
        by_itm = (
            subset
            .groupby(["ReportDate", "PrimaryITM", "Office", "Product"], as_index=False)
            .agg(PnL=(HAWK_PRODUCT_PNL_COL, "sum"))
        )
        return (
            by_itm
            .groupby("Product", as_index=False)
            .agg(PnL=("PnL", "sum"))
        )

    pnl_1d = _agg(last_1).rename(columns={"PnL": "PnL_1D"})
    pnl_5d = _agg(last_5).rename(columns={"PnL": "PnL_5D"})

    return pnl_1d.merge(pnl_5d, on="Product", how="outer")
