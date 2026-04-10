from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from screener.config import APP_TITLE, DB_PATH
from screener.metrics import build_price_matrix, correlation_matrix, hedge_ratios, mandate_fit_row, portfolio_metrics, portfolio_series
from screener.repository import get_mandates, get_price_history, get_universe
from screener.seed import ensure_seeded, reset_and_seed

st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")


@st.cache_data(show_spinner=False)
def load_data(seed_nonce: int = 0):
    ensure_seeded(DB_PATH)
    universe = get_universe()
    mandates = get_mandates()
    return universe, mandates



def rating_order(series: pd.Series) -> pd.Series:
    scale = {"NR": 0, "B": 1, "BB": 2, "BBB": 3, "A": 4, "AA": 5, "AAA": 6}
    return series.astype(str).str.upper().map(scale).fillna(-1)



def fmt_pct(x):
    return "-" if pd.isna(x) else f"%{x:,.2f}"



def fmt_num(x):
    return "-" if pd.isna(x) else f"{x:,.2f}"


if "seed_nonce" not in st.session_state:
    st.session_state.seed_nonce = 0

universe, mandates = load_data(st.session_state.seed_nonce)

st.title("📊 Fund Manager Workstation")
st.caption("Tek web uygulaması içinde screener + compare + mandate fit + portfolio lab. Demo veri ve mevcut legacy CSV'lerin birleşimiyle çalışır.")

with st.sidebar:
    st.subheader("Kontrol Merkezi")
    st.write("Bu sürümde ayrı Excel / VBA / Sheets / Apps Script zinciri yok. Verinin başlangıç yüklemesi ve yenilemesi uygulama içinden yapılır.")
    if st.button("Veritabanını sıfırla ve yeniden kur", use_container_width=True, type="primary"):
        result = reset_and_seed(DB_PATH)
        st.session_state.seed_nonce += 1
        st.success(f"Kuruldu: {result.instruments} enstrüman, {result.mandates} mandate, {result.prices} fiyat satırı.")
        st.rerun()

    st.markdown("---")
    selected_mandate_id = st.selectbox("Aktif mandate", mandates["mandate_id"].tolist(), format_func=lambda x: mandates.loc[mandates["mandate_id"] == x, "name"].iloc[0])
    selected_mandate = mandates[mandates["mandate_id"] == selected_mandate_id].iloc[0]
    st.info(f"Baz para birimi: {selected_mandate['base_currency']}\n\nAllowed: {selected_mandate['allowed_asset_classes']}")

# Build mandate fit table once
fit = universe.apply(lambda r: mandate_fit_row(r, selected_mandate), axis=1, result_type="expand")
universe["mandate_fit"] = fit[0]
universe["mandate_note"] = fit[1]

# Main tabs
summary_tab, screener_tab, compare_tab, portfolio_tab, mandate_tab, data_tab = st.tabs([
    "Market Map", "Screener", "Compare", "Portfolio Lab", "Mandates", "Data"
])

with summary_tab:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam enstrüman", f"{len(universe)}")
    c2.metric("Asset class", f"{universe['asset_class'].nunique()}")
    c3.metric("Pass sayısı", f"{(universe['mandate_fit'] == 'Pass').sum()}")
    c4.metric("Warning/Block", f"{(universe['mandate_fit'] != 'Pass').sum()}")

    left, right = st.columns([1.4, 1])
    with left:
        asset_counts = universe.groupby("asset_class").size().reset_index(name="count")
        fig = px.bar(asset_counts, x="asset_class", y="count", title="Asset class dağılımı")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        top_yield = universe.sort_values("ytm_pct", ascending=False).head(10)[["name", "asset_class", "currency", "ytm_pct", "esg_score", "mandate_fit"]]
        top_yield = top_yield.rename(columns={"name": "Enstrüman", "asset_class": "Asset", "currency": "Döviz", "ytm_pct": "YTM", "esg_score": "ESG", "mandate_fit": "Mandate"})
        st.dataframe(top_yield, use_container_width=True, hide_index=True)

    st.markdown("#### Bugün neye bakmalı?")
    quick = universe.sort_values(["mandate_fit", "esg_score", "liquidity_score"], ascending=[True, False, False]).head(12)[
        ["name", "asset_class", "category", "currency", "yield_pct", "ytm_pct", "esg_score", "liquidity_score", "mandate_fit", "mandate_note"]
    ]
    quick = quick.rename(columns={"name": "Enstrüman", "asset_class": "Asset", "category": "Kategori", "currency": "Döviz", "yield_pct": "Getiri", "ytm_pct": "YTM", "esg_score": "ESG", "liquidity_score": "Likidite", "mandate_fit": "Fit", "mandate_note": "Not"})
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

    s1, s2, s3 = st.columns([1.6, 1, 1])
    with s1:
        search = st.text_input("Ara", placeholder="green, eurobond, repo, treasury...")
    with s2:
        only_pass = st.checkbox("Sadece Pass", value=False)
    with s3:
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

    if sort_by == "Mandate fit":
        filt = filt.assign(_fit_order=filt["mandate_fit"].map({"Pass": 0, "Warning": 1, "Block": 2}).fillna(3), _rating=rating_order(filt["rating"]))
        filt = filt.sort_values(["_fit_order", "_rating", "liquidity_score", "ytm_pct"], ascending=[True, False, False, False]).drop(columns=["_fit_order", "_rating"])
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
    display = filt[["name", "asset_class", "sub_asset_class", "category", "currency", "rating", "duration_years", "yield_pct", "ytm_pct", "esg_score", "liquidity_score", "aum_mn", "theme", "mandate_fit", "mandate_note"]].rename(
        columns={
            "name": "Enstrüman", "asset_class": "Asset", "sub_asset_class": "Alt Sınıf", "category": "Kategori", "currency": "Döviz", "rating": "Rating",
            "duration_years": "Duration", "yield_pct": "Getiri", "ytm_pct": "YTM", "esg_score": "ESG", "liquidity_score": "Likidite", "aum_mn": "AUM(mn)",
            "theme": "Tema", "mandate_fit": "Fit", "mandate_note": "Mandate Notu"
        }
    )
    st.dataframe(display, use_container_width=True, hide_index=True)

with compare_tab:
    st.markdown("### Compare Desk")
    compare_ids = st.multiselect("Karşılaştırılacak enstrümanlar", universe["instrument_id"].tolist(), format_func=lambda x: universe.loc[universe["instrument_id"] == x, "name"].iloc[0], default=universe["instrument_id"].head(3).tolist())
    if compare_ids:
        comp = universe[universe["instrument_id"].isin(compare_ids)].copy()
        comp_display = comp[["name", "asset_class", "category", "currency", "rating", "duration_years", "yield_pct", "ytm_pct", "expense_ratio", "esg_score", "liquidity_score", "aum_mn", "mandate_fit", "mandate_note"]]
        comp_display = comp_display.rename(columns={"name": "Enstrüman", "asset_class": "Asset", "category": "Kategori", "currency": "Döviz", "rating": "Rating", "duration_years": "Duration", "yield_pct": "Getiri", "ytm_pct": "YTM", "expense_ratio": "Gider", "esg_score": "ESG", "liquidity_score": "Likidite", "aum_mn": "AUM(mn)", "mandate_fit": "Fit", "mandate_note": "Not"})
        st.dataframe(comp_display, use_container_width=True, hide_index=True)

        history = get_price_history(compare_ids)
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
                st.dataframe(hedge[["hedge_from_name", "hedge_with_name", "ratio"]].rename(columns={"hedge_from_name": "Pozisyon", "hedge_with_name": "Hedge Aracı", "ratio": "Oran"}), use_container_width=True, hide_index=True)
    else:
        st.info("En az 1 enstrüman seç.")

with portfolio_tab:
    st.markdown("### Portfolio Lab")
    default_ids = universe[universe["mandate_fit"] == "Pass"]["instrument_id"].head(3).tolist() or universe["instrument_id"].head(3).tolist()
    selected_ids = st.multiselect("Portföye eklenecek enstrümanlar", universe["instrument_id"].tolist(), format_func=lambda x: universe.loc[universe["instrument_id"] == x, "name"].iloc[0], default=default_ids)
    if selected_ids:
        weight_df = pd.DataFrame({
            "instrument_id": selected_ids,
            "Enstrüman": [universe.loc[universe["instrument_id"] == i, "name"].iloc[0] for i in selected_ids],
            "Ağırlık (%)": [round(100 / len(selected_ids), 2)] * len(selected_ids),
        })
        edited = st.data_editor(weight_df, use_container_width=True, hide_index=True, num_rows="fixed")
        weights = dict(zip(edited["instrument_id"], pd.to_numeric(edited["Ağırlık (%)"], errors="coerce").fillna(0) / 100))
        total_weight = sum(weights.values())
        if total_weight <= 0:
            st.error("Ağırlık toplamı sıfır olamaz.")
        else:
            history = get_price_history(selected_ids)
            px_matrix = build_price_matrix(history)
            port = portfolio_series(px_matrix, weights)
            if port.empty:
                st.warning("Yeterli fiyat geçmişi yok.")
            else:
                metrics = portfolio_metrics(port)
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("CAGR", fmt_pct(metrics.get("CAGR") * 100 if metrics.get("CAGR") is not None else None))
                m2.metric("Vol", fmt_pct(metrics.get("Annual Vol") * 100 if metrics.get("Annual Vol") is not None else None))
                m3.metric("Max DD", fmt_pct(metrics.get("Max Drawdown") * 100 if metrics.get("Max Drawdown") is not None else None))
                m4.metric("Sharpe", fmt_num(metrics.get("Sharpe")))

                series_df = (port / port.iloc[0] * 100).reset_index()
                series_df.columns = ["date", "portfolio"]
                fig = px.line(series_df, x="date", y="portfolio", title="Portföy geçmiş performansı (100=başlangıç)")
                st.plotly_chart(fig, use_container_width=True)

                metrics_table = pd.DataFrame({"Metric": list(metrics.keys()), "Value": list(metrics.values())})
                st.dataframe(metrics_table, use_container_width=True, hide_index=True)

                comp = universe[universe["instrument_id"].isin(selected_ids)][["name", "asset_class", "currency", "rating", "duration_years", "liquidity_score", "mandate_fit"]].copy()
                comp["Ağırlık (%)"] = comp["name"].map(dict(zip(edited["Enstrüman"], edited["Ağırlık (%)"])))
                st.markdown("#### Sepet özeti")
                st.dataframe(comp.rename(columns={"name": "Enstrüman", "asset_class": "Asset", "currency": "Döviz", "rating": "Rating", "duration_years": "Duration", "liquidity_score": "Likidite", "mandate_fit": "Fit"}), use_container_width=True, hide_index=True)

                corr = correlation_matrix(px_matrix)
                if not corr.empty:
                    st.markdown("#### Portföy içi korelasyon")
                    st.dataframe(corr.style.format("{:.2f}"), use_container_width=True)
    else:
        st.info("Portföye en az 1 enstrüman ekle.")

with mandate_tab:
    st.markdown("### Mandate merkezi")
    st.dataframe(mandates.rename(columns={"mandate_id": "Kod", "name": "Mandate", "base_currency": "Baz Döviz", "allowed_asset_classes": "İzinli Asset Class", "min_rating": "Min Rating", "max_duration_years": "Max Duration", "min_liquidity_score": "Min Likidite", "min_esg_score": "Min ESG", "allow_fx": "FX Serbest", "notes": "Not"}), use_container_width=True, hide_index=True)

    st.markdown("#### Aktif mandate altında blokajlar")
    blocked = universe[universe["mandate_fit"] != "Pass"][ ["name", "asset_class", "currency", "rating", "duration_years", "esg_score", "liquidity_score", "mandate_fit", "mandate_note"] ]
    blocked = blocked.rename(columns={"name": "Enstrüman", "asset_class": "Asset", "currency": "Döviz", "rating": "Rating", "duration_years": "Duration", "esg_score": "ESG", "liquidity_score": "Likidite", "mandate_fit": "Fit", "mandate_note": "Not"})
    st.dataframe(blocked, use_container_width=True, hide_index=True)

with data_tab:
    st.markdown("### Data açıklaması")
    st.write("Bu sürüm tek proje içinde çalışır. Ayrı Excel, VBA, Google Sheets veya Apps Script kurulumu gerektirmez. Uygulama kendi SQLite veritabanını oluşturur ve Python'un standart `sqlite3` modülünü kullanır. citeturn646562search1")
    st.write("Aşağıdaki legacy CSV'ler projeye gömülü olarak gelir ve ilk kurulumda otomatik içeri alınır: mevcut instruments, quotes, rules. Ek olarak demo ETF / bond / eurobond evreni ve sentetik geçmiş seri üretilir.")
    st.write("Pilot yayına çıkmak için en basit yol, kodu GitHub repo'suna koyup Streamlit Community Cloud'da deploy etmektir; platform GitHub repo'sundan doğrudan deploy eder. citeturn646562search0turn646562search10")

    st.markdown("#### Mevcut kaynak durumu")
    source_view = universe.groupby(["asset_class", "source"]).size().reset_index(name="adet")
    st.dataframe(source_view, use_container_width=True, hide_index=True)

    st.markdown("#### Bu sürümde ne hazır?")
    st.write("- Yeni veri şeması")
    st.write("- Mandate fit motoru")
    st.write("- Universal screener")
    st.write("- Compare ekranı")
    st.write("- Portfolio lab")
    st.write("- Tek tuşla veritabanı kurulum/yenileme")
    st.warning("Not: ETF, bond ve eurobond tarafındaki ek veri bu ilk sürümde demo seed veridir. Gerçek tarihsel seri ve canlı kaynak entegrasyonu ikinci adımda eklenmeli.")
