from typing import Dict, Any
import pandas as pd
import numpy as np

def safe_val(df: pd.DataFrame, metric: str, period: str, default: float = 0.0) -> float:
    try:
        if metric in df.index and period in df.columns:
            val = df.loc[metric, period]
            return float(val) if pd.notna(val) else default
        
        metric_col = next((c for c in df.columns if str(c).lower() in ["metric", "line_item", "canonical_name"]), None)
        if metric_col and period in df.columns:
            matched = df[df[metric_col].astype(str).str.lower() == metric.lower()]
            if not matched.empty:
                val = matched.iloc[0][period]
                return float(val) if pd.notna(val) else default
    except Exception:
        pass
    return default

def compute_financial_ratios(df_financials: pd.DataFrame, unit_label: str = "Cr") -> pd.DataFrame:
    ratios = {}
    periods = [col for col in df_financials.columns if str(col).lower() not in ["metric", "category", "line_item"]]

    for period in periods:
        rev = safe_val(df_financials, "revenue", period, 0.0)
        ebitda = safe_val(df_financials, "ebitda", period, 0.0)
        pat = safe_val(df_financials, "pat", period, 0.0)
        equity = safe_val(df_financials, "total_equity", period, 0.0)
        debt = safe_val(df_financials, "total_borrowings", period, 0.0)
        cash = safe_val(df_financials, "cash_and_equivalents", period, 0.0)
        receivables = safe_val(df_financials, "trade_receivables", period, 0.0)
        cfo = safe_val(df_financials, "cfo", period, 0.0)
        capex = safe_val(df_financials, "capex", period, 0.0)

        ebitda_margin = (ebitda / rev * 100) if rev > 0 else 0.0
        pat_margin = (pat / rev * 100) if rev > 0 else 0.0
        net_debt = max(debt - cash, 0.0)
        net_debt_ebitda = (net_debt / ebitda) if ebitda > 0 else 0.0

        # Negative Equity Guardrail
        if equity < 0:
            roe_display = f"Negative Net Worth ({equity:,.0f})"
            roce_display = "Capital Impaired"
        elif equity > 0:
            roe = (pat / equity * 100)
            roce = ((ebitda * 0.75) / (equity + debt) * 100) if (equity + debt) > 0 else 0.0
            roe_display = f"{roe:.2f}%"
            roce_display = f"{roce:.2f}%"
        else:
            roe_display = "N/A"
            roce_display = "N/A"

        receivable_days = (receivables / rev * 365) if rev > 0 else 0.0
        fcf = cfo - capex
        cfo_pat_ratio = (cfo / pat) if pat > 0 else 0.0

        ratios[period] = {
            "EBITDA Margin (%)": f"{ebitda_margin:.2f}%",
            "PAT Margin (%)": f"{pat_margin:.2f}%",
            "ROE Evaluation": roe_display,
            "ROCE Evaluation": roce_display,
            "Receivable Days": f"{receivable_days:.1f} days",
            "Net Debt / EBITDA (x)": f"{net_debt_ebitda:.2f}x",
            f"Free Cash Flow ({unit_label})": f"{fcf:,.2f}",
            "CFO / PAT (Cash Quality)": f"{cfo_pat_ratio:.2f}x"
        }

    return pd.DataFrame(ratios)