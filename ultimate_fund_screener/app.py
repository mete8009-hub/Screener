from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from screener.config import APP_TITLE, DB_PATH
from screener.live_refresh import refresh_all, refresh_public_try, refresh_tefas, refresh_yfinance
from screener.metrics import (
    build_price_matrix,
    correlation_matrix,
    hedge_ratios,
    mandate_fit_row,
    portfolio_metrics,
    portfolio_series,
    weighted_portfolio_attributes,
)
from screener.repository import get_app_meta, get_mandates, get_price_history, get_refresh_log, get_universe
from screener.seed import ensure_seeded, reset_and_seed

st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")


@st.cache_data(show_spinner=False)
def load_data(cache_buster: int = 0):
    ensure_seeded(DB_PATH)
    return get_universe(), get_mandates(), get_refresh_log(), get_app_meta()


@st.cache_data(show_spinner=False)
def load_history(instrument_ids: tuple[str, ...], cache_buster: int = 0):
    return get_price_history(list(instrument_ids))


def rating_order(series: pd.Series) -> pd.Series:
    scale = {"NR": 0, "B": 1, "BB": 2, "BBB": 3, "A": 4, "AA": 5, "AAA": 6}
    return series.astype(str).str.upper().map(scale).fillna(-1)


def fmt_pct(x):
    return "-" if pd.isna(x) else f"%{x:,.2f}"


def fmt_num(x):
    return "-" if pd.isna(x) else f"{x:,.2f}"


def fmt_short_dt(x: str | None) -> str:
    if not x:
        return "-"
    ts = pd.to_datetime(x, errors="coerce")
    return "-" if pd.isna(ts) else ts.strftime("%d.%m.%Y %H:%M")


if "cache_buster" not in st.session_state:
    st.session_state.cache_buster = 0

universe, mandates, refresh_log, app_meta = load_data(st.session_state.cache_buster)

st.title("📊 Fund Manager Workstation v2")
st.caption(
    "Tek web uygulamasında screener + compare + portfolio lab + mandate fit. "
    "Gerçek entegrasyon tarafında TEFAS, Yahoo Finance ve TRY kamu referansları tek tuşla yenilenir. "
    "Doğrudan kamuya açık canlı fiyatı olmayan sınıflar ise seed veriyle çalışır."
)

with st.sidebar:
    st.subheader("Kontrol Merkezi")
    if st.button("Veritabanını sıfırla ve temel veriyi yeniden kur", use_container_width=True):
        result = reset_and_seed(DB_PATH)
        st.session_state.cache_buster += 1
        st.success(f"Kuruldu: {result.instruments} enstrüman, {result.mandates} mandate, {result.prices} tarihçe satırı.")
        st.rerun()

    st.markdown("### Gerçek veri yenile")
    if st.button("Tüm gerçek / kamu verisini yenile", type="primary", use_container_width=True):
        summary = refresh_all(DB_PATH, years=3)
        st.session_state.cache_buster += 1
        ok_count = sum(1 for r in summary.runs if r.status == "ok")
        st.success(f"Yenileme tamamlandı. Başarılı kaynak: {ok_count}/{len(summary.runs)}")
        for run in summary.runs:
            if run.status == "ok":
                st.write(f"✅ {run.source}: {run.message}")
            else:
                st.write(f"⚠️ {run.source}: {run.message}")
        st.rerun()

    c1, c2 = st.columns(2)
    if c1.button("TEFAS", use_container_width=True):
        run = refresh_tefas(DB_PATH)
        st.session_state.cache_buster += 1
        st.success(run.message if run.status == "ok" else run.message)
        st.rerun()
    if c2.button("ETF", use_container_width=True):
        run = refresh_yfinance(DB_PATH, years=3)
        st.session_state.cache_buster += 1
        st.success(run.message if run.status == "ok" else run.message)
        st.rerun()
    if st.button("TRY kamu referansı", use_container_width=True):
        run = refresh_public_try(DB_PATH)
        st.session_state.cache_buster += 1
        st.success(run.message if run.status == "ok" else run.message)
        st.rerun()

    st.markdown("---")
    selected_mandate_id = st.selectbox(
        "Aktif mandate",
        mandates["mandate_id"].tolist(),
        format_func=lambda x: mandates.loc[mandates["mandate_id"] == x, "name"].iloc[0],
    )
    selected_mandate = mandates[mandates["mandate_id"] == selected_mandate_id].iloc[0]
    st.info(
        f"Baz döviz: {selected_mandate['base_currency']}\n\n"
        f"İzinli sınıflar: {selected_mandate['allowed_asset_classes']}\n\n"
        f"Min rating: {selected_mandate['min_rating']}"
    )

    meta_map = dict(zip(app_meta["key"], app_meta["value"])) if not app_meta.empty else {}
    st.caption(f"Son seed: {fmt_short_dt(meta_map.get('last_seeded_at'))}")
    st.caption(f"Son ETF yenileme: {fmt_short_dt(meta_map.get('last_refresh_yfinance'))}")
    st.caption(f"Son TEFAS yenileme: {fmt_short_dt(meta_map.get('last_refresh_tefas'))}")
    st.caption(f"Son TRY referans: {fmt_short_dt(meta_map.get('last_refresh_public_try'))}")

fit = universe.apply(lambda r: mandate_fit_row(r, selected_mandate), axis=1, result_type="expand")
universe = universe.copy()
universe["mandate_fit"] = fit[0]
universe["mandate_note"] = fit[1]
universe["data_status"] = universe["is_demo"].map({0: "Canlı / Kamu", 1: "Seed"}).fillna("Seed")

market_tab, screener_tab, compare_tab, portfolio_tab, mandate_tab, data_tab = st.tabs(
    ["Market Map", "Screener", "Compare", "Portfolio Lab", "Mandates", "Data"]
)

with market_tab:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam enstrüman", f"{len(universe)}")
    c2.metric("Asset class", f"{universe['asset_class'].nunique()}")
    c3.metric("Pass sayısı", f"{(universe['mandate_fit'] == 'Pass').sum()}")
    c4.metric("Canlı/Kamu veri", f"{(universe['is_demo'] == 0).sum()}")

    left, right = st.columns([1.4, 1])
    with left:
        asset_counts = universe.groupby(["asset_class", "data_status"]).size().reset_index(name="count")
        fig = px.bar(asset_counts, x="asset_class", y="count", color="data_status", barmode="group", title="Asset class dağılımı")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        top_yield = universe.sort_values("ytm_pct", ascending=False).head(12)[["name", "asset_class", "currency", "ytm_pct", "esg_score", "data_status", "mandate_fit"]]
        top_yield = top_yield.rename(columns={"name": "Enstrüman", "asset_class": "Asset", "currency": "Döviz", "ytm_pct": "YTM", "esg_score": "ESG", "data_status": "Veri", "mandate_fit": "Fit"})
        st.dataframe(top_yield, use_container_width=True, hide_index=True)

    st.markdown("#### Hızlı bakış")
    quick = universe.sort_values(["mandate_fit", "data_status", "liquidity_score", "ytm_pct"], ascending=[True, True, False, False]).head(15)
    quick = quick[["name", "asset_class", "category", "currency", "yield_pct", "ytm_pct", "esg_score", "liquidity_score", "data_status", "mandate_fit", "mandate_note"]]
    quick = quick.rename(columns={"name": "Enstrüman", "asset_class": "Asset", "category": "Kategori", "currency": "Döviz", "yield_pct": "Getiri", "ytm_pct": "YTM", "esg_score": "ESG", "liquidity_score": "Likidite", "data_status": "Veri", "mandate_fit": "Fit", "mandate_note": "Not"})
    st.dataframe(quick, use_container_width=True, hide_index=True)

with screener_tab:
    st.markdown("### Universal Screener")
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        asset_filter = st.multiselect("Asset class", sorted(universe["asset_class"].dropna().unique()), default=[])
        category_filter = st.multiselect("Kategori", sorted(universe["category"].dropna().astype(str).unique()), default=[])
    with f2:
        currency_filter = st.multiselect("Döviz", sorted(universe["currency"].dropna().unique()), default=[])
        theme_filter = st.multiselect("Tema", sorted([x for x in universe["theme"].dropna().astype(str).unique() if x]), default=[])
    with f3:
        min_esg = st.slider("Minimum ESG", 0, 100, 0)
        min_liq = st.slider("Minimum likidite", 0, 100, 0)
    with f4:
        max_duration = st.slider("Maksimum duration (yıl)", 0.0, 15.0, 15.0, 0.5)
        min_ytm = st.number_input("Minimum YTM", value=0.0, step=0.5)

    s1, s2, s3, s4 = st.columns([1.6, 1, 1, 1])
    with s1:
        search = st.text_input("Ara", placeholder="green, eurobond, repo, treasury...")
    with s2:
        only_pass = st.checkbox("Sadece Pass", value=False)
    with s3:
        only_live = st.checkbox("Sadece canlı/kamu", value=False)
    with s4:
        sort_by = st.selectbox("Sırala", ["Mandate fit", "YTM yüksekten", "ESG yüksekten", "Likidite yüksekten", "AUM yüksekten", "Duration kısadan"])

    filt = universe.copy()
    if asset_filter:
        filt = filt[filt["asset_class"].isin(asset_filter)]
    if category_filter:
        filt = filt[filt["category"].isin(category_filter)]
    if currency_filter:
        filt = filt[filt["currency"].isin(currency_filter)]
    if theme_filter:
        filt = filt[filt["theme"].isin(theme_filter)]
    filt = filt[(filt["esg_score"].fillna(0) >= min_esg) & (filt["liquidity_score"].fillna(0) >= min_liq)]
    filt = filt[(filt["duration_years"].fillna(0) <= max_duration) & (filt["ytm_pct"].fillna(0) >= min_ytm)]
    if search:
        q = search.lower().strip()
        mask = (
            filt["name"].astype(str).str.lower().str.contains(q)
            | filt["category"].astype(str).str.lower().str.contains(q)
            | filt["asset_class"].astype(str).str.lower().str.contains(q)
            | filt["theme"].astype(str).str.lower().str.contains(q)
        )
        filt = filt[mask]
    if only_pass:
        filt = filt[filt["mandate_fit"] == "Pass"]
    if only_live:
        filt = filt[filt["is_demo"] == 0]

    if sort_by == "Mandate fit":
        filt = filt.assign(_fit_order=filt["mandate_fit"].map({"Pass": 0, "Warning": 1, "Block": 2}).fillna(3), _rating=rating_order(filt["rating"]))
        filt = filt.sort_values(["_fit_order", "is_demo", "_rating", "liquidity_score", "ytm_pct"], ascending=[True, True, False, False, False]).drop(columns=["_fit_order", "_rating"])
    elif sort_by == "YTM yüksekten":
        filt = filt.sort_values("ytm_pct", ascending=False)
    elif sort_by == "ESG yüksekten":
        filt = filt.sort_values("esg_score", ascending=False)
    elif sort_by == "Likidite yüksekten":
        filt = filt.sort_values("liquidity_score", ascending=False)
    elif sort_by == "AUM yüksekten":
        filt = filt.sort_values("aum_mn", ascending=False)
    else:
        filt = filt.sort_values("duration_years", ascending=True)

    st.write(f"Sonuç: {len(filt)} enstrüman")
    display = filt[["instrument_id", "name", "asset_class", "sub_asset_class", "category", "currency", "rating", "duration_years", "yield_pct", "ytm_pct", "esg_score", "liquidity_score", "aum_mn", "theme", "data_status", "mandate_fit", "mandate_note"]].rename(
        columns={
            "instrument_id": "Kod",
            "name": "Enstrüman",
            "asset_class": "Asset",
            "sub_asset_class": "Alt Sınıf",
            "category": "Kategori",
            "currency": "Döviz",
            "rating": "Rating",
            "duration_years": "Duration",
            "yield_pct": "Getiri",
            "ytm_pct": "YTM",
            "esg_score": "ESG",
            "liquidity_score": "Likidite",
            "aum_mn": "AUM(mn)",
            "theme": "Tema",
            "data_status": "Veri",
            "mandate_fit": "Fit",
            "mandate_note": "Mandate Notu",
        }
    )
    st.dataframe(display, use_container_width=True, hide_index=True)

with compare_tab:
    st.markdown("### Compare Desk")
    compare_ids = st.multiselect(
        "Karşılaştırılacak enstrümanlar",
        universe["instrument_id"].tolist(),
        format_func=lambda x: universe.loc[universe["instrument_id"] == x, "name"].iloc[0],
        default=universe["instrument_id"].head(3).tolist(),
    )
    if compare_ids:
        comp = universe[universe["instrument_id"].isin(compare_ids)].copy()
        comp_display = comp[["name", "asset_class", "category", "currency", "rating", "duration_years", "yield_pct", "ytm_pct", "expense_ratio", "esg_score", "liquidity_score", "aum_mn", "data_status", "mandate_fit", "mandate_note"]]
        comp_display = comp_display.rename(columns={"name": "Enstrüman", "asset_class": "Asset", "category": "Kategori", "currency": "Döviz", "rating": "Rating", "duration_years": "Duration", "yield_pct": "Getiri", "ytm_pct": "YTM", "expense_ratio": "Gider", "esg_score": "ESG", "liquidity_score": "Likidite", "aum_mn": "AUM(mn)", "data_status": "Veri", "mandate_fit": "Fit", "mandate_note": "Not"})
        st.dataframe(comp_display, use_container_width=True, hide_index=True)

        history = load_history(tuple(compare_ids), st.session_state.cache_buster)
        px_matrix = build_price_matrix(history)
        if not px_matrix.empty:
            normalized = px_matrix / px_matrix.iloc[0] * 100
            fig = px.line(normalized.reset_index(), x="date", y=normalized.columns, title="Normalize performans (100=başlangıç)")
            st.plotly_chart(fig, use_container_width=True)

            corr = correlation_matrix(px_matrix)
            st.markdown("#### Korelasyon")
            st.dataframe(corr.style.format("{:.2f}"), use_container_width=True)

            hedge = hedge_ratios(px_matrix)
            if not hedge.empty:
                hedge["hedge_from_name"] = hedge["hedge_from"].map(dict(zip(universe["instrument_id"], universe["name"])))
                hedge["hedge_with_name"] = hedge["hedge_with"].map(dict(zip(universe["instrument_id"], universe["name"])))
                st.markdown("#### Basit hedge oranları")
                st.dataframe(
                    hedge[["hedge_from_name", "hedge_with_name", "ratio"]]
                    .rename(columns={"hedge_from_name": "Pozisyon", "hedge_with_name": "Hedge Aracı", "ratio": "Oran"})
                    .sort_values("Oran", ascending=False),
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.info("Bu seçim için yeterli tarihçe yok.")
    else:
        st.info("En az 1 enstrüman seç.")

with portfolio_tab:
    st.markdown("### Portfolio Lab")
    default_ids = universe[universe["mandate_fit"] == "Pass"]["instrument_id"].head(3).tolist() or universe["instrument_id"].head(3).tolist()
    selected_ids = st.multiselect(
        "Portföye eklenecek enstrümanlar",
        universe["instrument_id"].tolist(),
        format_func=lambda x: universe.loc[universe["instrument_id"] == x, "name"].iloc[0],
        default=default_ids,
    )
    if selected_ids:
        weight_df = pd.DataFrame(
            {
                "instrument_id": selected_ids,
                "Enstrüman": [universe.loc[universe["instrument_id"] == i, "name"].iloc[0] for i in selected_ids],
                "Ağırlık (%)": [round(100 / len(selected_ids), 2)] * len(selected_ids),
            }
        )
        edited = st.data_editor(weight_df, use_container_width=True, hide_index=True, num_rows="fixed")
        weights = dict(zip(edited["instrument_id"], pd.to_numeric(edited["Ağırlık (%)"], errors="coerce").fillna(0) / 100))
        total_weight = sum(weights.values())
        if total_weight <= 0:
            st.error("Ağırlık toplamı sıfır olamaz.")
        else:
            history = load_history(tuple(selected_ids), st.session_state.cache_buster)
            px_matrix = build_price_matrix(history)
            port = portfolio_series(px_matrix, weights)
            if port.empty:
                st.warning("Yeterli fiyat geçmişi yok.")
            else:
                metrics = portfolio_metrics(port)
                attrs = weighted_portfolio_attributes(universe, weights)
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("CAGR", fmt_pct(metrics.get("CAGR") * 100 if metrics.get("CAGR") is not None else None))
                m2.metric("Vol", fmt_pct(metrics.get("Annual Vol") * 100 if metrics.get("Annual Vol") is not None else None))
                m3.metric("Max DD", fmt_pct(metrics.get("Max Drawdown") * 100 if metrics.get("Max Drawdown") is not None else None))
                m4.metric("Sharpe", fmt_num(metrics.get("Sharpe")))

                a1, a2, a3, a4 = st.columns(4)
                a1.metric("Ağırlıklı YTM", fmt_pct(attrs.get("Weighted YTM")))
                a2.metric("Ağırlıklı Duration", fmt_num(attrs.get("Weighted Duration")))
                a3.metric("Ağırlıklı ESG", fmt_num(attrs.get("Weighted ESG")))
                a4.metric("Ağırlıklı Likidite", fmt_num(attrs.get("Weighted Liquidity")))

                series_df = (port / port.iloc[0] * 100).reset_index()
                series_df.columns = ["date", "portfolio"]
                fig = px.line(series_df, x="date", y="portfolio", title="Portföy geçmiş performansı (100=başlangıç)")
                st.plotly_chart(fig, use_container_width=True)

                metrics_table = pd.DataFrame({"Metric": list(metrics.keys()), "Value": list(metrics.values())})
                st.dataframe(metrics_table, use_container_width=True, hide_index=True)

                comp = universe[universe["instrument_id"].isin(selected_ids)][["instrument_id", "name", "asset_class", "currency", "rating", "duration_years", "liquidity_score", "mandate_fit", "data_status"]].copy()
                comp["Ağırlık (%)"] = comp["instrument_id"].map(dict(zip(edited["instrument_id"], edited["Ağırlık (%)"])))
                st.markdown("#### Sepet özeti")
                st.dataframe(comp.rename(columns={"name": "Enstrüman", "asset_class": "Asset", "currency": "Döviz", "rating": "Rating", "duration_years": "Duration", "liquidity_score": "Likidite", "mandate_fit": "Fit", "data_status": "Veri"}), use_container_width=True, hide_index=True)

                corr = correlation_matrix(px_matrix)
                if not corr.empty:
                    st.markdown("#### Portföy içi korelasyon")
                    st.dataframe(corr.style.format("{:.2f}"), use_container_width=True)
    else:
        st.info("Portföye en az 1 enstrüman ekle.")

with mandate_tab:
    st.markdown("### Mandate merkezi")
    st.dataframe(
        mandates.rename(columns={"mandate_id": "Kod", "name": "Mandate", "base_currency": "Baz Döviz", "allowed_asset_classes": "İzinli Asset Class", "min_rating": "Min Rating", "max_duration_years": "Max Duration", "min_liquidity_score": "Min Likidite", "min_esg_score": "Min ESG", "allow_fx": "FX Serbest", "notes": "Not"}),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### Aktif mandate altında warning / block listesi")
    blocked = universe[universe["mandate_fit"] != "Pass"][ ["name", "asset_class", "currency", "rating", "duration_years", "esg_score", "liquidity_score", "data_status", "mandate_fit", "mandate_note"] ]
    blocked = blocked.rename(columns={"name": "Enstrüman", "asset_class": "Asset", "currency": "Döviz", "rating": "Rating", "duration_years": "Duration", "esg_score": "ESG", "liquidity_score": "Likidite", "data_status": "Veri", "mandate_fit": "Fit", "mandate_note": "Not"})
    st.dataframe(blocked, use_container_width=True, hide_index=True)

with data_tab:
    st.markdown("### Veri ve kapsam")
    coverage = universe.groupby(["asset_class", "data_status"]).size().reset_index(name="adet")
    st.dataframe(coverage, use_container_width=True, hide_index=True)

    st.markdown("#### Son yenileme logu")
    if refresh_log.empty:
        st.info("Henüz yenileme logu yok.")
    else:
        st.dataframe(refresh_log.rename(columns={"run_at": "Zaman", "source": "Kaynak", "status": "Durum", "message": "Mesaj", "rows_loaded": "Satır"}), use_container_width=True, hide_index=True)

    st.markdown("#### Bu v2 sürümünde ne gerçek?")
    st.write("- ETF ve ETF tarihçesi: Yahoo Finance üzerinden tek tuşla yenilenir.")
    st.write("- TEFAS watchlist: fon sayfalarından tek tuşla yenilenir.")
    st.write("- Repo ve TPP: kamuya açık resmi sayfalardan referans olarak yenilenir.")
    st.write("- Kamuya açık doğrudan canlı fiyatı olmayan bazı local bond / eurobond satırları: seed olarak kalır.")

    st.markdown("#### Kullanım")
    st.write("1. İlk kurulumdan sonra soldan 'Tüm gerçek / kamu verisini yenile' tuşuna bas.")
    st.write("2. Screener'da filtrele, Compare'da yan yana bak, Portfolio Lab'de sepet kur.")
    st.write("3. Verisi seed olan sınıfları Data sekmesinden gör; ileride lisanslı feed eklenince aynı yapıya bağlanabilir.")
