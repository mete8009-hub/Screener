from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import DB_PATH


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS instruments (
    instrument_id TEXT PRIMARY KEY,
    symbol TEXT,
    name TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    sub_asset_class TEXT,
    category TEXT,
    currency TEXT,
    region TEXT,
    country TEXT,
    issuer TEXT,
    issuer_type TEXT,
    rating TEXT,
    duration_years REAL,
    maturity_date TEXT,
    coupon REAL,
    expense_ratio REAL,
    aum_mn REAL,
    esg_score REAL,
    liquidity_score REAL,
    yield_pct REAL,
    ytm_pct REAL,
    risk_score REAL,
    theme TEXT,
    tradable INTEGER DEFAULT 1,
    source TEXT,
    is_demo INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS market_snapshot (
    instrument_id TEXT NOT NULL,
    asof_date TEXT NOT NULL,
    price REAL,
    nav REAL,
    yield_pct REAL,
    ytm_pct REAL,
    spread_bps REAL,
    expense_ratio REAL,
    esg_score REAL,
    liquidity_score REAL,
    aum_mn REAL,
    quote_source TEXT,
    updated_at TEXT,
    PRIMARY KEY (instrument_id, asof_date),
    FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id)
);

CREATE TABLE IF NOT EXISTS price_history (
    instrument_id TEXT NOT NULL,
    date TEXT NOT NULL,
    value REAL NOT NULL,
    PRIMARY KEY (instrument_id, date),
    FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id)
);

CREATE TABLE IF NOT EXISTS mandates (
    mandate_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_currency TEXT,
    allowed_asset_classes TEXT,
    min_rating TEXT,
    max_duration_years REAL,
    min_liquidity_score REAL,
    min_esg_score REAL,
    allow_fx INTEGER DEFAULT 1,
    notes TEXT
);
"""


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path), check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


@contextmanager
def get_connection(db_path: Path | str = DB_PATH):
    con = connect(db_path)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db(db_path: Path | str = DB_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with get_connection(db_path) as con:
        con.executescript(SCHEMA_SQL)
