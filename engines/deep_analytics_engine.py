import pandas as pd
import numpy as np
from typing import Dict, Any

def safe_val(df: pd.DataFrame, metric_name: str, period: str, default: float = None) -> float:
    try:
        if metric_name in df.index and period in df.columns:
            val = df.loc[metric_name, period]
            return float(val) if pd.notna(val) else default
        metric_col = next((c for c in df.columns if str(c).lower() in ["metric", "line_item", "canonical_name"]), None)
        if metric_col and period in df.columns:
            matched = df[df[metric_col].astype(str).str.lower() == metric_name.lower()]
            if not matched.empty:
                val = matched.iloc[0][period]
                return float(val) if pd.notna(val) else default
        if metric_name in df.columns and period in df.index:
            val = df.loc[period, metric_name]
            return float(val) if pd.notna(val) else default
    except Exception:
        pass
    return default


def calculate_piotroski_f_score(df: pd.DataFrame) -> Dict[str, Any]:
    """Computes Joseph Piotroski's 9-Signal Index with explicit verifiable vs unavailable tracking."""
    periods = [col for col in df.columns if str(col).lower() not in ["metric", "category", "line_item"]]
    if len(periods) < 2:
        return {
            "summary_label": "N/A — Insufficient Multi-Cycle History",
            "verifiable_count": 0, "passing_count": 0, "unavailable_count": 9, "signals": {}
        }

    curr, prev = periods[-1], periods[-2]
    signals = {}
    passes = 0
    verifiable = 0
    unavailable = 0

    def record_signal(name: str, passed: bool = None, detail: str = ""):
        nonlocal passes, verifiable, unavailable
        if passed is None:
            signals[name] = {"status": "UNAVAILABLE", "label": "N/A — Insufficient source data", "detail": detail}
            unavailable += 1
        elif passed:
            signals[name] = {"status": "PASS", "label": "Pass (1)", "detail": detail}
            passes += 1
            verifiable += 1
        else:
            signals[name] = {"status": "FLAG", "label": "Flag (0)", "detail": detail}
            verifiable += 1

    # 1. Positive ROA
    pat_c = safe_val(df, "pat", curr)
    ast_c = safe_val(df, "total_assets", curr)
    if pat_c is not None and ast_c and ast_c > 0:
        roa = pat_c / ast_c
        record_signal("1. Positive Return on Assets (ROA)", roa > 0, f"ROA: {roa*100:.2f}% (PAT: {pat_c:,.0f} / Assets: {ast_c:,.0f})")
    else:
        record_signal("1. Positive Return on Assets (ROA)", None, "Missing PAT or Assets")

    # 2. Positive CFO
    cfo_c = safe_val(df, "cfo", curr)
    if cfo_c is not None:
        record_signal("2. Positive Operating Cash Flow (CFO)", cfo_c > 0, f"Reported CFO: {cfo_c:,.0f}")
    else:
        record_signal("2. Positive Operating Cash Flow (CFO)", None, "Missing Cash Flow Statement")

    # 3. ROA Improvement
    pat_p = safe_val(df, "pat", prev)
    ast_p = safe_val(df, "total_assets", prev)
    if all(v is not None for v in [pat_c, ast_c, pat_p, ast_p]) and ast_c > 0 and ast_p > 0:
        roa_c = pat_c / ast_c
        roa_p = pat_p / ast_p
        record_signal("3. Year-over-Year ROA Improvement", roa_c > roa_p, f"Current: {roa_c*100:.2f}% vs Prev: {roa_p*100:.2f}%")
    else:
        record_signal("3. Year-over-Year ROA Improvement", None, "Missing comparative cycle items")

    # 4. CFO > Net Income
    if cfo_c is not None and pat_c is not None:
        record_signal("4. Accrual Quality (CFO > Net Income)", cfo_c > pat_c, f"CFO: {cfo_c:,.0f} vs PAT: {pat_c:,.0f}")
    else:
        record_signal("4. Accrual Quality (CFO > Net Income)", None, "Missing CFO or PAT")

    # 5. Deleveraging Trend
    d_c = safe_val(df, "total_borrowings", curr)
    d_p = safe_val(df, "total_borrowings", prev)
    if all(v is not None for v in [d_c, ast_c, d_p, ast_p]) and ast_c > 0 and ast_p > 0:
        record_signal("5. Deleveraging Trend (Debt / Assets)", (d_c / ast_c) <= (d_p / ast_p), f"Current: {(d_c/ast_c):.2f}x vs Prev: {(d_p/ast_p):.2f}x")
    else:
        record_signal("5. Deleveraging Trend (Debt / Assets)", None, "Borrowings or Assets incomplete")

    # 6. Current Ratio Improvement
    ca_c, cl_c = safe_val(df, "current_assets", curr), safe_val(df, "current_liabilities", curr)
    ca_p, cl_p = safe_val(df, "current_assets", prev), safe_val(df, "current_liabilities", prev)
    if all(v is not None for v in [ca_c, cl_c, ca_p, cl_p]) and cl_c > 0 and cl_p > 0:
        record_signal("6. Liquidity Improvement (Current Ratio)", (ca_c / cl_c) > (ca_p / cl_p), f"Current: {(ca_c/cl_c):.2f}x vs Prev: {(ca_p/cl_p):.2f}x")
    else:
        record_signal("6. Liquidity Improvement (Current Ratio)", None, "Condensed statements lack isolated Current Assets / Liabilities breakdown")

    # 7. Share Dilution Guardrail
    sh_c = safe_val(df, "no_of_shares", curr)
    sh_p = safe_val(df, "no_of_shares", prev)
    if sh_c is not None and sh_p is not None:
        record_signal("7. Share Dilution Guardrail", sh_c <= sh_p, f"Shares: {sh_c:,.0f} vs Prev: {sh_p:,.0f}")
    else:
        record_signal("7. Share Dilution Guardrail", None, "Share count not reported in canonical schedule")

    # 8. Operating Margin Improvement
    r_c, r_p = safe_val(df, "revenue", curr), safe_val(df, "revenue", prev)
    e_c, e_p = safe_val(df, "ebitda", curr), safe_val(df, "ebitda", prev)
    if all(v is not None for v in [r_c, r_p, e_c, e_p]) and r_c > 0 and r_p > 0:
        record_signal("8. Operating Margin Improvement", (e_c / r_c) > (e_p / r_p), f"Current: {(e_c/r_c)*100:.2f}% vs Prev: {(e_p/r_p)*100:.2f}%")
    else:
        record_signal("8. Operating Margin Improvement", None, "Missing comparative revenue/EBITDA")

    # 9. Asset Turnover Improvement
    if all(v is not None for v in [r_c, r_p, ast_c, ast_p]) and ast_c > 0 and ast_p > 0:
        record_signal("9. Asset Turnover Improvement", (r_c / ast_c) > (r_p / ast_p), f"Current: {(r_c/ast_c):.2f}x vs Prev: {(r_p/ast_p):.2f}x")
    else:
        record_signal("9. Asset Turnover Improvement", None, "Turnover components incomplete")

    return {
        "summary_label": f"{passes} / {verifiable} Verifiable ({unavailable} Unavailable)",
        "verifiable_count": verifiable,
        "passing_count": passes,
        "unavailable_count": unavailable,
        "signals": signals
    }


def calculate_altman_z(df: pd.DataFrame, period: str, is_bank: bool = False, extra_meta: Dict[str, Any] = None) -> Dict[str, Any]:
    """Computes Altman Z-Score with full transparent audit of inputs and formula version."""
    if is_bank:
        return {
            "model_name": "Altman Z-Score",
            "formula_version": "Inapplicable",
            "z_score": "N/A",
            "zone": "Inapplicable",
            "applicability_warning": "Altman Z is conceptually invalid for banks and deposit-taking institutions.",
            "formula_audit": []
        }

    assets = max(safe_val(df, "total_assets", period, 1.0), 1.0)
    rev = safe_val(df, "revenue", period, 0.0)
    ebitda = safe_val(df, "ebitda", period, 0.0)
    debt = safe_val(df, "total_borrowings", period, 0.0)
    equity = safe_val(df, "total_equity", period, 0.0)
    cash = safe_val(df, "cash_and_equivalents", period, 0.0)
    rec = safe_val(df, "trade_receivables", period, 0.0)

    # TRUE Retained Earnings: Read Reserves & Surplus directly from balance sheet
    # In corporate balance sheets, accumulated losses reside in Reserves & Surplus
    reserves_val = safe_val(df, "reserves", period, None)
    if reserves_val is None and extra_meta:
        reserves_val = extra_meta.get("reserves", None)
    if reserves_val is None:
        # If reserves not isolated, book equity - share capital
        eq_cap = safe_val(df, "equity_share_capital", period, 0.0)
        reserves_val = equity - eq_cap if eq_cap else equity

    retained_earnings = float(reserves_val)

    # Input Calculations
    wc_proxy = (cash + rec) - (debt * 0.15)
    x1 = wc_proxy / assets
    x2 = retained_earnings / assets
    x3 = ebitda / assets
    x4 = equity / max(debt, 1.0) if debt > 0 else 1.0
    x5 = rev / assets

    raw_z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 0.999 * x5
    z_score = round(float(raw_z), 2)

    formula_audit = [
        {
            "Term": "A: Working Capital / Assets",
            "Formula": "(Cash + Debtors - Est. Short Term Debt) / Total Assets",
            "Numerator": f"₹{wc_proxy:,.0f} Cr (Working Capital Proxy)",
            "Denominator": f"₹{assets:,.0f} Cr (Total Assets)",
            "Value": f"{x1:.4f}",
            "Weight": "1.20",
            "Contribution": f"{1.2 * x1:.2f}",
            "Source": "Balance Sheet (Cash & Receivables schedules)"
        },
        {
            "Term": "B: Retained Earnings / Assets",
            "Formula": "Cumulative Reserves & Surplus / Total Assets",
            "Numerator": f"₹{retained_earnings:,.0f} Cr (Reported Reserves)",
            "Denominator": f"₹{assets:,.0f} Cr (Total Assets)",
            "Value": f"{x2:.4f}",
            "Weight": "1.40",
            "Contribution": f"{1.4 * x2:.2f}",
            "Source": "Balance Sheet (Reserves & Surplus schedule)"
        },
        {
            "Term": "C: Operating Profit / Assets",
            "Formula": "Operating EBITDA / Total Assets",
            "Numerator": f"₹{ebitda:,.0f} Cr (Operating EBITDA)",
            "Denominator": f"₹{assets:,.0f} Cr (Total Assets)",
            "Value": f"{x3:.4f}",
            "Weight": "3.30",
            "Contribution": f"{3.3 * x3:.2f}",
            "Source": "Statement of Profit & Loss (Operating EBITDA)"
        },
        {
            "Term": "D: Book Equity / Liabilities",
            "Formula": "Total Shareholders' Equity / Total Gross Debt",
            "Numerator": f"₹{equity:,.0f} Cr (Total Shareholders' Equity)",
            "Denominator": f"₹{debt:,.0f} Cr (Total Borrowings)",
            "Value": f"{x4:.4f}",
            "Weight": "0.60",
            "Contribution": f"{0.6 * x4:.2f}",
            "Source": "Balance Sheet (Equity Base vs Borrowings schedule)"
        },
        {
            "Term": "E: Sales / Assets",
            "Formula": "Gross Revenue from Operations / Total Assets",
            "Numerator": f"₹{rev:,.0f} Cr (Revenue from Operations)",
            "Denominator": f"₹{assets:,.0f} Cr (Total Assets)",
            "Value": f"{x5:.4f}",
            "Weight": "0.999",
            "Contribution": f"{0.999 * x5:.2f}",
            "Source": "Statement of Profit & Loss (Revenue schedule)"
        }
    ]

    if z_score >= 2.99:
        zone = "Safe Zone (Statistical Low Distress Probability)"
    elif z_score >= 1.81:
        zone = "Grey Zone (Financial Leverage Strain)"
    else:
        zone = "Distress Zone (High Leverage Profile)"

    warning = (
        "Model Applicability Warning: The Altman Z-Score formula was originally calibrated on manufacturing "
        "populations. For capital-intensive telecom, utilities, or asset-heavy service corporations with heavy debt "
        "or negative reserves, mechanical score thresholds must be evaluated alongside actual debt refinancing ability "
        "and operational cash generation."
    )

    return {
        "model_name": "Altman Z-Score",
        "formula_version": "Original Z (Manufacturing Calibration with Working Capital Proxy)",
        "z_score": z_score,
        "zone": zone,
        "applicability_warning": warning,
        "formula_audit": formula_audit
    }


def perform_dupont_decomposition(df: pd.DataFrame, period: str) -> Dict[str, Any]:
    """Safely decomposes ROE with negative net worth detection."""
    rev = safe_val(df, "revenue", period, 0.0)
    pat = safe_val(df, "pat", period, 0.0)
    assets = max(safe_val(df, "total_assets", period, 1.0), 1.0)
    equity = safe_val(df, "total_equity", period, 0.0)

    if equity < 0:
        return {
            "Net Profit Margin (%)": round((pat / rev * 100) if rev > 0 else 0.0, 2),
            "Asset Turnover (x)": round((rev / assets) if assets > 0 else 0.0, 2),
            "Financial Leverage Multiplier (x)": "Negative (Capital Deficit)",
            "Decomposed ROE (%)": "Inappropriate (Negative Book Equity)",
            "is_negative_equity": True,
            "equity_val": equity
        }

    net_margin = (pat / rev * 100) if rev > 0 else 0.0
    asset_turnover = rev / assets if assets > 0 else 0.0
    financial_leverage = assets / equity if equity > 0 else 0.0
    roe = (pat / equity) * 100 if equity > 0 else 0.0

    return {
        "Net Profit Margin (%)": round(net_margin, 2),
        "Asset Turnover (x)": round(asset_turnover, 2),
        "Financial Leverage Multiplier (x)": round(financial_leverage, 2),
        "Decomposed ROE (%)": f"{round(roe, 2)}%",
        "is_negative_equity": False,
        "equity_val": equity
    }