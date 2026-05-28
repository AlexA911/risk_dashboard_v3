"""
data/db_rollview.py — Queries for the Roll Risk tab.

Two views:

  RISK VIEW  (get_roll_risk)
    Fixed Income | Equities — full product breakdown with currency subgroups.
    Subgroup derived from Asset_Class directly — no separate product→subgroup map.
    Section total = Cumulus netted from Rates / Equity Indices asset classes.

  ROLLS VIEW  (get_roll_risk_rolls)
    FI Rolls | Equity Rolls — flat bond/equity product list, no STIRs, no subgroups.
    Section total = Cumulus netted from Asset_Class = 'FI Rolls' / 'Equity Rolls'.

All reference data lives in data/reference.py. This file contains only queries.
"""

import pandas as pd
from data.dates import today, get_latest_eod_dates, date_context
from data.db_connection import get_connection
from data.reference import (
    FUTURES_FIRST_OFFICE,
    ROLL_SECTORS,
    ROLL_SECTORS_ROLLS,
    ROLL_AC_TO_SUBGROUP,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────



def _d(a, b):
    return (a - b) if a is not None and b is not None else None


def _fetch_products(office_val, asset_classes, confidence, lookback, date, eod):
    ac_ph = ",".join(["?"] * len(asset_classes))
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


def _fetch_subgroup_netted(office_val, asset_classes, confidence, lookback, date, eod):
    if not asset_classes:
        return None, None
    ac_ph    = ",".join(["?"] * len(asset_classes))
    is_total = (office_val == FUTURES_FIRST_OFFICE)

    if is_total:
        if eod:
            q = f"""
                SELECT SUM(iVaR) AS iVaR, SUM(Margin) AS Margin
                FROM dbo.ProductRisk
                WHERE IsEOD = 1 AND Date = ? AND Confidence = ? AND Lookback = ?
                  AND Office = 'Futures First' AND Analyst = 'Futures First'
                  AND Product IN ({ac_ph})
            """
            p = [date, confidence, lookback] + asset_classes
        else:
            q = f"""
                SELECT SUM(iVaR) AS iVaR, SUM(Margin) AS Margin
                FROM dbo.ProductRisk
                WHERE IsEOD = 0 AND Date = ? AND Confidence = ? AND Lookback = ?
                  AND Office = 'Futures First' AND Analyst = 'Futures First'
                  AND Product IN ({ac_ph})
                  AND Time = (
                      SELECT MAX(p2.Time) FROM dbo.ProductRisk p2
                      WHERE p2.Office = 'Futures First' AND p2.Analyst = 'Futures First'
                        AND p2.Date = ? AND p2.IsEOD = 0
                        AND p2.Confidence = ? AND p2.Lookback = ?
                  )
            """
            p = [date, confidence, lookback] + asset_classes + [date, confidence, lookback]
    else:
        if eod:
            q = f"""
                SELECT SUM(iVaR) AS iVaR, SUM(Margin) AS Margin
                FROM dbo.ProductRisk
                WHERE IsEOD = 1 AND Date = ? AND Confidence = ? AND Lookback = ?
                  AND Office = ? AND Analyst = Office AND Product IN ({ac_ph})
            """
            p = [date, confidence, lookback, office_val] + asset_classes
        else:
            q = f"""
                SELECT SUM(iVaR) AS iVaR, SUM(Margin) AS Margin
                FROM dbo.ProductRisk
                WHERE IsEOD = 0 AND Date = ? AND Confidence = ? AND Lookback = ?
                  AND Office = ? AND Analyst = Office AND Product IN ({ac_ph})
                  AND Time = (
                      SELECT MAX(p2.Time) FROM dbo.ProductRisk p2
                      WHERE p2.Office = ? AND p2.Date = ? AND p2.IsEOD = 0
                        AND p2.Confidence = ? AND p2.Lookback = ?
                  )
            """
            p = [date, confidence, lookback, office_val] + asset_classes + \
                [office_val, date, confidence, lookback]

    with get_connection() as conn:
        df = pd.read_sql(q, conn, params=p)

    if df.empty or df["iVaR"].iloc[0] is None:
        return None, None
    return float(df["iVaR"].iloc[0]), float(df["Margin"].iloc[0])


def _fetch_rolls_netted(office_val, sql_asset_class, confidence, lookback, date, eod):
    is_total = (office_val == FUTURES_FIRST_OFFICE)

    if is_total:
        if eod:
            q = """
                SELECT SUM(iVaR) AS iVaR, SUM(Margin) AS Margin
                FROM dbo.ProductRisk
                WHERE IsEOD = 1 AND Date = ? AND Confidence = ? AND Lookback = ?
                  AND Office = 'Futures First' AND Analyst = 'Futures First'
                  AND Asset_Class = ? AND Product = Asset_Class
            """
            p = [date, confidence, lookback, sql_asset_class]
        else:
            q = """
                SELECT SUM(iVaR) AS iVaR, SUM(Margin) AS Margin
                FROM dbo.ProductRisk
                WHERE IsEOD = 0 AND Date = ? AND Confidence = ? AND Lookback = ?
                  AND Office = 'Futures First' AND Analyst = 'Futures First'
                  AND Asset_Class = ? AND Product = Asset_Class
                  AND Time = (
                      SELECT MAX(p2.Time) FROM dbo.ProductRisk p2
                      WHERE p2.Office = 'Futures First' AND p2.Analyst = 'Futures First'
                        AND p2.Date = ? AND p2.IsEOD = 0
                        AND p2.Confidence = ? AND p2.Lookback = ?
                  )
            """
            p = [date, confidence, lookback, sql_asset_class, date, confidence, lookback]
    else:
        if eod:
            q = """
                SELECT SUM(iVaR) AS iVaR, SUM(Margin) AS Margin
                FROM dbo.ProductRisk
                WHERE IsEOD = 1 AND Date = ? AND Confidence = ? AND Lookback = ?
                  AND Office = ? AND Analyst = Office
                  AND Asset_Class = ? AND Product = Asset_Class
            """
            p = [date, confidence, lookback, office_val, sql_asset_class]
        else:
            q = """
                SELECT SUM(iVaR) AS iVaR, SUM(Margin) AS Margin
                FROM dbo.ProductRisk
                WHERE IsEOD = 0 AND Date = ? AND Confidence = ? AND Lookback = ?
                  AND Office = ? AND Analyst = Office
                  AND Asset_Class = ? AND Product = Asset_Class
                  AND Time = (
                      SELECT MAX(p2.Time) FROM dbo.ProductRisk p2
                      WHERE p2.Office = ? AND p2.Date = ? AND p2.IsEOD = 0
                        AND p2.Confidence = ? AND p2.Lookback = ?
                  )
            """
            p = [date, confidence, lookback, office_val, sql_asset_class,
                 office_val, date, confidence, lookback]

    with get_connection() as conn:
        df = pd.read_sql(q, conn, params=p)

    if df.empty or df["iVaR"].iloc[0] is None:
        return None, None
    return float(df["iVaR"].iloc[0]), float(df["Margin"].iloc[0])


def _build_product_df(office_val, asset_classes,
                      last_night_95, t1_95, today_str,
                      last_night_100, t1_100):
    sod_95  = _fetch_products(office_val, asset_classes, 95.0,  100, last_night_95,  eod=True)
    t1_95_  = _fetch_products(office_val, asset_classes, 95.0,  100, t1_95,          eod=True)
    cur_95  = _fetch_products(office_val, asset_classes, 95.0,  100, today_str,           eod=False)
    sod_100 = _fetch_products(office_val, asset_classes, 100.0,  10, last_night_100,  eod=True)
    t1_100_ = _fetch_products(office_val, asset_classes, 100.0,  10, t1_100,          eod=True)
    cur_100 = _fetch_products(office_val, asset_classes, 100.0,  10, today_str,            eod=False)

    if cur_95.empty:  cur_95  = sod_95.copy()
    if cur_100.empty: cur_100 = sod_100.copy()

    keys    = ["Product", "Asset_Class"]
    sod_95  = sod_95.rename(columns={"iVaR": "_var100_sod",  "Margin": "_margin_sod"})
    t1_95_  = t1_95_.rename(columns={"iVaR": "_var100_t1",   "Margin": "_margin_t1"})
    cur_95  = cur_95.rename(columns={"iVaR": "_var100_cur",  "Margin": "_margin_cur"})
    sod_100 = sod_100.rename(columns={"iVaR": "_var10_sod"})
    t1_100_ = t1_100_.rename(columns={"iVaR": "_var10_t1"})
    cur_100 = cur_100.rename(columns={"iVaR": "_var10_cur"})

    df = (
        sod_95 [keys + ["_var100_sod", "_margin_sod"]]
        .merge(t1_95_ [keys + ["_var100_t1",  "_margin_t1"]],  on=keys, how="outer")
        .merge(cur_95 [keys + ["_var100_cur", "_margin_cur"]], on=keys, how="outer")
        .merge(sod_100[keys + ["_var10_sod"]],                 on=keys, how="outer")
        .merge(t1_100_[keys + ["_var10_t1"]],                  on=keys, how="outer")
        .merge(cur_100[keys + ["_var10_cur"]],                  on=keys, how="outer")
    )

    df["VaR_100D"]        = df["_var100_cur"].abs()
    df["Delta_100D"]      = df["_var100_cur"] - df["_var100_sod"]
    df["Delta_100D_t1"]   = df["_var100_cur"] - df["_var100_t1"]
    df["VaR_10D"]         = df["_var10_cur"].abs()
    df["Delta_10D"]       = df["_var10_cur"]  - df["_var10_sod"]
    df["Delta_10D_t1"]    = df["_var10_cur"]  - df["_var10_t1"]
    df["Margin"]          = df["_margin_cur"]
    df["Delta_Margin"]    = df["_margin_cur"] - df["_margin_sod"]
    df["Delta_Margin_t1"] = df["_margin_cur"] - df["_margin_t1"]

    return df


def _make_product_row(row) -> dict:
    return {
        "Product":         row["Product"],
        "Asset_Class":     row["Asset_Class"],
        "_rowType":        "product",
        "VaR_100D":        row["VaR_100D"],
        "Delta_100D":      row["Delta_100D"],
        "Delta_100D_t1":   row["Delta_100D_t1"],
        "VaR_10D":         row["VaR_10D"],
        "Delta_10D":       row["Delta_10D"],
        "Delta_10D_t1":    row["Delta_10D_t1"],
        "Margin":          row["Margin"],
        "Delta_Margin":    row["Delta_Margin"],
        "Delta_Margin_t1": row["Delta_Margin_t1"],
        # P&L merged client-side from /api/hawk-roll-pnl
        "_pnl1d":          None,
        "_pnl5d":          None,
    }




# ─────────────────────────────────────────────────────────────────────────────
# Public: Risk view
# ─────────────────────────────────────────────────────────────────────────────

def get_roll_risk(location: str = "Total") -> list[dict]:
    """
    Risk view — Fixed Income (bond+STIR products) and Equities.
    Subgroup derived from Asset_Class via ROLL_AC_TO_SUBGROUP.
    Section total = Cumulus netted from Rates / Equity Indices.
    P&L is None here — merged client-side from /api/hawk-roll-pnl.
    """
    dc = date_context()
    office_val = FUTURES_FIRST_OFFICE if location == "Total" else location

    result = []

    for section_name, cfg in ROLL_SECTORS.items():
        asset_classes = cfg["asset_classes"]
        subgroups     = cfg["subgroups"]
        sg_acs        = cfg["subgroup_asset_classes"]

        df = _build_product_df(office_val, asset_classes,
                               dc.last_night_95, dc.t1_95, dc.today_str,
                               dc.last_night_100, dc.t1_100)
        # Derive subgroup from Asset_Class — no product→subgroup map needed
        df["Subgroup"] = df["Asset_Class"].map(ROLL_AC_TO_SUBGROUP).fillna("Other")

        sec100_cur, sec_mar_cur = _fetch_subgroup_netted(office_val, asset_classes, 95.0,  100, dc.today_str,          eod=False)
        sec100_sod, sec_mar_sod = _fetch_subgroup_netted(office_val, asset_classes, 95.0,  100, dc.last_night_95,  eod=True)
        sec100_t1,  sec_mar_t1  = _fetch_subgroup_netted(office_val, asset_classes, 95.0,  100, dc.t1_95,          eod=True)
        sec10_cur,  _           = _fetch_subgroup_netted(office_val, asset_classes, 100.0,  10, dc.today_str,          eod=False)
        sec10_sod,  _           = _fetch_subgroup_netted(office_val, asset_classes, 100.0,  10, dc.last_night_100, eod=True)
        sec10_t1,   _           = _fetch_subgroup_netted(office_val, asset_classes, 100.0,  10, dc.t1_100,         eod=True)

        if sec100_cur  is None: sec100_cur  = sec100_sod
        if sec_mar_cur is None: sec_mar_cur = sec_mar_sod
        if sec10_cur   is None: sec10_cur   = sec10_sod

        section_row = {
            "Product": section_name, "Asset_Class": None, "_rowType": "section",
            "VaR_100D":        abs(sec100_cur) if sec100_cur is not None else None,
            "Delta_100D":      _d(sec100_cur, sec100_sod),
            "Delta_100D_t1":   _d(sec100_cur, sec100_t1),
            "VaR_10D":         abs(sec10_cur)  if sec10_cur  is not None else None,
            "Delta_10D":       _d(sec10_cur,  sec10_sod),
            "Delta_10D_t1":    _d(sec10_cur,  sec10_t1),
            "Margin":          sec_mar_cur,
            "Delta_Margin":    _d(sec_mar_cur, sec_mar_sod),
            "Delta_Margin_t1": _d(sec_mar_cur, sec_mar_t1),
            "_pnl1d": None, "_pnl5d": None,
        }

        rows = [section_row]

        for sg in subgroups:
            acs = sg_acs.get(sg, [])
            var100_cur, mar_cur = _fetch_subgroup_netted(office_val, acs, 95.0,  100, dc.today_str,          eod=False)
            var100_sod, mar_sod = _fetch_subgroup_netted(office_val, acs, 95.0,  100, dc.last_night_95,  eod=True)
            var100_t1,  mar_t1  = _fetch_subgroup_netted(office_val, acs, 95.0,  100, dc.t1_95,          eod=True)
            var10_cur,  _       = _fetch_subgroup_netted(office_val, acs, 100.0,  10, dc.today_str,          eod=False)
            var10_sod,  _       = _fetch_subgroup_netted(office_val, acs, 100.0,  10, dc.last_night_100, eod=True)
            var10_t1,   _       = _fetch_subgroup_netted(office_val, acs, 100.0,  10, dc.t1_100,         eod=True)

            if var100_cur is None: var100_cur = var100_sod
            if mar_cur    is None: mar_cur    = mar_sod
            if var10_cur  is None: var10_cur  = var10_sod

            rows.append({
                "Product": sg, "Asset_Class": None, "_rowType": "subgroup",
                "VaR_100D":        abs(var100_cur) if var100_cur is not None else None,
                "Delta_100D":      _d(var100_cur, var100_sod),
                "Delta_100D_t1":   _d(var100_cur, var100_t1),
                "VaR_10D":         abs(var10_cur)  if var10_cur  is not None else None,
                "Delta_10D":       _d(var10_cur,  var10_sod),
                "Delta_10D_t1":    _d(var10_cur,  var10_t1),
                "Margin":          mar_cur,
                "Delta_Margin":    _d(mar_cur, mar_sod),
                "Delta_Margin_t1": _d(mar_cur, mar_t1),
                "_pnl1d": None, "_pnl5d": None,
            })

            for _, row in df[df["Subgroup"] == sg].sort_values(
                "VaR_100D", ascending=False
            ).iterrows():
                rows.append(_make_product_row(row))

        result.append({"section": section_name, "rows": rows})

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Public: Rolls view
# ─────────────────────────────────────────────────────────────────────────────

def get_roll_risk_rolls(location: str = "Total") -> list[dict]:
    """
    Rolls view — FI Rolls (bond futures only, no STIRs) and Equity Rolls.
    Section total = Cumulus netted from Asset_Class = 'FI Rolls' / 'Equity Rolls'.
    P&L is None here — merged client-side from /api/hawk-roll-pnl.
    """
    dc = date_context()
    office_val = FUTURES_FIRST_OFFICE if location == "Total" else location

    result = []

    for section_name, cfg in ROLL_SECTORS_ROLLS.items():
        sql_ac         = cfg["sql_asset_class"]
        product_acs    = cfg["product_asset_classes"]
        product_filter = cfg["product_filter"]

        sec100_cur, sec_mar_cur = _fetch_rolls_netted(office_val, sql_ac, 95.0,  100, dc.today_str,      eod=False)
        sec100_sod, sec_mar_sod = _fetch_rolls_netted(office_val, sql_ac, 95.0,  100, dc.last_night_95,  eod=True)
        sec100_t1,  sec_mar_t1  = _fetch_rolls_netted(office_val, sql_ac, 95.0,  100, dc.t1_95,          eod=True)
        sec10_cur,  _           = _fetch_rolls_netted(office_val, sql_ac, 100.0,  10, dc.today_str,      eod=False)
        sec10_sod,  _           = _fetch_rolls_netted(office_val, sql_ac, 100.0,  10, dc.last_night_100, eod=True)
        sec10_t1,   _           = _fetch_rolls_netted(office_val, sql_ac, 100.0,  10, dc.t1_100,         eod=True)

        if sec100_cur  is None: sec100_cur  = sec100_sod
        if sec_mar_cur is None: sec_mar_cur = sec_mar_sod
        if sec10_cur   is None: sec10_cur   = sec10_sod

        section_row = {
            "Product": section_name, "Asset_Class": None, "_rowType": "section",
            "VaR_100D":        abs(sec100_cur) if sec100_cur is not None else None,
            "Delta_100D":      _d(sec100_cur, sec100_sod),
            "Delta_100D_t1":   _d(sec100_cur, sec100_t1),
            "VaR_10D":         abs(sec10_cur)  if sec10_cur  is not None else None,
            "Delta_10D":       _d(sec10_cur,  sec10_sod),
            "Delta_10D_t1":    _d(sec10_cur,  sec10_t1),
            "Margin":          sec_mar_cur,
            "Delta_Margin":    _d(sec_mar_cur, sec_mar_sod),
            "Delta_Margin_t1": _d(sec_mar_cur, sec_mar_t1),
            "_pnl1d": None, "_pnl5d": None,
        }

        df = _build_product_df(office_val, product_acs,
                               dc.last_night_95, dc.t1_95, dc.today_str,
                               dc.last_night_100, dc.t1_100)
        df = df[df["Product"].isin(product_filter)]

        rows = [section_row]
        for _, row in df.sort_values("VaR_100D", ascending=False).iterrows():
            rows.append(_make_product_row(row))

        result.append({"section": section_name, "rows": rows})

    return result
