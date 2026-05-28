"""
data/dates.py — Shared date helpers used across all query modules.

Centralised so all SQL queries agree on what "today" and "EOD dates" mean.

Functions:
  today()                  — today's date as YYYY-MM-DD string
  get_latest_eod_dates()   — N most recent EOD dates for a given VaR config
"""
import pandas as pd
from data.db_connection import get_connection


def today() -> str:
    """Return today's date as YYYY-MM-DD."""
    return pd.Timestamp.now().strftime("%Y-%m-%d")


def get_latest_eod_dates(confidence: float, lookback: int, n: int = 1) -> list:
    """
    Return the N most recent EOD dates for a given confidence/lookback config.
    Queries OfficeRisk — same source used by all query modules.
    Returns a list of YYYY-MM-DD strings, most recent first.
    """
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