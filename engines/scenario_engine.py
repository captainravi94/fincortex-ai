import pandas as pd
import numpy as np
from typing import Dict, Any

def run_multi_driver_simulation(
    base_rev: float,
    base_ebitda: float,
    base_pat: float,
    base_debt: float,
    base_cfo: float,
    base_capex: float,
    rev_growth_pct: float,
    margin_shift_bps: float,
    cost_inflation_pct: float,
    rec_day_shift: int,
    rate_shock_bps: float,
    capex_growth_pct: float,
    tax_rate: float = 0.25
) -> Dict[str, float]:
    """
    Executes an institutional driver-based financial simulation.
    Supports revenue shocks from -50% to +300%.
    """
    # 1. Revenue
    sim_rev = max(base_rev * (1.0 + (rev_growth_pct / 100.0)), 0.0)

    # 2. Operating EBITDA: Base Margin adjusted by bps shift and direct cost inflation
    base_margin = (base_ebitda / base_rev) if base_rev > 0 else 0.15
    sim_margin = max(base_margin + (margin_shift_bps / 10000.0) - (cost_inflation_pct / 100.0), 0.01)
    sim_ebitda = sim_rev * sim_margin

    # 3. Financing Cost impact from Rate Shock
    interest_drag = base_debt * (rate_shock_bps / 10000.0)

    # 4. Net Profit (PAT) Adjustment
    ebitda_delta = sim_ebitda - base_ebitda
    pretax_delta = ebitda_delta - interest_drag
    tax_impact = pretax_delta * tax_rate
    sim_pat = base_pat + (pretax_delta - tax_impact)

    # 5. Working Capital Cash Drag from Receivable Extension
    wc_drag = (sim_rev / 365.0) * rec_day_shift

    # 6. Operating Cash Flow (CFO) and Free Cash Flow (FCF)
    sim_cfo = base_cfo + (sim_ebitda - base_ebitda) - wc_drag
    sim_capex = max(base_capex * (1.0 + (capex_growth_pct / 100.0)), 0.0)
    sim_fcf = sim_cfo - sim_capex

    return {
        "Revenue": sim_rev,
        "EBITDA": sim_ebitda,
        "EBITDA Margin (%)": sim_margin * 100.0,
        "Net Profit (PAT)": sim_pat,
        "PAT Margin (%)": (sim_pat / sim_rev * 100.0) if sim_rev > 0 else 0.0,
        "Operating CFO": sim_cfo,
        "Capex Reinvestment": sim_capex,
        "Free Cash Flow": sim_fcf
    }


def generate_scenario_matrix(
    base_rev: float,
    base_ebitda: float,
    base_pat: float,
    base_debt: float,
    base_cfo: float,
    base_capex: float,
    custom_drivers: Dict[str, Any]
) -> pd.DataFrame:
    """
    Generates side-by-side: Base Case, Custom Scenario, Best Case (+30% Rev, +200 bps margin),
    and Worst Case (-20% Rev, -300 bps margin, +15 days DSO, +150 bps rate shock).
    """
    # 1. Base Case
    base_case = run_multi_driver_simulation(
        base_rev, base_ebitda, base_pat, base_debt, base_cfo, base_capex,
        rev_growth_pct=0.0, margin_shift_bps=0.0, cost_inflation_pct=0.0,
        rec_day_shift=0, rate_shock_bps=0.0, capex_growth_pct=0.0
    )

    # 2. Custom Simulated Case
    custom_case = run_multi_driver_simulation(
        base_rev, base_ebitda, base_pat, base_debt, base_cfo, base_capex,
        rev_growth_pct=custom_drivers["rev_growth"],
        margin_shift_bps=custom_drivers["margin_shift_bps"],
        cost_inflation_pct=custom_drivers["cost_inflation"],
        rec_day_shift=custom_drivers["rec_days"],
        rate_shock_bps=custom_drivers["rate_shock_bps"],
        capex_growth_pct=custom_drivers["capex_growth"]
    )

    # 3. Best Case (Institutional Upside Model)
    best_case = run_multi_driver_simulation(
        base_rev, base_ebitda, base_pat, base_debt, base_cfo, base_capex,
        rev_growth_pct=max(custom_drivers["rev_growth"] * 1.5, 30.0),
        margin_shift_bps=200.0,
        cost_inflation_pct=0.0,
        rec_day_shift=-10,
        rate_shock_bps=-50.0,
        capex_growth_pct=10.0
    )

    # 4. Worst Case (Institutional Stress-Test Model)
    worst_case = run_multi_driver_simulation(
        base_rev, base_ebitda, base_pat, base_debt, base_cfo, base_capex,
        rev_growth_pct=-20.0,
        margin_shift_bps=-300.0,
        cost_inflation_pct=4.0,
        rec_day_shift=20,
        rate_shock_bps=150.0,
        capex_growth_pct=-15.0
    )

    table = {
        "Metric": [
            "Top-Line Gross Revenue",
            "Operating Profit (EBITDA)",
            "EBITDA Margin (%)",
            "Net Profit (PAT)",
            "PAT Margin (%)",
            "Operating Cash Flow (CFO)",
            "Capital Expenditure (Capex)",
            "Free Cash Flow (FCF)"
        ],
        "Worst Case (Downside)": [
            worst_case["Revenue"], worst_case["EBITDA"], worst_case["EBITDA Margin (%)"],
            worst_case["Net Profit (PAT)"], worst_case["PAT Margin (%)"],
            worst_case["Operating CFO"], worst_case["Capex Reinvestment"], worst_case["Free Cash Flow"]
        ],
        "Base Case (Audited)": [
            base_case["Revenue"], base_case["EBITDA"], base_case["EBITDA Margin (%)"],
            base_case["Net Profit (PAT)"], base_case["PAT Margin (%)"],
            base_case["Operating CFO"], base_case["Capex Reinvestment"], base_case["Free Cash Flow"]
        ],
        "Simulated Model": [
            custom_case["Revenue"], custom_case["EBITDA"], custom_case["EBITDA Margin (%)"],
            custom_case["Net Profit (PAT)"], custom_case["PAT Margin (%)"],
            custom_case["Operating CFO"], custom_case["Capex Reinvestment"], custom_case["Free Cash Flow"]
        ],
        "Best Case (Optimistic)": [
            best_case["Revenue"], best_case["EBITDA"], best_case["EBITDA Margin (%)"],
            best_case["Net Profit (PAT)"], best_case["PAT Margin (%)"],
            best_case["Operating CFO"], best_case["Capex Reinvestment"], best_case["Free Cash Flow"]
        ]
    }
    return pd.DataFrame(table)