import os
import streamlit as st
import pandas as pd
import numpy as np

from engines.extraction_engine import DynamicReportExtractor
from engines.ratio_engine import compute_financial_ratios, safe_val
from engines.risk_engine import CFOForensicAudit, safe_get_metric
from engines.deep_analytics_engine import (
    calculate_piotroski_f_score,
    calculate_altman_z,
    perform_dupont_decomposition
)
from engines.data_ingestion_engine import ingest_from_excel_or_csv, fetch_from_ir_link
from engines.visualization_engine import (
    build_growth_trajectory_chart,
    build_margin_trend_chart,
    build_cash_waterfall
)
from engines.reconciliation_engine import FinancialReconciliationEngine
from engines.anomaly_engine import FinancialAnomalyEngine
from engines.working_capital_engine import WorkingCapitalBridgeEngine
from engines.notes_engine import FootnoteDisclosuresEngine
from ai.gemini_intelligence import GeminiFinancialAnalyst
from utils.pdf_viewer import display_evidence_drawer
from utils.pdf_exporter import InstitutionalPDFExporter

st.set_page_config(page_title="FINCORTEX AI | Institutional Financial Intelligence", page_icon="🏛️", layout="wide")

# ----------------- SESSION STATE PERSISTENCE -----------------
if "df_metrics" not in st.session_state:
    st.session_state.df_metrics = None
if "company_name" not in st.session_state:
    st.session_state.company_name = "Tata Motors Limited"
if "taxonomy" not in st.session_state:
    st.session_state.taxonomy = "Corporate / Industrial"
if "currency_symbol" not in st.session_state:
    st.session_state.currency_symbol = "₹"
if "unit_scale" not in st.session_state:
    st.session_state.unit_scale = "Cr"

# Safe Secret Resolution (Works both locally without secrets.toml and on Streamlit Cloud)
if "gemini_api_key" not in st.session_state:
    key_found = ""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            key_found = st.secrets["GEMINI_API_KEY"]
    except Exception:
        key_found = os.environ.get("GEMINI_API_KEY", "")
    st.session_state.gemini_api_key = key_found

if "extra_meta" not in st.session_state:
    st.session_state.extra_meta = {}
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
if "pdf_meta" not in st.session_state:
    st.session_state.pdf_meta = {}

# ----------------- INSTITUTIONAL BENCHMARK PRESETS -----------------
PRESETS = {
    "Tata Motors Limited": {
        "name": "Tata Motors Limited",
        "taxonomy": "Corporate / Industrial",
        "currency": "₹",
        "scale": "Cr",
        "data": {
            "FY2023-24": {"revenue": 345967.0, "ebitda": 45600.0, "pat": 17900.0, "total_borrowings": 125000.0, "cash_and_equivalents": 32000.0, "equity_share_capital": 765.0, "reserves": 64235.0, "total_equity": 65000.0, "total_assets": 285000.0, "total_liabilities": 285000.0, "trade_receivables": 14200.0, "cfo": 38500.0, "capex": 24000.0, "other_income": 3200.0},
            "FY2024-25": {"revenue": 392000.0, "ebitda": 54800.0, "pat": 24200.0, "total_borrowings": 110000.0, "cash_and_equivalents": 38000.0, "equity_share_capital": 765.0, "reserves": 81235.0, "total_equity": 82000.0, "total_assets": 312000.0, "total_liabilities": 312000.0, "trade_receivables": 15800.0, "cfo": 44000.0, "capex": 28000.0, "other_income": 4100.0},
            "FY2025-26": {"revenue": 437928.0, "ebitda": 62114.0, "pat": 31807.0, "total_borrowings": 96000.0, "cash_and_equivalents": 44000.0, "equity_share_capital": 765.0, "reserves": 104235.0, "total_equity": 105000.0, "total_assets": 345000.0, "total_liabilities": 345000.0, "trade_receivables": 21800.0, "cfo": 41200.0, "capex": 31500.0, "other_income": 4800.0}
        }
    },
    "Citigroup Inc.": {
        "name": "Citigroup Inc.",
        "taxonomy": "Banking / Financial Institution",
        "currency": "$",
        "scale": "M",
        "data": {
            "2023": {"revenue": 78462.0, "ebitda": 11800.0, "pat": 9228.0, "total_borrowings": 1310000.0, "cash_and_equivalents": 260000.0, "equity_share_capital": 18000.0, "reserves": 190000.0, "total_equity": 208000.0, "total_assets": 2372000.0, "total_liabilities": 2372000.0, "trade_receivables": 687000.0, "cfo": 18200.0, "capex": 3100.0, "other_income": 1200.0},
            "2024": {"revenue": 81300.0, "ebitda": 15600.0, "pat": 12500.0, "total_borrowings": 1335000.0, "cash_and_equivalents": 275000.0, "equity_share_capital": 18000.0, "reserves": 194000.0, "total_equity": 212000.0, "total_assets": 2410000.0, "total_liabilities": 2410000.0, "trade_receivables": 712000.0, "cfo": 21400.0, "capex": 3400.0, "other_income": 1450.0},
            "2025": {"revenue": 84500.0, "ebitda": 18200.0, "pat": 14600.0, "total_borrowings": 1360000.0, "cash_and_equivalents": 290000.0, "equity_share_capital": 18000.0, "reserves": 200000.0, "total_equity": 218000.0, "total_assets": 2480000.0, "total_liabilities": 2480000.0, "trade_receivables": 745000.0, "cfo": 24500.0, "capex": 3600.0, "other_income": 1600.0}
        }
    }
}

# ----------------- SIDEBAR INGESTION HUB -----------------
with st.sidebar:
    st.header("🏛️ Ingestion Hub")
    ingest_mode = st.radio(
        "Source Pipeline:", 
        ["PDF Annual Report", "Upload Excel / CSV", "Investor Relations URL", "Benchmark Models"]
    )

    if ingest_mode == "PDF Annual Report":
        uploaded_pdf = st.file_uploader("Upload Annual Report (.pdf)", type=["pdf"])
        if uploaded_pdf and st.button("Parse PDF Document", type="primary"):
            with st.spinner("Executing document layout analysis & statement extraction..."):
                try:
                    pdf_bytes_data = uploaded_pdf.read()
                    extractor = DynamicReportExtractor(pdf_bytes_data)
                    df_extr, comp, tax, pdf_meta = extractor.extract_and_spread()
                    if df_extr is not None and not df_extr.empty:
                        st.session_state.df_metrics = df_extr
                        st.session_state.company_name = comp
                        st.session_state.taxonomy = tax
                        st.session_state.currency_symbol = "$" if "citi" in comp.lower() or "inc" in comp.lower() else "₹"
                        st.session_state.unit_scale = "M" if "citi" in comp.lower() or "inc" in comp.lower() else "Cr"
                        st.session_state.pdf_bytes = pdf_bytes_data
                        st.session_state.pdf_meta = pdf_meta
                        st.session_state.extra_meta = {
                            "unit_consistent": True,
                            "source_doc": uploaded_pdf.name,
                            "detected_pages": pdf_meta.get("detected_pages", {})
                        }
                        st.success(f"Successfully extracted financial statements for {comp}")
                        st.rerun()
                    else:
                        st.error("Failed to parse tabular financial statements from this PDF.")
                except Exception as e:
                    st.error(f"PDF Extraction Error: {str(e)}")

    elif ingest_mode == "Upload Excel / CSV":
        uploaded_sheet = st.file_uploader("Upload Statements (.xlsx / .csv)", type=["xlsx", "xls", "csv"])
        if uploaded_sheet and st.button("Ingest Spreadsheet", type="primary"):
            df_sheet, msg, comp_name, tax, cur, scale, extra = ingest_from_excel_or_csv(uploaded_sheet)
            if df_sheet is not None:
                st.session_state.df_metrics = df_sheet
                if comp_name:
                    st.session_state.company_name = comp_name
                if tax:
                    st.session_state.taxonomy = tax
                st.session_state.currency_symbol = cur
                st.session_state.unit_scale = scale
                st.session_state.extra_meta = extra
                st.session_state.pdf_bytes = None
                st.session_state.pdf_meta = {}
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    elif ingest_mode == "Investor Relations URL":
        ir_url = st.text_input("Enter Financial Table URL:", value="https://www.investor.gov")
        if st.button("Scrape Tables"):
            with st.spinner("Fetching tables from target domain..."):
                tbl, msg = fetch_from_ir_link(ir_url)
                if tbl is not None:
                    st.success(msg)
                    st.dataframe(tbl.head(4))
                else:
                    st.warning(msg)

    elif ingest_mode == "Benchmark Models":
        choice = st.selectbox("Select Institution:", list(PRESETS.keys()))
        if st.button("Load Institution"):
            sel = PRESETS[choice]
            st.session_state.df_metrics = pd.DataFrame(sel["data"])
            st.session_state.company_name = sel["name"]
            st.session_state.taxonomy = sel["taxonomy"]
            st.session_state.currency_symbol = sel["currency"]
            st.session_state.unit_scale = sel["scale"]
            st.session_state.extra_meta = {}
            st.session_state.pdf_bytes = None
            st.session_state.pdf_meta = {}
            st.rerun()

    st.markdown("---")
    st.header("🤖 AI Copilot Config")
    user_api_key = st.text_input("Gemini API Key (Optional)", type="password", value=st.session_state.gemini_api_key)
    if user_api_key != st.session_state.gemini_api_key:
        st.session_state.gemini_api_key = user_api_key

# ----------------- FALLBACK INITIALIZATION -----------------
if st.session_state.df_metrics is None:
    def_data = PRESETS["Tata Motors Limited"]
    st.session_state.df_metrics = pd.DataFrame(def_data["data"])
    st.session_state.company_name = def_data["name"]
    st.session_state.taxonomy = def_data["taxonomy"]
    st.session_state.currency_symbol = def_data["currency"]
    st.session_state.unit_scale = def_data["scale"]

df_metrics = st.session_state.df_metrics
if "metric" in df_metrics.columns:
    df_metrics = df_metrics.set_index("metric")
st.session_state.df_metrics = df_metrics

company_name = st.session_state.company_name
taxonomy = st.session_state.taxonomy
unit = st.session_state.currency_symbol
scale = st.session_state.unit_scale

periods = [col for col in df_metrics.columns if str(col).lower() not in ["metric", "category", "line_item"]]

with st.sidebar:
    st.markdown("---")
    target_period = st.selectbox("Valuation Period", periods, index=len(periods)-1)

# ----------------- MAIN INSTITUTIONAL HEADER -----------------
st.title(f"🏛️ FINCORTEX AI | {company_name}")
st.caption(f"Taxonomy: **{taxonomy}** | Cycle: **{target_period}** | Document-to-Decision Financial Intelligence")

# ----------------- EXECUTIVE PRODUCT INTRO VIDEO (ROBUST RESOLUTION) -----------------
assets_dir = os.path.join(os.path.dirname(__file__), "assets")
video_files = [f for f in os.listdir(assets_dir) if f.lower().endswith(".mp4")] if os.path.exists(assets_dir) else []

if video_files:
    video_path = os.path.join(assets_dir, video_files[0])
    with st.expander("🎬 **WATCH: Introducing FINCORTEX AI (10s Overview)**", expanded=True):
        col_v1, col_v2, col_v3 = st.columns([1, 4, 1])
        with col_v2:
            try:
                with open(video_path, "rb") as vfile:
                    video_bytes = vfile.read()
                st.video(video_bytes, format="video/mp4", autoplay=False)
                st.caption("🔊 *Turn sound on for the institutional audio briefing.*")
            except Exception as e:
                st.warning(f"Could not load intro video: {str(e)}")

# Core Financial Metrics Extraction
curr_rev = safe_get_metric(df_metrics, "revenue", target_period)
curr_ebitda = safe_get_metric(df_metrics, "ebitda", target_period)
curr_pat = safe_get_metric(df_metrics, "pat", target_period)
curr_cfo = safe_get_metric(df_metrics, "cfo", target_period)
curr_capex = safe_get_metric(df_metrics, "capex", target_period)
curr_fcf = curr_cfo - curr_capex
curr_equity = safe_get_metric(df_metrics, "total_equity", target_period)
curr_other_inc = safe_get_metric(df_metrics, "other_income", target_period)

df_ratios = compute_financial_ratios(df_metrics, unit_label=scale)
risk_alerts = CFOForensicAudit.analyze_health(df_metrics)
dupont = perform_dupont_decomposition(df_metrics, target_period)
altman = calculate_altman_z(df_metrics, target_period, is_bank=(taxonomy != "Corporate / Industrial"), extra_meta=st.session_state.extra_meta)
piotroski = calculate_piotroski_f_score(df_metrics)
anomalies = FinancialAnomalyEngine.detect_anomalies(df_metrics, target_period, st.session_state.extra_meta)

# ----------------- TOP DATA QUALITY & RECONCILIATION GATE -----------------
recon = FinancialReconciliationEngine.audit_statement_integrity(df_metrics, target_period, st.session_state.extra_meta)

with st.expander(f"🔐 FINCORTEX DATA QUALITY CHECK — Confidence: {recon['confidence_pct']}% ({recon['overall_status']})", expanded=False):
    st.caption("Verification check across statement balance identities, cash flow reconciliations, and period alignment.")
    c_q1, c_q2 = st.columns([1, 2])
    with c_q1:
        st.metric("Statement Data Confidence", f"{recon['confidence_pct']}%", delta=f"{recon['score_points']} / {recon['max_points']} Validation Checks")
        if recon["overall_status"] == "HEALTHY":
            st.success("✓ All statements balanced & reconciled.")
        else:
            st.warning("⚠️ Statement variances or proxy definitions identified.")
    with c_q2:
        st.dataframe(pd.DataFrame(recon["checks"])[["test", "status", "evidence"]], use_container_width=True)

# Top KPI Metric Banner
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
ebitda_m = (curr_ebitda / curr_rev * 100) if curr_rev > 0 else 0.0
kpi1.metric("Reported Gross Sales", f"{unit}{curr_rev:,.0f} {scale}", delta=f"{ebitda_m:.2f}% Operating Margin")
kpi2.metric("Operating EBITDA", f"{unit}{curr_ebitda:,.0f} {scale}")

if curr_other_inc > (curr_ebitda * 0.5):
    kpi3.metric("Reported PAT", f"{unit}{curr_pat:,.0f} {scale}", delta=f"⚠️ Incl. {unit}{curr_other_inc:,.0f} {scale} Other Income", delta_color="off")
else:
    kpi3.metric("Reported PAT", f"{unit}{curr_pat:,.0f} {scale}")

if curr_equity < 0:
    kpi4.metric("Derived Free Cash Flow", f"{unit}{curr_fcf:,.0f} {scale}", delta=f"⚠️ Net Worth: {unit}{curr_equity:,.0f} {scale}", delta_color="inverse")
else:
    cash_qual = (curr_cfo / curr_pat) if curr_pat > 0 else 0.0
    kpi4.metric("Derived Free Cash Flow", f"{unit}{curr_fcf:,.0f} {scale}", delta=f"Cash Quality: {cash_qual:.2f}x CFO/PAT")

st.markdown("---")

# Navigation Tabs
tab_spread, tab_wc, tab_scenarios, tab_ai, tab_anomalies, tab_deep, tab_charts, tab_forensics, tab_cfo_report = st.tabs([
    "📑 Spreading",
    "🌉 Cash Flow Bridge",
    "🎛️ Scenario Analysis",
    "🧠 Seven-Tier AI",
    "⚡ Anomaly Engine",
    "🔬 Model Validation",
    "📈 Visual Charts",
    "🚨 CFO Radar",
    "📄 Boardroom Dossier"
])

# ----------------- TAB 1: SPREADING -----------------
with tab_spread:
    col_s1, col_s2 = st.columns([1.2, 1], gap="large")
    with col_s1:
        st.subheader("Reported Financial Data (Spreaded Statements)")
        st.caption(f"Source: Annual Report & Financial Statement Disclosures ({target_period})")
        def format_currency_cell(val):
            try:
                num = float(val)
                if abs(num) >= 1000:
                    return f"{unit}{num:,.0f} {scale}"
                return f"{unit}{num:,.2f} {scale}"
            except (ValueError, TypeError):
                return str(val)
        st.dataframe(df_metrics.style.format(format_currency_cell), use_container_width=True, height=380)

    with col_s2:
        st.subheader("Institutional Ratio Matrix")
        st.dataframe(df_ratios, use_container_width=True, height=380)

# ----------------- TAB 2: CASH FLOW & WORKING CAPITAL BRIDGE -----------------
with tab_wc:
    st.subheader("🌉 Working Capital Movement & Cash Realization Bridge")
    st.caption("Itemized mathematical walkthrough decomposing Operating EBITDA into final Operating Cash Flow (CFO).")

    wc_bridge = WorkingCapitalBridgeEngine.compute_bridge(df_metrics, target_period)

    if wc_bridge["status"] == "SUCCESS":
        c_b1, c_b2 = st.columns([1.4, 1])
        with c_b1:
            st.markdown("**EBITDA-to-CFO Cash Flow Reconciliation Walkway**")
            b_df = pd.DataFrame(wc_bridge["bridge"])
            
            def fmt_impact(val):
                if abs(val) >= 1000:
                    return f"{unit}{val:,.0f} {scale}"
                return f"{unit}{val:,.2f} {scale}"

            b_disp = b_df.copy()
            b_disp["Impact"] = b_disp["Impact"].apply(fmt_impact)
            st.dataframe(b_disp, use_container_width=True, height=300)

        with c_b2:
            st.markdown("**Working Capital Efficiency Summary**")
            st.write(f"• **Starting Operating EBITDA:** {unit}{wc_bridge['ebitda']:,.0f} {scale}")
            st.write(f"• **Net Balance Sheet WC Impact:** {unit}{wc_bridge['net_wc_movement']:+,.0f} {scale}")
            st.write(f"• **Final Operating CFO Realized:** **{unit}{wc_bridge['cfo']:,.0f} {scale}**")
            
            cash_drag_status = "Generated Cash from Balance Sheet Release" if wc_bridge['net_wc_movement'] >= 0 else "Absorbed Operating Cash into Working Capital"
            st.info(f"👉 **Working Capital Direction:** {cash_drag_status}")

    st.markdown("---")
    st.subheader("🔍 Interactive Footnote & Schedule Drilldown")
    st.caption("Inspect underlying note schedules for exceptional items, non-operating income, and capital obligations.")

    note_choice = st.selectbox("Select Footnote Schedule to Audit:", ["Other Income Note", "Borrowings Note"])
    
    note_data = FootnoteDisclosuresEngine.drilldown_note(
        note_category=note_choice,
        company_name=company_name,
        context_data={"other_income": curr_other_inc, "total_borrowings": safe_get_metric(df_metrics, "total_borrowings", target_period)}
    )

    st.markdown(f"**{note_data['note_title']}** (Reported Total: **{unit}{note_data['reported_total']:,.0f} {scale}**)")
    st.caption(f"Accounting Classification: `{note_data['accounting_treatment']}`")
    
    if note_data["components"]:
        comp_df = pd.DataFrame(note_data["components"])
        comp_df["Amount"] = comp_df["Amount"].apply(lambda v: f"{unit}{v:,.0f} {scale}")
        st.dataframe(comp_df, use_container_width=True)

    st.warning(f"Auditor Examination Directive: {note_data['auditor_observation']}")

# ----------------- TAB 3: SCENARIO ANALYSIS & STRESS TESTING -----------------
with tab_scenarios:
    st.subheader("🎛️ FP&A Multi-Driver Stress Testing & Scenario Console")
    st.caption("Underwrite institutional upside, base, downside, and operational shock models.")

    b_rev = curr_rev
    b_ebitda = curr_ebitda
    b_pat = curr_pat
    b_debt = safe_get_metric(df_metrics, "total_borrowings", target_period)
    b_cfo = curr_cfo
    b_capex = curr_capex

    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        st.markdown("**1. Top-Line Trajectory & Pricing Power**")
        rev_shock = st.slider("Revenue Growth Delta (%)", min_value=-50.0, max_value=300.0, value=25.0, step=1.0)
        margin_shift = st.slider("Operating Margin Shift (bps)", min_value=-800, max_value=800, value=100, step=25)

    with col_d2:
        st.markdown("**2. Cost Structure & Working Capital**")
        cost_shock = st.slider("Input Cost / Inflation (%)", min_value=0.0, max_value=25.0, value=2.0, step=0.5)
        rec_drag = st.slider("Receivables / DSO Extension (Days)", min_value=-30, max_value=60, value=10, step=2)

    with col_d3:
        st.markdown("**3. Capital Structure & Reinvestment**")
        rate_shock = st.slider("Effective Debt Rate Shock (bps)", min_value=-150, max_value=400, value=50, step=25)
        capex_growth = st.slider("Capex Expansion Budget (%)", min_value=-50.0, max_value=150.0, value=15.0, step=5.0)

    def run_sim(rev_g, m_bps, cost_inf, dso, rate_bps, cap_g):
        s_rev = max(b_rev * (1.0 + rev_g / 100.0), 0.0)
        base_m = (b_ebitda / b_rev) if b_rev > 0 else 0.15
        s_m = max(base_m + (m_bps / 10000.0) - (cost_inf / 100.0), 0.01)
        s_ebitda = s_rev * s_m
        int_drag = b_debt * (rate_bps / 10000.0)
        ebitda_delta = s_ebitda - b_ebitda
        pretax_delta = ebitda_delta - int_drag
        tax_impact = pretax_delta * 0.25
        s_pat = b_pat + (pretax_delta - tax_impact)
        wc_drag = (s_rev / 365.0) * dso
        s_cfo = b_cfo + (s_ebitda - b_ebitda) - wc_drag
        s_capex = max(b_capex * (1.0 + cap_g / 100.0), 0.0)
        s_fcf = s_cfo - s_capex
        return {
            "Revenue": s_rev,
            "EBITDA": s_ebitda,
            "Margin": s_m * 100.0,
            "PAT": s_pat,
            "PAT_Margin": (s_pat / s_rev * 100.0) if s_rev > 0 else 0.0,
            "CFO": s_cfo,
            "Capex": s_capex,
            "FCF": s_fcf
        }

    worst = run_sim(rev_g=-20.0, m_bps=-300.0, cost_inf=4.0, dso=20, rate_bps=150.0, cap_g=-15.0)
    base = run_sim(rev_g=0.0, m_bps=0.0, cost_inf=0.0, dso=0, rate_bps=0.0, cap_g=0.0)
    sim = run_sim(rev_g=rev_shock, m_bps=float(margin_shift), cost_inf=cost_shock, dso=rec_drag, rate_bps=float(rate_shock), cap_g=capex_growth)
    best = run_sim(rev_g=max(rev_shock * 1.5, 30.0), m_bps=200.0, cost_inf=0.0, dso=-10, rate_bps=-50.0, cap_g=10.0)

    scenario_matrix_df = pd.DataFrame({
        "Financial Metric": [
            "Top-Line Gross Revenue",
            "Operating Profit (EBITDA)",
            "EBITDA Margin (%)",
            "Net Profit (PAT)",
            "PAT Margin (%)",
            "Operating Cash Flow (CFO)",
            "Capital Expenditure (Capex)",
            "Analytically Derived Free Cash Flow"
        ],
        "Worst Case (Downside)": [
            f"{unit}{worst['Revenue']:,.0f} {scale}", f"{unit}{worst['EBITDA']:,.0f} {scale}", f"{worst['Margin']:.2f}%",
            f"{unit}{worst['PAT']:,.0f} {scale}", f"{worst['PAT_Margin']:.2f}%", f"{unit}{worst['CFO']:,.0f} {scale}",
            f"{unit}{worst['Capex']:,.0f} {scale}", f"{unit}{worst['FCF']:,.0f} {scale}"
        ],
        "Base Case (Audited)": [
            f"{unit}{base['Revenue']:,.0f} {scale}", f"{unit}{base['EBITDA']:,.0f} {scale}", f"{base['Margin']:.2f}%",
            f"{unit}{base['PAT']:,.0f} {scale}", f"{base['PAT_Margin']:.2f}%", f"{unit}{base['CFO']:,.0f} {scale}",
            f"{unit}{base['Capex']:,.0f} {scale}", f"{unit}{base['FCF']:,.0f} {scale}"
        ],
        "Simulated Model": [
            f"{unit}{sim['Revenue']:,.0f} {scale}", f"{unit}{sim['EBITDA']:,.0f} {scale}", f"{sim['Margin']:.2f}%",
            f"{unit}{sim['PAT']:,.0f} {scale}", f"{sim['PAT_Margin']:.2f}%", f"{unit}{sim['CFO']:,.0f} {scale}",
            f"{unit}{sim['Capex']:,.0f} {scale}", f"{unit}{sim['FCF']:,.0f} {scale}"
        ],
        "Best Case (Optimistic)": [
            f"{unit}{best['Revenue']:,.0f} {scale}", f"{unit}{best['EBITDA']:,.0f} {scale}", f"{best['Margin']:.2f}%",
            f"{unit}{best['PAT']:,.0f} {scale}", f"{best['PAT_Margin']:.2f}%", f"{unit}{best['CFO']:,.0f} {scale}",
            f"{unit}{best['Capex']:,.0f} {scale}", f"{unit}{best['FCF']:,.0f} {scale}"
        ]
    })

    st.markdown("---")
    st.subheader("📊 Comparative Scenario Underwriting Matrix")
    st.dataframe(scenario_matrix_df, use_container_width=True)

    base_fcf = b_cfo - b_capex
    m1, m2, m3 = st.columns(3)
    m1.metric("Simulated Top-Line", f"{unit}{sim['Revenue']:,.0f} {scale}", delta=f"{rev_shock:+.1f}% vs Base")
    m2.metric("Simulated Operating EBITDA", f"{unit}{sim['EBITDA']:,.0f} {scale}", delta=f"{sim['Margin']:.2f}% Margin")
    m3.metric("Simulated Free Cash Flow", f"{unit}{sim['FCF']:,.0f} {scale}", delta=f"{unit}{(sim['FCF'] - base_fcf):+,.0f} {scale} vs Base")

# ----------------- TAB 4: SEVEN-TIER FORENSIC AI -----------------
with tab_ai:
    st.subheader(f"🧠 Forensic Lineage Appraisal: {company_name} ({target_period})")
    st.caption("Classification: 🔵 Reported Data | 🟣 Calculated Metric | 🟠 Analytical Observation | ⚠️ Limitation | 🔴 Investigation Required")

    extra_diagnostics = {
        "other_income": curr_other_inc,
        "book_equity": curr_equity
    }

    analyst = GeminiFinancialAnalyst(api_key=st.session_state.gemini_api_key)
    dossier = analyst.generate_boardroom_dossier(
        company_name, target_period, df_metrics, df_ratios, altman, piotroski, risk_alerts, extra_diagnostics
    )
    
    if dossier["status"] == "LIVE_GEMINI":
        st.success("⚡ Live Gemini AI Intelligence Active (Validation Protocol Active)")
    else:
        st.info("ℹ️ Running on Institutional Deterministic Rule Engine with Strict Lineage Guards.")

    st.markdown(dossier["content"])

    if st.session_state.pdf_bytes is not None and st.session_state.pdf_meta:
        trace = st.session_state.pdf_meta.get("lineage_trace", {})
        if "revenue" in trace:
            rev_p = trace["revenue"].get("page", 1)
            display_evidence_drawer(
                st.session_state.pdf_bytes,
                page_number=rev_p,
                line_item="Revenue from Operations",
                reported_value=f"{unit}{curr_rev:,.0f} {scale}"
            )

# ----------------- TAB 5: FINANCIAL ANOMALY ENGINE -----------------
with tab_anomalies:
    st.subheader("⚡ Automated Financial Anomaly Scanner")
    st.caption("Detects mathematical divergences, non-operating distortions, and accounting balance anomalies.")
    if not anomalies:
        st.success("✓ No critical statistical or accounting anomalies detected for this cycle.")
    else:
        for anom in anomalies:
            st.error(f"**[{anom['id']}] {anom['title']} ({anom['severity']})**")
            st.write(f"• **Discovered Metric:** `{anom['metric']}`")
            st.write(f"• **Reported Evidence:** {anom['evidence']}")
            st.caption(f"👉 **Investigation Required:** {anom['investigation']}")
            st.markdown("---")

# ----------------- TAB 6: MODEL VALIDATION & FORMULA AUDIT -----------------
with tab_deep:
    st.subheader("🔬 Financial Model Validation & Interpretation")
    
    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        st.markdown("**Altman Z-Score Model Check**")
        st.metric(label="Z-Score Value", value=altman["z_score"], delta=altman["zone"])
        st.caption(f"**Version:** {altman['formula_version']}")
        st.caption(f"⚠️ {altman['applicability_warning']}")

    with col_d2:
        st.markdown("**Piotroski Quality Index**")
        st.metric(label="Quality Result", value=piotroski["summary_label"])
        st.caption(f"Verifiable: {piotroski['verifiable_count']} | Passing: {piotroski['passing_count']} | Unavailable: {piotroski['unavailable_count']}")
        st.caption("Signals without direct statement line items are strictly isolated as 'Unavailable'.")

    with col_d3:
        st.markdown("**Capital Structure & Equity Validity**")
        if dupont["is_negative_equity"]:
            st.error(f"**Negative Book Equity:** Reported carrying value of liabilities exceeds assets by **{unit}{abs(curr_equity):,.0f} {scale}**.")
            st.caption("Conventional ROE cannot be interpreted meaningfully. Priority must focus on cash liquidity and debt service.")
        else:
            net_margin = dupont.get("Net Profit Margin (%)", 0.0)
            asset_turnover = dupont.get("Asset Turnover (x)", 0.0)
            leverage_mult = dupont.get("Financial Leverage Multiplier (x)", dupont.get("Financial Leverage Ratio (x)", 1.0))
            comp_roe = dupont.get("Decomposed ROE (%)", "0.00%")

            st.write(f"• **Net Profit Margin:** {net_margin}%")
            st.write(f"• **Asset Turnover:** {asset_turnover}x")
            st.write(f"• **Financial Leverage Multiplier:** {leverage_mult}x")
            st.write(f"👉 **Compound ROE:** **{comp_roe}**")

    st.markdown("---")
    st.subheader("📑 Altman Z-Score Formula & Input Verification Audit")
    if altman.get("formula_audit"):
        st.dataframe(pd.DataFrame(altman["formula_audit"]), use_container_width=True)

    st.markdown("---")
    st.subheader("Signal-by-Signal Piotroski Verification Matrix")
    sig_data = []
    for k, v in piotroski["signals"].items():
        sig_data.append({
            "Signal Test": k,
            "Verification Status": v["status"],
            "Verification Label": v["label"],
            "Reported Evidence / Details": v["detail"]
        })
    st.dataframe(pd.DataFrame(sig_data), use_container_width=True)

# ----------------- TAB 7: DYNAMIC VISUAL CHARTS -----------------
with tab_charts:
    c_left, c_right = st.columns(2)
    with c_left:
        st.plotly_chart(build_growth_trajectory_chart(df_metrics), use_container_width=True)
        numeric_ratios = compute_financial_ratios(df_metrics)
        clean_num_ratios = pd.DataFrame(index=numeric_ratios.index, columns=numeric_ratios.columns)
        for row in numeric_ratios.index:
            for col in numeric_ratios.columns:
                val_str = str(numeric_ratios.loc[row, col]).replace("%", "").replace("x", "").replace("days", "").replace(",", "").strip()
                try:
                    clean_num_ratios.loc[row, col] = float(val_str)
                except ValueError:
                    clean_num_ratios.loc[row, col] = 0.0
        st.plotly_chart(build_margin_trend_chart(clean_num_ratios), use_container_width=True)
    with c_right:
        st.plotly_chart(build_cash_waterfall(df_metrics, target_period), use_container_width=True)

# ----------------- TAB 8: CFO EARLY WARNING RADAR -----------------
with tab_forensics:
    st.subheader("CFO Early-Warning Radar & Reconciliation")
    if not risk_alerts:
        st.success("✓ Primary working capital movements within historical tolerances.")
    else:
        for alert in risk_alerts:
            st.error(f"**[{alert['category']}] {alert['metric']}**")
            st.write(f"**Reported Evidence:** {alert['evidence']}")
            st.caption(f"**Forensic Implication:** {alert['implication']}")
            st.markdown("---")

# ----------------- TAB 9: BOARDROOM EXECUTIVE DOSSIER & EXPORT HUB -----------------
with tab_cfo_report:
    st.subheader("📄 Formal Boardroom Dossier & Institutional Export Hub")
    st.caption("Generate, preview, and download boardroom reports and financial spreads across formats.")

    cfo_report_md = f"""# EXECUTIVE CFO FINANCIAL DOSSIER
**ENTITY:** {company_name}  
**TAXONOMY:** {taxonomy}  
**REPORTING CYCLE:** {target_period}  
**CURRENCY / SCALE:** {unit} in {scale}  
**DATA QUALITY CONFIDENCE:** {recon.get('confidence_pct', 0)}% ({recon.get('overall_status', 'N/A')})

---

## 1. Reported Financial Data & Earnings Quality
* **Gross Sales:** {unit}{curr_rev:,.0f} {scale}
* **Operating Profit (EBITDA):** {unit}{curr_ebitda:,.0f} {scale} (Operating Margin: {ebitda_m:.2f}%)
* **Reported Other Income:** {unit}{curr_other_inc:,.0f} {scale}
* **Reported PAT:** {unit}{curr_pat:,.0f} {scale} ({f"⚠️ Heavily driven by {unit}{curr_other_inc:,.0f} {scale} in Other Income" if curr_other_inc > (curr_ebitda * 0.5) else "Reflecting core operational conversion"})
* **Operating Cash Flow (CFO):** {unit}{curr_cfo:,.0f} {scale}
* **Capital Expenditures:** {unit}{curr_capex:,.0f} {scale}
* **Analytically Derived Free Cash Flow:** {unit}{curr_fcf:,.0f} {scale}

---

## 2. Balance Sheet & Capital Structure Diagnostics
* **Equity Share Capital:** {unit}{safe_get_metric(df_metrics, 'equity_share_capital', target_period):,.0f} {scale}
* **Total Shareholders' Equity / Net Worth:** {unit}{curr_equity:,.0f} {scale} ({f"⚠️ Liabilities exceed assets by {unit}{abs(curr_equity):,.0f} {scale}" if curr_equity < 0 else "Solvent Net Asset Base"})
* **Total Gross Borrowings:** {unit}{safe_get_metric(df_metrics, 'total_borrowings', target_period):,.0f} {scale}
* **Days Sales Outstanding (DSO):** {df_ratios.loc['Receivable Days', target_period] if 'Receivable Days' in df_ratios.index else 'N/A'} (Note: A complete working capital movement analysis across inventory and payables is required).

---

## 3. Financial Model Validation
* **Altman Z-Score:** `{altman.get('z_score', 'N/A')}` — {altman.get('zone', 'N/A')}  
  * *Version:* {altman.get('formula_version', 'N/A')}  
  * *Applicability:* {altman.get('applicability_warning', 'N/A')}
* **Piotroski Quality Index:** `{piotroski.get('summary_label', 'N/A')}`

---

## 4. Analytical Observations & Directives
{dossier.get('content', '')}
"""

    st.markdown(cfo_report_md)
    st.markdown("---")
    st.subheader("📥 Export Downloads")

    col_dl1, col_dl2, col_dl3 = st.columns(3)

    with col_dl1:
        st.download_button(
            label="📥 Download Dossier (.md)",
            data=cfo_report_md,
            file_name=f"{company_name}_{target_period}_Boardroom_Dossier.md",
            mime="text/markdown",
            use_container_width=True,
            type="primary"
        )

    with col_dl2:
        try:
            pdf_bytes = InstitutionalPDFExporter.build_pdf_dossier(
                company_name=company_name,
                period=target_period,
                taxonomy=taxonomy,
                unit=unit,
                scale=scale,
                recon=recon,
                df_metrics=df_metrics,
                df_ratios=df_ratios,
                altman=altman,
                piotroski=piotroski,
                anomalies=anomalies,
                dossier_text=dossier.get("content", "")
            )
            st.download_button(
                label="📥 Download Executive Briefing (.pdf)",
                data=pdf_bytes,
                file_name=f"{company_name}_{target_period}_Executive_Dossier.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as e:
            st.warning("⚠️ PDF generation encountered a layout warning. Please use the Markdown or CSV exports.")

    with col_dl3:
        csv_data = df_metrics.to_csv().encode("utf-8")
        st.download_button(
            label="📊 Download Statement Matrix (.csv)",
            data=csv_data,
            file_name=f"{company_name}_{target_period}_Financial_Spread.csv",
            mime="text/csv",
            use_container_width=True
        )