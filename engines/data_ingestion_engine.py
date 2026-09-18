import io
import pandas as pd
import requests
from typing import Tuple, Optional, Dict, Any

def parse_screener_datasheet(xls: pd.ExcelFile) -> Tuple[Optional[pd.DataFrame], str, str, str, str, Dict[str, Any]]:
    ds = pd.read_excel(xls, sheet_name="Data Sheet")

    company_name = "Corporate Entity"
    if "COMPANY NAME" in ds.columns:
        company_name = str(ds.columns[1]).strip()
    elif "COMPANY NAME" in str(ds.iloc[0, 0]):
        company_name = str(ds.iloc[0, 1]).strip()

    sections = {}
    for r in range(len(ds)):
        val = str(ds.iloc[r, 0]).strip().upper()
        if "PROFIT & LOSS" in val and "PL" not in sections:
            sections["PL"] = r
        elif "QUARTERS" in val and "QUARTERS" not in sections:
            sections["QUARTERS"] = r
        elif "BALANCE SHEET" in val and "BS" not in sections:
            sections["BS"] = r
        elif val.startswith("CASH FLOW") and "CF" not in sections:
            sections["CF"] = r

    if "PL" not in sections or "BS" not in sections or "CF" not in sections:
        return None, "Missing financial sections", "Corporate", "₹", "Cr", {}

    date_row = ds.iloc[sections["PL"] + 1]
    annual_cols = {}
    for c in range(1, len(date_row)):
        d_val = date_row[c]
        if pd.notna(d_val):
            try:
                dt = pd.to_datetime(d_val)
                annual_cols[c] = f"FY{dt.strftime('%y')}"
            except Exception:
                annual_cols[c] = str(d_val)[:10]

    canonical_keys = [
        "revenue", "ebitda", "pat", "total_borrowings", 
        "cash_and_equivalents", "equity_share_capital", "reserves",
        "total_equity", "total_assets", "total_liabilities",
        "trade_receivables", "cfo", "capex", "other_income"
    ]
    extracted = {k: {p: 0.0 for p in annual_cols.values()} for k in canonical_keys}

    # 1. P&L Section
    pl_start = sections["PL"]
    pl_end = sections.get("QUARTERS", sections["BS"])
    pbt_row, depr_row, int_row, oinc_row = None, None, None, None

    for r in range(pl_start, pl_end):
        lbl = str(ds.iloc[r, 0]).strip().lower()
        if lbl == "sales":
            for c, p in annual_cols.items():
                extracted["revenue"][p] = float(ds.iloc[r, c]) if pd.notna(ds.iloc[r, c]) else 0.0
        elif lbl == "net profit":
            for c, p in annual_cols.items():
                extracted["pat"][p] = float(ds.iloc[r, c]) if pd.notna(ds.iloc[r, c]) else 0.0
        elif lbl == "profit before tax":
            pbt_row = r
        elif lbl == "depreciation":
            depr_row = r
        elif lbl == "interest":
            int_row = r
        elif lbl == "other income":
            oinc_row = r

    for c, p in annual_cols.items():
        pbt_val = float(ds.iloc[pbt_row, c]) if pbt_row and pd.notna(ds.iloc[pbt_row, c]) else 0.0
        dep_val = float(ds.iloc[depr_row, c]) if depr_row and pd.notna(ds.iloc[depr_row, c]) else 0.0
        int_val = float(ds.iloc[int_row, c]) if int_row and pd.notna(ds.iloc[int_row, c]) else 0.0
        oinc_val = float(ds.iloc[oinc_row, c]) if oinc_row and pd.notna(ds.iloc[oinc_row, c]) else 0.0
        extracted["ebitda"][p] = round(pbt_val + dep_val + int_val - oinc_val, 2)
        extracted["other_income"][p] = oinc_val

    # 2. Balance Sheet Section
    bs_start = sections["BS"]
    bs_end = sections["CF"]
    eq_row, res_row = None, None

    for r in range(bs_start, bs_end):
        lbl = str(ds.iloc[r, 0]).strip().lower()
        if lbl == "equity share capital":
            eq_row = r
        elif lbl == "reserves":
            res_row = r
        elif lbl == "borrowings":
            for c, p in annual_cols.items():
                extracted["total_borrowings"][p] = float(ds.iloc[r, c]) if pd.notna(ds.iloc[r, c]) else 0.0
        elif lbl == "receivables":
            for c, p in annual_cols.items():
                extracted["trade_receivables"][p] = float(ds.iloc[r, c]) if pd.notna(ds.iloc[r, c]) else 0.0
        elif lbl == "cash & bank":
            for c, p in annual_cols.items():
                extracted["cash_and_equivalents"][p] = float(ds.iloc[r, c]) if pd.notna(ds.iloc[r, c]) else 0.0
        elif lbl == "total" and extracted["total_assets"][list(annual_cols.values())[0]] == 0.0:
            for c, p in annual_cols.items():
                t_val = float(ds.iloc[r, c]) if pd.notna(ds.iloc[r, c]) else 0.0
                extracted["total_assets"][p] = t_val
                extracted["total_liabilities"][p] = t_val

    for c, p in annual_cols.items():
        eq_cap = float(ds.iloc[eq_row, c]) if eq_row and pd.notna(ds.iloc[eq_row, c]) else 0.0
        res = float(ds.iloc[res_row, c]) if res_row and pd.notna(ds.iloc[res_row, c]) else 0.0
        extracted["equity_share_capital"][p] = eq_cap
        extracted["reserves"][p] = res
        extracted["total_equity"][p] = round(eq_cap + res, 2)

    # 3. Cash Flow Section
    cf_start = sections["CF"]
    cff_dict = {}
    net_cf_dict = {}
    for r in range(cf_start, len(ds)):
        lbl = str(ds.iloc[r, 0]).strip().lower()
        if "cash from operating" in lbl:
            for c, p in annual_cols.items():
                extracted["cfo"][p] = float(ds.iloc[r, c]) if pd.notna(ds.iloc[r, c]) else 0.0
        elif "cash from investing" in lbl:
            for c, p in annual_cols.items():
                extracted["capex"][p] = abs(float(ds.iloc[r, c])) if pd.notna(ds.iloc[r, c]) else 0.0
        elif "cash from financing" in lbl:
            for c, p in annual_cols.items():
                cff_dict[p] = float(ds.iloc[r, c]) if pd.notna(ds.iloc[r, c]) else 0.0
        elif lbl == "net cash flow":
            for c, p in annual_cols.items():
                net_cf_dict[p] = float(ds.iloc[r, c]) if pd.notna(ds.iloc[r, c]) else 0.0

    df_out = pd.DataFrame(extracted).T.fillna(0.0)
    if df_out.shape[1] > 5:
        df_out = df_out.iloc[:, -5:]

    latest_p = list(annual_cols.values())[-1]
    extra_meta = {
        "latest_other_income": extracted["other_income"][latest_p],
        "reserves": extracted["reserves"][latest_p],
        "cff": cff_dict.get(latest_p, 0.0),
        "net_cash_flow": net_cf_dict.get(latest_p, 0.0),
        "unit_consistent": True
    }

    return df_out, company_name, "Corporate / Industrial", "₹", "Cr", extra_meta


def ingest_from_excel_or_csv(file_buffer) -> Tuple[Optional[pd.DataFrame], str, Optional[str], Optional[str], str, str, Dict[str, Any]]:
    try:
        if file_buffer.name.endswith(".csv"):
            df = pd.read_csv(file_buffer)
            if "metric" in df.columns:
                df = df.set_index("metric")
            return df.apply(pd.to_numeric, errors="coerce").fillna(0.0), "CSV Ingested.", None, None, "₹", "Cr", {}

        xls = pd.ExcelFile(file_buffer)
        if "Data Sheet" in xls.sheet_names:
            df, comp, tax, cur, scale, extra = parse_screener_datasheet(xls)
            return df, f"Successfully parsed audited data for {comp}", comp, tax, cur, scale, extra

        df = pd.read_excel(file_buffer)
        if "metric" in df.columns:
            df = df.set_index("metric")
        return df.apply(pd.to_numeric, errors="coerce").fillna(0.0), "Excel Ingested.", None, None, "₹", "Cr", {}
    except Exception as e:
        return None, f"Error: {str(e)}", None, None, "₹", "Cr", {}


def fetch_from_ir_link(url: str) -> Tuple[Optional[pd.DataFrame], str]:
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code != 200:
            return None, f"Failed with HTTP Status {res.status_code}"
        tables = pd.read_html(io.StringIO(res.text))
        if tables:
            largest = max(tables, key=lambda t: t.shape[0] * t.shape[1])
            return largest, f"Extracted table of shape {largest.shape} from URL."
        return None, "No structured HTML tables found."
    except Exception as e:
        return None, f"URL parse error: {str(e)}"