from __future__ import annotations

import pandas as pd

from .db import connect


def query_df(sql: str, params: tuple | None = None) -> pd.DataFrame:
    with connect() as con:
        return pd.read_sql_query(sql, con, params=params or ())


def get_universe() -> pd.DataFrame:
    sql = """
    WITH latest AS (
        SELECT ms.*
        FROM market_snapshot ms
        JOIN (
            SELECT instrument_id, MAX(asof_date) AS max_asof
            FROM market_snapshot
            GROUP BY instrument_id
        ) x ON x.instrument_id = ms.instrument_id AND x.max_asof = ms.asof_date
    )
    SELECT
        i.instrument_id,
        COALESCE(i.symbol, i.instrument_id) AS symbol,
        i.name,
        i.asset_class,
        i.sub_asset_class,
        i.category,
        i.currency,
        i.region,
        i.country,
        i.issuer,
        i.issuer_type,
        i.rating,
        i.duration_years,
        i.maturity_date,
        i.coupon,
        COALESCE(latest.expense_ratio, i.expense_ratio) AS expense_ratio,
        COALESCE(latest.aum_mn, i.aum_mn) AS aum_mn,
        COALESCE(latest.esg_score, i.esg_score) AS esg_score,
        COALESCE(latest.liquidity_score, i.liquidity_score) AS liquidity_score,
        COALESCE(latest.yield_pct, i.yield_pct) AS yield_pct,
        COALESCE(latest.ytm_pct, i.ytm_pct) AS ytm_pct,
        i.risk_score,
        i.theme,
        latest.price,
        latest.nav,
        latest.spread_bps,
        latest.asof_date,
        latest.quote_source,
        i.source,
        i.is_demo,
        i.tradable
    FROM instruments i
    LEFT JOIN latest ON latest.instrument_id = i.instrument_id
    ORDER BY i.asset_class, i.name
    """
    return query_df(sql)


def get_price_history(instrument_ids: list[str] | tuple[str, ...]) -> pd.DataFrame:
    if not instrument_ids:
        return pd.DataFrame(columns=["instrument_id", "date", "value"])
    placeholders = ",".join(["?"] * len(instrument_ids))
    sql = f"SELECT instrument_id, date, value FROM price_history WHERE instrument_id IN ({placeholders}) ORDER BY date"
    df = query_df(sql, tuple(instrument_ids))
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def get_mandates() -> pd.DataFrame:
    return query_df("SELECT * FROM mandates ORDER BY name")
