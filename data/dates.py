"""
data/dates.py — Shared date helpers used across all query modules.

Centralised so all SQL queries agree on what "today" and "EOD dates" mean.
"""
import pandas as pd


def today() -> str:
    """Return today's date as YYYY-MM-DD."""
    return pd.Timestamp.now().strftime("%Y-%m-%d")