# ── Database connections ──────────────────────────────────────────────────────
DATABASES = {
    "ff_risk": {
        "server":   r"it-ixe-sql-01.corp.hertshtengroup.com\TrackOrders",
        "database": "FF_Risk",
        "driver":   "ODBC Driver 17 for SQL Server",
    },
    # Legacy — kept for reference during transition
    # "market_risk": {
    #     "server":   r"it-ixe-sql-01.corp.hertshtengroup.com\TrackOrders",
    #     "database": "Market_Risk",
    #     "driver":   "ODBC Driver 17 for SQL Server",
    # },
}

# ── Dashboard constants ───────────────────────────────────────────────────────
# Offices excluded from all views (IsExcluded = 1 in dbo.Office)
EXCLUDED_OFFICES = ['London P&C', 'Mumbai']

# Futures First firm-wide netting group code in FF_Risk
FUTURES_FIRST_OFFICE = 'Futures First'

VAR_CONFIGS = {
    "100D 95%": {"lookback": 100, "confidence": 95.00},
    "10D 100%": {"lookback": 10,  "confidence": 100.00},
}

# Primary config used for metric cards and charts
PRIMARY_CONFIDENCE = 95.00
PRIMARY_LOOKBACK   = 100