import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import date

st.set_page_config(page_title="EquityScout India", page_icon="📊", layout="wide")
st.title("EquityScout India")
st.caption("Fundamental research workspace for NSE/BSE equities | Stage 2")

st.warning(
    "Data-source control: this build analyses uploaded financial data and records its source/date. "
    "It does not yet connect to a licensed live-data API or independently authenticate exchange filings. "
    "Do not treat illustrative/demo data as real securities or investment recommendations."
)

st.sidebar.header("Research controls")
sector_mode = st.sidebar.selectbox(
    "Company type",
    ["Auto-detect from uploaded sector", "Non-financial", "Bank", "NBFC", "Insurance"]
)
min_revenue = st.sidebar.slider("Minimum 3Y revenue CAGR (%)", 0, 40, 10)
min_profit = st.sidebar.slider("Minimum 3Y PAT CAGR (%)", 0, 50, 12)
min_return = st.sidebar.slider("Minimum ROCE / ROE (%)", 0, 40, 15)
max_de = st.sidebar.slider("Maximum debt/equity (non-financials)", 0.0, 3.0, 0.5, 0.1)
max_pledge = st.sidebar.slider("Promoter pledge alert threshold (%)", 0, 100, 5)
max_pe_premium = st.sidebar.slider("PE premium vs industry alert (%)", -80, 200, 40)

st.subheader("1. Upload normalized financial data")
st.markdown(
    "Upload a company master CSV and (optionally) an annual financials CSV. "
    "Use the downloadable templates to preserve column names and units."
)

MASTER_COLS = [
    "symbol","company","sector","business_model","market_cap_cr","price",
    "pe","industry_pe","pb","ev_ebitda","promoter_holding_pct",
    "promoter_pledge_pct","auditor_qualification","auditor_resignation",
    "related_party_flag","dilution_flag","source_url","data_as_of"
]
ANNUAL_COLS = [
    "symbol","fy","revenue_cr","ebitda_cr","pat_cr","eps",
    "operating_cash_flow_cr","capex_cr","total_debt_cr","net_worth_cr",
    "roce_pct","roe_pct","net_npa_pct","gross_npa_pct","capital_adequacy_pct"
]

def template(cols):
    return pd.DataFrame(columns=cols).to_csv(index=False).encode("utf-8")

col1, col2 = st.columns(2)
with col1:
    master_file = st.file_uploader("Company master CSV", type=["csv"], key="master")
    st.download_button("Download company master template", template(MASTER_COLS),
                       "equityscout_company_master_template.csv", "text/csv")
with col2:
    annual_file = st.file_uploader("Annual financials CSV", type=["csv"], key="annual")
    st.download_button("Download annual financials template", template(ANNUAL_COLS),
                       "equityscout_annual_financials_template.csv", "text/csv")

if master_file is None:
    st.info("Upload your company master CSV to begin. A small fictional demo dataset is available below.")
    demo = pd.DataFrame([
        ["DEMO1","Example Industrials Ltd","Industrials","Non-financial",8500,250,24,27,3.1,14,48,0,False,False,False,False,"https://example.com","2026-09-30"],
        ["DEMO2","Example Bank Ltd","Bank","Bank",12500,120,13,14,1.8,1.7,0,0,False,False,False,False,"https://example.com","2026-09-30"]
    ], columns=MASTER_COLS)
    st.dataframe(demo, use_container_width=True, hide_index=True)
    st.caption("Fictional examples only. Upload actual company data to run analysis.")
    st.stop()

master = pd.read_csv(master_file)
missing = [c for c in MASTER_COLS if c not in master.columns]
if missing:
    st.error("Company master is missing columns: " + ", ".join(missing))
    st.stop()

annual = pd.read_csv(annual_file) if annual_file else pd.DataFrame(columns=ANNUAL_COLS)
if annual_file:
    miss_a = [c for c in ANNUAL_COLS if c not in annual.columns]
    if miss_a:
        st.error("Annual financials file is missing columns: " + ", ".join(miss_a))
        st.stop()

for c in MASTER_COLS:
    if c not in ["symbol","company","sector","business_model","auditor_qualification",
                 "auditor_resignation","related_party_flag","dilution_flag","source_url","data_as_of"]:
        master[c] = pd.to_numeric(master[c], errors="coerce")
for c in ["auditor_qualification","auditor_resignation","related_party_flag","dilution_flag"]:
    master[c] = master[c].astype(str).str.strip().str.lower().isin(["true","yes","1","y"])

if not annual.empty:
    for c in ANNUAL_COLS:
        if c not in ["symbol","fy"]:
            annual[c] = pd.to_numeric(annual[c], errors="coerce")
    annual["fy_num"] = pd.to_numeric(annual["fy"].astype(str).str.extract(r"(\d{4})")[0], errors="coerce")
    annual = annual.sort_values(["symbol","fy_num"])
    annual["ocf_positive"] = annual["operating_cash_flow_cr"] > 0
    annual["fcf_cr"] = annual["operating_cash_flow_cr"] - annual["capex_cr"]
    def cagr(series, years=3):
        s = series.dropna()
        if len(s) < 2: return np.nan
        first, last = s.iloc[-min(years+1, len(s))], s.iloc[-1]
        n = min(years, len(s)-1)
        if first <= 0 or last < 0: return np.nan
        return ((last / first) ** (1/n) - 1) * 100
    metrics = []
    for sym, g in annual.groupby("symbol"):
        g = g.sort_values("fy_num")
        metrics.append({
            "symbol": sym,
            "revenue_cagr_3y_pct": cagr(g["revenue_cr"]),
            "pat_cagr_3y_pct": cagr(g["pat_cr"]),
            "latest_ocf_cr": g["operating_cash_flow_cr"].iloc[-1],
            "latest_fcf_cr": g["fcf_cr"].iloc[-1],
            "latest_roce_pct": g["roce_pct"].iloc[-1],
            "latest_roe_pct": g["roe_pct"].iloc[-1],
            "years_data": g["fy"].nunique(),
            "annual_data_as_of": g["fy"].iloc[-1]
        })
    metrics = pd.DataFrame(metrics)
    master = master.merge(metrics, on="symbol", how="left")
else:
    for c in ["revenue_cagr_3y_pct","pat_cagr_3y_pct","latest_ocf_cr","latest_fcf_cr",
              "latest_roce_pct","latest_roe_pct","years_data","annual_data_as_of"]:
        master[c] = np.nan

# Master data may contain externally supplied CAGR fields; use annual data if present.
for c in ["revenue_cagr_3y_pct","pat_cagr_3y_pct","latest_ocf_cr","latest_fcf_cr",
          "latest_roce_pct","latest_roe_pct"]:
    master[c] = pd.to_numeric(master[c], errors="coerce")

def is_financial(row):
    typ = str(row.get("business_model","")).lower()
    sec = str(row.get("sector","")).lower()
    return any(x in typ or x in sec for x in ["bank","nbfc","financial","insurance"])

def company_flags(r):
    flags = []
    if not r.get("source_url"): flags.append("No source URL supplied")
    if not r.get("data_as_of"): flags.append("No data date supplied")
    if bool(r["auditor_qualification"]): flags.append("Auditor qualification")
    if bool(r["auditor_resignation"]): flags.append("Auditor resignation")
    if bool(r["related_party_flag"]): flags.append("Related-party transaction requires review")
    if bool(r["dilution_flag"]): flags.append("Equity dilution requires review")
    if pd.notna(r["promoter_pledge_pct"]) and r["promoter_pledge_pct"] > max_pledge:
        flags.append("Promoter pledge above alert threshold")
    if not is_financial(r):
        if pd.notna(r["debt_equity"]) and r["debt_equity"] > max_de: flags.append("High debt/equity")
        if pd.notna(r["latest_ocf_cr"]) and r["latest_ocf_cr"] < 0: flags.append("Negative operating cash flow")
        if pd.notna(r["latest_fcf_cr"]) and r["latest_fcf_cr"] < 0: flags.append("Negative free cash flow; assess capex cycle")
    else:
        if pd.notna(r["gross_npa_pct"]) if "gross_npa_pct" in r.index else False:
            pass
    if pd.notna(r["pe"]) and pd.notna(r["industry_pe"]) and r["industry_pe"] > 0:
        prem = (r["pe"]/r["industry_pe"]-1)*100
        if prem > max_pe_premium: flags.append("PE premium above selected threshold")
    return flags

def score(r):
    # Transparent provisional score. Missing inputs are excluded from the denominator.
    components = []
    def add(value, target, weight):
        if pd.notna(value) and target > 0:
            components.append((min(1.0, max(0.0, float(value) / target)) * weight, weight))
    add(r["revenue_cagr_3y_pct"], max(min_revenue, 1), 15)
    add(r["pat_cagr_3y_pct"], max(min_profit, 1), 15)
    ret = r["latest_roe_pct"] if is_financial(r) else r["latest_roce_pct"]
    add(ret, max(min_return, 1), 20)
    if not is_financial(r):
        if pd.notna(r["debt_equity"]):
            components.append((10 if r["debt_equity"] <= max_de else 0, 10))
        if pd.notna(r["latest_ocf_cr"]):
            components.append((10 if r["latest_ocf_cr"] > 0 else 0, 10))
        if pd.notna(r["latest_fcf_cr"]):
            components.append((5 if r["latest_fcf_cr"] > 0 else 0, 5))
    else:
        # A placeholder data-completeness component, not a bank-quality judgement.
        if pd.notna(r["pb"]):
            components.append((7.5, 15))
    if pd.notna(r["promoter_pledge_pct"]):
        components.append((10 if r["promoter_pledge_pct"] <= max_pledge else 0, 10))
    if pd.notna(r["pe"]) and pd.notna(r["industry_pe"]) and r["industry_pe"] > 0:
        premium = r["pe"] / r["industry_pe"] - 1
        components.append((15 if premium <= 0 else max(0, 15 * (1 - premium)), 15))
    denominator = sum(weight for _, weight in components)
    return round(sum(points for points, _ in components) / denominator * 100, 1) if denominator else np.nan

master["flags"] = master.apply(lambda r: "; ".join(company_flags(r)) or "No flags from supplied fields", axis=1)
master["research_score"] = master.apply(score, axis=1)
master["financial_sector"] = master.apply(is_financial, axis=1)
master["pe_premium_pct"] = np.where((master["industry_pe"] > 0) & master["pe"].notna(),
                                     (master["pe"]/master["industry_pe"]-1)*100, np.nan)

st.subheader("2. Screening results")
k1,k2,k3 = st.columns(3)
k1.metric("Companies", len(master))
k2.metric("With annual history", int(master["years_data"].notna().sum()))
k3.metric("Companies with review flags", int((master["flags"] != "No flags from supplied fields").sum()))

sort = master.sort_values("research_score", ascending=False)
display_cols = ["symbol","company","sector","business_model","market_cap_cr",
                "revenue_cagr_3y_pct","pat_cagr_3y_pct","latest_roce_pct",
                "latest_roe_pct","pe","pb","ev_ebitda","research_score","flags"]
st.dataframe(sort[[c for c in display_cols if c in sort.columns]], use_container_width=True, hide_index=True)

st.subheader("3. Company research profile")
symbols = master["symbol"].dropna().astype(str).tolist()
if symbols:
    chosen = st.selectbox("Choose company", symbols)
    r = master[master["symbol"].astype(str)==chosen].iloc[0]
    st.markdown(f"### {r['company']} ({r['symbol']})")
    st.write(f"**Sector:** {r['sector']} | **Business model:** {r['business_model']} | **Data as of:** {r['data_as_of']}")
    st.write(f"**Research score:** {r['research_score']} / 100 — provisional screening indicator, not a recommendation.")
    st.write("**Review flags:** " + r["flags"])
    if r["source_url"]:
        st.markdown(f"[Open supplied source]({r['source_url']})")
    if not annual.empty:
        hist = annual[annual["symbol"].astype(str)==chosen].sort_values("fy_num")
        if not hist.empty:
            st.markdown("#### Annual financial history (₹ crore unless stated)")
            st.dataframe(hist.drop(columns=["fy_num","ocf_positive"], errors="ignore"),
                         use_container_width=True, hide_index=True)
            chart = hist.set_index("fy")[["revenue_cr","ebitda_cr","pat_cr"]]
            st.line_chart(chart)
    st.markdown("#### Analyst checklist")
    st.checkbox("Business model and competitive position reviewed", key="c1")
    st.checkbox("Cash-flow quality and working capital reviewed", key="c2")
    st.checkbox("Auditor report and notes to accounts reviewed", key="c3")
    st.checkbox("Promoter holding, pledging and related parties reviewed", key="c4")
    st.checkbox("Valuation compared with peers and own history", key="c5")
    st.checkbox("Risks and downside scenario documented", key="c6")

st.subheader("4. Export")
st.download_button("Download screening results", sort.to_csv(index=False).encode("utf-8"),
                   "equityscout_stage2_screening.csv", "text/csv")

with st.expander("Methodology and limitations"):
    st.markdown("""
    - Annual growth rates are calculated from the first and last available positive observations in the uploaded history; ensure the file contains consecutive fiscal years.
    - For banks/NBFCs/insurers, debt/equity, ROCE and FCF are not treated like industrial-company metrics. This prototype uses ROE as a return proxy but does not yet implement full bank-specific asset-quality, capital adequacy, NIM or credit-cost scoring.
    - P/E is not meaningful for loss-making firms. Peer comparisons must use comparable business models and accounting periods.
    - Promoter pledge, auditor matters, related-party transactions and dilution are only flagged if supplied in the master CSV. The app does not independently detect them.
    - A negative FCF can reflect planned investment. It requires explanation, not automatic rejection.
    - Score weights are provisional and should be calibrated and back-tested before use.
    """)
