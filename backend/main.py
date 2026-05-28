"""
backend/main.py — Risk Dashboard v3
Run: python run.py  (backend port 8002, frontend port 3001)
"""
import sys, os, math, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

from data import db_office
from data import db_analyst
from data import db_rollview
from data import db_hawk

app = FastAPI(title="Risk Dashboard v3", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Simple in-memory cache ────────────────────────────────────────────────────
_cache: dict = {}
_CACHE_TTL   = 60  # seconds

def get_cached(key: str, fn):
    now = time.time()
    if key in _cache and now - _cache[key]["ts"] < _CACHE_TTL:
        return _cache[key]["data"]
    result = fn()
    _cache[key] = {"data": result, "ts": now}
    return result


# ── JSON serialiser (DataFrames) ──────────────────────────────────────────────
def clean(df: pd.DataFrame) -> list:
    records = df.where(pd.notna(df), None).to_dict(orient="records")
    return [
        {k: (None if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else v)
         for k, v in row.items()}
        for row in records
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "database": "FF_Risk"}


# ─────────────────────────────────────────────────────────────────────────────
# Locations dropdown
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/locations")
def locations():
    try:
        df = get_cached("locations", db_office.get_offices)
        return {"locations": df["Office"].tolist()}
    except Exception as e:
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Metric cards
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/metrics")
def metrics(location: str = "Total", confidence: float = 95.0, lookback: int = 100):
    try:
        key = f"metrics:{location}:{confidence}:{lookback}"
        return get_cached(key, lambda: db_office.get_metrics(location, confidence, lookback))
    except Exception as e:
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# VIX margin (limit utilisation denominator)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/vix-margin")
def vix_margin():
    try:
        return get_cached("vix-margin", db_office.get_vix_margin)
    except Exception as e:
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Last snapshot timestamp — drives "Data as of" in NavBar
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/last-snapshot")
def last_snapshot():
    try:
        return get_cached("last-snapshot", db_office.get_last_snapshot)
    except Exception as e:
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Rolling VaR + Margin chart
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/rolling-chart")
def rolling_chart(
    location: str = "Total",
    confidence: float = 95.0,
    lookback: int = 100,
    days: int = 5,
):
    try:
        key = f"rolling:{location}:{confidence}:{lookback}:{days}"
        df = get_cached(key, lambda: db_office.get_rolling_chart(location, confidence, lookback, days))
        return {"data": clean(df)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/sector-chart")
def sector_chart(
    location: str = "Total",
    sector: str = "Energy",
    confidence: float = 95.0,
    lookback: int = 100,
    days: int = 5,
):
    try:
        key = f"sector-chart:{location}:{sector}:{confidence}:{lookback}:{days}"
        df = get_cached(key, lambda: db_office.get_sector_chart(location, sector, confidence, lookback, days))
        return {"data": clean(df)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/product-chart")
def product_chart(
    location: str = "Total",
    product: str = "",
    confidence: float = 95.0,
    lookback: int = 100,
    days: int = 5,
):
    try:
        key = f"product-chart:{location}:{product}:{confidence}:{lookback}:{days}"
        df = get_cached(key, lambda: db_office.get_product_chart(location, product, confidence, lookback, days))
        return {"data": clean(df)}
    except Exception as e:
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Location summary table
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/location-table")
def location_table(location: str = "Total"):
    try:
        key = f"location-table:{location}"
        df = get_cached(key, lambda: db_office.get_location_table(location))
        return {"data": clean(df)}
    except Exception as e:
        import traceback
        print(f"[LOCATION-TABLE ERROR] {traceback.format_exc()}")
        raise HTTPException(500, str(e))

# ─────────────────────────────────────────────────────────────────────────────
# HAWK P&L — office level (from parquet cache)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/hawk-office-pnl")
def hawk_office_pnl():
    try:
        key = "hawk-office-pnl"
        df = get_cached(key, lambda: db_hawk.get_office_pnl())
        return {"data": clean(df)}
    except Exception as e:
        import traceback
        print(f"[HAWK ERROR] {traceback.format_exc()}")
        raise HTTPException(500, str(e))

# ─────────────────────────────────────────────────────────────────────────────
# Analyst summary table (Summary tab drill-down — existing)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/analyst-table")
def analyst_table(location: str = "Total"):
    try:
        key = f"analyst-table:{location}"
        df = get_cached(key, lambda: db_office.get_analyst_table(location))
        return {"data": clean(df)}
    except Exception as e:
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Asset class tables
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/asset-class-table")
def asset_class_table(location: str = "Total"):
    try:
        key = f"asset-class-table:{location}"
        df = get_cached(key, lambda: db_office.get_asset_class_table(location))
        return {"data": clean(df)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/asset-class-table-grouped")
def asset_class_table_grouped(location: str = "Total"):
    try:
        key = f"asset-class-table-grouped:{location}"
        df = get_cached(key, lambda: db_office.get_asset_class_table_grouped(location))
        return {"data": clean(df)}
    except Exception as e:
        import traceback
        print(f"[ERROR] {traceback.format_exc()}")
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Product tables
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/product-table")
def product_table(location: str = "Total"):
    try:
        key = f"product-table:{location}"
        df = get_cached(key, lambda: db_office.get_product_table(location))
        return {"data": clean(df)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/product-table-by-sector")
def product_table_by_sector(location: str = "Total", sector: str = "Energy"):
    try:
        key = f"product-table-by-sector:{location}:{sector}"
        df = get_cached(key, lambda: db_office.get_product_table_by_sector(location, sector))
        return {"data": clean(df)}
    except Exception as e:
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Analyst tab (db_analyst.py)
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/api/analysts")
def analysts(location: str = "Total"):
    try:
        key = f"analysts:{location}"
        df = get_cached(key, lambda: db_analyst.get_analyst_table_for_tab(location))
        return {"data": clean(df)}
    except Exception as e:
        import traceback
        print(f"[ANALYSTS ERROR] {traceback.format_exc()}")
        raise HTTPException(500, str(e))



@app.get("/api/analyst-chart")
def analyst_chart(
    analyst:    str   = Query(...),
    office:     str   = Query(...),
    confidence: float = Query(95.0),
    lookback:   int   = Query(100),
    days:       int   = Query(30),
):
    """EOD VaR + Margin history for a single analyst."""
    try:
        key = f"analyst-chart:{analyst}:{office}:{confidence}:{lookback}:{days}"
        df = get_cached(key, lambda: db_analyst.get_analyst_chart(
            analyst, office, confidence, lookback, days))
        return {"data": clean(df)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/analyst-products")
def analyst_products(
    analyst:    str   = Query(...),
    office:     str   = Query(...),
    confidence: float = Query(95.0),
    lookback:   int   = Query(100),
):
    """Latest iVaR breakdown by product for a single analyst."""
    try:
        key = f"analyst-products:{analyst}:{office}:{confidence}:{lookback}"
        df = get_cached(key, lambda: db_analyst.get_analyst_products(
            analyst, office, confidence, lookback))
        return {"data": clean(df)}
    except Exception as e:
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# HAWK P&L — analyst level (from parquet cache)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/hawk-analyst-pnl")
def hawk_analyst_pnl(location: str = "Total"):
    try:
        key = f"hawk-analyst-pnl:{location}"
        df = get_cached(key, lambda: db_hawk.get_analyst_pnl(location))
        return {"data": clean(df)}
    except Exception as e:
        import traceback
        print(f"[HAWK-ANALYST-PNL ERROR] {traceback.format_exc()}")
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# HAWK P&L — analyst product level YTD (from parquet cache)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/hawk-analyst-product-pnl")
def hawk_analyst_product_pnl(analyst: str = Query(...)):
    try:
        key = f"hawk-analyst-product-pnl:{analyst}"
        df = get_cached(key, lambda: db_hawk.get_analyst_product_pnl(analyst))
        return {"data": clean(df)}
    except Exception as e:
        import traceback
        print(f"[HAWK-ANALYST-PRODUCT-PNL ERROR] {traceback.format_exc()}")
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Roll Risk
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/roll-risk")
def roll_risk(location: str = "Total"):
    try:
        key = f"roll-risk:{location}"
        sections = get_cached(key, lambda: db_rollview.get_roll_risk(location))
        def sanitise(v):
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return None
            return v
        clean_sections = [
            {
                "section": sec["section"],
                "rows": [{k: sanitise(val) for k, val in row.items()} for row in sec["rows"]],
            }
            for sec in sections
        ]
        return {"sections": clean_sections}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/roll-risk-rolls")
def roll_risk_rolls(location: str = "Total"):
    try:
        key = f"roll-risk-rolls:{location}"
        sections = get_cached(key, lambda: db_rollview.get_roll_risk_rolls(location))
        def sanitise(v):
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return None
            return v
        clean_sections = [
            {
                "section": sec["section"],
                "rows": [{k: sanitise(val) for k, val in row.items()} for row in sec["rows"]],
            }
            for sec in sections
        ]
        return {"sections": clean_sections}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/hawk-roll-pnl")
def hawk_roll_pnl():
    try:
        df = db_hawk.get_roll_product_pnl("Total")
        return {"data": df.replace({float("nan"): None}).to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/cache/clear")
def clear_cache():
    _cache.clear()
    return {"cleared": True}


# ─────────────────────────────────────────────────────────────────────────────
# Cache management
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/analyst-product-chart")
def analyst_product_chart(
    analyst:    str   = Query(...),
    office:     str   = Query(...),
    product:    str   = Query(...),
    confidence: float = Query(95.0),
    lookback:   int   = Query(100),
    days:       int   = Query(30),
):
    """EOD iVaR history for a single analyst x product."""
    try:
        key = f"analyst-product-chart:{analyst}:{office}:{product}:{confidence}:{lookback}:{days}"
        df = get_cached(key, lambda: db_analyst.get_analyst_product_chart(
            analyst, office, product, confidence, lookback, days))
        return {"data": clean(df)}
    except Exception as e:
        raise HTTPException(500, str(e))




@app.post("/api/cache/clear")
def clear_cache():
    _cache.clear()
    return {"cleared": True}
