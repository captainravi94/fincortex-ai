import re
from typing import Optional, Any, Dict, List
from pydantic import BaseModel

class LineItemMetadata(BaseModel):
    raw_label: str
    canonical_name: str
    value: float
    unit: str = "Millions"
    page: int = 1
    statement: str = "PL"
    period: str = "FY26"

CORPORATE_SYNONYMS = {
    "revenue": ["revenue from operations", "total revenue", "net sales", "turnover", "total revenues, net of interest expense"],
    "ebitda": ["operating profit", "ebitda", "profit before depreciation, finance costs and tax", "operating income"],
    "pat": ["profit for the year", "net income", "net profit after tax", "pat", "net income applicable to common shareholders"],
    "total_borrowings": ["total borrowings", "long-term borrowings", "total debt", "short-term borrowings"],
    "cash_and_equivalents": ["cash and cash equivalents", "cash and bank balances", "cash and due from banks"],
    "total_equity": ["total equity", "shareholders' funds", "total stockholders' equity", "net worth"],
    "total_assets": ["total assets"],
    "total_liabilities": ["total liabilities", "total liabilities and equity"],
    "trade_receivables": ["trade receivables", "accounts receivable", "receivables"],
    "cfo": ["net cash flows from operating activities", "operating cash flow", "net cash provided by operating activities"],
    "capex": ["purchase of property, plant and equipment", "capital expenditure", "additions to property, plant and equipment"]
}

BANKING_SYNONYMS = {
    "revenue": ["total revenues, net of interest expense", "total revenues", "total net revenue", "net interest income plus non-interest revenue"],
    "ebitda": ["income before taxes", "operating profit", "pre-tax pre-provision operating profit", "income before income taxes"],
    "pat": ["net income", "net income applicable to common shareholders", "profit after tax"],
    "total_borrowings": ["total deposits", "deposits", "borrowed funds", "long-term debt"],
    "cash_and_equivalents": ["cash and due from banks", "cash and cash equivalents", "deposits with banks"],
    "total_equity": ["total stockholders' equity", "total equity", "common equity"],
    "total_assets": ["total assets"],
    "total_liabilities": ["total liabilities"],
    "trade_receivables": ["loans, net of allowance", "loans and leases", "total loans", "trade receivables"],
    "cfo": ["net cash provided by operating activities", "operating cash flow"],
    "capex": ["capital expenditures", "payments for property and equipment", "capex"]
}

def clean_numeric(val_str: Any) -> Optional[float]:
    if val_str is None:
        return None
    if isinstance(val_str, (int, float)):
        return float(val_str)
    
    cleaned = str(val_str).strip().replace(",", "").replace("$", "").replace("₹", "")
    if not cleaned or cleaned in ["-", "—", "N/A", "nil", "None"]:
        return 0.0

    is_negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        is_negative = True
        cleaned = cleaned[1:-1]
    elif cleaned.startswith("-"):
        is_negative = True
        cleaned = cleaned[1:]

    try:
        val = float(cleaned)
        return -val if is_negative else val
    except ValueError:
        return None

def match_canonical(raw_label: str, is_bank: bool = False) -> Optional[str]:
    cleaned = re.sub(r"[^a-zA-Z\s]", "", str(raw_label)).lower().strip()
    synonym_map = BANKING_SYNONYMS if is_bank else CORPORATE_SYNONYMS
    
    for canon_key, syns in synonym_map.items():
        for syn in syns:
            if syn in cleaned:
                return canon_key
    return None