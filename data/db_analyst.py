"""
data/db_analyst.py — All queries for the Analyst tab.

Tables used:
  dbo.AnalystRisk   — VaR + Margin by analyst within office
  dbo.ProductRisk   — iVaR + Margin by analyst x product
  dbo.Lookup_Office — office names, IsExcluded flag

Follows the same patterns as db_var.py:
  - get_connection() used as a context manager inside each function
  - Returns pd.DataFrame (not raw dicts)
  - EXCLUDED_OFFICES + FUTURES_FIRST_OFFICE from reference
  - EOD dates resolved via OfficeRisk same as db_summary

Note: Cumulus only computes intraday VaR for the top analysts by VaR size.
Analysts not in the intraday run fall back to SOD values. IsIntraday=False
flags these rows so the frontend can display them differently.
"""

import pandas as pd
from data.dates import today, get_latest_eod_dates, date_context
from data.db_connection import get_connection
from data.reference import EXCLUDED_OFFICES, FUTURES_FIRST_OFFICE


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _excl_ph():
    return ",".join(["?"] * len(EXCLUDED_OFFICES))




# ─────────────────────────────────────────────────────────────────────────────
# Analyst summary table
# ─────────────────────────────────────────────────────────────────────────────

def get_analyst_table_for_tab(location: str = "Total") -> pd.DataFrame:
    """
    Full analyst table for the Analyst tab — includes t-1 deltas.
    Returns columns:
      Office, Analyst,
      VaR_10D,  Delta_10D,  Delta_10D_t1,
      VaR_100D, Delta_100D, Delta_100D_t1,
      Margin,   Delta_Margin, Delta_Margin_t1,
      IsIntraday  — False if analyst not in intraday run (showing SOD fallback)
    """

    dc = date_context()

    if location == "Total":
        where  = f"Office NOT IN ({_excl_ph()}) AND Office != ?"
        params = list(EXCLUDED_OFFICES) + [FUTURES_FIRST_OFFICE]
    else:
        where  = "Office = ?"
        params = [location]

    def fetch_eod(confidence, lookback, date):
        query = f"""
            SELECT Office, Analyst, VaR, Margin
            FROM dbo.AnalystRisk
            WHERE IsEOD      = 1
              AND Date       = ?
              AND Confidence = ?
              AND Lookback   = ?
              AND {where}
        """
        with get_connection() as conn:
            return pd.read_sql(query, conn, params=[date, confidence, lookback] + params)

    def fetch_intraday(confidence, lookback):
        query = f"""
            SELECT Office, Analyst, VaR, Margin
            FROM dbo.AnalystRisk a1
            WHERE IsEOD      = 0
              AND Date       = ?
              AND Confidence = ?
              AND Lookback   = ?
              AND Time = (
                  SELECT MAX(a2.Time)
                  FROM dbo.AnalystRisk a2
                  WHERE a2.Office     = a1.Office
                    AND a2.Analyst    = a1.Analyst
                    AND a2.Date       = a1.Date
                    AND a2.Confidence = a1.Confidence
                    AND a2.Lookback   = a1.Lookback
                    AND a2.IsEOD      = 0
              )
              AND {where}
        """
        with get_connection() as conn:
            return pd.read_sql(query, conn, params=[dc.today_str, confidence, lookback] + params)

    sod_95  = fetch_eod(95.0,  100, dc.last_night_95)
    t1_95_  = fetch_eod(95.0,  100, dc.t1_95)
    sod_100 = fetch_eod(100.0,  10, dc.last_night_100)
    t1_100_ = fetch_eod(100.0,  10, dc.t1_100)
    cur_95  = fetch_intraday(95.0,  100)
    cur_100 = fetch_intraday(100.0,  10)

    # Capture which analysts are in the intraday run BEFORE any fallback
    intraday_analysts = set(cur_95["Analyst"].tolist()) if not cur_95.empty else set()

    if cur_95.empty:  cur_95  = sod_95.copy()
    if cur_100.empty: cur_100 = sod_100.copy()

    keys = ["Office", "Analyst"]
    sod_95  = sod_95.rename(columns={"VaR": "_var100_sod", "Margin": "_margin_sod"})
    t1_95_  = t1_95_.rename(columns={"VaR": "_var100_t1",  "Margin": "_margin_t1"})
    cur_95  = cur_95.rename(columns={"VaR": "_var100_cur", "Margin": "_margin_cur"})
    sod_100 = sod_100.rename(columns={"VaR": "_var10_sod", "Margin": "_m100_sod"})
    t1_100_ = t1_100_.rename(columns={"VaR": "_var10_t1",  "Margin": "_m100_t1"})
    cur_100 = cur_100.rename(columns={"VaR": "_var10_cur", "Margin": "_m100_cur"})

    df = (
        sod_95[keys + ["_var100_sod", "_margin_sod"]]
        .merge(t1_95_ [keys + ["_var100_t1",  "_margin_t1"]],  on=keys, how="outer")
        .merge(cur_95 [keys + ["_var100_cur", "_margin_cur"]], on=keys, how="outer")
        .merge(sod_100[keys + ["_var10_sod"]],                  on=keys, how="outer")
        .merge(t1_100_[keys + ["_var10_t1"]],                   on=keys, how="outer")
        .merge(cur_100[keys + ["_var10_cur"]],                   on=keys, how="outer")
    )

    # Per-analyst SOD fallback — analysts not in intraday run show SOD as current
    # Deltas will be zero for these analysts (correct — we don't know intraday change)
    df["_var100_cur"] = df["_var100_cur"].fillna(df["_var100_sod"])
    df["_var10_cur"]  = df["_var10_cur"].fillna(df["_var10_sod"])
    df["_margin_cur"] = df["_margin_cur"].fillna(df["_margin_sod"])

    df["VaR_100D"]        = df["_var100_cur"]
    df["Delta_100D"]      = df["_var100_cur"] - df["_var100_sod"]
    df["Delta_100D_t1"]   = df["_var100_cur"] - df["_var100_t1"]
    df["VaR_10D"]         = df["_var10_cur"]
    df["Delta_10D"]       = df["_var10_cur"]  - df["_var10_sod"]
    df["Delta_10D_t1"]    = df["_var10_cur"]  - df["_var10_t1"]
    df["Margin"]          = df["_margin_cur"]
    df["Delta_Margin"]    = df["_margin_cur"] - df["_margin_sod"]
    df["Delta_Margin_t1"] = df["_margin_cur"] - df["_margin_t1"]

    # Flag analysts not in intraday run
    df["IsIntraday"] = df["Analyst"].isin(intraday_analysts)

    return (
        df[keys + [
            "VaR_10D",  "Delta_10D",  "Delta_10D_t1",
            "VaR_100D", "Delta_100D", "Delta_100D_t1",
            "Margin",   "Delta_Margin", "Delta_Margin_t1",
            "IsIntraday",
        ]]
        .sort_values("VaR_100D", ascending=False)
        .reset_index(drop=True)
    )


# ─────────────────────────────────────────────────────────────────────────────
# Analyst rolling chart
# ─────────────────────────────────────────────────────────────────────────────

def get_analyst_chart(analyst: str, office: str, confidence: float,
                      lookback: int, days: int = 30) -> pd.DataFrame:
    """
    EOD VaR + Margin history for a single analyst over the last N trading days.
    Returns columns: Date, VaR, Margin
    """
    query = """
        SELECT TOP (?) CONVERT(VARCHAR(10), Date, 23) AS Date, VaR, Margin
        FROM dbo.AnalystRisk
        WHERE IsEOD      = 1
          AND Analyst    = ?
          AND Office     = ?
          AND Confidence = ?
          AND Lookback   = ?
        ORDER BY Date DESC
    """
    with get_connection() as conn:
        df = pd.read_sql(query, conn, params=[days, analyst, office, confidence, lookback])
    return df.iloc[::-1].reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Analyst product breakdown
# ─────────────────────────────────────────────────────────────────────────────
def get_analyst_products(analyst: str, office: str, confidence: float,
                         lookback: int) -> pd.DataFrame:
    """
    Latest iVaR breakdown by product for a single analyst, with subgroup
    header rows interleaved between products.

    Uses ProductRisk WHERE Analyst != Office (analyst-level rows only —
    excludes office-level netting group rows where Analyst = Office).

    At the analyst level, Cumulus writes two flavours of rows:

      * Product rows — `Product` is a specific instrument
        (e.g. 'ICE Brent Crude', 'Cocoa (Liffe)').
      * Netting rows — `Product` is an asset class name
        (e.g. 'Cocoa', 'NG', 'Oils - Refined'). These hold the netted
        iVaR / Margin for that asset class as a whole at the analyst level.

    We use the netting rows as the *headline* values on each subgroup
    header (so the COCOA header shows the netted Cocoa figure, not the
    sum of Cocoa (Liffe) + Cocoa (ICE US) which would double-count and
    miss netting offsets). Products listed underneath are the individual
    instruments that contribute to that netted figure.

    Returns columns:
      _rowType      — "subgroup" for header rows, "product" for product rows
      _subgroup     — subgroup name (set on both header and product rows
                      so the frontend can group visually)
      _sector       — sector name
      Asset_Class, Product, iVaR, Margin,
      Delta_iVaR (vs last EOD), Delta_iVaR_t1 (vs t-1 EOD)

    Subgroups with no netting row at the analyst level show "—" on the
    header values (frontend renders null as "—").

    Truly orphan products (not in PRODUCT_SUBGROUP, not a netting row)
    are grouped under a synthetic "Other" subgroup at the end of their
    sector, with no header values.
    """
    from data.reference import (
        PRODUCT_SUBGROUP, SUBGROUP_ORDER, SUBGROUP_NETTED_ASSET_CLASSES,
        SECTOR_MAP, sort_sectors,
    )

    # Build reverse lookup once: netting-row Product name → subgroup name.
    # e.g. {"Cocoa": "Cocoa", "NG": "Natural Gas", "Oils - Refined": "Oil Refined", ...}
    # Subgroups with empty asset-class lists (e.g. "Power & Carbon": []) are
    # naturally skipped.
    netting_product_to_subgroup = {}
    for subgroup, asset_classes in SUBGROUP_NETTED_ASSET_CLASSES.items():
        for ac in asset_classes:
            netting_product_to_subgroup[ac] = subgroup

    dc = date_context()

    def fetch_eod(date):
        query = """
            SELECT Product, Asset_Class, SUM(iVaR) AS iVaR, SUM(Margin) AS Margin
            FROM dbo.ProductRisk
            WHERE IsEOD      = 1
              AND Date       = ?
              AND Analyst    = ?
              AND Office     = ?
              AND Confidence = ?
              AND Lookback   = ?
              AND Analyst   != Office
            GROUP BY Product, Asset_Class
        """
        with get_connection() as conn:
            return pd.read_sql(query, conn,
                               params=[date, analyst, office, confidence, lookback])

    def fetch_intraday():
        query = """
            SELECT Product, Asset_Class, SUM(iVaR) AS iVaR, SUM(Margin) AS Margin
            FROM dbo.ProductRisk p1
            WHERE IsEOD      = 0
              AND Date       = ?
              AND Analyst    = ?
              AND Office     = ?
              AND Confidence = ?
              AND Lookback   = ?
              AND Analyst   != Office
              AND Time = (
                  SELECT MAX(p2.Time)
                  FROM dbo.ProductRisk p2
                  WHERE p2.Analyst    = p1.Analyst
                    AND p2.Office     = p1.Office
                    AND p2.Date       = p1.Date
                    AND p2.Confidence = p1.Confidence
                    AND p2.Lookback   = p1.Lookback
                    AND p2.IsEOD      = 0
              )
            GROUP BY Product, Asset_Class
        """
        with get_connection() as conn:
            return pd.read_sql(query, conn,
                               params=[dc.today_str, analyst, office, confidence, lookback])

    sod = fetch_eod(dc.last_night_95)
    t1_ = fetch_eod(dc.t1_95)
    cur = fetch_intraday()

    if cur.empty: cur = sod.copy()

    keys = ["Product", "Asset_Class"]
    sod = sod.rename(columns={"iVaR": "_ivar_sod", "Margin": "_margin_sod"})
    t1_ = t1_.rename(columns={"iVaR": "_ivar_t1",  "Margin": "_margin_t1"})
    cur = cur.rename(columns={"iVaR": "_ivar_cur", "Margin": "_margin_cur"})

    df = (
        cur[keys + ["_ivar_cur", "_margin_cur"]]
        .merge(sod[keys + ["_ivar_sod", "_margin_sod"]], on=keys, how="left")
        .merge(t1_[keys + ["_ivar_t1",  "_margin_t1"]],  on=keys, how="left")
    )

    df["iVaR"]          = df["_ivar_cur"]
    df["Delta_iVaR"]    = df["_ivar_cur"] - df["_ivar_sod"]
    df["Delta_iVaR_t1"] = df["_ivar_cur"] - df["_ivar_t1"]
    df["Margin"]        = df["_margin_cur"]

    all_rows = df[keys + ["iVaR", "Delta_iVaR", "Delta_iVaR_t1", "Margin"]].copy()
    if all_rows.empty:
        return pd.DataFrame(columns=[
            "_rowType", "_subgroup", "_sector",
            "Product", "Asset_Class",
            "iVaR", "Delta_iVaR", "Delta_iVaR_t1", "Margin",
        ])

    # ── Split rows: netting rows vs true product rows ─────────────────────
    is_netting = all_rows["Product"].isin(netting_product_to_subgroup)

    netting = all_rows[is_netting].copy()
    products = all_rows[~is_netting].copy()

    # Map netting rows by subgroup name. If duplicates somehow appear,
    # keep the first.
    netting["_subgroup"] = netting["Product"].map(netting_product_to_subgroup)
    netting_by_subgroup = {row["_subgroup"]: row for _, row in netting.iterrows()}

    # Assign each product row to a subgroup and sector
    products["_subgroup"] = products["Product"].map(PRODUCT_SUBGROUP).fillna("Other")
    products["_sector"]   = products["Asset_Class"].map(SECTOR_MAP).fillna("Other")

    # ── Build ordered output ──────────────────────────────────────────────
    rows = []

    # All sectors present across both products AND netting headers.
    # A subgroup might have a netting row but no product rows for this
    # analyst, or vice versa — show it either way.
    sectors_with_products = set(products["_sector"].unique())
    sectors_with_netting  = {
        SECTOR_MAP.get(ac, "Other")
        for ac in netting["Product"].tolist()
    }
    sectors_present = sort_sectors(list(sectors_with_products | sectors_with_netting))

    for sector in sectors_present:
        sector_products = products[products["_sector"] == sector]

        # Subgroups present in this sector — from product rows AND
        # from netting rows whose mapped asset class belongs to this sector
        subgroups_from_products = set(sector_products["_subgroup"].unique())
        subgroups_from_netting = {
            sg for sg, row in netting_by_subgroup.items()
            if SECTOR_MAP.get(row["Product"], "Other") == sector
        }
        present = subgroups_from_products | subgroups_from_netting

        # Order: known subgroups in SUBGROUP_ORDER first, then leftovers
        # alphabetically, then "Other" last
        sector_order = SUBGROUP_ORDER.get(sector, [])
        ordered = [s for s in sector_order if s in present]
        leftover = sorted(s for s in present if s not in sector_order and s != "Other")
        if "Other" in present:
            leftover.append("Other")
        ordered.extend(leftover)

        for subgroup in ordered:
            subgroup_products = sector_products[sector_products["_subgroup"] == subgroup]
            netting_row = netting_by_subgroup.get(subgroup)

            # Skip subgroups with neither header nor products (shouldn't happen
            # given the union above, but defensive)
            if subgroup_products.empty and netting_row is None:
                continue

            # Header row — netted values when available, else None
            if netting_row is not None:
                rows.append({
                    "_rowType":      "subgroup",
                    "_subgroup":     subgroup,
                    "_sector":       sector,
                    "Product":       subgroup,
                    "Asset_Class":   None,
                    "iVaR":          netting_row["iVaR"],
                    "Delta_iVaR":    netting_row["Delta_iVaR"],
                    "Delta_iVaR_t1": netting_row["Delta_iVaR_t1"],
                    "Margin":        netting_row["Margin"],
                })
            else:
                rows.append({
                    "_rowType":      "subgroup",
                    "_subgroup":     subgroup,
                    "_sector":       sector,
                    "Product":       subgroup,
                    "Asset_Class":   None,
                    "iVaR":          None,
                    "Delta_iVaR":    None,
                    "Delta_iVaR_t1": None,
                    "Margin":        None,
                })

            # Product rows, sorted by absolute iVaR
            for _, p in subgroup_products.sort_values("iVaR", ascending=False, key=abs).iterrows():
                rows.append({
                    "_rowType":      "product",
                    "_subgroup":     subgroup,
                    "_sector":       sector,
                    "Product":       p["Product"],
                    "Asset_Class":   p["Asset_Class"],
                    "iVaR":          p["iVaR"],
                    "Delta_iVaR":    p["Delta_iVaR"],
                    "Delta_iVaR_t1": p["Delta_iVaR_t1"],
                    "Margin":        p["Margin"],
                })

    return pd.DataFrame(rows)

def get_analyst_product_chart(analyst: str, office: str, product: str,
                               confidence: float, lookback: int,
                               days: int = 30) -> pd.DataFrame:
    """
    EOD iVaR history for a single analyst x product over the last N trading days.
    Used when a product row is clicked in the analyst detail panel.
    Returns columns: Date, iVaR
    """
    query = """
        SELECT TOP (?) CONVERT(VARCHAR(10), Date, 23) AS Date, SUM(iVaR) AS iVaR
        FROM dbo.ProductRisk
        WHERE IsEOD      = 1
          AND Analyst    = ?
          AND Office     = ?
          AND Product    = ?
          AND Confidence = ?
          AND Lookback   = ?
          AND Analyst   != Office
        GROUP BY Date
        ORDER BY Date DESC
    """
    with get_connection() as conn:
        df = pd.read_sql(query, conn,
                         params=[days, analyst, office, product, confidence, lookback])
    return df.iloc[::-1].reset_index(drop=True)
