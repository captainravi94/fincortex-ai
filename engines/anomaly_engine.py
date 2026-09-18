import pandas as pd
import numpy as np
from typing import Dict, Any, List

class FinancialAnomalyEngine:
    """
    Scans financial statements for structural anomalies, growth-accrual divergences,
    and outsized non-operating movements before triggering analytical commentary.
    """

    @staticmethod
    def detect_anomalies(df: pd.DataFrame, period: str, extra_meta: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        anomalies: List[Dict[str, Any]] = []
        periods = [c for c in df.columns if c not in ["metric", "category", "line_item"]]
        if not periods or period not in periods:
            return anomalies

        curr = period
        prev = periods[periods.index(curr) - 1] if periods.index(curr) > 0 else None

        def g(k, p):
            try:
                if k in df.index and p in df.columns:
                    v = df.loc[k, p]
                    return float(v) if pd.notna(v) else 0.0
            except Exception:
                pass
            return 0.0

        rev_c, rev_p = g("revenue", curr), g("revenue", prev) if prev else 0.0
        ebitda_c, ebitda_p = g("ebitda", curr), g("ebitda", prev) if prev else 0.0
        pat_c = g("pat", curr)
        other_inc_c = g("other_income", curr)
        cfo_c = g("cfo", curr)
        debt_c, debt_p = g("total_borrowings", curr), g("total_borrowings", prev) if prev else 0.0
        eq_c = g("total_equity", curr)
        rec_c, rec_p = g("trade_receivables", curr), g("trade_receivables", prev) if prev else 0.0

        # Anomaly 1: Disproportionate Other Income
        if ebitda_c > 0 and (other_inc_c / ebitda_c) >= 1.0:
            ratio = other_inc_c / ebitda_c
            anomalies.append({
                "id": "ANOMALY-001",
                "severity": "CRITICAL",
                "title": "Other Income Relative to Operating Profit Exceeds Threshold",
                "metric": f"Other Income / EBITDA = {ratio:.2f}x",
                "evidence": f"Reported Other Income of ₹{other_inc_c:,.0f} Cr vs Operating EBITDA of ₹{ebitda_c:,.0f} Cr",
                "investigation": "Inspect Note on 'Other Income' to decompose recurring treasury yield vs non-recurring liability derecognitions or asset sales."
            })

        # Anomaly 2: Net Profit vs Operating Cash Flow Divergence
        if pat_c > 0 and cfo_c > 0 and (cfo_c / pat_c) < 0.70:
            cfo_pat = cfo_c / pat_c
            anomalies.append({
                "id": "ANOMALY-002",
                "severity": "HIGH",
                "title": "Earnings-to-Cash Realization Divergence",
                "metric": f"CFO / PAT = {cfo_pat:.2f}x",
                "evidence": f"Reported PAT of ₹{pat_c:,.0f} Cr realized only ₹{cfo_c:,.0f} Cr in Operating Cash Flow",
                "investigation": "Determine if gap is driven by non-operating accounting credits in PAT or balance sheet working capital expansion."
            })

        # Anomaly 3: Negative Shareholders' Equity / Deficit Net Worth
        if eq_c < 0:
            anomalies.append({
                "id": "ANOMALY-003",
                "severity": "CRITICAL",
                "title": "Negative Shareholders' Equity / Net Worth Deficit",
                "metric": f"Shareholders' Equity = ₹{eq_c:,.0f} Cr",
                "evidence": f"Carrying value of liabilities exceeds total assets by ₹{abs(eq_c):,.0f} Cr",
                "investigation": "Evaluate debt maturity profile, statutory refinancing support, and stakeholder equity undertakings."
            })

        # Anomaly 4: Debt Reduction Attribution Check
        if prev and (debt_p - debt_c) > (rev_c * 0.20):
            debt_reduction = debt_p - debt_c
            anomalies.append({
                "id": "ANOMALY-004",
                "severity": "MEDIUM",
                "title": "Substantial Gross Borrowings Contraction",
                "metric": f"Gross Debt Reduction = ₹{debt_reduction:,.0f} Cr",
                "evidence": f"Borrowings decreased from ₹{debt_p:,.0f} Cr to ₹{debt_c:,.0f} Cr",
                "investigation": "Reconcile Cash Flow from Financing Activities to verify whether debt was extinguished through cash repayment, debt-to-equity swap, or moratorium rescheduling."
            })

        # Anomaly 5: Revenue vs Debtor Growth Disconnect
        if prev and rev_p > 0 and rec_p > 0:
            rev_growth = (rev_c - rev_p) / rev_p
            rec_growth = (rec_c - rec_p) / rec_p
            if (rec_growth - rev_growth) > 0.30:
                anomalies.append({
                    "id": "ANOMALY-005",
                    "severity": "HIGH",
                    "title": "Receivables Growth Accelerating Faster Than Sales",
                    "metric": f"Receivables Growth: {rec_growth*100:+.1f}% vs Sales: {rev_growth*100:+.1f}%",
                    "evidence": f"Debtors grew by {rec_growth*100:.1f}% while Revenue expanded by {rev_growth*100:.1f}%",
                    "investigation": "Audit customer payment terms, overdue aging buckets (>180 days), and provisioning adequacy."
                })

        return anomalies