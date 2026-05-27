"""
data/reference.py — Single source of truth for all cross-system reference data.

This file owns every static mapping and lookup used across the dashboard.
When a new product appears, office is added, or data source arrives —
this is the only file that needs updating.

Imported by: db_office.py, db_hawk.py, and any future data modules.

Sections:
  1.  Excluded offices
  2.  Office display order
  3.  Sector display order
  4.  FF_Risk: Sector → Asset class mapping  (used by db_office.py)
  5.  FF_Risk: Asset class → Sector mapping  (inverse lookup)
  6.  FF_Risk: Subgroup netted asset classes (Cumulus netting group rows)
  7.  FF_Risk: Subgroup display order per sector
  8.  FF_Risk: Product → Subgroup mapping
  9.  HAWK: AssetClass + SubAssetClass → Dashboard sector
  10. HAWK: Product-level sector overrides
  11. HAWK: Parquet column names
  11. Helper functions
"""

# ─── 1. Excluded offices ──────────────────────────────────────────────────────
# Never shown in any dashboard view, across all data sources.

EXCLUDED_OFFICES = [
    "London P&C",  # wound down, no active traders
    "Mumbai",  # excluded from VaR scope
    "Montreal",  # excluded from dashboard views
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
# Used by db_office.py to filter ProductRisk rows by sector.

SECTOR_ASSET_CLASSES = {
    "Energy":     ["Oils - Crude", "WTI", "NG", "Oils - Refined", "Oils"],
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
# Used by db_hawk.py and any future module that needs to resolve FF_Risk
# asset class names to dashboard sectors.

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
# Maps subgroup header names to the FF_Risk asset classes whose Cumulus
# netted VaR rows should be summed for that header.
# Empty list = no Cumulus netting data available for this subgroup.

SUBGROUP_NETTED_ASSET_CLASSES = {
    # Energy
    "Oils":               ["Oils", "Oils - Crude"],
    "WTI":                ["WTI"],
    "Natural Gas":        ["NG"],
    "Oil Refined":        ["Oils - Refined"],
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
    # Passthrough sectors (no subgroups — AC = subgroup)
    "Equity Indices":     ["Equity Indices"],
    "Volatility Indices": ["Volatility Indices"],
    "FX":                 ["FX"],
    "Crypto":             ["Crypto"],
}


# ─── 7. FF_Risk: Subgroup display order per sector ────────────────────────────

SUBGROUP_ORDER = {
    "Energy":     ["Oils", "WTI", "Natural Gas", "Oil Refined", "Power & Carbon"],
    "Rates":      ["USD", "GBP", "EUR", "CAD", "AUD", "CHF"],
    "Metals":     ["Precious", "Base"],
    "Ags":        ["Grains", "Livestock", "Dairy"],
    "Softs":      ["Cocoa", "Coffee", "Sugar", "Cotton", "OJ"],
}


# ─── 8. FF_Risk: Product → Subgroup mapping ───────────────────────────────────
# Maps FF_Risk product names (from ProductRisk.Product) to subgroup headers.
# Used by db_office.py to interleave subgroup header rows in the product table.

PRODUCT_SUBGROUP = {
    # Energy: Oils
    "Abu Dhabi Murban Crude Oil Futures":                      "Oils",
    "Brent Crude":                                             "Oils",
    "Brent Crude Oil":                                         "Oils",
    "Dubai 1st line Crude Futures":                            "Oils",
    "Dubai Crude Oil":                                         "Oils",
    "ICE Brent Crude":                                         "Oils",
    "ICE Murban Crude Oil Futures":                            "Oils",
    "Murban Crude Oil":                                        "Oils",
    # Energy: WTI
    "Nymex Brent Crude":                                       "WTI",
    "Nymex Light Sweet":                                       "WTI",
    "WTI Crude Oil":                                           "WTI",
    "ICE WTI Crude":                                           "WTI",
    "ICE WTI Crude TAS":                                       "WTI",
    "Micro WTI Crude Oil Futures":                             "WTI",
    # Energy: Natural Gas
    "ICE Dutch TTF Gas Futures":                               "Natural Gas",
    "ICE UK Natural Gas":                                      "Natural Gas",
    "Micro Henry Hub Natural Gas":                             "Natural Gas",
    "Natural Gas":                                             "Natural Gas",
    "Natural Gas (Henry Hub) Penultimate Financial Futures":   "Natural Gas",
    "Natural Gas (HH) (Henry Hub) Last-day Financial Futures": "Natural Gas",
    # Energy: Oil Refined
    "Heating Oil":                                             "Oil Refined",
    "ICE LS GasOil":                                           "Oil Refined",
    "ICE LS GasOil TAS":                                       "Oil Refined",
    "Low Sulphur Gasoil":                                      "Oil Refined",
    "NY Harbor ULSD":                                          "Oil Refined",
    "RBOB Gasoline":                                           "Oil Refined",
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
# Maps (AssetClass, SubAssetClass) tuples from DailyProductTransactions.
# None = exclude from sector P&L views.

HAWK_SECTOR_MAP: dict[tuple[str, str], str | None] = {
    ("Energy",           "Energy"):           "Energy",
    ("STIRs",            "American STIRs"):   "Rates",
    ("STIRs",            "European STIRs"):   "Rates",
    ("STIRs",            "Asian STIRs"):      "Rates",
    ("STIRs",            "Australian STIRs"): "Rates",
    ("STIRs",            "Brazilian DI"):     "Rates",
    ("Indices & Stocks", "Indices & Stocks"): "Equities",  # overridden per product below
    ("Commodity",        "Softs"):            "Softs",
    ("Commodity",        "Grains & Oils"):    "Ags",
    ("Commodity",        "Livestock"):        "Ags",
    ("Commodity",        "Wood&Rubber"):      "Ags",
    ("Commodity",        "Metals"):           "Metals",
    ("Currency",         "Currency"):         "FX",
    ("Crypto",           "Crypto"):           "Crypto",
    # Excluded
    ("Other Product",    "Other Product"):    None,
    ("Option Product",   "Option Product"):   None,
    ("Commodity",        "Other Product"):    None,
    ("Energy",           "Other Product"):    None,
    ("Indices & Stocks", "Other Product"):    None,
    ("Crypto",           "Other Product"):    None,
}


# ─── 10. HAWK: Product-level sector overrides ─────────────────────────────────
# Products misclassified by HAWK at AssetClass/SubAssetClass level.
# Takes priority over HAWK_SECTOR_MAP.

HAWK_PRODUCT_SECTOR_OVERRIDES: dict[str, str | None] = {
    "EFVS":  "Volatility",   # VSTOXX Futures — sits under Indices & Stocks in HAWK
    "VIXXF": "Volatility",   # VIX Futures — sits under Indices & Stocks in HAWK
    "DX":    "FX",           # US Dollar Index — sits under Indices & Stocks in HAWK
}


# ─── 11. Helper functions ─────────────────────────────────────────────────────

def hawk_sector(asset_class: str, sub_asset_class: str, product: str) -> str | None:
    """
    Resolve a HAWK product to a dashboard sector.
    Product override takes priority over AssetClass/SubAssetClass lookup.
    Returns None if unclassified — exclude from sector views.
    """
    if product in HAWK_PRODUCT_SECTOR_OVERRIDES:
        return HAWK_PRODUCT_SECTOR_OVERRIDES[product]
    return HAWK_SECTOR_MAP.get((asset_class, sub_asset_class), None)


def ff_risk_sector(asset_class: str) -> str | None:
    """Resolve an FF_Risk asset class to a dashboard sector."""
    return SECTOR_MAP.get(asset_class, None)


def sort_offices(offices: list[str]) -> list[str]:
    """Sort offices per OFFICE_DISPLAY_ORDER. Unknown offices go last alphabetically."""
    order = {name: i for i, name in enumerate(OFFICE_DISPLAY_ORDER)}
    return sorted(offices, key=lambda o: (order.get(o, len(OFFICE_DISPLAY_ORDER)), o))


def sort_sectors(sectors: list[str]) -> list[str]:
    """Sort sectors per SECTOR_ORDER. Unknown sectors go last alphabetically."""
    order = {name: i for i, name in enumerate(SECTOR_ORDER)}
    return sorted(sectors, key=lambda s: (order.get(s, len(SECTOR_ORDER)), s))


# ─── 11. HAWK parquet column names ───────────────────────────────────────────
# DailyAnalystTransactions and DailyProductTransactions use different column
# names for the same concept. Use these constants throughout db_hawk.py rather
# than hardcoding column names, so any upstream changes require only one edit.
#
# Known discrepancy vs HAWK frontend (as of 2026-05-26):
#   - Daily firm total: LCY-SQL3 = 1,472,362 vs HAWK frontend = 1,473,483 (~1,121 gap)
#   - MRN YTD: LCY-SQL3 = 4,803,381 vs HAWK frontend = 5,026,635 (~223k gap)
#   - Rebate fields (VolumeRebates, ExchangeRebates) match exactly between sources
#   - Root cause: LCY-SQL3 may be a replica of the primary AWS RDS instance
#     (TM-DBINST1.CTMLJWOTKQUZ.EU-WEST-1.RDS.AMAZONAWS.COM) with incomplete sync
#   - Raised with HAWK team for investigation

# DailyAnalystTransactions — gross P&L field
HAWK_ANALYST_PNL_COL = "GrossPnL"

# DailyProductTransactions — gross P&L field (different name to analyst table)
HAWK_PRODUCT_PNL_COL = "PnL"
