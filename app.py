import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="EquityScout India", page_icon="📊", layout="wide")

st.title("EquityScout India")
st.caption("Indian equity research workspace | Screening support, not investment advice")

st.warning(
    "Data integrity notice: this version does not fetch live NSE/BSE data. "
    "Upload a CSV containing verified financial data. Confirm every figure against "
    "company filings before making an investment decision."
)

REQUIRED = [
    "symbol", "company", "sector", "market_cap_cr", "revenue_cagr_3y_pct",
    "profit_cagr_3y_pct", "roce_pct", "roe_pct", "debt_equity",
    "operating_cash_flow_cr", "free_cash_flow_cr", "promoter_pledge_pct",
    "pe", "industry_pe"
]
OPTIONAL = ["sales_growth_latest_pct", "profit_growth_latest_pct", "data_as_of", "source_url"]

SAMPLE = [
    ["ABC", "Example Industrials Ltd", "Industrials", 8500, 15, 18, 19, 16, 0.25, 320, 180, 0, 24, 27, 12, 14, "2026-09-30", "https://example.com"],
    ["XYZ", "Example Consumer Ltd", "Consumer", 4200, 11, 9, 14, 13, 0.70, 90, -25, 12, 38, 30, 8, 7, "2026-09-30", "https://example.com"],
]
SAMPLE_COLUMNS = REQUIRED + OPTIONAL

with st.sidebar:
    st.header("Screening settings")
    min_revenue = st.slider("Minimum 3Y revenue CAGR (%)", 0, 40, 10)
    min_profit = st.slider("Minimum 3Y profit CAGR (%)", 0, 50, 12)
    min_roce = st.slider("Minimum ROCE (%)", 0, 40, 15)
    max_de = st.slider("Maximum debt/equity", 0.0, 3.0, 0.5, 0.1)
    max_pledge = st.slider("Maximum promoter pledge (%)", 0, 100, 5)
    max_pe_premium = st.slider("Maximum PE premium vs industry (%)", -80, 200, 40)
    sectors = st.multiselect("Sectors", [], default=[])

uploaded = st.file_uploader("Upload your company fundamentals CSV", type=["csv"])

if uploaded:
    try:
        df = pd.read_csv(uploaded)
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        st.stop()
else:
    df = pd.DataFrame(SAMPLE, columns=SAMPLE_COLUMNS)
    st.info("Showing illustrative sample companies. Upload your own verified CSV to screen real companies.")

missing = [c for c in REQUIRED if c not in df.columns]
if missing:
    st.error("Missing required columns: " + ", ".join(missing))
    st.stop()

numeric_cols = [c for c in REQUIRED if c not in ["symbol", "company", "sector"]]
for c in numeric_cols:
    df[c] = pd.to_numeric(df[c], errors="coerce")

if "data_as_of" not in df.columns:
    df["data_as_of"] = "Not supplied"
if "source_url" not in df.columns:
    df["source_url"] = ""

df["pe_premium_pct"] = np.where(
    (df["industry_pe"] > 0) & df["pe"].notna(),
    (df["pe"] / df["industry_pe"] - 1) * 100,
    np.nan
)

def score_row(r):
    score = 0
    # Growth: 25
    score += 12.5 if r.revenue_cagr_3y_pct >= min_revenue else max(0, 12.5*r.revenue_cagr_3y_pct/max(min_revenue, 1))
    score += 12.5 if r.profit_cagr_3y_pct >= min_profit else max(0, 12.5*r.profit_cagr_3y_pct/max(min_profit, 1))
    # Returns: 20; sector-sensitive interpretation still required
    score += 10 if r.roce_pct >= min_roce else max(0, 10*r.roce_pct/max(min_roce, 1))
    score += 10 if r.roe_pct >= 15 else max(0, 10*r.roe_pct/15)
    # Balance sheet / cash: 25
    score += 10 if r.debt_equity <= max_de else max(0, 10*(1-r.debt_equity/ max(max_de*3, 0.1)))
    score += 8 if r.operating_cash_flow_cr > 0 else 0
    score += 7 if r.free_cash_flow_cr > 0 else 0
    # Governance: 15
    score += 15 if r.promoter_pledge_pct <= max_pledge else max(0, 15*(1-r.promoter_pledge_pct/100))
    # Relative valuation: 15
    if pd.notna(r.pe_premium_pct):
        score += 15 if r.pe_premium_pct <= max_pe_premium else max(0, 15*(1-r.pe_premium_pct/200))
    return round(min(score, 100), 1)

df["screen_score"] = df.apply(score_row, axis=1)

def flags(r):
    f = []
    if pd.isna(r.roce_pct) or pd.isna(r.pe):
        f.append("Missing key data")
    if r.operating_cash_flow_cr <= 0: f.append("Negative operating cash flow")
    if r.free_cash_flow_cr <= 0: f.append("Negative free cash flow")
    if r.debt_equity > max_de: f.append("Debt/equity above selected limit")
    if r.promoter_pledge_pct > max_pledge: f.append("Promoter pledge above selected limit")
    if pd.notna(r.pe_premium_pct) and r.pe_premium_pct > max_pe_premium: f.append("PE premium above selected limit")
    return "; ".join(f) if f else "No rule-based flag"

df["screen_flags"] = df.apply(flags, axis=1)

all_sectors = sorted(df["sector"].dropna().astype(str).unique().tolist())
selected_sectors = st.sidebar.multiselect("Filter by sector", all_sectors, default=all_sectors)
filtered = df[df["sector"].astype(str).isin(selected_sectors)].copy()
shortlist = filtered[
    (filtered["revenue_cagr_3y_pct"] >= min_revenue) &
    (filtered["profit_cagr_3y_pct"] >= min_profit) &
    (filtered["roce_pct"] >= min_roce) &
    (filtered["debt_equity"] <= max_de) &
    (filtered["promoter_pledge_pct"] <= max_pledge)
].copy().sort_values("screen_score", ascending=False)

c1, c2, c3 = st.columns(3)
c1.metric("Companies loaded", len(df))
c2.metric("Companies passing hard filters", len(shortlist))
c3.metric("Average score", f"{filtered.screen_score.mean():.1f}" if len(filtered) else "—")

st.subheader("Ranked screening results")
show_cols = ["symbol", "company", "sector", "market_cap_cr", "screen_score",
             "revenue_cagr_3y_pct", "profit_cagr_3y_pct", "roce_pct", "debt_equity",
             "pe", "industry_pe", "promoter_pledge_pct", "screen_flags"]
st.dataframe(filtered.sort_values("screen_score", ascending=False)[show_cols], use_container_width=True, hide_index=True)

st.subheader("Shortlist")
if shortlist.empty:
    st.write("No companies pass all selected hard filters. Adjust filters or review the source data.")
else:
    st.dataframe(shortlist[show_cols], use_container_width=True, hide_index=True)

st.subheader("Company detail")
choices = filtered["symbol"].dropna().astype(str).tolist()
if choices:
    symbol = st.selectbox("Select a company", choices)
    r = filtered[filtered.symbol.astype(str) == symbol].iloc[0]
    a, b = st.columns(2)
    with a:
        st.write("**Company:**", r.company)
        st.write("**Sector:**", r.sector)
        st.write("**Market cap (₹ crore):**", r.market_cap_cr)
        st.write("**Data as of:**", r.data_as_of)
    with b:
        st.write("**Screen score:**", r.screen_score)
        st.write("**Rule-based flags:**", r.screen_flags)
        st.write("**Source:**", r.source_url if r.source_url else "Not supplied")

csv = filtered.to_csv(index=False).encode("utf-8")
st.download_button("Download screened results (CSV)", csv, "equityscout_screened_results.csv", "text/csv")

st.subheader("Data template")
template = pd.DataFrame(columns=SAMPLE_COLUMNS)
st.download_button("Download CSV input template", template.to_csv(index=False).encode("utf-8"),
                   "equityscout_input_template.csv", "text/csv")

with st.expander("How to interpret this version"):
    st.markdown("""
    - Scores are screening aids, not buy/sell recommendations.
    - Thresholds are user-adjustable and should be adapted by sector.
    - ROCE, ROE and debt/equity are not directly comparable across banks, NBFCs, insurers and non-financial companies.
    - Negative free cash flow can be normal during planned capex; investigate rather than automatically reject.
    - PE comparisons are meaningful only when accounting, business mix and growth are reasonably comparable.
    - The sample rows are fictional and must not be treated as real securities.
    - Before investing, verify financial statements, cash flows, auditor reports, pledging, related-party transactions, dilution and exchange disclosures.
    """)
