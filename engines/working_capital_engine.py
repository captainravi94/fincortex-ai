import pandas as pd
import numpy as np
from typing import Dict, Any, List

class WorkingCapitalBridgeEngine:
    """
    Deconstructs the mathematical bridge between Operating EBITDA / PAT 
    and Operating Cash Flow (CFO) across individual balance sheet working capital movements.
    """

    @staticmethod
    def compute_bridge(df: pd.DataFrame, period: str) -> Dict[str, Any]:
        periods = [c for c in df.columns if str(c).lower() not in ["metric", "category", "line_item"]]
        if not periods or period not in periods:
            return {"status": "INSUFFICIENT_DATA", "bridge": []}

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

        ebitda = g("ebitda", curr)
        pat = g("pat", curr)
        cfo = g("cfo", curr)
        other_inc = g("other_income", curr)

        # Working capital line items
        rec_c, rec_p = g("trade_receivables", curr), g("trade_receivables", prev) if prev else g("trade_receivables", curr)
        inv_c, inv_p = g("inventories", curr), g("inventories", prev) if prev else g("inventories", curr)
        pay_c, pay_p = g("trade_payables", curr), g("trade_payables", prev) if prev else g("trade_payables", curr)
        other_liab_c = g("other_liabilities", curr)
        other_liab_p = g("other_liabilities", prev) if prev else other_liab_c

        # Cash Flow Movements:
        # Increase in Asset = Cash Outflow (-); Increase in Liability = Cash Inflow (+)
        delta_rec = -(rec_c - rec_p)
        delta_inv = -(inv_c - inv_p)
        delta_pay = (pay_c - pay_p)
        delta_other_liab = (other_liab_c - other_liab_p)

        net_wc_movement = delta_rec + delta_inv + delta_pay + delta_other_liab
        unreconciled_gap = cfo - (ebitda + net_wc_movement)

        bridge_steps = [
            {
                "Step": "1. Operating EBITDA",
                "Category": "Operating Base",
                "Impact": ebitda,
                "Description": "Reported Core Operating Profit before non-operating income & tax"
            },
            {
                "Step": "2. Δ Trade Receivables",
                "Category": "Working Capital",
                "Impact": delta_rec,
                "Description": f"{'Cash absorbed by debtors' if delta_rec < 0 else 'Cash released from collections'} (Receivables: {rec_p:,.0f} → {rec_c:,.0f})"
            },
            {
                "Step": "3. Δ Inventories",
                "Category": "Working Capital",
                "Impact": delta_inv,
                "Description": f"{'Cash tied up in stock' if delta_inv < 0 else 'Cash released from inventory liquidation'} (Inventory: {inv_p:,.0f} → {inv_c:,.0f})"
            },
            {
                "Step": "4. Δ Trade Payables",
                "Category": "Working Capital",
                "Impact": delta_pay,
                "Description": f"{'Vendor credit expansion (Cash preserved)' if delta_pay >= 0 else 'Supplier repayments (Cash outflow)'} (Payables: {pay_p:,.0f} → {pay_c:,.0f})"
            },
            {
                "Step": "5. Δ Other Operational Liabilities",
                "Category": "Working Capital",
                "Impact": delta_other_liab,
                "Description": f"Net variation in customer advances, statutory dues & operating provisions"
            },
            {
                "Step": "6. Taxes & Non-Cash Adjustments",
                "Category": "Taxes / Non-Cash",
                "Impact": unreconciled_gap,
                "Description": "Direct corporate taxes paid, provisions, and non-operating timing differences"
            },
            {
                "Step": "7. Audited Operating Cash Flow (CFO)",
                "Category": "Final Realization",
                "Impact": cfo,
                "Description": "Actual cash delivered into treasury from operating operations"
            }
        ]

        return {
            "status": "SUCCESS",
            "ebitda": ebitda,
            "cfo": cfo,
            "net_wc_movement": net_wc_movement,
            "bridge": bridge_steps
        }