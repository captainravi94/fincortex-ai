from typing import List, Dict, Any
import pandas as pd

def safe_get_metric(df: pd.DataFrame, metric_name: str, period: str, default: float = 0.0) -> float:
    """Safely retrieves a metric value whether df is indexed by metric or has a 'metric' column."""
    try:
        # Case 1: Metric is the row index
        if metric_name in df.index and period in df.columns:
            val = df.loc[metric_name, period]
            return float(val) if pd.notna(val) else default
        
        # Case 2: There is a column named 'metric' or 'line_item'
        metric_col = next((c for c in df.columns if str(c).lower() in ["metric", "line_item", "canonical_name"]), None)
        if metric_col and period in df.columns:
            matched = df[df[metric_col].astype(str).str.lower() == metric_name.lower()]
            if not matched.empty:
                val = matched.iloc[0][period]
                return float(val) if pd.notna(val) else default

        # Case 3: Inverted DataFrame (periods are row index, metrics are columns)
        if metric_name in df.columns and period in df.index:
            val = df.loc[period, metric_name]
            return float(val) if pd.notna(val) else default
    except Exception:
        pass
    return default


class CFOForensicAudit:
    @staticmethod
    def analyze_health(df_metrics: pd.DataFrame) -> List[Dict[str, Any]]:
        """Evaluates trend divergences across the latest two reporting cycles with safe metric retrieval."""
        alerts = []
        if df_metrics is None or df_metrics.empty:
            return alerts

        # Determine period columns
        periods = [col for col in df_metrics.columns if str(col).lower() not in ["metric", "category", "line_item"]]
        if len(periods) < 2:
            return alerts

        curr = periods[-1]
        prev = periods[-2]

        c_rev = safe_get_metric(df_metrics, "revenue", curr)
        p_rev = safe_get_metric(df_metrics, "revenue", prev)
        rev_growth = ((c_rev - p_rev) / p_rev) * 100 if p_rev > 0 else 0.0

        # 1. Receivables vs. Revenue Growth Disparity
        c_rec = safe_get_metric(df_metrics, "trade_receivables", curr)
        p_rec = safe_get_metric(df_metrics, "trade_receivables", prev)
        rec_growth = ((c_rec - p_rec) / p_rec) * 100 if p_rec > 0 else 0.0

        if rec_growth > (rev_growth + 12) and rec_growth > 0:
            alerts.append({
                "category": "Working Capital Deterioration",
                "severity": "HIGH",
                "metric": "Debtors vs Sales Divergence",
                "evidence": f"Trade Receivables grew +{rec_growth:.1f}% while Revenue only grew +{rev_growth:.1f}%.",
                "implication": "Indicates aggressive credit terms or uncollected receivables, degrading cash collection efficiency."
            })

        # 2. Operating Margin Compression
        c_ebitda = safe_get_metric(df_metrics, "ebitda", curr)
        p_ebitda = safe_get_metric(df_metrics, "ebitda", prev)
        c_ebitda_m = (c_ebitda / c_rev) * 100 if c_rev > 0 else 0.0
        p_ebitda_m = (p_ebitda / p_rev) * 100 if p_rev > 0 else 0.0
        margin_delta_bps = (c_ebitda_m - p_ebitda_m) * 100

        if margin_delta_bps < -150 and p_ebitda_m > 0:
            alerts.append({
                "category": "Profitability Compression",
                "severity": "HIGH",
                "metric": "EBITDA Margin Erosion",
                "evidence": f"Operating margin contracted by {abs(margin_delta_bps):.0f} bps ({p_ebitda_m:.1f}% → {c_ebitda_m:.1f}%).",
                "implication": "Input cost inflation or adverse pricing mix impacting operating profitability."
            })

        # 3. Cash Quality: CFO / PAT Decoupling
        c_pat = safe_get_metric(df_metrics, "pat", curr)
        c_cfo = safe_get_metric(df_metrics, "cfo", curr)
        if c_pat > 0 and (c_cfo / c_pat) < 0.70:
            alerts.append({
                "category": "Cash Flow Integrity",
                "severity": "CRITICAL",
                "metric": "Operating Cash Conversion Gap",
                "evidence": f"CFO to PAT conversion ratio dropped to {(c_cfo/c_pat):.2f}x (Reported PAT: {c_pat:,.0f} vs CFO: {c_cfo:,.0f}).",
                "implication": "Earnings are heavily driven by non-cash accruals rather than realized cash inflow."
            })

        return alerts