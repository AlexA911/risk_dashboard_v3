"""
data/db_rollview.py — Queries for the Roll Risk tab.

Two views:

  RISK VIEW  (get_roll_risk)
    Fixed Income | Equities — full product breakdown with currency subgroups.
    Section total = Cumulus netted from Rates / Equity Indices asset classes.

  ROLLS VIEW  (get_roll_risk_rolls)
    FI Rolls | Equity Rolls — flat product list, no subgroups.
    Section total = Cumulus netted from Asset_Class IN ('FI Rolls','Equity Rolls').
    Products = BOND_PRODUCTS for FI Rolls; all equities for Equity Rolls.
    Product iVaRs are informational — pulled from Rates/Equities data.
"""

import pandas as pd
from data.db_connection import get_connection
from data.reference import EXCLUDED_OFFICES, FUTURES_FIRST_OFFICE

# ─── Risk view sector definitions ─────────────────────────────────────────────

ROLL_SECTORS = {
    "Fixed Income": {
        "asset_classes": [
            "USD Rates", "GBP Rates", "EUR Rates",
            "CAD Rates", "AUD Rates", "CHF Rates",
        ],
        "subgroups": ["USD", "GBP", "EUR", "CAD", "AUD", "CHF"],
        "subgroup_asset_classes": {
            "USD": ["USD Rates"],
            "GBP": ["GBP Rates"],
            "EUR": ["EUR Rates"],
            "CAD": ["CAD Rates"],
            "AUD": ["AUD Rates"],
            "CHF": ["CHF Rates"],
        },
    },
    "Equities": {
        "asset_classes": ["Equity Indices"],
        "subgroups": ["Equity Indices"],
        "subgroup_asset_classes": {
            "Equity Indices": ["Equity Indices"],
        },
    },
}

# ─── Product → subgroup mapping ───────────────────────────────────────────────

PRODUCT_SUBGROUP = {
    # USD
    "1-Month SOFR":                    "USD", "30 Day Fed Fund":               "USD",
    "3-Month SOFR":                    "USD", "SOFR":                          "USD",
    "US 10Yr T-Note":                  "USD", "US 2Yr T-Note":                 "USD",
    "US 30Yr T-Bond":                  "USD", "US 30Yr T-Bond(ZB)":            "USD",
    "US 5Yr T-Note":                   "USD", "US Ultra 10Yr T-Note":          "USD",
    "US Ultra Bond":                   "USD", "U.S. 10 Year Treasury Bond":    "USD",
    "U.S. 10-Year T-Note":             "USD", "U.S. 2-Year T-Note":            "USD",
    "U.S. 3 Year Treasury Bond":       "USD", "U.S. 30 Day Federal Funds":     "USD",
    "U.S. 5-Year T-Note":              "USD", "U.S. Treasury Bond":            "USD",
    # GBP
    "Gilt (Long)":                     "GBP", "MPC Dated SONIA Futures":       "GBP",
    "Three Month SONIA (CME)":         "GBP", "Three Month SONIA (ICE)":       "GBP",
    "Three-Month Sonia Index":         "GBP", "UK Long Gilt":                  "GBP",
    # EUR
    "Bobl":                            "EUR", "Bund":                          "EUR",
    "Buxl":                            "EUR", "Euribor":                       "EUR",
    "Euro-Bobl":                       "EUR", "Euro-Bund":                     "EUR",
    "Euro-OAT":                        "EUR", "Euro-Schatz":                   "EUR",
    "French 10Yr Oat":                 "EUR", "Italian 2Yr BTP":               "EUR",
    "Italian BTP":                     "EUR", "Long-Term Euro-BTP":            "EUR",
    "Schatz":                          "EUR", "Three Month ESTR Indexed Future":"EUR",
    "Three-Month Euribor":             "EUR",
    # CAD
    "CGB":                             "CAD", "CGF":                           "CAD",
    "CGZ":                             "CAD", "One Month CORRA Futures":       "CAD",
    "One-month CORRA":                 "CAD", "Three-month CORRA":             "CAD",
    "Three-Month CORRA Futures":       "CAD",
    # AUD
    "10Yr Aus Bond":                   "AUD", "3Yr Aus Bill":                  "AUD",
    "5Yr Aus Bond":                    "AUD", "90 Day Aus Bill":               "AUD",
    # CHF
    "Three Month SARON Index":         "CHF", "Three Month Saron Index Future":"CHF",
    # Equities
    "CAC40":                           "Equity Indices",
    "Dax":                             "Equity Indices",
    "E-Mini Russell 2000":             "Equity Indices",
    "E-mini S&P Midcap 400":           "Equity Indices",
    "EuroStocks":                      "Equity Indices",
    "FTSE":                            "Equity Indices",
    "Mini Dow":                        "Equity Indices",
    "Mini-Dax":                        "Equity Indices",
    "MSCI EAFE Index":                 "Equity Indices",
    "MSCI Emerging Markets Index":     "Equity Indices",
    "S&P/TSX 60 Index":                "Equity Indices",
    "SPI 200 Index":                   "Equity Indices",
    "STOXX Europe 600":                "Equity Indices",
    "Swiss Market Index (SMI)":        "Equity Indices",
    "e-Mini Nasdaq 100":               "Equity Indices",
    "e-Mini S&P 500":                  "Equity Indices",
    "Micro E-Mini S&P 500 Futures":    "Equity Indices",
    "Micro E-Mini Nasdaq 100":         "Equity Indices",
}

# ─── Bond products for Rolls view ─────────────────────────────────────────────
# STIRs excluded: SOFR, Fed Funds, SONIA, Euribor, ESTR, CORRA, SARON variants.
# CHF excluded entirely (all CHF products are STIRs).

BOND_PRODUCTS = {
    # USD bonds
    "US Ultra Bond", "US 30Yr T-Bond", "US 30Yr T-Bond(ZB)",
    "US Ultra 10Yr T-Note", "US 10Yr T-Note", "US 5Yr T-Note", "US 2Yr T-Note",
    "U.S. Treasury Bond", "U.S. 10 Year Treasury Bond", "U.S. 10-Year T-Note",
    "U.S. 5-Year T-Note", "U.S. 2-Year T-Note", "U.S. 3 Year Treasury Bond",
    # GBP bonds
    "Gilt (Long)", "UK Long Gilt",
    # EUR bonds
    "Bund", "Bobl", "Schatz", "Buxl",
    "Euro-Bund", "Euro-Bobl", "Euro-Schatz", "Euro-OAT",
    "French 10Yr Oat", "Italian BTP", "Italian 2Yr BTP", "Long-Term Euro-BTP",
    # CAD bonds
    "CGB", "CGF", "CGZ",
    # AUD bonds
    "10Yr Aus Bond", "3Yr Aus Bill", "5Yr Aus Bond", "90 Day Aus Bill",
}

EQUITY_PRODUCTS = {
    "CAC40", "Dax", "E-Mini Russell 2000", "E-mini S&P Midcap 400",
    "EuroStocks", "FTSE", "Mini Dow", "Mini-Dax", "MSCI EAFE Index",
    "MSCI Emerging Markets Index", "S&P/TSX 60 Index", "SPI 200 Index",
    "STOXX Europe 600", "Swiss Market Index (SMI)", "e-Mini Nasdaq 100",
    "e-Mini S&P 500", "Micro E-Mini S&P 500 Futures", "Micro E-Mini Nasdaq 100",
}

# Rolls view sector definitions
ROLL_SECTORS_ROLLS = {
    "FI Rolls": {
        "sql_asset_class":     "FI Rolls",       # for section netted total
        "product_asset_classes": [               # for underlying product rows
            "USD Rates", "GBP Rates", "EUR Rates", "CAD Rates", "AUD Rates",
        ],
        "product_filter": BOND_PRODUCTS,
    },
    "Equity Rolls": {
        "sql_asset_class":     "Equity Rolls",
        "product_asset_classes": ["Equity Indices"],
        "product_filter": EQUITY_PRODUCTS,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_latest_eod_dates(confidence: float, lookback: int, n: int = 1) -> list:
    query = """
        SELECT TOP (?) CONVERT(VARCHAR(10), Date, 23) AS Date
        FROM dbo.OfficeRisk
        WHERE IsEOD      = 1
          AND Confidence = ?
          AND Lookback   = ?
        GROUP BY Date
        ORDER BY Date DESC
    """
    with get_connection() as conn:
        df = pd.read_sql(query, conn, params=[n, confidence, lookback])
    return df["Date"].tolist()


def _today() -> str:
    return pd.Timestamp.now().strftime("%Y-%m-%d")


def _d(a, b):
    return (a - b) if a is not None and b is not None else None


def _fetch_products(office_val, asset_classes, confidence, lookback, date, eod):
    """Fetch product-level iVaR + Margin for a given office and asset class list."""
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
    """Fetch Cumulus netted iVaR + Margin for a list of asset classes (Risk view)."""
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
    """
    Fetch Cumulus netted iVaR + Margin for FI Rolls / Equity Rolls directly
    from the Asset_Class rows (Analyst = Office, Product = Asset_Class).
    """
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
                      last_night_95, t1_95, today,
                      last_night_100, t1_100):
    """Fetch and merge product rows across all configs/dates."""
    sod_95  = _fetch_products(office_val, asset_classes, 95.0,  100, last_night_95,  eod=True)
    t1_95_  = _fetch_products(office_val, asset_classes, 95.0,  100, t1_95,          eod=True)
    cur_95  = _fetch_products(office_val, asset_classes, 95.0,  100, today,           eod=False)
    sod_100 = _fetch_products(office_val, asset_classes, 100.0,  10, last_night_100,  eod=True)
    t1_100_ = _fetch_products(office_val, asset_classes, 100.0,  10, t1_100,          eod=True)
    cur_100 = _fetch_products(office_val, asset_classes, 100.0,  10, today,            eod=False)

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
        "_pnl1d":          None,  # placeholder — HAWK API not yet wired
        "_pnl5d":          None,  # placeholder — HAWK API not yet wired
    }


def _get_dates():
    today          = _today()
    eod_95         = _get_latest_eod_dates(95.0,  100, n=2)
    eod_100        = _get_latest_eod_dates(100.0,  10, n=2)
    last_night_95  = eod_95[0]  if eod_95  else today
    t1_95          = eod_95[1]  if len(eod_95)  > 1 else last_night_95
    last_night_100 = eod_100[0] if eod_100 else today
    t1_100         = eod_100[1] if len(eod_100) > 1 else last_night_100
    return today, last_night_95, t1_95, last_night_100, t1_100


# ─────────────────────────────────────────────────────────────────────────────
# Public: Risk view
# ─────────────────────────────────────────────────────────────────────────────

def get_roll_risk(location: str = "Total") -> list[dict]:
    """
    Risk view — Fixed Income and Equities with currency subgroups.
    Section total = Cumulus netted from Rates / Equity Indices.
    """
    today, last_night_95, t1_95, last_night_100, t1_100 = _get_dates()
    office_val = FUTURES_FIRST_OFFICE if location == "Total" else location

    result = []

    for section_name, cfg in ROLL_SECTORS.items():
        asset_classes = cfg["asset_classes"]
        subgroups     = cfg["subgroups"]
        sg_acs        = cfg["subgroup_asset_classes"]

        df = _build_product_df(office_val, asset_classes,
                               last_night_95, t1_95, today,
                               last_night_100, t1_100)
        df["Subgroup"] = df["Product"].map(PRODUCT_SUBGROUP).fillna("Other")

        # Section summary row
        sec100_cur, sec_mar_cur = _fetch_subgroup_netted(office_val, asset_classes, 95.0,  100, today,          eod=False)
        sec100_sod, sec_mar_sod = _fetch_subgroup_netted(office_val, asset_classes, 95.0,  100, last_night_95,  eod=True)
        sec100_t1,  sec_mar_t1  = _fetch_subgroup_netted(office_val, asset_classes, 95.0,  100, t1_95,          eod=True)
        sec10_cur,  _           = _fetch_subgroup_netted(office_val, asset_classes, 100.0,  10, today,          eod=False)
        sec10_sod,  _           = _fetch_subgroup_netted(office_val, asset_classes, 100.0,  10, last_night_100, eod=True)
        sec10_t1,   _           = _fetch_subgroup_netted(office_val, asset_classes, 100.0,  10, t1_100,         eod=True)

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
            "_pnl1d":          None,
            "_pnl5d":          None,
        }

        rows = [section_row]

        for sg in subgroups:
            acs = sg_acs.get(sg, [])
            var100_cur, mar_cur = _fetch_subgroup_netted(office_val, acs, 95.0,  100, today,          eod=False)
            var100_sod, mar_sod = _fetch_subgroup_netted(office_val, acs, 95.0,  100, last_night_95,  eod=True)
            var100_t1,  mar_t1  = _fetch_subgroup_netted(office_val, acs, 95.0,  100, t1_95,          eod=True)
            var10_cur,  _       = _fetch_subgroup_netted(office_val, acs, 100.0,  10, today,          eod=False)
            var10_sod,  _       = _fetch_subgroup_netted(office_val, acs, 100.0,  10, last_night_100, eod=True)
            var10_t1,   _       = _fetch_subgroup_netted(office_val, acs, 100.0,  10, t1_100,         eod=True)

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
                "_pnl1d":          None,
                "_pnl5d":          None,
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
    Rolls view — FI Rolls and Equity Rolls.
    Section total = Cumulus netted from Asset_Class = 'FI Rolls' / 'Equity Rolls'.
    Products = BOND_PRODUCTS for FI Rolls; EQUITY_PRODUCTS for Equity Rolls.
    No subgroup layer — flat list sorted by VaR_100D desc.
    """
    today, last_night_95, t1_95, last_night_100, t1_100 = _get_dates()
    office_val = FUTURES_FIRST_OFFICE if location == "Total" else location

    result = []

    for section_name, cfg in ROLL_SECTORS_ROLLS.items():
        sql_ac        = cfg["sql_asset_class"]
        product_acs   = cfg["product_asset_classes"]
        product_filter = cfg["product_filter"]

        # ── Section netted total from FI Rolls / Equity Rolls rows ───────────
        sec100_cur, sec_mar_cur = _fetch_rolls_netted(office_val, sql_ac, 95.0,  100, today,          eod=False)
        sec100_sod, sec_mar_sod = _fetch_rolls_netted(office_val, sql_ac, 95.0,  100, last_night_95,  eod=True)
        sec100_t1,  sec_mar_t1  = _fetch_rolls_netted(office_val, sql_ac, 95.0,  100, t1_95,          eod=True)
        sec10_cur,  _           = _fetch_rolls_netted(office_val, sql_ac, 100.0,  10, today,          eod=False)
        sec10_sod,  _           = _fetch_rolls_netted(office_val, sql_ac, 100.0,  10, last_night_100, eod=True)
        sec10_t1,   _           = _fetch_rolls_netted(office_val, sql_ac, 100.0,  10, t1_100,         eod=True)

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
            "_pnl1d":          None,
            "_pnl5d":          None,
        }

        # ── Underlying products filtered to bonds / equities ──────────────────
        df = _build_product_df(office_val, product_acs,
                               last_night_95, t1_95, today,
                               last_night_100, t1_100)
        df = df[df["Product"].isin(product_filter)]

        rows = [section_row]
        for _, row in df.sort_values("VaR_100D", ascending=False).iterrows():
            rows.append(_make_product_row(row))

        result.append({"section": section_name, "rows": rows})

    return result
