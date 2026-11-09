# EquityScout India — iPad-friendly Stage 1

A browser-based Streamlit stock screener. It can be operated from Safari on an iPad.

## Important scope
This is a CSV-driven prototype. It does **not** fetch live market data, connect to Zerodha Kite, validate exchange filings, or place orders. The sample companies are fictional. Never use sample data to make investment decisions.

## Deploy from an iPad

1. Open GitHub in Safari and sign in (or create an account).
2. Create a new **public** repository named `equityscout-india`. Do not upload secrets or personal financial documents.
3. Upload `app.py`, `requirements.txt`, and `README.md` from this folder to the repository root.
4. Open `https://share.streamlit.io/` in Safari and sign in with GitHub.
5. Select **Create app**, choose the repository, branch `main`, and main file path `app.py`.
6. Deploy. Open the generated app URL in Safari and optionally add it to the iPad Home Screen.

## Input CSV fields

Required:
`symbol, company, sector, market_cap_cr, revenue_cagr_3y_pct, profit_cagr_3y_pct, roce_pct, roe_pct, debt_equity, operating_cash_flow_cr, free_cash_flow_cr, promoter_pledge_pct, pe, industry_pe`

Optional:
`sales_growth_latest_pct, profit_growth_latest_pct, data_as_of, source_url`

Use percentages as numbers (e.g. 15 means 15%, not 0.15). Cash flow and market cap are in ₹ crore.

## Next development stages
- Sector-specific financial models (banks/NBFCs, insurers, manufacturing, IT, etc.).
- Verified data ingestion from licensed sources and NSE/BSE filings.
- Historical financial statements and valuation history.
- Governance and auditor-risk checks.
- Portfolio tracking and allocation.
- Read-only Kite integration only if supported by a suitable official API and user approval.

## Security
Never enter Zerodha passwords, PINs, OTPs, API secrets, or access tokens into the app or ChatGPT. Keep any future API credentials in Streamlit secrets, not source code.
