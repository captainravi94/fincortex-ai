import io
import requests
import pandas as pd
import numpy as np

def ingest_from_excel_or_csv(uploaded_file):
    try:
        fname = uploaded_file.name.lower()
        if fname.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            xl = pd.ExcelFile(uploaded_file)
            
            # Scan sheets to find the one containing financial statements
            target_sheet = xl.sheet_names[0]
            for s in xl.sheet_names:
                raw_s = pd.read_excel(xl, sheet_name=s, header=None)
                text_blob = raw_s.to_string().lower()
                if "sales" in text_blob or "revenue" in text_blob or "net profit" in text_blob:
                    target_sheet = s
                    break
            
            raw = pd.read_excel(xl, sheet_name=target_sheet, header=None)
            
            # Hunt for the exact row where financial line items begin
            header_row = 0
            for idx, row in raw.iterrows():
                row_str = " ".join([str(v) for v in row.values if pd.notna(v)]).lower()
                if any(k in row_str for k in ["sales", "revenue", "particulars", "mar 20", "mar 2024", "mar 2023"]):
                    header_row = idx
                    break
            
            df = pd.read_excel(xl, sheet_name=target_sheet, skiprows=header_row)

        # Drop empty rows and columns
        df = df.dropna(how="all").dropna(axis=1, how="all")
        if df.empty or len(df.columns) < 2:
            return None, "Spreadsheet contains insufficient tabular data.", None, None, "₹", "Cr", {}

        # First column is the metric line items
        first_col = df.columns[0]
        df = df.rename(columns={first_col: "metric"})
        df = df[df["metric"].notna()]
        df["metric"] = df["metric"].astype(str).str.strip()

        # Clean numeric data across all period columns
        period_cols = [c for c in df.columns if c != "metric"]
        for col in period_cols:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.replace("₹", "", regex=False)
                .str.replace("$", "", regex=False)
                .str.replace("(", "-", regex=False)
                .str.replace(")", "", regex=False)
                .str.replace("%", "", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        df = df.set_index("metric")
        df = df[~df.index.duplicated(keep="first")]

        comp_name = uploaded_file.name.rsplit(".", 1)[0].replace("_", " ").title()
        return df, f"Successfully parsed {len(df.columns)} financial periods for {comp_name}", comp_name, "Corporate / Industrial", "₹", "Cr", {}

    except Exception as e:
        return None, f"Parsing error: {str(e)}", None, None, "₹", "Cr", {}

def fetch_from_ir_link(url: str):
    try:
        if not url.startswith("http"):
            url = "https://" + url
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        tables = pd.read_html(io.StringIO(resp.text))
        if tables:
            best = max(tables, key=lambda t: t.shape[0] * t.shape[1])
            return best, f"Extracted table ({best.shape[0]} rows x {best.shape[1]} cols)."
        return None, "No HTML tables detected"
    except Exception as e:
        return None, str(e)