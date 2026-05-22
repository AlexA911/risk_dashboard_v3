# ── Replace get_asset_class_table and get_product_table in db_office.py ─────────


def get_asset_class_table(location: str) -> pd.DataFrame:
    """
    Asset class breakdown - firm-wide only.
    Asset class rows have the asset class name stored directly as Account_Code.
    No office filter possible on these rows - they are always firm-wide aggregates.
    """
    last_night, _ = get_two_latest_eod_dates(95.0, 100)
    today = pd.Timestamp.now().strftime('%Y-%m-%d')

    asset_classes = get_asset_class_names()
    if not asset_classes:
        return pd.DataFrame(columns=['Asset_Class', 'VaR_10D', 'Delta_10D',
                                     'VaR_100D', 'Delta_100D', 'Margin', 'Delta_Margin'])
    ac_ph = ','.join(['?' for _ in asset_classes])

    def _fetch(confidence, lookback, date, eod=False):
        tf = "= '23:00:00.0000000'" if eod else f"""= (
            SELECT MAX(Time) FROM MarginDataTable
            WHERE Date = '{date}' AND Confidence = {confidence} AND Lookback = {lookback}
        )"""

        q = f"""
            SELECT Account_Code as Asset_Class,
                   SUM(VAR)    as VaR,
                   SUM(Margin) as Margin
            FROM MarginDataTable
            WHERE Date = ? AND Confidence = ? AND Lookback = ?
            AND Time {tf}
            AND Account_Code IN ({ac_ph})
            AND Office NOT IN ({_excl_ph()})
            GROUP BY Account_Code
            ORDER BY SUM(VAR) DESC
        """
        params = [date, confidence, lookback] + asset_classes + EXCLUDED_OFFICES
        with get_connection() as conn:
            df = pd.read_sql(q, conn, params=params)
        df['VaR']    = df['VaR'].abs()
        df['Margin'] = df['Margin'].abs()
        return df

    curr_10  = _fetch(100.0, 10,  today)
    curr_100 = _fetch(95.0,  100, today)
    if curr_10.empty:  curr_10  = _fetch(100.0, 10,  last_night, eod=True)
    if curr_100.empty: curr_100 = _fetch(95.0,  100, last_night, eod=True)

    sod_10  = _fetch(100.0, 10,  last_night, eod=True)
    sod_100 = _fetch(95.0,  100, last_night, eod=True)

    df = curr_100[['Asset_Class', 'VaR', 'Margin']].rename(columns={'VaR': 'VaR_100D'})
    df = df.merge(curr_10[['Asset_Class', 'VaR']].rename(columns={'VaR': 'VaR_10D'}),
                  on='Asset_Class', how='outer')
    df = df.merge(sod_100[['Asset_Class', 'VaR']].rename(columns={'VaR': 'SOD_100D'}),
                  on='Asset_Class', how='left')
    df = df.merge(sod_10[['Asset_Class', 'VaR']].rename(columns={'VaR': 'SOD_10D'}),
                  on='Asset_Class', how='left')
    df = df.merge(sod_100[['Asset_Class', 'Margin']].rename(columns={'Margin': 'SOD_Margin'}),
                  on='Asset_Class', how='left')

    df['Delta_100D']   = df['VaR_100D']  - df['SOD_100D']
    df['Delta_10D']    = df['VaR_10D']   - df['SOD_10D']
    df['Delta_Margin'] = df['Margin']    - df['SOD_Margin']

    return df[['Asset_Class', 'VaR_10D', 'Delta_10D',
               'VaR_100D', 'Delta_100D', 'Margin', 'Delta_Margin']] \
        .sort_values('VaR_100D', ascending=False).reset_index(drop=True)


def get_product_table(location: str) -> pd.DataFrame:
    """
    Product breakdown - firm-wide only.
    Product rows have Account_Code format: '9108 ICE Brent Crude'
    SUBSTRING strips the analyst ID prefix to get the clean product name.
    """
    last_night, _ = get_two_latest_eod_dates(95.0, 100)
    today = pd.Timestamp.now().strftime('%Y-%m-%d')

    asset_classes = get_asset_class_names()
    ac_ph = ','.join(['?' for _ in asset_classes]) if asset_classes else "''"

    def _fetch(confidence, lookback, date, eod=False):
        tf = "= '23:00:00.0000000'" if eod else f"""= (
            SELECT MAX(Time) FROM MarginDataTable
            WHERE Date = '{date}' AND Confidence = {confidence} AND Lookback = {lookback}
        )"""

        ac_exclude = f"""AND SUBSTRING(Account_Code, CHARINDEX(' ', Account_Code) + 1,
                          LEN(Account_Code)) NOT IN ({ac_ph})""" if asset_classes else ""

        q = f"""
            SELECT
                SUBSTRING(Account_Code,
                          CHARINDEX(' ', Account_Code) + 1,
                          LEN(Account_Code)) as Product,
                SUM(VAR)    as VaR,
                SUM(Margin) as Margin
            FROM MarginDataTable
            WHERE Date = ? AND Confidence = ? AND Lookback = ?
            AND Time {tf}
            AND ISNUMERIC(Account_Code) = 0
            AND CHARINDEX(' ', Account_Code) > 0
            {ac_exclude}
            AND Office NOT IN ({_excl_ph()})
            GROUP BY SUBSTRING(Account_Code,
                               CHARINDEX(' ', Account_Code) + 1,
                               LEN(Account_Code))
            ORDER BY SUM(VAR) DESC
        """
        params = [date, confidence, lookback] + (asset_classes if asset_classes else []) + EXCLUDED_OFFICES
        with get_connection() as conn:
            df = pd.read_sql(q, conn, params=params)
        df['VaR']    = df['VaR'].abs()
        df['Margin'] = df['Margin'].abs()
        return df

    curr_10  = _fetch(100.0, 10,  today)
    curr_100 = _fetch(95.0,  100, today)
    if curr_10.empty:  curr_10  = _fetch(100.0, 10,  last_night, eod=True)
    if curr_100.empty: curr_100 = _fetch(95.0,  100, last_night, eod=True)

    sod_10  = _fetch(100.0, 10,  last_night, eod=True)
    sod_100 = _fetch(95.0,  100, last_night, eod=True)

    df = curr_100[['Product', 'VaR', 'Margin']].rename(columns={'VaR': 'VaR_100D'})
    df = df.merge(curr_10[['Product', 'VaR']].rename(columns={'VaR': 'VaR_10D'}),
                  on='Product', how='outer')
    df = df.merge(sod_100[['Product', 'VaR']].rename(columns={'VaR': 'SOD_100D'}),
                  on='Product', how='left')
    df = df.merge(sod_10[['Product', 'VaR']].rename(columns={'VaR': 'SOD_10D'}),
                  on='Product', how='left')
    df = df.merge(sod_100[['Product', 'Margin']].rename(columns={'Margin': 'SOD_Margin'}),
                  on='Product', how='left')

    df['Delta_100D']   = df['VaR_100D']  - df['SOD_100D']
    df['Delta_10D']    = df['VaR_10D']   - df['SOD_10D']
    df['Delta_Margin'] = df['Margin']    - df['SOD_Margin']

    return df[['Product', 'VaR_10D', 'Delta_10D',
               'VaR_100D', 'Delta_100D', 'Margin', 'Delta_Margin']] \
        .sort_values('VaR_100D', ascending=False).reset_index(drop=True)
