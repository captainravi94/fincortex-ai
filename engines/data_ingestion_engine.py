import io
import re
import requests
import pandas as pd
import numpy as np

def ingest_from_excel_or_csv(uploaded_file):
    """
    Robust spreadsheet ingestion supporting Excel (.xlsx, .xls) and CSV files.
    Auto-detects reporting header rows, normalizes line-item metric names,
    cleans formatted currency strings, and extracts financial spreads.
    """
    try:
        fname = uploaded_file.name.lower()
        if fname.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            # First pass: read without header to locate the actual period/year row
            raw_df = pd.read_excel(uploaded_file, header=None)
            
            header_idx = 0
            for idx, row in raw_df.iterrows():
                row_str = " ".join([str(x) for x in row.values if pd.notna(x)]).lower()
                if any(yr in row_str for yr in ["202", "fy", "mar", "dec", "sep", "jun", "period"]):
                    header_idx = idx
                    break
            
            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file, skiprows=header_idx)

        # Drop entirely empty rows and empty columns
        df = df.dropna(how="all").dropna(axis=1, how="all")
        
        if df.empty or len(df.columns) < 2:
            return None, "Spreadsheet contains insufficient tabular data.", None, None, "₹", "Cr", {}

        # First column is always metric / line item
        first_col = df.columns[0]
        df = df.rename(columns={first_col: "metric"})
        df = df[df["metric"].notna()]
        df["metric"] = df["metric"].astype(str).str.strip()

        # Clean numeric cells across period columns
        for col in df.columns[1:]:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.replace("₹", "", regex=False)
                .str.replace("$", "", regex=False)
                .str.replace("(", "-", regex=False)
                .str.replace(")", "", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        df = df.set_index("metric")
        
        # Infer company name and classification
        comp_name = uploaded_file.name.rsplit(".", 1)[0].replace("_", " ").title()
        taxonomy = "Banking / Financial Institution" if any(w in comp_name.lower() for w in ["bank", "citi", "hdfc", "icici", "sbi"]) else "Corporate / Industrial"
        currency = "$" if any(w in comp_name.lower() for w in ["inc", "corp", "apple", "tesla", "citi"]) else "₹"
        scale = "M" if currency == "$" else "Cr"

        return df, f"Successfully loaded financial spread for {comp_name}", comp_name, taxonomy, currency, scale, {"source": "Spreadsheet Ingestion"}
    except Exception as e:
        return None, f"Parsing failure: {str(e)}", None, None, "₹", "Cr", {}


def fetch_from_ir_link(url: str):
    """
    Extracts HTML tabular financial disclosures from Investor Relations web pages.
    """
    try:
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return None, f"HTTP request failed with status code {resp.status_code}"

        tables = pd.read_html(io.StringIO(resp.text))
        if not tables:
            return None, "No HTML tables detected at the provided IR URL."

        # Return the largest detected financial table
        best_tbl = max(tables, key=lambda t: t.shape[0] * t.shape[1])
        return best_tbl, f"Found {len(tables)} tables. Extracted primary table ({best_tbl.shape[0]} rows x {best_tbl.shape[1]} cols)."
    except Exception as e:
        return None, f"Failed to fetch IR tables: {str(e)}"