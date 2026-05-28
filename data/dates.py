"""
data/dates.py — Shared date helpers used across all query modules.

Centralised so all SQL queries agree on what "today" and "EOD dates" mean.

Functions:
  today()                  — today's date as YYYY-MM-DD string
  get_latest_eod_dates()   — N most recent EOD dates for a given VaR config
  date_context()           — returns a DateContext with all standard date refs
                             resolved in one call. Use this in table functions
                             instead of repeating the 7-line date-resolution block.

Usage:
  from data.dates import today, get_latest_eod_dates, date_context

  dc = date_context()
  sod_95  = fetch(95.0,  100, dc.last_night_95,  eod=True)
  cur_95  = fetch(95.0,  100, dc.today_str,       eod=False)
  sod_100 = fetch(100.0,  10, dc.last_night_100,  eod=True)
"""
import pandas as pd
from dataclasses import dataclass
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


@dataclass
class DateContext:
    """
    All standard date references needed by a table query function.
    Produced by date_context() — never instantiate directly.

    Attributes:
        today_str:      today's date as YYYY-MM-DD
        last_night_95:  most recent EOD date for 95/100 config
        t1_95:          second most recent EOD date for 95/100 config
        last_night_100: most recent EOD date for 100/10 config
        t1_100:         second most recent EOD date for 100/10 config
    """
    today_str:      str
    last_night_95:  str
    t1_95:          str
    last_night_100: str
    t1_100:         str


def date_context() -> DateContext:
    """
    Resolve all standard date references in one DB round-trip pair.
    Call once at the top of any table function that needs EOD date comparisons.
    """
    today_str      = today()
    eod_95         = get_latest_eod_dates(95.0,  100, n=2)
    eod_100        = get_latest_eod_dates(100.0,  10, n=2)
    last_night_95  = eod_95[0]  if len(eod_95)  > 0 else today_str
    t1_95          = eod_95[1]  if len(eod_95)  > 1 else last_night_95
    last_night_100 = eod_100[0] if len(eod_100) > 0 else today_str
    t1_100         = eod_100[1] if len(eod_100) > 1 else last_night_100
    return DateContext(
        today_str      = today_str,
        last_night_95  = last_night_95,
        t1_95          = t1_95,
        last_night_100 = last_night_100,
        t1_100         = t1_100,
    )