from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import BUSINESS_DAYS, DATA_DIR, LEGACY_DIR, SEED_VERSION
from .db import DB_PATH, get_connection, init_db


@dataclass
class SeedResult:
    instruments: int
    mandates: int
    prices: int
    snapshots: int


RATING_MAP = {"NR": "NR", "BBB": "BBB", "A": "A", "AA": "AA", "AAA": "AAA", "BB": "BB", "B": "B"}


def _today() -> pd.Timestamp:
    return pd.Timestamp.today().normalize()


def load_demo_instruments() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "seed_instruments.csv")


def load_legacy_instruments() -> pd.DataFrame:
    path = LEGACY_DIR / "instruments_master.csv"
    if not path.exists():
        return pd.DataFrame()
    legacy = pd.read_csv(path)
    asset_class_map = {
        "Repo": "TL Money Market",
        "TersRepo": "TL Money Market",
        "TPP": "TL Money Market",
        "PPF": "TEFAS Fund",
        "KVBAF": "TEFAS Fund",
        "Katılım": "TEFAS Fund",
        "Mevduat": "Deposit",
    }
    sub_map = {
        "Repo": "Repo",
        "TersRepo": "Reverse Repo",
        "TPP": "Takasbank Money Market",
        "PPF": "Money Market Fund",
        "KVBAF": "Short Term Debt Fund",
        "Katılım": "Participation Fund",
        "Mevduat": "Deposit",
    }
    df = pd.DataFrame(
        {
            "instrument_id": legacy["instrument_id"],
            "name": legacy["instrument_name"],
            "asset_class": legacy["instrument_type"].map(asset_class_map).fillna("Other"),
            "sub_asset_class": legacy["instrument_type"].map(sub_map).fillna(legacy["instrument_type"]),
            "category": legacy.get("instrument_family", legacy["instrument_type"]),
            "currency": "TRY",
            "region": "Turkey",
            "country": "Turkey",
            "issuer": legacy.get("provider_name", "Legacy"),
            "issuer_type": legacy.get("issuer_type", "Market"),
            "rating": legacy.get("rating", "NR").fillna("NR"),
            "duration_years": pd.to_numeric(legacy.get("tenor_days"), errors="coerce") / 365.0,
            "maturity_date": None,
            "coupon": 0.0,
            "expense_ratio": np.where(legacy["instrument_type"].isin(["PPF", "KVBAF", "Katılım"]), 0.8, 0.0),
            "aum_mn": np.nan,
            "esg_score": np.nan,
            "liquidity_score": pd.to_numeric(legacy.get("base_liquidity_score"), errors="coerce"),
            "yield_pct": np.nan,
            "ytm_pct": np.nan,
            "risk_score": 10,
            "theme": np.nan,
            "price": 1.0,
            "spread_bps": np.nan,
            "history_style": np.where(legacy["instrument_type"].isin(["Repo", "TersRepo", "TPP", "PPF", "KVBAF", "Katılım"]), "fund_cash", "cash"),
            "annual_return": np.where(legacy["instrument_type"].isin(["Repo", "TersRepo", "TPP", "PPF", "KVBAF", "Katılım"]), 0.42, 0.35),
            "annual_vol": np.where(legacy["instrument_type"].isin(["Repo", "TersRepo", "TPP"]), 0.01, 0.03),
            "source": "Legacy Seed",
        }
    )
    return df


def load_legacy_snapshots() -> pd.DataFrame:
    path = LEGACY_DIR / "market_quotes.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    today = _today().strftime("%Y-%m-%d")
    return pd.DataFrame(
        {
            "instrument_id": df["instrument_id"],
            "asof_date": today,
            "price": 1.0,
            "nav": 1.0,
            "yield_pct": pd.to_numeric(df.get("net_yield"), errors="coerce"),
            "ytm_pct": pd.to_numeric(df.get("net_yield"), errors="coerce"),
            "spread_bps": np.nan,
            "expense_ratio": np.nan,
            "esg_score": np.nan,
            "liquidity_score": np.nan,
            "aum_mn": np.nan,
            "quote_source": df.get("source", "Legacy Seed"),
            "updated_at": pd.to_datetime(df.get("quote_timestamp"), errors="coerce").fillna(_today()).astype(str),
        }
    )


def load_legacy_mandates() -> pd.DataFrame:
    path = LEGACY_DIR / "portfolio_rules.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    mapped_classes = {
        "Repo": "TL Money Market",
        "TersRepo": "TL Money Market",
        "TPP": "TL Money Market",
        "PPF": "TEFAS Fund",
        "KVBAF": "TEFAS Fund",
        "Katılım": "TEFAS Fund",
        "Mevduat": "Deposit",
    }

    def _map_allowed(text: str) -> str:
        raw = [x.strip() for x in str(text).split("|") if x.strip()]
        return "|".join(sorted({mapped_classes.get(x, x) for x in raw}))

    return pd.DataFrame(
        {
            "mandate_id": df["portfolio_id"],
            "name": df["portfolio_name"],
            "base_currency": "TRY",
            "allowed_asset_classes": df["allowed_instrument_types"].apply(_map_allowed),
            "min_rating": df["min_rating"].fillna("NR"),
            "max_duration_years": pd.to_numeric(df["max_horizon_days"], errors="coerce") / 365.0,
            "min_liquidity_score": np.where(df["government_only_flag"].astype(str).str.lower() == "true", 60, 40),
            "min_esg_score": np.nan,
            "allow_fx": 0,
            "notes": df.get("notes", ""),
        }
    )


def default_mandates() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "mandate_id": "GEN_TL_LIQ",
                "name": "TRY Likidite Odaklı",
                "base_currency": "TRY",
                "allowed_asset_classes": "TL Money Market|TEFAS Fund|Local Bond",
                "min_rating": "A",
                "max_duration_years": 2.0,
                "min_liquidity_score": 65,
                "min_esg_score": np.nan,
                "allow_fx": 0,
                "notes": "Likidite yüksek, duration kısa, kur riski yok.",
            },
            {
                "mandate_id": "ESG_BALANCED",
                "name": "ESG Dengeli",
                "base_currency": "USD",
                "allowed_asset_classes": "ETF|Eurobond|Local Bond|TEFAS Fund",
                "min_rating": "BBB",
                "max_duration_years": 7.0,
                "min_liquidity_score": 50,
                "min_esg_score": 75,
                "allow_fx": 1,
                "notes": "ESG eşiği yüksek, esnek karma yapı.",
            },
            {
                "mandate_id": "USD_RESERVE",
                "name": "USD Rezerv / Savunmacı",
                "base_currency": "USD",
                "allowed_asset_classes": "Eurobond|ETF",
                "min_rating": "BBB",
                "max_duration_years": 5.0,
                "min_liquidity_score": 60,
                "min_esg_score": np.nan,
                "allow_fx": 1,
                "notes": "USD tabanlı, orta-düşük riskli rezerv portföyü.",
            },
        ]
    )


def synthetic_history_for_row(row: pd.Series, dates: pd.DatetimeIndex) -> pd.DataFrame:
    seed = abs(hash(row["instrument_id"])) % (2**32 - 1)
    rng = np.random.default_rng(seed)
    annual_ret = float(row.get("annual_return", 0.08) or 0.08)
    annual_vol = float(row.get("annual_vol", 0.10) or 0.10)
    style = str(row.get("history_style", "balanced"))
    start = float(row.get("price", 100.0) or 100.0)

    if style == "fund_cash":
        daily = annual_ret / 252
        noise = rng.normal(0, annual_vol / np.sqrt(252), len(dates)) * 0.15
        rets = np.clip(daily + noise, -0.001, 0.004)
    elif style in {"bond", "eurobond", "etf_bond"}:
        mu = annual_ret / 252
        sigma = annual_vol / np.sqrt(252)
        rets = rng.normal(mu, sigma, len(dates))
        shock_idx = np.arange(120, len(dates), 160)
        for i in shock_idx:
            rets[i : i + 2] -= sigma * 2.2
    else:
        mu = annual_ret / 252
        sigma = annual_vol / np.sqrt(252)
        rets = rng.normal(mu, sigma, len(dates))
        shock_idx = np.arange(90, len(dates), 150)
        for i in shock_idx:
            rets[i : i + 3] -= sigma * 2.8

    values = start * np.cumprod(1 + rets)
    return pd.DataFrame({"instrument_id": row["instrument_id"], "date": dates.strftime("%Y-%m-%d"), "value": values})


def build_seed_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    demo = load_demo_instruments()
    legacy_inst = load_legacy_instruments()
    all_inst = pd.concat([legacy_inst, demo], ignore_index=True, sort=False)
    all_inst["symbol"] = all_inst["instrument_id"]
    all_inst["tradable"] = 1
    all_inst["is_demo"] = 1
    all_inst = all_inst.drop_duplicates(subset=["instrument_id"], keep="last")

    today = _today().strftime("%Y-%m-%d")
    demo_snapshots = all_inst[["instrument_id", "price", "yield_pct", "ytm_pct", "expense_ratio", "esg_score", "liquidity_score", "aum_mn", "spread_bps", "source"]].copy()
    demo_snapshots["asof_date"] = today
    demo_snapshots["nav"] = demo_snapshots["price"]
    demo_snapshots["quote_source"] = demo_snapshots["source"]
    demo_snapshots["updated_at"] = str(_today())
    demo_snapshots = demo_snapshots[["instrument_id", "asof_date", "price", "nav", "yield_pct", "ytm_pct", "spread_bps", "expense_ratio", "esg_score", "liquidity_score", "aum_mn", "quote_source", "updated_at"]]

    legacy_snapshots = load_legacy_snapshots()
    snapshots = pd.concat([demo_snapshots, legacy_snapshots], ignore_index=True, sort=False)
    snapshots = snapshots.sort_values(["instrument_id", "asof_date"]).drop_duplicates(["instrument_id", "asof_date"], keep="last")

    mandates = pd.concat([load_legacy_mandates(), default_mandates()], ignore_index=True, sort=False)
    mandates = mandates.drop_duplicates(subset=["mandate_id"], keep="last")

    dates = pd.bdate_range(end=_today(), periods=BUSINESS_DAYS)
    price_frames = [synthetic_history_for_row(row, dates) for _, row in all_inst.iterrows()]
    prices = pd.concat(price_frames, ignore_index=True)
    return all_inst, snapshots, mandates, prices


def reset_and_seed(db_path: Path | str = DB_PATH) -> SeedResult:
    init_db(db_path)
    inst, snapshots, mandates, prices = build_seed_frames()
    with get_connection(db_path) as con:
        con.execute("DELETE FROM app_meta")
        con.execute("DELETE FROM refresh_log")
        con.execute("DELETE FROM market_snapshot")
        con.execute("DELETE FROM price_history")
        con.execute("DELETE FROM mandates")
        con.execute("DELETE FROM instruments")

        inst[[
            "instrument_id", "symbol", "name", "asset_class", "sub_asset_class", "category", "currency", "region", "country",
            "issuer", "issuer_type", "rating", "duration_years", "maturity_date", "coupon", "expense_ratio", "aum_mn",
            "esg_score", "liquidity_score", "yield_pct", "ytm_pct", "risk_score", "theme", "tradable", "source", "is_demo"
        ]].to_sql("instruments", con, if_exists="append", index=False)
        snapshots.to_sql("market_snapshot", con, if_exists="append", index=False)
        mandates.to_sql("mandates", con, if_exists="append", index=False)
        prices.to_sql("price_history", con, if_exists="append", index=False)
        con.execute("INSERT OR REPLACE INTO app_meta(key, value) VALUES (?, ?)", ("seed_version", SEED_VERSION))
        con.execute("INSERT OR REPLACE INTO app_meta(key, value) VALUES (?, ?)", ("last_seeded_at", str(pd.Timestamp.now())))
    return SeedResult(instruments=len(inst), mandates=len(mandates), prices=len(prices), snapshots=len(snapshots))


def ensure_seeded(db_path: Path | str = DB_PATH) -> None:
    init_db(db_path)
    with get_connection(db_path) as con:
        row = con.execute("SELECT value FROM app_meta WHERE key='seed_version'").fetchone()
        if row is None or row[0] != SEED_VERSION:
            reset_and_seed(db_path)
