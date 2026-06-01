"""
data/db_summary.py — All VaR queries against FF_Risk database.

Tables used:
  dbo.OfficeRisk    — VaR + Margin by office (Futures First = firm-wide)
  dbo.AnalystRisk   — VaR + Margin by analyst within office
  dbo.ProductRisk   — iVaR + Margin by analyst x product
  dbo.Lookup_Office — lookup: office names, IsExcluded flag

Key facts:
  - IsEOD = 1 and Time = '23:00' identifies EOD snapshots
  - Office = 'Futures First' is the firm-wide netting group
  - London P&C and Mumbai are excluded (IsExcluded = 1)
  - Primary config:   Confidence=95.00, Lookback=100
  - Secondary config: Confidence=100.00, Lookback=10

ProductRisk contains one row per analyst x product. All asset class and
office-level product aggregations are derived at query time via GROUP BY.
For office-level asset class rows, Analyst = Office (netting group rows).
For Futures First, Analyst = 'Futures First'.

Output columns for location/analyst tables (frontend expects these names):
  Office, Analyst,
  VaR_10D,   Delta_10D,   Delta_10D_t1,
  VaR_100D,  Delta_100D,  Delta_100D_t1,
  Margin,    Delta_Margin, Delta_Margin_t1
"""

import pandas as pd
from data.dates import today, get_latest_eod_dates, date_context
from data.query_helpers import build_var_table
from data.db_connection import get_connection
from data.reference import (
    EXCLUDED_OFFICES,
    FUTURES_FIRST_OFFICE,
    SECTOR_MAP,
    SECTOR_ORDER,
    SECTOR_ASSET_CLASSES,
    SUBGROUP_NETTED_ASSET_CLASSES,
    SUBGROUP_ORDER,
    PRODUCT_SUBGROUP,
)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _excl_ph():
    return ",".join(["?"] * len(EXCLUDED_OFFICES))


def _get_subgroup_netted_var(office_val: str, subgroups: list, sector: str) -> pd.DataFrame:
    """
    Fetches Cumulus-provided netted VaR for each subgroup header row.

    Total view (Futures First):
        Queries Office = 'Futures First', Analyst = 'Futures First', Product = Asset_Class.
        These rows are written by ff_risk_db.py from processed_summary compound rows
        e.g. '00000 WTI', '00000 Cocoa'.

    Individual office view:
        Queries Office = <office>, Analyst = Office, Product = Asset_Class.
        These are Cumulus office-level netting group rows.

    Returns a DataFrame with columns: Subgroup, _rowType, VaR_100D, Delta_100D,
    Delta_100D_t1, VaR_10D, Delta_10D, Delta_10D_t1, Margin, Delta_Margin,
    Delta_Margin_t1
    """

    dc = date_context()

    is_total = (office_val == FUTURES_FIRST_OFFICE)

    rows = []
    for sg in subgroups:
        acs = SUBGROUP_NETTED_ASSET_CLASSES.get(sg, [])
        if not acs:
            rows.append({
                "Subgroup": sg, "_rowType": "subgroup",
                "VaR_100D": None, "Delta_100D": None, "Delta_100D_t1": None,
                "VaR_10D":  None, "Delta_10D":  None, "Delta_10D_t1":  None,
                "Margin":   None, "Delta_Margin": None, "Delta_Margin_t1": None,
            })
            continue

        ac_ph = ",".join(["?"] * len(acs))

        def fetch_netted(confidence, lookback, date, eod, _acs=acs, _is_total=is_total):
            if _is_total:
                if eod:
                    q = f"""
                        SELECT SUM(iVaR) AS iVaR, SUM(Margin) AS Margin
                        FROM dbo.ProductRisk
                        WHERE IsEOD = 1 AND Date = ? AND Confidence = ?
                          AND Lookback = ?
                          AND Office = 'Futures First'
                          AND Analyst = 'Futures First'
                          AND Product IN ({ac_ph})
                    """
                    p = [date, confidence, lookback] + _acs
                else:
                    q = f"""
                        SELECT SUM(iVaR) AS iVaR, SUM(Margin) AS Margin
                        FROM dbo.ProductRisk
                        WHERE IsEOD = 0 AND Date = ? AND Confidence = ?
                          AND Lookback = ?
                          AND Office = 'Futures First'
                          AND Analyst = 'Futures First'
                          AND Product IN ({ac_ph})
                          AND Time = (
                              SELECT MAX(p2.Time) FROM dbo.ProductRisk p2
                              WHERE p2.Office = 'Futures First'
                                AND p2.Analyst = 'Futures First'
                                AND p2.Date = ? AND p2.IsEOD = 0
                                AND p2.Confidence = ? AND p2.Lookback = ?
                          )
                    """
                    p = [date, confidence, lookback] + _acs + [date, confidence, lookback]
            else:
                if eod:
                    q = f"""
                        SELECT SUM(iVaR) AS iVaR, SUM(Margin) AS Margin
                        FROM dbo.ProductRisk
                        WHERE IsEOD = 1 AND Date = ? AND Confidence = ?
                          AND Lookback = ? AND Office = ? AND Analyst = Office
                          AND Product IN ({ac_ph})
                    """
                    p = [date, confidence, lookback, office_val] + _acs
                else:
                    q = f"""
                        SELECT SUM(iVaR) AS iVaR, SUM(Margin) AS Margin
                        FROM dbo.ProductRisk
                        WHERE IsEOD = 0 AND Date = ? AND Confidence = ?
                          AND Lookback = ? AND Office = ? AND Analyst = Office
                          AND Product IN ({ac_ph})
                          AND Time = (
                              SELECT MAX(p2.Time) FROM dbo.ProductRisk p2
                              WHERE p2.Office = ? AND p2.Date = ? AND p2.IsEOD = 0
                                AND p2.Confidence = ? AND p2.Lookback = ?
                          )
                    """
                    p = [date, confidence, lookback, office_val] + _acs + [office_val, date, confidence, lookback]
            with get_connection() as conn:
                return pd.read_sql(q, conn, params=p)

        s95  = fetch_netted(95.0,  100, dc.last_night_95,  eod=True)
        t95  = fetch_netted(95.0,  100, dc.t1_95,          eod=True)
        c95  = fetch_netted(95.0,  100, dc.today_str,           eod=False)
        if c95.empty or c95['iVaR'].iloc[0] is None:
            c95 = s95.copy()

        s100 = fetch_netted(100.0,  10, dc.last_night_100,  eod=True)
        t100 = fetch_netted(100.0,  10, dc.t1_100,          eod=True)
        c100 = s100.copy()

        def val(df, col):
            v = df[col].iloc[0] if not df.empty else None
            return float(v) if v is not None else None

        def delta(a, b):
            return (a - b) if a is not None and b is not None else None

        var100_cur = val(c95,  "iVaR")
        var100_sod = val(s95,  "iVaR")
        var100_t1  = val(t95,  "iVaR")
        var10_cur  = val(c100, "iVaR")
        var10_sod  = val(s100, "iVaR")
        var10_t1   = val(t100, "iVaR")
        mar_cur    = val(c95,  "Margin")
        mar_sod    = val(s95,  "Margin")
        mar_t1     = val(t95,  "Margin")

        rows.append({
            "Subgroup": sg,
            "_rowType": "subgroup",
            "VaR_100D": abs(var100_cur) if var100_cur is not None else None,
            "Delta_100D": delta(var100_cur, var100_sod),
            "VaR_100D_EOD": abs(var100_sod) if var100_sod is not None else None,  # ADD
            "Delta_100D_t1": delta(var100_cur, var100_t1),
            "VaR_10D": abs(var10_cur) if var10_cur is not None else None,
            "Delta_10D": delta(var10_cur, var10_sod),
            "VaR_10D_EOD": abs(var10_sod) if var10_sod is not None else None,  # ADD
            "Delta_10D_t1": delta(var10_cur, var10_t1),
            "Margin": mar_cur,
            "Delta_Margin": delta(mar_cur, mar_sod),
            "Margin_EOD": mar_sod,  # ADD
            "Delta_Margin_t1": delta(mar_cur, mar_t1),
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Locations dropdown
# ─────────────────────────────────────────────────────────────────────────────

def get_offices() -> pd.DataFrame:
    query = """
        SELECT OfficeName AS Office
        FROM dbo.Lookup_Office
        WHERE IsExcluded = 0
          AND OfficeName != ?
        ORDER BY OfficeName
    """
    with get_connection() as conn:
        return pd.read_sql(query, conn, params=[FUTURES_FIRST_OFFICE])


# ─────────────────────────────────────────────────────────────────────────────
# Metric cards
# ─────────────────────────────────────────────────────────────────────────────

def get_metrics(location: str, confidence: float, lookback: int) -> dict:
    dates = get_latest_eod_dates(confidence, lookback, n=1)
    if not dates:
        return {"var_current": None, "var_sod": None,
                "margin_current": None, "margin_sod": None}

    last_night = dates[0]
    office_val = FUTURES_FIRST_OFFICE if location == "Total" else location

    eod_query = """
        SELECT VaR, Margin
        FROM dbo.OfficeRisk
        WHERE IsEOD      = 1
          AND Date       = ?
          AND Confidence = ?
          AND Lookback   = ?
          AND Office     = ?
    """
    with get_connection() as conn:
        eod = pd.read_sql(eod_query, conn,
                          params=[last_night, confidence, lookback, office_val])

    var_sod    = float(eod["VaR"].iloc[0])    if not eod.empty else None
    margin_sod = float(eod["Margin"].iloc[0]) if not eod.empty else None

    intraday_query = """
        SELECT VaR, Margin
        FROM dbo.OfficeRisk
        WHERE IsEOD      = 0
          AND Date       = ?
          AND Confidence = ?
          AND Lookback   = ?
          AND Office     = ?
        ORDER BY Time DESC
    """
    with get_connection() as conn:
        intra = pd.read_sql(intraday_query, conn,
                            params=[today(), confidence, lookback, office_val])

    if not intra.empty:
        var_current    = float(intra["VaR"].iloc[0])
        margin_current = float(intra["Margin"].iloc[0])
    else:
        var_current    = var_sod
        margin_current = margin_sod

    return {
        "var_current":    var_current,
        "var_sod":        var_sod,
        "margin_current": margin_current,
        "margin_sod":     margin_sod,
    }


def get_vix_margin() -> dict:
    sod_query = """
        SELECT TOP 1 Margin
        FROM dbo.ProductRisk
        WHERE IsEOD      = 1
          AND Confidence = 95.0
          AND Lookback   = 100
          AND Office     = 'Futures First'
          AND Analyst    = 'Futures First'
          AND Product    = 'CBOE Volatility Index Future'
        ORDER BY Date DESC, Time DESC
    """
    intra_query = """
        SELECT TOP 1 Margin
        FROM dbo.ProductRisk
        WHERE IsEOD      = 0
          AND Confidence = 95.0
          AND Lookback   = 100
          AND Date       = ?
          AND Office     = 'Futures First'
          AND Analyst    = 'Futures First'
          AND Product    = 'CBOE Volatility Index Future'
        ORDER BY Date DESC, Time DESC
    """
    with get_connection() as conn:
        sod_df   = pd.read_sql(sod_query,   conn)
        intra_df = pd.read_sql(intra_query, conn, params=[today()])

    vix_sod     = float(sod_df["Margin"].iloc[0])   if not sod_df.empty   else None
    vix_current = float(intra_df["Margin"].iloc[0]) if not intra_df.empty else vix_sod

    return {"vix_current": vix_current, "vix_sod": vix_sod}


def get_last_snapshot() -> dict:
    query = """
        SELECT TOP 1
            CONVERT(VARCHAR(10), Date, 23)  AS snapshot_date,
            CONVERT(VARCHAR(5),  Time, 108) AS snapshot_time
        FROM dbo.OfficeRisk
        WHERE Office     = 'Futures First'
          AND Confidence = 95.0
          AND Lookback   = 100
        ORDER BY Date DESC, Time DESC
    """
    with get_connection() as conn:
        df = pd.read_sql(query, conn)
    if df.empty:
        return {"snapshot_date": None, "snapshot_time": None}
    return {
        "snapshot_date": str(df["snapshot_date"].iloc[0]),
        "snapshot_time": str(df["snapshot_time"].iloc[0]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Rolling chart
# ─────────────────────────────────────────────────────────────────────────────

def get_rolling_chart(location: str, confidence: float, lookback: int,
                      days: int = 5) -> pd.DataFrame:
    office_val = FUTURES_FIRST_OFFICE if location == "Total" else location

    if days == 1:
        # True rolling 24hr window — current time minus 24 hours
        query = """
                SELECT
                    CONVERT(VARCHAR(10), Date, 23) + ' ' + CONVERT(VARCHAR(5), Time, 108) AS Date,
                    VaR, Margin
                FROM dbo.OfficeRisk
                WHERE IsEOD      = 0
                  AND Confidence = ?
                  AND Lookback   = ?
                  AND Office     = ?
                  AND DATEADD(SECOND,
                        DATEDIFF(SECOND, '00:00:00', CAST(Time AS TIME)),
                        CAST(CAST(Date AS DATE) AS DATETIME)
                      ) >= DATEADD(HOUR, -25, GETDATE())
                ORDER BY Date ASC, Time ASC
            """
        with get_connection() as conn:
            df = pd.read_sql(query, conn,
                             params=[confidence, lookback, office_val])
        return df

    else:

        # N-1 EOD points + intraday points across the full window — continuous line

        eod_days = days - 1

        eod_query = """
                SELECT TOP (?)
                    CONVERT(VARCHAR(10), Date, 23) AS Date,
                    VaR, Margin,
                    CAST(CAST(Date AS DATE) AS DATETIME) AS SortDT
                FROM dbo.OfficeRisk
                WHERE IsEOD      = 1
                  AND Confidence = ?
                  AND Lookback   = ?
                  AND Office     = ?
                ORDER BY Date DESC
            """
        intra_query = """
                SELECT
                    CONVERT(VARCHAR(10), Date, 23) + ' ' + CONVERT(VARCHAR(5), Time, 108) AS Date,
                    VaR, Margin,
                    DATEADD(SECOND,
                        DATEDIFF(SECOND, '00:00:00', CAST(Time AS TIME)),
                        CAST(CAST(Date AS DATE) AS DATETIME)
                    ) AS SortDT
                FROM dbo.OfficeRisk
                WHERE IsEOD      = 0
                  AND Date       >= CAST(DATEADD(DAY, -(? - 1), CAST(GETDATE() AS DATE)) AS DATE)
                  AND Confidence = ?
                  AND Lookback   = ?
                  AND Office     = ?
            """
        with get_connection() as conn:
            eod_df = pd.read_sql(eod_query, conn,
                                 params=[eod_days, confidence, lookback, office_val])
            intra_df = pd.read_sql(intra_query, conn,
                                 params=[days, confidence, lookback, office_val])

        df = pd.concat([eod_df, intra_df], ignore_index=True)
        df = df.sort_values("SortDT").drop(columns="SortDT").reset_index(drop=True)

        return df

def get_sector_chart(location: str, sector: str, confidence: float,
                     lookback: int, days: int) -> pd.DataFrame:
    """
    iVaR summed by sector from ProductRisk for chart display.
    1D: last 24 hours EOD + intraday. 5D/1M: EOD + today's intraday.
    Output columns: Date, iVaR, Margin
    """
    asset_classes = SECTOR_ASSET_CLASSES.get(sector, [])
    if not asset_classes:
        return pd.DataFrame(columns=["Date", "iVaR", "Margin"])

    office_val = FUTURES_FIRST_OFFICE if location == "Total" else location
    ac_ph = ",".join(["?"] * len(asset_classes))

    if days == 1:
        query = f"""
            SELECT
                CASE
                    WHEN IsEOD = 1 THEN 'EOD'
                    ELSE CONVERT(VARCHAR(5), Time, 108)
                END AS Date,
                SUM(iVaR) AS iVaR,
                SUM(Margin) AS Margin
            FROM dbo.ProductRisk
            WHERE Confidence = ?
              AND Lookback   = ?
              AND Office     = ?
              AND Analyst    = Office
              AND Product   != Asset_Class
              AND Asset_Class IN ({ac_ph})
              AND DATEADD(SECOND,
                    DATEDIFF(SECOND, '00:00:00', CAST(Time AS TIME)),
                    CAST(CAST(Date AS DATE) AS DATETIME)
                  ) >= DATEADD(HOUR, -24, GETDATE())
            GROUP BY IsEOD, Time
            ORDER BY Time ASC
        """
        params = [confidence, lookback, office_val] + asset_classes
        with get_connection() as conn:
            return pd.read_sql(query, conn, params=params)

    else:
        eod_days = days - 1
        eod_query = f"""
            SELECT TOP (?)
                CONVERT(VARCHAR(10), Date, 23) AS Date,
                SUM(iVaR) AS iVaR,
                SUM(Margin) AS Margin,
                CAST(CAST(Date AS DATE) AS DATETIME) AS SortDT
            FROM dbo.ProductRisk
            WHERE IsEOD      = 1
              AND Confidence = ?
              AND Lookback   = ?
              AND Office     = ?
              AND Analyst    = Office
              AND Product   != Asset_Class
              AND Asset_Class IN ({ac_ph})
            GROUP BY Date
            ORDER BY Date DESC
        """
        intra_query = f"""
            SELECT
                CONVERT(VARCHAR(5), Time, 108) AS Date,
                SUM(iVaR) AS iVaR,
                SUM(Margin) AS Margin,
                DATEADD(SECOND,
                    DATEDIFF(SECOND, '00:00:00', CAST(Time AS TIME)),
                    CAST(CAST(GETDATE() AS DATE) AS DATETIME)
                ) AS SortDT
            FROM dbo.ProductRisk
            WHERE IsEOD      = 0
              AND Date       = CAST(GETDATE() AS DATE)
              AND Confidence = ?
              AND Lookback   = ?
              AND Office     = ?
              AND Analyst    = Office
              AND Product   != Asset_Class
              AND Asset_Class IN ({ac_ph})
              AND Time = (
                  SELECT MAX(p2.Time)
                  FROM dbo.ProductRisk p2
                  WHERE p2.Office     = 'Futures First'
                    AND p2.Date       = CAST(GETDATE() AS DATE)
                    AND p2.Confidence = ?
                    AND p2.Lookback   = ?
                    AND p2.IsEOD      = 0
              )
            GROUP BY Time
        """
        with get_connection() as conn:
            eod_df   = pd.read_sql(eod_query,   conn,
                                   params=[eod_days, confidence, lookback, office_val] + asset_classes)
            intra_df = pd.read_sql(intra_query, conn,
                                   params=[confidence, lookback, office_val] + asset_classes + [confidence, lookback])

        df = pd.concat([eod_df, intra_df], ignore_index=True)
        df = df.sort_values("SortDT").drop(columns="SortDT").reset_index(drop=True)
        return df


def get_product_chart(location: str, product: str, confidence: float,
                      lookback: int, days: int) -> pd.DataFrame:
    """
    iVaR + Margin for a single product from ProductRisk for chart display.
    1D: last 24 hours. 5D/1M: EOD + today's intraday.
    Output columns: Date, iVaR, Margin
    """
    office_val = FUTURES_FIRST_OFFICE if location == "Total" else location

    if days == 1:
        query = """
            SELECT
                CASE
                    WHEN pr.IsEOD = 1 THEN 'EOD'
                    ELSE CONVERT(VARCHAR(5), pr.Time, 108)
                END AS Date,
                SUM(pr.iVaR) AS iVaR,
                SUM(pr.Margin) AS Margin
            FROM dbo.ProductRisk pr
            WHERE pr.Confidence = ?
              AND pr.Lookback   = ?
              AND pr.Office     = ?
              AND pr.Analyst    = pr.Office
              AND pr.Product    = ?
              AND DATEADD(SECOND,
                    DATEDIFF(SECOND, '00:00:00', CAST(pr.Time AS TIME)),
                    CAST(CAST(pr.Date AS DATE) AS DATETIME)
                  ) >= DATEADD(HOUR, -24, GETDATE())
            GROUP BY pr.IsEOD, pr.Time
            ORDER BY pr.Time ASC
        """
        with get_connection() as conn:
            return pd.read_sql(query, conn,
                               params=[confidence, lookback, office_val, product])

    else:
        eod_days = days - 1
        eod_query = """
            SELECT TOP (?)
                CONVERT(VARCHAR(10), Date, 23) AS Date,
                SUM(iVaR) AS iVaR,
                SUM(Margin) AS Margin,
                CAST(CAST(Date AS DATE) AS DATETIME) AS SortDT
            FROM dbo.ProductRisk
            WHERE IsEOD      = 1
              AND Confidence = ?
              AND Lookback   = ?
              AND Office     = ?
              AND Analyst    = Office
              AND Product    = ?
            GROUP BY Date
            ORDER BY Date DESC
        """
        intra_query = """
            SELECT
                CONVERT(VARCHAR(5), pr.Time, 108) AS Date,
                SUM(pr.iVaR) AS iVaR,
                SUM(pr.Margin) AS Margin,
                DATEADD(SECOND,
                    DATEDIFF(SECOND, '00:00:00', CAST(pr.Time AS TIME)),
                    CAST(CAST(GETDATE() AS DATE) AS DATETIME)
                ) AS SortDT
            FROM dbo.ProductRisk pr
            WHERE pr.IsEOD      = 0
              AND pr.Date       = CAST(GETDATE() AS DATE)
              AND pr.Confidence = ?
              AND pr.Lookback   = ?
              AND pr.Office     = ?
              AND pr.Analyst    = pr.Office
              AND pr.Product    = ?
              AND pr.Time = (
                  SELECT MAX(p2.Time)
                  FROM dbo.ProductRisk p2
                  WHERE p2.Office     = pr.Office
                    AND p2.Date       = pr.Date
                    AND p2.Confidence = pr.Confidence
                    AND p2.Lookback   = pr.Lookback
                    AND p2.IsEOD      = 0
              )
            GROUP BY pr.Time
        """
        with get_connection() as conn:
            eod_df   = pd.read_sql(eod_query,   conn,
                                   params=[eod_days, confidence, lookback, office_val, product])
            intra_df = pd.read_sql(intra_query, conn,
                                   params=[confidence, lookback, office_val, product])

        df = pd.concat([eod_df, intra_df], ignore_index=True)
        df = df.sort_values("SortDT").drop(columns="SortDT").reset_index(drop=True)
        return df


# ─────────────────────────────────────────────────────────────────────────────
# Location table
# ─────────────────────────────────────────────────────────────────────────────

def _get_ff_row(last_night_95, last_night_100, t1_95, t1_100, today_str):
    def fetch(confidence, lookback, date, eod):
        query = """
            SELECT Office, VaR, Margin
            FROM dbo.OfficeRisk
            WHERE IsEOD      = ?
              AND Date       = ?
              AND Confidence = ?
              AND Lookback   = ?
              AND Office     = ?
            ORDER BY Time DESC
        """
        with get_connection() as conn:
            df = pd.read_sql(query, conn,
                             params=[1 if eod else 0, date, confidence,
                                     lookback, FUTURES_FIRST_OFFICE])
        return df.head(1)

    sod_95  = fetch(95.0,  100, last_night_95,  eod=True)
    sod_100 = fetch(100.0,  10, last_night_100,  eod=True)
    t1_95_  = fetch(95.0,  100, t1_95,           eod=True)
    t1_100_ = fetch(100.0,  10, t1_100,          eod=True)
    cur_95  = fetch(95.0,  100, today_str,            eod=False)
    cur_100 = fetch(100.0,  10, today_str,            eod=False)

    if cur_95.empty:  cur_95  = sod_95.copy()
    if cur_100.empty: cur_100 = sod_100.copy()

    def val(df, col):
        return float(df[col].iloc[0]) if not df.empty else None

    var100 = val(cur_95,  "VaR")
    var10  = val(cur_100, "VaR")
    margin = val(cur_95,  "Margin")

    return pd.DataFrame([{
        "Office":          FUTURES_FIRST_OFFICE,
        "VaR_100D":        var100,
        "Delta_100D":      (var100 - val(sod_95,  "VaR"))    if var100  is not None and not sod_95.empty  else 0,
        "Delta_100D_t1":   (var100 - val(t1_95_,  "VaR"))    if var100  is not None and not t1_95_.empty  else 0,
        "VaR_10D":         var10,
        "Delta_10D":       (var10  - val(sod_100, "VaR"))    if var10   is not None and not sod_100.empty else 0,
        "Delta_10D_t1":    (var10  - val(t1_100_, "VaR"))    if var10   is not None and not t1_100_.empty else 0,
        "Margin":          margin,
        "Delta_Margin":    (margin - val(sod_95,  "Margin")) if margin  is not None and not sod_95.empty  else 0,
        "Delta_Margin_t1": (margin - val(t1_95_,  "Margin")) if margin  is not None and not t1_95_.empty  else 0,
    }])


def get_location_table(location: str = "Total") -> pd.DataFrame:

    dc = date_context()

    if location == "Total":
        where  = f"Office NOT IN ({_excl_ph()}) AND Office != ?"
        params = EXCLUDED_OFFICES + [FUTURES_FIRST_OFFICE]
    else:
        where  = "Office = ?"
        params = [location]

    def fetch(confidence, lookback, date, eod: bool):
        if eod:
            query = f"""
                SELECT Office, VaR, Margin
                FROM dbo.OfficeRisk
                WHERE IsEOD      = 1
                  AND Date       = ?
                  AND Confidence = ?
                  AND Lookback   = ?
                  AND {where}
            """
        else:
            query = f"""
                SELECT Office, VaR, Margin
                FROM dbo.OfficeRisk r1
                WHERE IsEOD      = 0
                  AND Date       = ?
                  AND Confidence = ?
                  AND Lookback   = ?
                  AND Time = (
                      SELECT MAX(r2.Time)
                      FROM dbo.OfficeRisk r2
                      WHERE r2.Office     = r1.Office
                        AND r2.Date       = r1.Date
                        AND r2.Confidence = r1.Confidence
                        AND r2.Lookback   = r1.Lookback
                        AND r2.IsEOD      = 0
                  )
                  AND {where}
            """
        with get_connection() as conn:
            return pd.read_sql(query, conn,
                               params=[date, confidence, lookback] + params)

    df = build_var_table(
        fetch_fn   = fetch,
        keys       = ["Office"],
        dc         = dc,
        var_col    = "VaR",
        margin_col = "Margin",
    )

    df = df.sort_values("VaR_100D", ascending=False).reset_index(drop=True)

    if location == "Total":
        ff = _get_ff_row(dc.last_night_95, dc.last_night_100, dc.t1_95, dc.t1_100, dc.today_str)
        df = pd.concat([ff, df], ignore_index=True)

    return df

# ─────────────────────────────────────────────────────────────────────────────
# Analyst table
# ─────────────────────────────────────────────────────────────────────────────

def get_analyst_table(location: str = "Total") -> pd.DataFrame:

    dc = date_context()

    if location == "Total":
        where  = f"Office NOT IN ({_excl_ph()})"
        params = EXCLUDED_OFFICES
    else:
        where  = "Office = ?"
        params = [location]

    def fetch(confidence, lookback, date, eod: bool):
        if eod:
            query = f"""
                SELECT Office, Analyst, VaR, Margin
                FROM dbo.AnalystRisk
                WHERE IsEOD      = 1
                  AND Date       = ?
                  AND Confidence = ?
                  AND Lookback   = ?
                  AND {where}
            """
        else:
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
            return pd.read_sql(query, conn,
                               params=[date, confidence, lookback] + params)

    keys = ["Office", "Analyst"]

    df = build_var_table(
        fetch_fn   = fetch,
        keys       = keys,
        dc         = dc,
        var_col    = "VaR",
        margin_col = "Margin",
    )

    return (
        df[keys + ["VaR_10D", "Delta_10D", "VaR_100D", "Delta_100D", "Margin", "Delta_Margin"]]
        .sort_values("VaR_100D", ascending=False)
        .reset_index(drop=True)
    )

# ─────────────────────────────────────────────────────────────────────────────
# Asset class table — GROUPED by sector
# ─────────────────────────────────────────────────────────────────────────────

def get_asset_class_table(location: str = "Total") -> pd.DataFrame:
    return pd.DataFrame()


def get_product_table(location: str = "Total") -> pd.DataFrame:
    return pd.DataFrame()

def get_asset_class_table_grouped(location: str = "Total") -> pd.DataFrame:
    _EMPTY = ["Sector",
              "VaR_10D", "Delta_10D", "VaR_10D_EOD", "Delta_10D_t1",
              "VaR_100D", "Delta_100D", "VaR_100D_EOD", "Delta_100D_t1",
              "Margin", "Delta_Margin", "Margin_EOD", "Delta_Margin_t1"]

    dc         = date_context()
    office_val = FUTURES_FIRST_OFFICE if location == "Total" else location

    def fetch(confidence, lookback, date, eod: bool):
        if eod:
            query = """
                SELECT Asset_Class, SUM(iVaR) AS iVaR, SUM(Margin) AS Margin
                FROM dbo.ProductRisk
                WHERE IsEOD      = 1
                  AND Date       = ?
                  AND Confidence = ?
                  AND Lookback   = ?
                  AND Office     = ?
                  AND Analyst    = Office
                  AND Product   != Asset_Class
                GROUP BY Asset_Class
            """
        else:
            query = """
                SELECT Asset_Class, SUM(iVaR) AS iVaR, SUM(Margin) AS Margin
                FROM dbo.ProductRisk p1
                WHERE IsEOD      = 0
                  AND Date       = ?
                  AND Confidence = ?
                  AND Lookback   = ?
                  AND Office     = ?
                  AND Analyst    = Office
                  AND Product   != Asset_Class
                  AND Time = (
                      SELECT MAX(p2.Time)
                      FROM dbo.ProductRisk p2
                      WHERE p2.Office     = p1.Office
                        AND p2.Date       = p1.Date
                        AND p2.Confidence = p1.Confidence
                        AND p2.Lookback   = p1.Lookback
                        AND p2.IsEOD      = 0
                  )
                GROUP BY Asset_Class
            """
        with get_connection() as conn:
            return pd.read_sql(query, conn,
                               params=[date, confidence, lookback, office_val])

    # Apply sector mapping then group by Sector before passing to build_var_table
    def fetch_by_sector(confidence, lookback, date, eod):
        df = fetch(confidence, lookback, date, eod)
        if df.empty:
            return pd.DataFrame(columns=["Sector", "iVaR", "Margin"])
        df["Sector"] = df["Asset_Class"].map(SECTOR_MAP).fillna("Other")
        return df.groupby("Sector", as_index=False).agg({"iVaR": "sum", "Margin": "sum"})

    result = build_var_table(
        fetch_fn   = fetch_by_sector,
        keys       = ["Sector"],
        dc         = dc,
        var_col    = "iVaR",
        margin_col = "Margin",
    )

    if result.empty:
        return pd.DataFrame(columns=_EMPTY)

    return result.sort_values("VaR_100D", ascending=False).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Product table filtered by sector
# ─────────────────────────────────────────────────────────────────────────────

def get_product_table_by_sector(location: str = "Total", sector: str = "Energy") -> pd.DataFrame:
    """
    iVaR + Margin by product from ProductRisk, filtered to a specific sector.
    Asset class resolved from Lookup_ProductAssetClass (canonical source of truth).
    Subgroup header rows with Cumulus netted VaR are interleaved with product rows.
    Output columns: Subgroup, Product, Asset_Class, _rowType,
                    VaR_10D, Delta_10D, Delta_10D_t1,
                    VaR_100D, Delta_100D, Delta_100D_t1,
                    Margin, Delta_Margin, Delta_Margin_t1
    """
    _EMPTY = ["Subgroup", "Product", "Asset_Class",
              "VaR_10D", "Delta_10D", "VaR_10D_EOD", "Delta_10D_t1",
              "VaR_100D", "Delta_100D", "VaR_100D_EOD", "Delta_100D_t1",
              "Margin", "Delta_Margin", "Margin_EOD", "Delta_Margin_t1"]

    asset_classes = SECTOR_ASSET_CLASSES.get(sector, [])
    if not asset_classes:
        return pd.DataFrame(columns=_EMPTY + ["_rowType"])

    dc         = date_context()
    office_val = FUTURES_FIRST_OFFICE if location == "Total" else location
    ac_ph      = ",".join(["?"] * len(asset_classes))

    def fetch(confidence, lookback, date, eod: bool):
        if eod:
            query = f"""
                SELECT pr.Product, pac.Asset_Class,
                       SUM(pr.iVaR) AS iVaR, SUM(pr.Margin) AS Margin
                FROM dbo.ProductRisk pr
                JOIN dbo.Lookup_ProductAssetClass pac ON pac.Product = pr.Product
                WHERE pr.IsEOD      = 1
                  AND pr.Date       = ?
                  AND pr.Confidence = ?
                  AND pr.Lookback   = ?
                  AND pr.Office     = ?
                  AND pr.Analyst    = pr.Office
                  AND pr.Product   != pr.Asset_Class
                  AND pac.Asset_Class IN ({ac_ph})
                GROUP BY pr.Product, pac.Asset_Class
            """
        else:
            query = f"""
                SELECT pr.Product, pac.Asset_Class,
                       SUM(pr.iVaR) AS iVaR, SUM(pr.Margin) AS Margin
                FROM dbo.ProductRisk pr
                JOIN dbo.Lookup_ProductAssetClass pac ON pac.Product = pr.Product
                WHERE pr.IsEOD      = 0
                  AND pr.Date       = ?
                  AND pr.Confidence = ?
                  AND pr.Lookback   = ?
                  AND pr.Office     = ?
                  AND pr.Analyst    = pr.Office
                  AND pr.Product   != pr.Asset_Class
                  AND pac.Asset_Class IN ({ac_ph})
                  AND pr.Time = (
                      SELECT MAX(p2.Time)
                      FROM dbo.ProductRisk p2
                      WHERE p2.Office     = pr.Office
                        AND p2.Date       = pr.Date
                        AND p2.Confidence = pr.Confidence
                        AND p2.Lookback   = pr.Lookback
                        AND p2.IsEOD      = 0
                  )
                GROUP BY pr.Product, pac.Asset_Class
            """
        with get_connection() as conn:
            return pd.read_sql(query, conn,
                               params=[date, confidence, lookback, office_val] + asset_classes)

    # ── Build the base product table ──────────────────────────────────────────
    df = build_var_table(
        fetch_fn   = fetch,
        keys       = ["Product", "Asset_Class"],
        dc         = dc,
        var_col    = "iVaR",
        margin_col = "Margin",
    )

    if df.empty:
        return pd.DataFrame(columns=_EMPTY + ["_rowType"])

    # ── Subgroup ordering ─────────────────────────────────────────────────────
    df["Subgroup"] = df["Product"].map(PRODUCT_SUBGROUP).fillna("Other")

    subgroup_order = SUBGROUP_ORDER.get(sector, [])
    df["_sg_order"] = df["Subgroup"].apply(
        lambda s: subgroup_order.index(s) if s in subgroup_order else len(subgroup_order)
    )
    df = df.sort_values(["_sg_order", "VaR_100D"], ascending=[True, False])
    df = df.drop(columns="_sg_order").reset_index(drop=True)
    df["_rowType"] = "product"

    # ── Interleave Cumulus netted subgroup header rows ────────────────────────
    all_subgroups = subgroup_order if subgroup_order else list(df["Subgroup"].unique())
    netted = _get_subgroup_netted_var(office_val, all_subgroups, sector)

    result_rows = []
    for sg in all_subgroups:
        hdr = netted[netted["Subgroup"] == sg]
        if not hdr.empty:
            h = hdr.iloc[0].to_dict()
            h["Product"]     = sg
            h["Asset_Class"] = None
            result_rows.append(h)
        for _, row in df[df["Subgroup"] == sg].iterrows():
            result_rows.append(row.to_dict())

    out = pd.DataFrame(result_rows)
    for col in _EMPTY:
        if col not in out.columns:
            out[col] = None
    out["_rowType"] = out["_rowType"].fillna("product")

    return out[_EMPTY + ["_rowType"]]