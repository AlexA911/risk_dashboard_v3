"""
data_layer.py — combines sources, calculates stats, returns clean dataframes.
No SQL. No UI. Pure logic.
"""
import pandas as pd
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data import db_office


def _abs_cols(df, cols):
    for col in cols:
        if col in df.columns:
            df[col] = df[col].abs()
    return df


def _calc_stats(history, group_col):
    return history.groupby(group_col)['VaR'].agg(
        Average='mean', Std='std', Min='min', Max='max'
    ).reset_index()


def _merge_t1(df, t1_df, name_col):
    if not t1_df.empty:
        return df.merge(
            t1_df[[name_col, 'VaR']].rename(columns={'VaR': 'T1'}),
            on=name_col, how='outer'
        )
    df['T1'] = None
    return df


def _add_range(df):
    if 'Min' in df.columns and 'Max' in df.columns:
        df['Range'] = df.apply(
            lambda r: f"{r['Min']:,.0f} - {r['Max']:,.0f}"
            if pd.notna(r['Min']) else "-", axis=1
        )
    return df


def get_snapshot_time(confidence: float, lookback: int) -> str:
    return db_office.get_latest_snapshot_time(confidence, lookback)


def build_location_summary(confidence: float, lookback: int) -> dict:
    last_night_date, t1_date = db_var.get_two_latest_eod_dates(confidence, lookback)
    today = pd.Timestamp.now().strftime('%Y-%m-%d')

    today_raw      = db_var.get_intraday_var(today, confidence, lookback)
    last_night_raw = db_var.get_eod_var(last_night_date, confidence, lookback)
    no_intraday    = today_raw.empty

    current = last_night_raw if no_intraday else today_raw
    t1_raw  = db_var.get_eod_var(t1_date, confidence, lookback) if t1_date else pd.DataFrame()
    history = db_var.get_historical_eod_var(confidence, lookback)
    stats   = _calc_stats(history, 'Office')

    df = current[['Office', 'VaR']].rename(columns={'VaR': 'Current_VaR'})
    df = df.merge(
        last_night_raw[['Office', 'VaR']].rename(columns={'VaR': 'Last_Night'}),
        on='Office', how='outer'
    )
    df = _merge_t1(df, t1_raw, 'Office')
    df = df.merge(stats, on='Office', how='left')
    df = _abs_cols(df, ['Current_VaR', 'Last_Night', 'T1', 'Average', 'Min', 'Max'])
    df['Intraday_Change'] = df['Current_VaR'] - df['Last_Night']
    df['Change_24hr']     = df['Last_Night']   - df['T1']
    df['Z_Score']         = (df['Last_Night'] - df['Average']) / df['Std']
    df = _add_range(df)
    df = df.sort_values('Current_VaR', ascending=False).reset_index(drop=True)

    return {
        'table':           df,
        'last_night_date': last_night_date,
        't1_date':         t1_date,
        'no_intraday':     no_intraday,
        'today_raw':       today_raw,
        'last_night_raw':  last_night_raw,
    }


def build_drill_down(level: str, confidence: float, lookback: int) -> pd.DataFrame:
    last_night_date, t1_date = db_var.get_two_latest_eod_dates(confidence, lookback)
    today = pd.Timestamp.now().strftime('%Y-%m-%d')

    fetch = {
        'analyst':     db_var.get_analyst_var,
        'product':     db_var.get_product_var,
        'asset_class': db_office.get_asset_class_var,
    }[level]

    name_col = {
        'analyst':     'Analyst',
        'product':     'Product',
        'asset_class': 'Asset_Class',
    }[level]

    current    = fetch(today, confidence, lookback, eod=False)
    if current.empty:
        current = fetch(last_night_date, confidence, lookback, eod=True)

    last_night = fetch(last_night_date, confidence, lookback, eod=True)
    t1         = fetch(t1_date, confidence, lookback, eod=True) if t1_date else pd.DataFrame()

    stats = pd.DataFrame()
    if level == 'analyst':
        history = db_var.get_analyst_history(confidence, lookback)
        if not history.empty:
            history['VaR'] = history['VaR'].abs()
            stats = _calc_stats(history, 'Analyst')
            stats.rename(columns={'Analyst': name_col}, inplace=True)

    merge_cols = [name_col, 'Office', 'VaR'] \
                 if (level == 'analyst' and 'Office' in current.columns) \
                 else [name_col, 'VaR']

    df = current[[c for c in merge_cols if c in current.columns]].copy()
    df = df.merge(
        last_night[[name_col, 'VaR']].rename(columns={'VaR': 'Last_Night'}),
        on=name_col, how='outer'
    )
    df = _merge_t1(df, t1, name_col)
    df = _abs_cols(df, ['VaR', 'Last_Night', 'T1'])
    df['Daily_Change'] = df['VaR'] - df['Last_Night']

    if not stats.empty:
        df = df.merge(stats, on=name_col, how='left')
        df = _abs_cols(df, ['Average', 'Min', 'Max'])
        df['Z_Score'] = (df['Last_Night'] - df['Average']) / df['Std']
        df = _add_range(df)
    else:
        df['Average'] = None
        df['Z_Score'] = None
        df['Range']   = None

    return df.sort_values('VaR', ascending=False).reset_index(drop=True)


def get_analyst_asset_classes(analyst: str, confidence: float,
                               lookback: int) -> pd.DataFrame:
    today = pd.Timestamp.now().strftime('%Y-%m-%d')
    df = db_var.get_analyst_asset_class_breakdown(today, confidence, lookback, analyst)
    if df.empty:
        last_night_date, _ = db_var.get_two_latest_eod_dates(confidence, lookback)
        df = db_var.get_analyst_asset_class_breakdown(
            last_night_date, confidence, lookback, analyst, eod=True
        )
    if not df.empty:
        # Normalise column name
        if 'VAR' in df.columns:
            df = df.rename(columns={'VAR': 'VaR'})
        df['VaR'] = df['VaR'].abs()
    return df

def get_rolling_var(confidence: float, lookback: int, days: int = 5) -> pd.DataFrame:
    return db_office.get_rolling_var(confidence, lookback, days)

def get_analyst_products(analyst: str, confidence: float, lookback: int,
                          asset_class: str = None) -> pd.DataFrame:
    today = pd.Timestamp.now().strftime('%Y-%m-%d')
    df = db_var.get_analyst_product_breakdown(
        today, confidence, lookback, analyst, asset_class
    )
    if df.empty:
        last_night_date, _ = db_var.get_two_latest_eod_dates(confidence, lookback)
        df = db_var.get_analyst_product_breakdown(
            last_night_date, confidence, lookback, analyst, asset_class, eod=True
        )
    if not df.empty:
        # Normalise column name
        if 'VAR' in df.columns:
            df = df.rename(columns={'VAR': 'VaR'})
        df['VaR'] = df['VaR'].abs()
    return df