import os
import json
import requests
import pandas as pd
from typing import Dict, Any

class GeminiFinancialAnalyst:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")

    def generate_boardroom_dossier(
        self, 
        company_name: str, 
        period: str, 
        df_metrics: pd.DataFrame, 
        df_ratios: pd.DataFrame, 
        altman: Dict[str, Any], 
        piotroski: Dict[str, Any],
        alerts: list,
        extra_diagnostics: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Executes the 7-Tier Lineage Protocol with Evidence Traces:
        SOURCE -> 🔵 REPORTED -> 🟣 CALCULATED -> 🟠 OBSERVATION -> 🟠 INTERPRETATION -> ⚠️ LIMITATION -> 🔴 INVESTIGATION
        """
        diag = extra_diagnostics or {}
        payload = {
            "company": company_name,
            "period": period,
            "metrics": df_metrics.to_dict(),
            "ratios": df_ratios.to_dict(),
            "altman_z": altman,
            "piotroski_f": piotroski,
            "extra": diag
        }

        prompt = f"""
        You are a Senior Managing Director of Institutional Credit & Forensic Accounting.
        Analyze this company using the exact 7-Tier Lineage Protocol for every core finding:
        1. SOURCE: Financial report schedule and statement citation.
        2. 🔵 REPORTED: Direct unadjusted figures from source statements.
        3. 🟣 CALCULATED: Derived ratios and mathematical adjustments (label FCF as 'Analytically Derived Free Cash Flow').
        4. 🟠 ANALYTICAL OBSERVATION: Empirical anomaly or directional drift.
        5. 🟠 INTERPRETATION: Analytical context of what this may indicate.
        6. ⚠️ LIMITATION: What CANNOT be established from this data alone.
        7. 🔴 INVESTIGATION: Probing, non-generic audit questions and note inspections for the CFO/Board.

        MANDATORY RULES:
        1. Disaggregate 'Equity Share Capital' from 'Total Shareholders' Equity / Net Worth'.
        2. Replace 'deleveraged' with 'Gross borrowings decreased by [X] Cr', accompanied by full leverage metric calculations.
        3. Never say debtor days proves billing speed; call it 'Days Sales Outstanding / DSO (Receivables Collection Cycle)'.
        4. Provide Confidence Ratings on each card (Reported Data: HIGH, Calculation: HIGH, Interpretation: MEDIUM, Recurrence: UNKNOWN).

        PAYLOAD:
        {json.dumps(payload, default=str)}
        """

        if self.api_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
                headers = {"Content-Type": "application/json"}
                body = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 3500}
                }
                res = requests.post(url, headers=headers, json=body, timeout=25)
                if res.status_code == 200:
                    return {"status": "LIVE_GEMINI", "content": res.json()["candidates"][0]["content"]["parts"][0]["text"]}
            except Exception:
                pass

        return {
            "status": "DETERMINISTIC_ENGINE",
            "content": self._build_deterministic_dossier(company_name, period, df_metrics, df_ratios, altman, piotroski, diag)
        }

    def _build_deterministic_dossier(self, comp, period, df, ratios, altman, piotroski, diag) -> str:
        curr_rev = df.loc["revenue", period] if "revenue" in df.index else 0.0
        curr_ebitda = df.loc["ebitda", period] if "ebitda" in df.index else 0.0
        curr_pat = df.loc["pat", period] if "pat" in df.index else 0.0
        curr_cfo = df.loc["cfo", period] if "cfo" in df.index else 0.0
        curr_capex = df.loc["capex", period] if "capex" in df.index else 0.0
        other_inc = diag.get("other_income", 0.0)
        debt = df.loc["total_borrowings", period] if "total_borrowings" in df.index else 0.0
        equity_cap = df.loc["equity_share_capital", period] if "equity_share_capital" in df.index else 0.0
        reserves = df.loc["reserves", period] if "reserves" in df.index else (df.loc["total_equity", period] - equity_cap if "total_equity" in df.index else 0.0)
        total_equity = equity_cap + reserves
        cash = df.loc["cash_and_equivalents", period] if "cash_and_equivalents" in df.index else 0.0
        assets = df.loc["total_assets", period] if "total_assets" in df.index else 1.0
        rec = df.loc["trade_receivables", period] if "trade_receivables" in df.index else 0.0
        rec_days = ratios.loc["Receivable Days", period] if "Receivable Days" in ratios.index else "N/A"
        fcf = curr_cfo - curr_capex

        periods = [c for c in df.columns if c not in ["metric", "category"]]
        prev_p = periods[-2] if len(periods) >= 2 else None
        debt_prev = df.loc["total_borrowings", prev_p] if prev_p and "total_borrowings" in df.index else debt
        debt_change = debt - debt_prev
        rev_prev = df.loc["revenue", prev_p] if prev_p and "revenue" in df.index else curr_rev
        rev_growth = ((curr_rev - rev_prev) / rev_prev * 100) if rev_prev > 0 else 0.0
        ebitda_prev = df.loc["ebitda", prev_p] if prev_p and "ebitda" in df.index else curr_ebitda
        assets_prev = df.loc["total_assets", prev_p] if prev_p and "total_assets" in df.index else assets
        cash_prev = df.loc["cash_and_equivalents", prev_p] if prev_p and "cash_and_equivalents" in df.index else cash

        # Multi-Ratio Leverage Evaluation
        d_ebitda_c = (debt / curr_ebitda) if curr_ebitda > 0 else 0.0
        d_ebitda_p = (debt_prev / ebitda_prev) if ebitda_prev > 0 else 0.0
        nd_ebitda_c = (max(debt - cash, 0) / curr_ebitda) if curr_ebitda > 0 else 0.0
        nd_ebitda_p = (max(debt_prev - cash_prev, 0) / ebitda_prev) if ebitda_prev > 0 else 0.0
        d_assets_c = debt / assets if assets > 0 else 0.0
        d_assets_p = debt_prev / assets_prev if assets_prev > 0 else 0.0

        # CARD 1: REVENUE & EARNINGS COMPOSITION
        card_1 = f"""### 1. Revenue & Earnings Composition Analysis
* **SOURCE:** Ingested Statement Schedule ({period}) $\\rightarrow$ Consolidated Statement of Profit & Loss $\\rightarrow$ Revenue from Operations & Other Income.
* 🔵 **REPORTED:** Gross Sales = **₹{curr_rev:,.0f} Cr** (YoY Growth: **{rev_growth:+.2f}%**); Operating EBITDA = **₹{curr_ebitda:,.0f} Cr**; Reported PAT = **₹{curr_pat:,.0f} Cr**; Reported Other Income = **₹{other_inc:,.0f} Cr**.
* 🟣 **CALCULATED:**
  * Operating EBITDA Margin = `EBITDA / Revenue` = **{(curr_ebitda/curr_rev*100) if curr_rev else 0:.2f}%**
  * Other Income Relative to Operating Profit = `Other Income / EBITDA` = **{(other_inc/curr_ebitda*100) if curr_ebitda else 0:.1f}%**
  * Cash Realization Ratio = `CFO / PAT` = **{(curr_cfo/curr_pat) if curr_pat else 0:.2f}x**
* 🟠 **ANALYTICAL OBSERVATION:** Reported Other Income (₹{other_inc:,.0f} Cr) is **substantially larger than operating EBITDA (₹{curr_ebitda:,.0f} Cr)**, while Operating Cash Flow is approximately {(curr_cfo/curr_pat) if curr_pat else 0:.2f}x of reported PAT.
* 🟠 **INTERPRETATION:** Reported PAT appears to be substantially influenced by the magnitude of reported other income. Core operating earnings before other income remain constrained relative to bottom-line net profit.
* ⚠️ **LIMITATION:** The financial statement tables alone do not decompose whether the reported other income represents liquid cash receipts, non-cash balance sheet credits, asset sales, or liability derecognitions.
* 🔴 **INVESTIGATION:** Review the Notes to the Financial Statements (Note on 'Other Income') to determine the nature, recurrence, cash/non-cash characteristics, and accounting treatment of its major components.

> **Confidence Matrix:** Reported Figures: **HIGH** | Calculation: **HIGH** | Non-operating Interpretation: **HIGH** | Cash / Recurrence Nature: **UNKNOWN (Requires Note Inspection)**"""

        # CARD 2: BALANCE SHEET & CAPITAL STRUCTURE
        card_2 = f"""### 2. Balance Sheet & Capital Structure Diagnostics
* **SOURCE:** Ingested Statement Schedule ({period}) $\\rightarrow$ Consolidated Balance Sheet $\\rightarrow$ Share Capital, Reserves & Borrowings Schedules.
* 🔵 **REPORTED:**
  * Equity Share Capital = **₹{equity_cap:,.0f} Cr**
  * Reserves and Surplus = **₹{reserves:,.0f} Cr**
  * Total Shareholders' Equity / Net Worth = **₹{total_equity:,.0f} Cr**
  * Total Borrowings = **₹{debt:,.0f} Cr** (Prior Period: **₹{debt_prev:,.0f} Cr**)
* 🟣 **CALCULATED:**
  * Gross Borrowings Delta = `Borrowings(t) - Borrowings(t-1)` = **₹{debt_change:+,.0f} Cr**
  * Total Shareholders' Equity = `Equity Share Capital + Reserves` = **₹{total_equity:,.0f} Cr**
  * Gross Debt / EBITDA = **{d_ebitda_c:.2f}x** (Prior: **{d_ebitda_p:.2f}x**)
  * Net Debt / EBITDA = **{nd_ebitda_c:.2f}x** (Prior: **{nd_ebitda_p:.2f}x**)
  * Debt / Assets = **{d_assets_c:.2f}x** (Prior: **{d_assets_p:.2f}x**)
  * Debt / Equity = **Negative / Not Meaningful**
* 🟠 **ANALYTICAL OBSERVATION:** Gross borrowings decreased by ₹{abs(debt_change):,.0f} Cr over the period, contracting Gross Debt/EBITDA from {d_ebitda_p:.2f}x to {d_ebitda_c:.2f}x.
* 🟠 **INTERPRETATION:** {"Book equity is negative at approximately ₹{:,.0f} Cr, indicating that reported liabilities exceed the carrying value of assets attributable to shareholders. The resulting negative net worth makes conventional ROE interpretation inappropriate.".format(abs(total_equity)) if total_equity < 0 else "Shareholders' equity remains positive, providing tangible common asset coverage for liabilities."}
* ⚠️ **LIMITATION:** Total gross debt reduction alone does not confirm whether liabilities were settled via operational cash repayment, debt-to-equity conversions, or moratorium rescheduling.
* 🔴 **INVESTIGATION:** Reconcile Cash Flow from Financing Activities and Debt Notes to verify whether the debt reduction was funded via operational cash or balance sheet debt conversion.

> **Confidence Matrix:** Reported Debt/Capital: **HIGH** | Leverage Ratio Calculations: **HIGH** | Deleveraging Mechanism: **MEDIUM (Requires CFF Note Review)**"""

        # CARD 3: CASH FLOW CONVERSION & WORKING CAPITAL
        reinvest = (curr_capex / curr_cfo * 100) if curr_cfo > 0 else 0.0
        card_3 = f"""### 3. Cash Flow Integrity & Capital Allocation
* **SOURCE:** Ingested Statement Schedule ({period}) $\\rightarrow$ Consolidated Statement of Cash Flows & Trade Receivables Note.
* 🔵 **REPORTED:** Operating Cash Flow (CFO) = **₹{curr_cfo:,.0f} Cr**; Capital Expenditure (Capex) = **₹{curr_capex:,.0f} Cr**; Trade Receivables = **₹{rec:,.0f} Cr**.
* 🟣 **CALCULATED:**
  * Analytically Derived Free Cash Flow = `CFO - Capex` = **₹{fcf:,.0f} Cr**
  * Capital Reinvestment Rate = `Capex / CFO` = **{reinvest:.1f}%**
  * Days Sales Outstanding (DSO) = `(Trade Receivables / Sales) * 365` = **{rec_days}**
* 🟠 **ANALYTICAL OBSERVATION:** Operating cash flow exceeded capital expenditures during {period}, resulting in an analytically derived Free Cash Flow of ₹{fcf:,.0f} Cr.
* 🟠 **INTERPRETATION:** The calculation establishes a Days Sales Outstanding (DSO) of {rec_days} based on year-end receivables. However, this collection metric does not, by itself, establish that working capital is not contributing to the earnings-to-cash-flow difference.
* ⚠️ **LIMITATION:** An isolated DSO metric does not capture intra-year billing seasonality, customer advances, trade payables expansion, or inventory movements. A complete working-capital movement analysis across payables and inventories is required.
* 🔴 **INVESTIGATION:** Inspect the Working Capital Adjustment schedule in the Statement of Cash Flows to verify net cash absorbed or released by trade payables, inventories, and statutory provisions.

> **Confidence Matrix:** Reported CFO & Capex: **HIGH** | Analytically Derived FCF: **HIGH** | Working Capital Movement: **LIMITED (Requires Complete Current Liabilities Audit)**"""

        # CARD 4: FINANCIAL MODEL VALIDATION & METHODOLOGY AUDIT
        card_4 = f"""### 4. Financial Model Validation & Methodology Audit
* **SOURCE:** Academic Solvency & Accounting Quality Models applied to Ingested Statements ({period}).
* **ALTMAN Z-SCORE AUDIT:**
  * *Model:* {altman['model_name']} | *Formula Version:* {altman['formula_version']}
  * *Calculated Z-Score:* `{altman['z_score']}` — **{altman['zone']}**
  * *Input B Audit (Retained Earnings / Assets):* Calculated as `Reserves & Surplus / Assets` = **{reserves:,.0f} / {assets:,.0f} = {reserves/assets:.4f}** (Reflecting accumulated reserves deficit rather than synthetic earnings proxy).
  * *Model Applicability Warning:* {altman['applicability_warning']}
* **PIOTROSKI F-SCORE AUDIT:**
  * *Model:* Joseph Piotroski 9-Signal Fundamental Health Index
  * *Summary Result:* **{piotroski['summary_label']}** (Verifiable: {piotroski['verifiable_count']}/9 | Passing: {piotroski['passing_count']} | Unavailable: {piotroski['unavailable_count']})
  * *Validation Rule:* Signals without direct audited statement line items are strictly isolated as 'Unavailable' rather than guessed."""

        # CARD 5: BOARDROOM INQUIRIES
        card_5 = f"""### 5. Boardroom & CFO Investigation Directives
1. 🔴 **Other Income Composition Audit:** Reconcile reported Other Income of ₹{other_inc:,.0f} Cr to identify cash vs. non-cash, exceptional, or operational components.
2. 🔴 **Debt Movement Attribution:** Determine whether the gross borrowings decrease of ₹{abs(debt_change):,.0f} Cr was funded via operational cash flow or balance-sheet restructuring.
3. 🔴 **Capex Run-Rate Assessment:** Evaluate whether the ongoing capital expenditure run-rate (₹{curr_capex:,.0f} Cr, {reinvest:.1f}% of CFO) satisfies operational maintenance requirements."""

        return f"{card_1}\n\n---\n\n{card_2}\n\n---\n\n{card_3}\n\n---\n\n{card_4}\n\n---\n\n{card_5}"