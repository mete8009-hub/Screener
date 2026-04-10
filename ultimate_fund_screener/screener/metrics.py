from __future__ import annotations

import math

import numpy as np
import pandas as pd

RATING_SCALE = {
    "NR": 0,
    "B": 1,
    "BB": 2,
    "BBB": 3,
    "A": 4,
    "AA": 5,
    "AAA": 6,
}


def rating_value(value: str | None) -> int:
    if value is None:
        return 0
    return RATING_SCALE.get(str(value).upper().strip(), 0)


def mandate_fit_row(row: pd.Series, mandate: pd.Series) -> tuple[str, str]:
    reasons: list[str] = []
    status = "Pass"

    allowed = {x.strip() for x in str(mandate.get("allowed_asset_classes", "")).split("|") if x.strip()}
    if allowed and row.get("asset_class") not in allowed:
        return "Block", "Asset class izinli değil"

    min_rating = rating_value(mandate.get("min_rating"))
    if rating_value(row.get("rating")) < min_rating:
        status = "Warning" if status == "Pass" else status
        reasons.append("Rating eşiğinin altında")

    max_duration = mandate.get("max_duration_years")
    try:
        duration = float(row.get("duration_years"))
    except Exception:
        duration = math.nan
    if pd.notna(max_duration) and pd.notna(duration) and duration > float(max_duration):
        status = "Warning" if status == "Pass" else status
        reasons.append("Duration limiti aşılıyor")

    min_liq = mandate.get("min_liquidity_score")
    if pd.notna(min_liq) and pd.notna(row.get("liquidity_score")) and float(row.get("liquidity_score")) < float(min_liq):
        status = "Warning" if status == "Pass" else status
        reasons.append("Likidite skoru düşük")

    min_esg = mandate.get("min_esg_score")
    if pd.notna(min_esg) and pd.notna(row.get("esg_score")) and float(row.get("esg_score")) < float(min_esg):
        status = "Warning" if status == "Pass" else status
        reasons.append("ESG skoru düşük")

    allow_fx = int(mandate.get("allow_fx", 1) or 0)
    base_currency = str(mandate.get("base_currency") or "").upper().strip()
    instrument_ccy = str(row.get("currency") or "").upper().strip()
    if not allow_fx and base_currency and instrument_ccy and instrument_ccy != base_currency:
        return "Block", "Kur riski mandate dışı"

    return status, " | ".join(reasons) if reasons else "Mandate ile uyumlu"



def build_price_matrix(price_history: pd.DataFrame) -> pd.DataFrame:
    if price_history.empty:
        return pd.DataFrame()
    px = price_history.pivot(index="date", columns="instrument_id", values="value").sort_index()
    return px.ffill().dropna(how="all")



def portfolio_series(price_matrix: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    if price_matrix.empty:
        return pd.Series(dtype=float)
    available = [c for c in price_matrix.columns if c in weights]
    if not available:
        return pd.Series(dtype=float)
    px = price_matrix[available].dropna(how="all").ffill().dropna()
    if px.empty:
        return pd.Series(dtype=float)
    rets = px.pct_change().fillna(0.0)
    w = np.array([weights[c] for c in available], dtype=float)
    if w.sum() == 0:
        return pd.Series(dtype=float)
    w = w / w.sum()
    port_rets = rets.mul(w, axis=1).sum(axis=1)
    return (1 + port_rets).cumprod()



def portfolio_metrics(series: pd.Series) -> dict[str, float]:
    if series.empty or len(series) < 3:
        return {}
    rets = series.pct_change().dropna()
    total_return = series.iloc[-1] / series.iloc[0] - 1
    years = max((series.index[-1] - series.index[0]).days / 365.25, 1 / 252)
    cagr = (series.iloc[-1] / series.iloc[0]) ** (1 / years) - 1
    vol = rets.std() * np.sqrt(252)
    downside = rets[rets < 0]
    sortino = (rets.mean() * 252) / (downside.std() * np.sqrt(252)) if len(downside) > 1 and downside.std() > 0 else np.nan
    sharpe = (rets.mean() * 252) / vol if vol > 0 else np.nan
    running_max = series.cummax()
    dd = series / running_max - 1
    max_dd = dd.min()
    calmar = cagr / abs(max_dd) if max_dd < 0 else np.nan
    hit_ratio = (rets > 0).mean()
    var95 = np.quantile(rets, 0.05)
    cvar95 = rets[rets <= var95].mean() if len(rets[rets <= var95]) else np.nan
    return {
        "Total Return": total_return,
        "CAGR": cagr,
        "Annual Vol": vol,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "Max Drawdown": max_dd,
        "Calmar": calmar,
        "Hit Ratio": hit_ratio,
        "VaR 95": var95,
        "CVaR 95": cvar95,
    }



def correlation_matrix(price_matrix: pd.DataFrame) -> pd.DataFrame:
    if price_matrix.empty:
        return pd.DataFrame()
    return price_matrix.pct_change().dropna().corr()



def hedge_ratios(price_matrix: pd.DataFrame) -> pd.DataFrame:
    if price_matrix.empty or price_matrix.shape[1] < 2:
        return pd.DataFrame(columns=["hedge_from", "hedge_with", "ratio"])
    rets = price_matrix.pct_change().dropna()
    rows = []
    cols = list(rets.columns)
    for i in cols:
        for j in cols:
            if i == j:
                continue
            var_j = rets[j].var()
            if var_j and not np.isnan(var_j):
                ratio = rets[i].cov(rets[j]) / var_j
                rows.append({"hedge_from": i, "hedge_with": j, "ratio": ratio})
    return pd.DataFrame(rows)
