import io
import pandas as pd
import numpy as np

def ingest_from_excel_or_csv(uploaded_file):
    try:
        fname = uploaded_file.name.lower()
        if fname.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            # header=None scans for actual header row to prevent IndexError: 1
            raw_df = pd.read_excel(uploaded_file, header=None)
            
            # Find the header row containing year/period patterns
            header_idx = 0
            for idx, row in raw_df.iterrows():
                row_str = " ".join([str(x) for x in row.values if pd.notna(x)]).lower()
                if any(yr in row_str for yr in ["202", "fy", "mar", "dec"]):
                    header_idx = idx
                    break
            
            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file, skiprows=header_idx)

        # Drop entirely empty rows and columns
        df = df.dropna(how="all").dropna(axis=1, how="all")
        
        # Ensure column 0 is recognized as Metric / Line Item
        first_col = df.columns[0]
        df = df.rename(columns={first_col: "metric"})
        df = df[df["metric"].notna()]
        df["metric"] = df["metric"].astype(str).str.strip()

        # Clean numeric cells
        for col in df.columns[1:]:
            df[col] = df[col].astype(str).str.replace(",", "").str.replace("₹", "").str.replace("$", "").str.strip()
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        df = df.set_index("metric")
        
        # Infer company name from filename
        comp_name = uploaded_file.name.rsplit(".", 1)[0].replace("_", " ").title()
        
        return df, f"Successfully loaded {comp_name}", comp_name, "Corporate / Industrial", "₹", "Cr", {}
    except Exception as e:
        return None, f"Parsing failure: {str(e)}", None, None, "₹", "Cr", {}