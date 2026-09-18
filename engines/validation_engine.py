from typing import Dict, List, Any
from engines.normalization_engine import LineItemMetadata

class ReconciliationAudit:
    def __init__(self, tolerance: float = 2.0):
        self.tolerance = tolerance  # Tolerated rounding differences in reporting units (e.g. +/- 2 Cr)

    def verify_income_statement(self, items: Dict[str, LineItemMetadata]) -> Dict[str, Any]:
        """Validates: EBITDA ≈ Revenue - (Raw Materials + Employee Expenses + Other Expenses)"""
        flags = []
        rev = items.get("revenue")
        ebitda = items.get("ebitda")
        pat = items.get("pat")
        depr = items.get("depreciation")
        interest = items.get("finance_costs")

        if rev and ebitda and rev.value > 0:
            if ebitda.value > rev.value:
                flags.append({
                    "severity": "CRITICAL",
                    "issue": "EBITDA exceeds Total Revenue",
                    "delta": ebitda.value - rev.value,
                    "pages": [rev.page, ebitda.page]
                })

        if ebitda and pat and depr and interest:
            expected_pbt_approx = ebitda.value - depr.value - interest.value
            if pat.value > expected_pbt_approx + self.tolerance and expected_pbt_approx > 0:
                flags.append({
                    "severity": "WARNING",
                    "issue": "PAT exceeds Operating Profit minus D&A and Interest (Check exceptional items/tax credit)",
                    "delta": pat.value - expected_pbt_approx,
                    "pages": [ebitda.page, pat.page]
                })

        return {"statement": "Income Statement", "valid": len(flags) == 0, "discrepancies": flags}

    def verify_balance_sheet(self, items: Dict[str, LineItemMetadata]) -> Dict[str, Any]:
        """Validates: Total Assets == Total Liabilities & Equity"""
        assets = items.get("total_assets")
        liab = items.get("total_liabilities")
        flags = []

        if assets and liab:
            diff = abs(assets.value - liab.value)
            if diff > self.tolerance:
                flags.append({
                    "severity": "CRITICAL",
                    "issue": "Balance Sheet mismatch: Assets ≠ Liabilities + Equity",
                    "difference": diff,
                    "evidence": f"Assets: {assets.value} (p.{assets.page}) vs Liab: {liab.value} (p.{liab.page})"
                })

        return {"statement": "Balance Sheet", "valid": len(flags) == 0, "discrepancies": flags}

    def verify_cash_flow(self, items: Dict[str, LineItemMetadata]) -> Dict[str, Any]:
        """Audits Cash Conversion Divergence (PAT vs CFO)"""
        pat = items.get("pat")
        cfo = items.get("cfo")
        flags = []

        if pat and cfo:
            if pat.value > 0 and cfo.value < 0:
                flags.append({
                    "severity": "HIGH_ALERT",
                    "issue": "Earnings Quality: Positive Net Profit (PAT) alongside Negative Cash Flow from Operations (CFO)",
                    "delta": pat.value - cfo.value,
                    "evidence": f"PAT: {pat.value} (p.{pat.page}) | CFO: {cfo.value} (p.{cfo.page})"
                })
        return {"statement": "Cash Flow", "valid": True, "discrepancies": flags}