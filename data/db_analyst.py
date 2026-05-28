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
from data.dates import today, get_latest_eod_dates
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
    today_str = today()

    eod_dates_95  = get_latest_eod_dates(95.0,  100, n=2)
    eod_dates_100 = get_latest_eod_dates(100.0,  10, n=2)

    last_night_95  = eod_dates_95[0]  if len(eod_dates_95)  > 0 else today_str
    t1_95          = eod_dates_95[1]  if len(eod_dates_95)  > 1 else last_night_95
    last_night_100 = eod_dates_100[0] if len(eod_dates_100) > 0 else today_str
    t1_100         = eod_dates_100[1] if len(eod_dates_100) > 1 else last_night_100

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
            return pd.read_sql(query, conn, params=[today_str, confidence, lookback] + params)

    sod_95  = fetch_eod(95.0,  100, last_night_95)
    t1_95_  = fetch_eod(95.0,  100, t1_95)
    sod_100 = fetch_eod(100.0,  10, last_night_100)
    t1_100_ = fetch_eod(100.0,  10, t1_100)
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
    Latest iVaR breakdown by product for a single analyst.
    Uses ProductRisk WHERE Analyst != Office (analyst-level rows only —
    excludes netting group rows where Analyst = Office).

    Returns columns: Asset_Class, Product, iVaR, Margin,
                     Delta_iVaR (vs last EOD), Delta_iVaR_t1 (vs t-1 EOD)
    """
    today_str = today()

    eod_dates = get_latest_eod_dates(confidence, lookback, n=2)
    last_night = eod_dates[0] if len(eod_dates) > 0 else today_str
    t1         = eod_dates[1] if len(eod_dates) > 1 else last_night

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
                               params=[today_str, analyst, office, confidence, lookback])

    sod  = fetch_eod(last_night)
    t1_  = fetch_eod(t1)
    cur  = fetch_intraday()

    if cur.empty: cur = sod.copy()

    keys = ["Product", "Asset_Class"]
    sod  = sod.rename(columns={"iVaR": "_ivar_sod", "Margin": "_margin_sod"})
    t1_  = t1_.rename(columns={"iVaR": "_ivar_t1",  "Margin": "_margin_t1"})
    cur  = cur.rename(columns={"iVaR": "_ivar_cur",  "Margin": "_margin_cur"})

    df = (
        cur[keys + ["_ivar_cur", "_margin_cur"]]
        .merge(sod[keys + ["_ivar_sod", "_margin_sod"]], on=keys, how="left")
        .merge(t1_[keys + ["_ivar_t1",  "_margin_t1"]],  on=keys, how="left")
    )

    df["iVaR"]          = df["_ivar_cur"]
    df["Delta_iVaR"]    = df["_ivar_cur"] - df["_ivar_sod"]
    df["Delta_iVaR_t1"] = df["_ivar_cur"] - df["_ivar_t1"]
    df["Margin"]        = df["_margin_cur"]

    return (
        df[keys + ["iVaR", "Delta_iVaR", "Delta_iVaR_t1", "Margin"]]
        .sort_values("iVaR", ascending=False, key=abs)
        .reset_index(drop=True)
    )


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
