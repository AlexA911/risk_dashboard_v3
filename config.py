# ── Database connections ──────────────────────────────────────────────────────
DATABASES = {
    "ff_risk": {
        "server":   r"it-ixe-sql-01.corp.hertshtengroup.com\TrackOrders",
        "database": "FF_Risk",
        "driver":   "ODBC Driver 17 for SQL Server",
    },
}

VAR_CONFIGS = {
    "100D 95%": {"lookback": 100, "confidence": 95.00},
    "10D 100%": {"lookback": 10,  "confidence": 100.00},
}

PRIMARY_CONFIDENCE = 95.00
PRIMARY_LOOKBACK   = 100