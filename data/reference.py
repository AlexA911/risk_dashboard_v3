"""
data/reference.py — Single source of truth for all cross-system reference data.

This file owns every static mapping and lookup used across the dashboard.
When a new product appears, office is added, or data source arrives —
this is the only file that needs updating.

Sections:
  1.  Excluded offices
  2.  Office display order
  3.  Sector display order
  4.  FF_Risk: Sector → Asset class mapping
  5.  FF_Risk: Asset class → Sector mapping (inverse)
  6.  FF_Risk: Subgroup netted asset classes
  7.  FF_Risk: Subgroup display order per sector
  8.  FF_Risk: Product → Subgroup mapping
  9.  HAWK: AssetClass + SubAssetClass → Dashboard sector
  10. HAWK: Product-level sector overrides
  11. HAWK: Parquet column names + helper functions
  12. Roll Risk tab reference data
"""

# ─── 1. Excluded offices ──────────────────────────────────────────────────────

EXCLUDED_OFFICES = [
    "London P&C",    # wound down, no active traders
    "Mumbai",        # excluded from VaR scope
    "Montreal",      # excluded from dashboard views
    "FI Rolls",      # Cumulus netting group pseudo-office
    "Equity Rolls",  # Cumulus netting group pseudo-office
]

FUTURES_FIRST_OFFICE = "Futures First"


# ─── 2. Office display order ──────────────────────────────────────────────────

OFFICE_DISPLAY_ORDER = [
    "Futures First",
    "Warsaw",
    "Poznan",
    "Swansea",
    "London MM",
    "London Macro",
    "London Seniors",
    "Dubai 6",
    "Gdansk",
    "IDC Hangzhou",
]


# ─── 3. Sector display order ──────────────────────────────────────────────────

SECTOR_ORDER = [
    "Energy", "Rates", "Equities", "Volatility",
    "FX", "Softs", "Ags", "Metals", "Crypto",
]


# ─── 4. FF_Risk: Sector → Asset classes ──────────────────────────────────────

SECTOR_ASSET_CLASSES = {
    "Energy":     ["Oils", "Oils - Crude", "WTI", "NG", "Oils - Refined", "Power & Carbon"],
    "Rates":      ["USD Rates", "GBP Rates", "EUR Rates", "CAD Rates", "AUD Rates", "CHF Rates"],
    "Equities":   ["Equity Indices"],
    "Volatility": ["Volatility Indices"],
    "FX":         ["FX"],
    "Softs":      ["Sugar", "Cocoa", "Coffee", "Cotton", "Softs"],
    "Ags":        ["Grains", "Live Stock", "Dairy"],
    "Metals":     ["Metal Base", "Metal Precious"],
    "Crypto":     ["Crypto"],
}


# ─── 5. FF_Risk: Asset class → Sector (inverse lookup) ───────────────────────

SECTOR_MAP = {
    "Oils - Crude":       "Energy",
    "WTI":                "Energy",
    "NG":                 "Energy",
    "Oils - Refined":     "Energy",
    "Oils":               "Energy",
    "USD Rates":          "Rates",
    "GBP Rates":          "Rates",
    "EUR Rates":          "Rates",
    "CAD Rates":          "Rates",
    "AUD Rates":          "Rates",
    "CHF Rates":          "Rates",
    "Equity Indices":     "Equities",
    "Volatility Indices": "Volatility",
    "FX":                 "FX",
    "Sugar":              "Softs",
    "Cocoa":              "Softs",
    "Coffee":             "Softs",
    "Cotton":             "Softs",
    "Softs":              "Softs",
    "Grains":             "Ags",
    "Live Stock":         "Ags",
    "Dairy":              "Ags",
    "Metal Base":         "Metals",
    "Metal Precious":     "Metals",
    "Crypto":             "Crypto",
}


# ─── 6. FF_Risk: Subgroup netted asset classes ────────────────────────────────

SUBGROUP_NETTED_ASSET_CLASSES = {
    # Energy
    "Oils Total":         ["Oils"],
    "Oils - Crude":       ["Oils - Crude"],
    "WTI":                ["WTI"],
    "Oils - Refined":      ["Oils - Refined"],
    "NG":                 ["NG"],
    "Power & Carbon":     [],
    # Rates
    "USD":                ["USD Rates"],
    "GBP":                ["GBP Rates"],
    "EUR":                ["EUR Rates"],
    "CAD":                ["CAD Rates"],
    "AUD":                [],
    "CHF":                [],
    # Metals
    "Precious":           ["Metal Precious"],
    "Base":               ["Metal Base"],
    # Ags
    "Grains":             ["Grains"],
    "Livestock":          ["Live Stock"],
    "Dairy":              ["Dairy"],
    # Softs
    "Cocoa":              ["Cocoa"],
    "Coffee":             ["Coffee"],
    "Sugar":              ["Sugar"],
    "Cotton":             [],
    "OJ":                 [],
    # Passthrough sectors (no subgroups)
    "Equity Indices":     ["Equity Indices"],
    "Volatility Indices": ["Volatility Indices"],
    "FX":                 ["FX"],
    "Crypto":             ["Crypto"],
}


# ─── 7. FF_Risk: Subgroup display order per sector ────────────────────────────

SUBGROUP_ORDER = {
    "Energy":     ["Oils Total", "Oils - Crude", "WTI", "Oils - Refined", "NG", "Power & Carbon"],
    "Rates":      ["USD", "GBP", "EUR", "CAD", "AUD", "CHF"],
    "Metals":     ["Precious", "Base"],
    "Ags":        ["Grains", "Livestock", "Dairy"],
    "Softs":      ["Cocoa", "Coffee", "Sugar", "Cotton", "OJ"],
}


# ─── 8. FF_Risk: Product → Subgroup mapping ───────────────────────────────────
# Used by db_summary.py to interleave subgroup header rows in the product table.

PRODUCT_SUBGROUP = {
    # Energy: Oils
    "Abu Dhabi Murban Crude Oil Futures":                      "Oils - Crude",
    "Brent Crude":                                             "Oils - Crude",
    "Brent Crude Oil":                                         "Oils - Crude",
    "Dubai 1st line Crude Futures":                            "Oils - Crude",
    "Dubai Crude Oil":                                         "Oils - Crude",
    "ICE Brent Crude":                                         "Oils - Crude",
    "ICE Murban Crude Oil Futures":                            "Oils - Crude",
    "Murban Crude Oil":                                        "Oils - Crude",
    "Nymex Brent Crude":                                       "Oils - Crude",
    # Energy: WTI
    "Nymex Light Sweet":                                       "WTI",
    "WTI Crude Oil":                                           "WTI",
    "ICE WTI Crude":                                           "WTI",
    "ICE WTI Crude TAS":                                       "WTI",
    "Micro WTI Crude Oil Futures":                             "WTI",
    # Energy: Natural Gas
    "ICE Dutch TTF Gas Futures":                               "NG",
    "ICE UK Natural Gas":                                      "NG",
    "Micro Henry Hub Natural Gas":                             "NG",
    "Natural Gas":                                             "NG",
    "Natural Gas (Henry Hub) Penultimate Financial Futures":   "NG",
    "Natural Gas (HH) (Henry Hub) Last-day Financial Futures": "NG",
    # Energy: Oil Refined
    "Heating Oil":                                             "Oils - Refined",
    "ICE LS GasOil":                                           "Oils - Refined",
    "ICE LS GasOil TAS":                                       "Oils - Refined",
    "Low Sulphur Gasoil":                                      "Oils - Refined",
    "NY Harbor ULSD":                                          "Oils - Refined",
    "RBOB Gasoline":                                           "Oils - Refined",
    # Energy: Power & Carbon
    "EEX French Power Bs M Ftr":                               "Power & Carbon",
    "EEX German Power Bs M Ftr":                               "Power & Carbon",
    "EEX Italian Power Bs M Ftr":                              "Power & Carbon",
    "ICE ECX CFI/EUA":                                         "Power & Carbon",
    # Rates: USD
    "1-Month SOFR":                                            "USD",
    "30 Day Fed Fund":                                         "USD",
    "3-Month SOFR":                                            "USD",
    "SOFR":                                                    "USD",
    "U.S. 10 Year Treasury Bond":                              "USD",
    "U.S. 10-Year T-Note":                                     "USD",
    "U.S. 2-Year T-Note":                                      "USD",
    "U.S. 3 Year Treasury Bond":                               "USD",
    "U.S. 30 Day Federal Funds":                               "USD",
    "U.S. 5-Year T-Note":                                      "USD",
    "U.S. Treasury Bond":                                      "USD",
    "US 10Yr T-Note":                                          "USD",
    "US 2Yr T-Note":                                           "USD",
    "US 30Yr T-Bond":                                          "USD",
    "US 30Yr T-Bond(ZB)":                                      "USD",
    "US 5Yr T-Note":                                           "USD",
    "US Ultra 10Yr T-Note":                                    "USD",
    "US Ultra Bond":                                           "USD",
    # Rates: GBP
    "Gilt (Long)":                                             "GBP",
    "MPC Dated SONIA Futures":                                 "GBP",
    "Three Month SONIA (CME)":                                 "GBP",
    "Three Month SONIA (ICE)":                                 "GBP",
    "Three-Month Sonia Index":                                 "GBP",
    "UK Long Gilt":                                            "GBP",
    # Rates: EUR
    "Bobl":                                                    "EUR",
    "Bund":                                                    "EUR",
    "Buxl":                                                    "EUR",
    "Euribor":                                                 "EUR",
    "Euro-Bobl":                                               "EUR",
    "Euro-Bund":                                               "EUR",
    "Euro-OAT":                                                "EUR",
    "Euro-Schatz":                                             "EUR",
    "French 10Yr Oat":                                         "EUR",
    "Italian 2Yr BTP":                                         "EUR",
    "Italian BTP":                                             "EUR",
    "Long-Term Euro-BTP":                                      "EUR",
    "Schatz":                                                  "EUR",
    "Three Month ESTR Indexed Future":                         "EUR",
    "Three-Month Euribor":                                     "EUR",
    # Rates: CAD
    "CGB":                                                     "CAD",
    "CGF":                                                     "CAD",
    "CGZ":                                                     "CAD",
    "One Month CORRA Futures":                                 "CAD",
    "One-month CORRA":                                         "CAD",
    "Three-month CORRA":                                       "CAD",
    "Three-Month CORRA Futures":                               "CAD",
    # Rates: AUD
    "10Yr Aus Bond":                                           "AUD",
    "3Yr Aus Bill":                                            "AUD",
    "5Yr Aus Bond":                                            "AUD",
    "90 Day Aus Bill":                                         "AUD",
    # Rates: CHF
    "Three Month SARON Index":                                 "CHF",
    "Three Month Saron Index Future":                          "CHF",
    # Equities
    "CAC40":                                                   "Equity Indices",
    "Dax":                                                     "Equity Indices",
    "E-Mini Russell 2000":                                     "Equity Indices",
    "E-mini S&P Midcap 400":                                   "Equity Indices",
    "EuroStocks":                                              "Equity Indices",
    "FTSE":                                                    "Equity Indices",
    "Mini Dow":                                                "Equity Indices",
    "Mini-Dax":                                                "Equity Indices",
    "MSCI EAFE Index":                                         "Equity Indices",
    "MSCI Emerging Markets Index":                             "Equity Indices",
    "S&P/TSX 60 Index":                                        "Equity Indices",
    "SPI 200 Index":                                           "Equity Indices",
    "STOXX Europe 600":                                        "Equity Indices",
    "Swiss Market Index (SMI)":                                "Equity Indices",
    "e-Mini Nasdaq 100":                                       "Equity Indices",
    "e-Mini S&P 500":                                          "Equity Indices",
    # Volatility
    "CBOE Volatility Index Future":                            "Volatility Indices",
    "VSTOXX Mini":                                             "Volatility Indices",
    # FX
    "AUD/USD-FX":                                              "FX",
    "AUD/USD-FX (SGX)":                                        "FX",
    "BRL/USD-FX (CME)":                                        "FX",
    "CAD/USD-FX":                                              "FX",
    "CHF/USD-FX":                                              "FX",
    "CNH/SGD-FX (SGX)":                                        "FX",
    "CNY/USD-FX (SGX)":                                        "FX",
    "E-micro AUD/USD-FX":                                      "FX",
    "E-micro CAD/USD-FX":                                      "FX",
    "E-micro EUR/USD-FX":                                      "FX",
    "E-micro GBP/USD-FX":                                      "FX",
    "E-micro JPY/USD-FX":                                      "FX",
    "EUR/CHF-FX":                                              "FX",
    "EUR/GBP-FX":                                              "FX",
    "EUR/JPY-FX":                                              "FX",
    "EUR/USD-FX":                                              "FX",
    "GBP/JPY-FX":                                              "FX",
    "GBP/USD-FX":                                              "FX",
    "INR/USD-FX":                                              "FX",
    "INR/USD-FX (SGX)":                                        "FX",
    "JPY/USD-FX":                                              "FX",
    "MICRO USD/JPY FUTURES":                                   "FX",
    "MXN/USD-FX":                                              "FX",
    "NZD/USD-FX":                                              "FX",
    "RUB/USD":                                                 "FX",
    "SGX KRW/USD FX Futures (Mini)":                           "FX",
    "Standard USD/JPY-FX (SGX)":                               "FX",
    "USD/CNH-FX (SGX)":                                        "FX",
    "USD/NOK-FX (CME)":                                        "FX",
    "USD/SEK-FX (CME)":                                        "FX",
    "ZAR/USD-FX":                                              "FX",
    # Softs: Cocoa
    "Cocoa (ICE US)":                                          "Cocoa",
    "Cocoa (Liffe)":                                           "Cocoa",
    # Softs: Coffee
    'Coffee "C"':                                              "Coffee",
    "Coffee (Liffe)":                                          "Coffee",
    # Softs: Sugar
    "Sugar No11":                                              "Sugar",
    "Sugar No11 TAS":                                          "Sugar",
    "Sugar (Liffe) White":                                     "Sugar",
    # Softs: Cotton
    "Cotton No2":                                              "Cotton",
    "Cotton No2 TAS":                                          "Cotton",
    # Softs: OJ
    "FCOJ":                                                    "OJ",
    # Ags: Grains
    "Canola":                                                  "Grains",
    "Canola Oil":                                              "Grains",
    "Corn":                                                    "Grains",
    "Corn (CBOT)":                                             "Grains",
    "Corn (CBOT) TAS":                                         "Grains",
    "Corn (Liffe)":                                            "Grains",
    "Milling Wheat":                                           "Grains",
    "Micro Soybean Futures":                                   "Grains",
    "Micro Soybean Meal Futures":                              "Grains",
    "Micro Soybean Oil Futures":                               "Grains",
    "Oats":                                                    "Grains",
    "Rapeseed":                                                "Grains",
    "Rice":                                                    "Grains",
    "Rough Rice":                                              "Grains",
    "Soybean (CBOT)":                                          "Grains",
    "Soybean (CBOT) TAS":                                      "Grains",
    "Soybean Meal":                                            "Grains",
    "Soybean Meal (CBOT)":                                     "Grains",
    "Soybean Meal (CBOT) TAS":                                 "Grains",
    "Soybean Oil":                                             "Grains",
    "Soybean Oil (CBOT)":                                      "Grains",
    "Soybeans":                                                "Grains",
    "Wheat":                                                   "Grains",
    "Wheat (CBOT)":                                            "Grains",
    "Wheat (KCBT)":                                            "Grains",
    # Ags: Livestock
    "Feeder Cattle":                                           "Livestock",
    "Lean Hogs":                                               "Livestock",
    "Live Cattle":                                             "Livestock",
    "Rubber":                                                  "Livestock",
    # Ags: Dairy
    "Cash Settled Cheese":                                     "Dairy",
    "Cheese":                                                  "Dairy",
    "Class III Milk":                                          "Dairy",
    "Milk Class III":                                          "Dairy",
    # Metals: Precious
    "100oz Silver Futures":                                    "Precious",
    "Gold":                                                    "Precious",
    "Gold (COMEX)":                                            "Precious",
    "Gold (COMEX) TAS":                                        "Precious",
    "Micro Gold":                                              "Precious",
    "Micro Silver (1000 Troy Oz)":                             "Precious",
    "Palladium":                                               "Precious",
    "Platinum":                                                "Precious",
    "Silver":                                                  "Precious",
    "Silver (1000 Troy Oz)":                                   "Precious",
    "Silver (COMEX)":                                          "Precious",
    # Metals: Base
    "Aluminium (COMEX)":                                       "Base",
    "Copper":                                                  "Base",
    "Copper (COMEX)":                                          "Base",
    "Iron Ore":                                                "Base",
    "Lumber":                                                  "Base",
    "Lumber Futures":                                          "Base",
    "Micro Copper":                                            "Base",
    "SICOM TSR 20 Rubber":                                     "Base",
    "TSI Iron Ore CFR China 62% Index":                        "Base",
    # Crypto
    "Bitcoin Futures (CME)":                                   "Crypto",
    "Ether Futures (CME)":                                     "Crypto",
    "Micro Bitcoin Futures":                                   "Crypto",
    "Micro Ether Futures (CME)":                               "Crypto",
}


# ─── 9. HAWK: AssetClass + SubAssetClass → Dashboard sector ──────────────────

HAWK_SECTOR_MAP: dict[tuple[str, str], str | None] = {
    ("Energy",           "Energy"):           "Energy",
    ("STIRs",            "American STIRs"):   "Rates",
    ("STIRs",            "European STIRs"):   "Rates",
    ("STIRs",            "Asian STIRs"):      "Rates",
    ("STIRs",            "Australian STIRs"): "Rates",
    ("STIRs",            "Brazilian DI"):     "Rates",
    ("Indices & Stocks", "Indices & Stocks"): "Equities",
    ("Commodity",        "Softs"):            "Softs",
    ("Commodity",        "Grains & Oils"):    "Ags",
    ("Commodity",        "Livestock"):        "Ags",
    ("Commodity",        "Wood&Rubber"):      "Ags",
    ("Commodity",        "Metals"):           "Metals",
    ("Currency",         "Currency"):         "FX",
    ("Crypto",           "Crypto"):           "Crypto",
    ("Other Product",    "Other Product"):    None,
    ("Option Product",   "Option Product"):   None,
    ("Commodity",        "Other Product"):    None,
    ("Energy",           "Other Product"):    None,
    ("Indices & Stocks", "Other Product"):    None,
    ("Crypto",           "Other Product"):    None,
}


# ─── 10. HAWK: Product-level sector overrides ─────────────────────────────────

HAWK_PRODUCT_SECTOR_OVERRIDES: dict[str, str | None] = {
    "EFVS":  "Volatility",   # VSTOXX Futures
    "VIXXF": "Volatility",   # VIX Futures
    "DX":    "FX",           # US Dollar Index
}


# ─── 11. HAWK: Parquet column names + helper functions ───────────────────────

HAWK_ANALYST_PNL_COL = "GrossPnL"
HAWK_PRODUCT_PNL_COL = "PnL"


def hawk_sector(asset_class: str, sub_asset_class: str, product: str) -> str | None:
    if product in HAWK_PRODUCT_SECTOR_OVERRIDES:
        return HAWK_PRODUCT_SECTOR_OVERRIDES[product]
    return HAWK_SECTOR_MAP.get((asset_class, sub_asset_class), None)


def ff_risk_sector(asset_class: str) -> str | None:
    return SECTOR_MAP.get(asset_class, None)


def sort_offices(offices: list[str]) -> list[str]:
    order = {name: i for i, name in enumerate(OFFICE_DISPLAY_ORDER)}
    return sorted(offices, key=lambda o: (order.get(o, len(OFFICE_DISPLAY_ORDER)), o))


def sort_sectors(sectors: list[str]) -> list[str]:
    order = {name: i for i, name in enumerate(SECTOR_ORDER)}
    return sorted(sectors, key=lambda s: (order.get(s, len(SECTOR_ORDER)), s))


# ─── 12. Roll Risk tab reference data ────────────────────────────────────────
# All static data for db_rollview.py and db_hawk.py.
# Equity Rolls reuses PRODUCT_SUBGROUP (section 8) — no separate list needed.

# Asset class → subgroup label for the Risk view.
# Derived directly from Asset_Class — no per-product mapping required.
ROLL_AC_TO_SUBGROUP = {
    "USD Rates":      "USD",
    "GBP Rates":      "GBP",
    "EUR Rates":      "EUR",
    "CAD Rates":      "CAD",
    "AUD Rates":      "AUD",
    "CHF Rates":      "CHF",
    "Equity Indices": "Equity Indices",
}

# Risk view: Fixed Income (all Rates, incl. STIRs) + Equities
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

# FI roll products: bond futures only — STIRs and CHF (all STIRs) excluded.
# Equity Rolls filter = all "Equity Indices" entries in PRODUCT_SUBGROUP above.
ROLL_FI_PRODUCTS = {
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
    "10Yr Aus Bond", "3Yr Aus Bill", "5Yr Aus Bond",
}

# Rolls view: FI Rolls (bonds only) and Equity Rolls (all equity index products).
# Equity product filter derived from PRODUCT_SUBGROUP at module load — no duplication.
ROLL_SECTORS_ROLLS = {
    "FI Rolls": {
        "sql_asset_class":       "FI Rolls",
        "product_asset_classes": [
            "USD Rates", "GBP Rates", "EUR Rates", "CAD Rates", "AUD Rates",
        ],
        "product_filter": ROLL_FI_PRODUCTS,
    },
    "Equity Rolls": {
        "sql_asset_class":       "Equity Rolls",
        "product_asset_classes": ["Equity Indices"],
        "product_filter": {p for p, sg in PRODUCT_SUBGROUP.items() if sg == "Equity Indices"},
    },
}

# HAWK exchange code → ProductRisk product name for Roll Risk P&L.
# Bond codes only (no STIRs) + equity codes.
# Multiple codes mapping to the same name are summed (e.g. TB + UBE).
HAWK_ROLL_PRODUCT_MAP: dict[str, str] = {
    # USD bonds
    "CMETN":  "US Ultra 10Yr T-Note",
    "FV":     "US 5Yr T-Note",
    "TB":     "US Ultra Bond",
    "TU":     "US 2Yr T-Note",
    "TY":     "US 10Yr T-Note",
    "UBE":    "US Ultra Bond",        # same row as TB — summed
    # GBP bonds
    "R":      "Gilt (Long)",
    # EUR bonds
    "FBTP":   "Italian BTP",
    "FBTS":   "Italian 2Yr BTP",
    "FGBL":   "Bund",
    "FGBM":   "Bobl",
    "FGBS":   "Schatz",
    "FGBX":   "Buxl",                 # uncomment when Buxl positions go live
    "FOAT":   "French 10Yr Oat",
    # CAD bonds
    "CGB":    "CGB",
    "CGF":    "CGF",
    "CGZ":    "CGZ",
    # AUD bonds — SFEXT/SFEYT omitted (no ProductRisk rows)
    # Equities
    "CMEMES": "Micro E-Mini S&P 500 Futures",
    "CMEMNQ": "Micro E-Mini Nasdaq 100",
    "ES":     "e-Mini S&P 500",
    "FDAX":   "Dax",
    "FDXM":   "Mini-Dax",
    "FESX":   "EuroStocks",
    "FSMI":   "Swiss Market Index (SMI)",
    "FXXP":   "STOXX Europe 600",
    "NQ":     "e-Mini Nasdaq 100",
    "YM":     "Mini Dow",
    "Z":      "FTSE",
}

# ─── 13. HAWK: Product ticker → ProductRisk name for summary product P&L ─────
#
# Maps HAWK exchange codes → FF_Risk.ProductRisk product names.
# Used by db_hawk.get_product_pnl() to translate before returning,
# so the frontend join (by Product name) works correctly.
#
# Rules:
#   - Tickers with no matching ProductRisk row are omitted (silently no P&L shown)
#   - Multiple tickers mapping to the same name are summed (e.g. BCOC + BCOP + BCO)
#   - Calendar spread / micro variants included where ProductRisk has a row
#   - Volatility products handled via HAWK_PRODUCT_SECTOR_OVERRIDES (section 10)
#     but still need a name mapping here to join to ProductRisk
#   - HAWK_ROLL_PRODUCT_MAP (section 12) covers Rates bonds + Equities;
#     this map covers everything else (Energy, FX, Softs, Ags, Metals, Crypto)
#     PLUS the STIRs that ROLL_MAP omits (Euribor, SONIA, SOFR etc.)

HAWK_PRODUCT_PNL_MAP: dict[str, str] = {

    # ── Energy: Oils - Crude ──────────────────────────────────────────────
    "BCO":    "ICE Brent Crude",
    "BCOC":   "ICE Brent Crude",            # calendar spread — summed with BCO
    "BCOP":   "ICE Brent Crude",            # calendar spread — summed with BCO
    "NBZ":    "Nymex Brent Crude",
    "ICEDBI": "Dubai 1st line Crude Futures",
    # ADM (Murban) — no ProductRisk row yet, omitted

    # ── Energy: WTI ───────────────────────────────────────────────────────
    "CL":     "Nymex Light Sweet",
    "CLC":    "Nymex Light Sweet",          # calendar spread — summed with CL
    "CLP":    "Nymex Light Sweet",          # calendar spread — summed with CL
    "WBS":    "ICE WTI Crude",
    # MCL (Micro WTI) — no ProductRisk row, omitted
    # ICEHOU (Permian WTI) — no ProductRisk row, omitted

    # ── Energy: Natural Gas ───────────────────────────────────────────────
    "NG":     "Natural Gas",
    "GCM":    "ICE UK Natural Gas",
    "MNG":    "Micro Henry Hub Natural Gas",
    "HP":     "Natural Gas (Henry Hub) Penultimate Financial Futures",
    "NYMHH":  "Natural Gas (HH) (Henry Hub) Last-day Financial Futures",

    # ── Energy: Oil Refined ───────────────────────────────────────────────
    "G":      "ICE LS GasOil",
    "HO":     "NY Harbor ULSD",
    "RB1":    "RBOB Gasoline",
    "ICENYH": "RBOB Gasoline",              # ICE listing — summed with RB1
    "ICEO":   "Heating Oil",

    # ── Rates: USD (STIRs + bonds) ────────────────────────────────────────
    # Bonds already in HAWK_ROLL_PRODUCT_MAP; duplicated here so this map
    # is self-contained for the summary product view.
    "TY":     "US 10Yr T-Note",
    "TU":     "US 2Yr T-Note",
    "FV":     "US 5Yr T-Note",
    "TB":     "US Ultra Bond",
    "UBE":    "US Ultra Bond",              # same instrument as TB — summed
    "CMETN":  "US Ultra 10Yr T-Note",
    "FF":     "30 Day Fed Fund",
    "CMESR1": "1-Month SOFR",
    "CMESR3": "3-Month SOFR",

    # ── Rates: GBP ────────────────────────────────────────────────────────
    "R":      "Gilt (Long)",
    "I":      "Three Month SONIA (ICE)",

    # ── Rates: EUR ────────────────────────────────────────────────────────
    "FGBL":   "Bund",
    "FGBM":   "Bobl",
    "FGBS":   "Schatz",
    "FGBX":   "Buxl",
    "FOAT":   "French 10Yr Oat",
    "FBTP":   "Italian BTP",
    "FBTS":   "Italian 2Yr BTP",
    "ICEER3": "Euribor",

    # ── Rates: CAD ────────────────────────────────────────────────────────
    "CGB":    "CGB",
    "CGF":    "CGF",
    "CGZ":    "CGZ",
    "CRA":    "One Month CORRA Futures",
    "3YR":    "Three-Month CORRA Futures",

    # ── Rates: AUD ────────────────────────────────────────────────────────
    "SFEIR":  "10Yr Aus Bond",
    "SFEYT":  "3Yr Aus Bill",
    # SFEXT / SFEVT — no clear ProductRisk match, omitted

    # ── Equities ──────────────────────────────────────────────────────────
    "ES":     "e-Mini S&P 500",
    "NQ":     "e-Mini Nasdaq 100",
    "YM":     "Mini Dow",
    "FDAX":   "Dax",
    "FDXM":   "Mini-Dax",
    "FESX":   "EuroStocks",
    "FSMI":   "Swiss Market Index (SMI)",
    "FXXP":   "STOXX Europe 600",
    "Z":      "FTSE",
    "CMEMES": "Micro E-Mini S&P 500 Futures",
    "CMEMNQ": "Micro E-Mini Nasdaq 100",

    # ── Volatility ────────────────────────────────────────────────────────
    "EFVS":   "VSTOXX Mini",
    "VIXXF":  "CBOE Volatility Index Future",

    # ── FX ────────────────────────────────────────────────────────────────
    "AD":     "AUD/USD-FX",
    "CD":     "CAD/USD-FX",
    "EU":     "EUR/USD-FX",
    "GBP":    "GBP/USD-FX",
    "J1":     "JPY/USD-FX",
    "SF":     "CHF/USD-FX",
    "BR":     "BRL/USD-FX (CME)",
    "M6A":    "E-micro AUD/USD-FX",
    "M6E":    "E-micro EUR/USD-FX",
    "CMEMJY": "MICRO USD/JPY FUTURES",
    "DX":     "US Dollar Index",
    # M6B, CRP, RF, CMECNH, CMEMCD, CMEMSF, CMESIR, SGXUC, MEXP — no ProductRisk match

    # ── Softs: Cocoa ──────────────────────────────────────────────────────
    "COC":    "Cocoa (Liffe)",
    "COCOA":  "Cocoa (ICE US)",
    "COCC":   "Cocoa (Liffe)",              # calendar spread — summed with COC
    "COCP":   "Cocoa (Liffe)",              # calendar spread — summed with COC

    # ── Softs: Coffee ─────────────────────────────────────────────────────
    # KF and LRC confirmed separately (see notes below — pending ProductDesc check)
    "KF":     "Coffee (Liffe)",             # CONFIRM: Robusta (Liffe)
    "KFC":    "Coffee (Liffe)",             # calendar spread
    "KFP":    "Coffee (Liffe)",             # calendar spread
    "LRC":    'Coffee "C"',                 # CONFIRM: Arabica (ICE US) — pending

    # ── Softs: Sugar ──────────────────────────────────────────────────────
    "SB":     "Sugar No11",
    "SBC":    "Sugar No11",                 # calendar spread — summed with SB
    "SBP":    "Sugar No11",                 # calendar spread — summed with SB
    "WSUG":   "Sugar (Liffe) White",

    # ── Softs: Cotton ─────────────────────────────────────────────────────
    "CT":     "Cotton No2",
    "CTC":    "Cotton No2",                 # calendar spread — summed with CT
    "CTP":    "Cotton No2",                 # calendar spread — summed with CT

    # ── Softs: OJ ─────────────────────────────────────────────────────────
    "OJ":     "FCOJ",

    # ── Ags: Grains ───────────────────────────────────────────────────────
    "BO":     "Soybean Oil (CBOT)",
    "CRN":    "Corn (CBOT)",
    "CSB":    "Soybean (CBOT)",
    "EBM":    "Milling Wheat",
    "EMA":    "Soybean Meal (CBOT)",        # CONFIRM: EMA = Soy Meal (Euronext?)
    "SM":     "Soybean Meal (CBOT)",        # CONFIRM: SM = Soy Meal (CBOT) — may sum with EMA
    "KW":     "Wheat (KCBT)",
    "RS":     "Rapeseed",
    "RRI":    "Rough Rice",
    "WH":     "Wheat (CBOT)",
    # ECO (Canola?), OAT — no ProductRisk match, omitted

    # ── Ags: Livestock ────────────────────────────────────────────────────
    "FCAT":   "Feeder Cattle",
    "LCAT":   "Live Cattle",
    "LN":     "Lean Hogs",

    # ── Metals: Precious ──────────────────────────────────────────────────
    "GD":           "Gold (COMEX)",
    "COMEX:FUT:1OZ":"Gold (COMEX)",         # physical gold cert — summed with GD
    "PL":           "Platinum",
    "SI":           "Silver (COMEX)",
    "CMESIL":       "Micro Silver (1000 Troy Oz)",
    # PA (Palladium), MGC (Micro Gold), MHG (Micro Copper) — no ProductRisk match

    # ── Metals: Base ──────────────────────────────────────────────────────
    "HG":     "Copper (COMEX)",
    "SGXFEF": "TSI Iron Ore CFR China 62% Index",
    # CMEALI (Aluminium) — no ProductRisk match

    # ── Crypto ────────────────────────────────────────────────────────────
    "CMEBTC":  "Bitcoin Futures (CME)",
    "CMEMBT":  "Micro Bitcoin Futures",
    "CMEETHM": "Micro Ether Futures (CME)",
    # CMEETH (Ether Futures CME) — not in ProductRisk list, omitted
}