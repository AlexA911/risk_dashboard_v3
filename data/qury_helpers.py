"""
data/query_helpers.py — Shared DataFrame assembly helpers for VaR query modules.

These functions own the structural work that's identical across all table
queries: fetching across configs and dates, fallback logic, column renaming,
merging, and delta computation.

The SQL itself stays in the calling module — query_helpers never touches
the database directly.

Functions:
  build_var_table()  — takes a fetch_fn + keys + DateContext, returns the
                       standard 9-column VaR result DataFrame.

Usage:
  from data.query_helpers import build_var_table

  def fetch(confidence, lookback, date, eod):
      # your SQL here
      ...

  df = build_var_table(fetch, keys=["Office"], dc=dc)
"""

import pandas as pd
from typing import Callable
from data.dates import DateContext


def build_var_table(
    fetch_fn:   Callable,
    keys:       list[str],
    dc:         DateContext,
    var_col:    str = "VaR",
    margin_col: str = "Margin",
) -> pd.DataFrame:
    """
    Assemble a standard 9-column VaR result from a caller-provided fetch function.

    Calls fetch_fn six times — EOD and intraday for both VaR configs — then
    applies SOD fallback, merges, and computes deltas vs SOD and t-1.

    Args:
        fetch_fn:   callable(confidence, lookback, date, eod) → pd.DataFrame.
                    Must return a DataFrame containing at least `keys`,
                    `var_col`, and `margin_col` columns.
        keys:       columns to merge on, e.g. ["Office"] or ["Office", "Analyst"]
                    or ["Product", "Asset_Class"].
        dc:         DateContext from date_context(). Provides all date references.
        var_col:    name of the VaR column in fetch_fn's result. Default "VaR".
                    Use "iVaR" for product-level queries.
        margin_col: name of the Margin column in fetch_fn's result.

    Returns:
        DataFrame with columns:
            keys + [VaR_10D, Delta_10D, Delta_10D_t1,
                    VaR_100D, Delta_100D, Delta_100D_t1,
                    Margin, Delta_Margin, Delta_Margin_t1]
    """
    # ── Fetch all six snapshots ───────────────────────────────────────────────
    sod_95  = fetch_fn(95.0,  100, dc.last_night_95,  eod=True)
    t1_95_  = fetch_fn(95.0,  100, dc.t1_95,          eod=True)
    cur_95  = fetch_fn(95.0,  100, dc.today_str,       eod=False)
    sod_100 = fetch_fn(100.0,  10, dc.last_night_100,  eod=True)
    t1_100_ = fetch_fn(100.0,  10, dc.t1_100,          eod=True)
    cur_100 = fetch_fn(100.0,  10, dc.today_str,        eod=False)

    # ── SOD fallback — use last night if no intraday data yet ─────────────────
    if cur_95.empty:  cur_95  = sod_95.copy()
    if cur_100.empty: cur_100 = sod_100.copy()

    # ── Rename value columns before merge ─────────────────────────────────────
    sod_95  = sod_95.rename(columns={var_col: "_var100_sod", margin_col: "_margin_sod"})
    t1_95_  = t1_95_.rename(columns={var_col: "_var100_t1",  margin_col: "_margin_t1"})
    cur_95  = cur_95.rename(columns={var_col: "_var100_cur", margin_col: "_margin_cur"})
    sod_100 = sod_100.rename(columns={var_col: "_var10_sod"})
    t1_100_ = t1_100_.rename(columns={var_col: "_var10_t1"})
    cur_100 = cur_100.rename(columns={var_col: "_var10_cur"})

    # ── Merge all six snapshots on keys ───────────────────────────────────────
    df = (
        sod_95 [keys + ["_var100_sod", "_margin_sod"]]
        .merge(t1_95_ [keys + ["_var100_t1",  "_margin_t1"]],  on=keys, how="outer")
        .merge(cur_95 [keys + ["_var100_cur", "_margin_cur"]], on=keys, how="outer")
        .merge(sod_100[keys + ["_var10_sod"]],                 on=keys, how="outer")
        .merge(t1_100_[keys + ["_var10_t1"]],                  on=keys, how="outer")
        .merge(cur_100[keys + ["_var10_cur"]],                  on=keys, how="outer")
    )

    # ── Compute output columns ────────────────────────────────────────────────
    df["VaR_100D"]        = df["_var100_cur"].abs()
    df["Delta_100D"]      = df["_var100_cur"] - df["_var100_sod"]
    df["Delta_100D_t1"]   = df["_var100_cur"] - df["_var100_t1"]
    df["VaR_10D"]         = df["_var10_cur"].abs()
    df["Delta_10D"]       = df["_var10_cur"]  - df["_var10_sod"]
    df["Delta_10D_t1"]    = df["_var10_cur"]  - df["_var10_t1"]
    df["Margin"]          = df["_margin_cur"]
    df["Delta_Margin"]    = df["_margin_cur"] - df["_margin_sod"]
    df["Delta_Margin_t1"] = df["_margin_cur"] - df["_margin_t1"]

    return df[keys + [
        "VaR_10D",  "Delta_10D",  "Delta_10D_t1",
        "VaR_100D", "Delta_100D", "Delta_100D_t1",
        "Margin",   "Delta_Margin", "Delta_Margin_t1",
    ]]