import plotly.graph_objects as go
import pandas as pd
import numpy as np

def _safe_get_series(df: pd.DataFrame, target_key: str) -> pd.Series:
    """
    Safely retrieves a row series from df_metrics without crashing if
    the row name doesn't match 'revenue' exactly.
    """
    if df is None or df.empty:
        return pd.Series(dtype=float)

    # 1. Exact match
    if target_key in df.index:
        return pd.to_numeric(df.loc[target_key], errors="coerce").fillna(0.0)

    # 2. Case-insensitive exact match
    norm_map = {str(k).strip().lower(): k for k in df.index}
    if target_key.lower() in norm_map:
        return pd.to_numeric(df.loc[norm_map[target_key.lower()]], errors="coerce").fillna(0.0)

    # 3. Fuzzy search for reporting aliases
    aliases = {
        "revenue": ["sales", "revenue from operations", "revenue", "turnover", "total income", "gross sales"],
        "ebitda": ["operating profit", "ebitda", "pbit", "operating margin"],
        "pat": ["net profit", "profit after tax", "profit for the period", "loss for the period", "net loss", "pat"],
        "cfo": ["cash from operating", "cash flow from operating", "operating activities", "cfo"],
        "capex": ["capital expenditure", "purchase of fixed assets", "purchase of property", "fixed assets purchased", "capex"],
        "total_borrowings": ["borrowings", "total debt", "debt", "loans", "liabilities"],
        "total_equity": ["equity", "net worth", "share capital", "shareholders fund", "reserves"]
    }

    lookup = aliases.get(target_key.lower(), [target_key.lower()])
    for row in df.index:
        clean = str(row).lower()
        if any(term in clean for term in lookup):
            return pd.to_numeric(df.loc[row], errors="coerce").fillna(0.0)

    # Fallback: empty series with matching columns
    return pd.Series(0.0, index=df.columns)


def build_growth_trajectory_chart(df_metrics: pd.DataFrame):
    fig = go.Figure()
    if df_metrics is None or df_metrics.empty:
        fig.update_layout(title="No Financial Data Available")
        return fig

    periods = [str(c) for c in df_metrics.columns if str(c).lower() not in ["metric", "category", "line_item"]]
    rev_series = _safe_get_series(df_metrics, "revenue")
    ebitda_series = _safe_get_series(df_metrics, "ebitda")
    pat_series = _safe_get_series(df_metrics, "pat")

    fig.add_trace(go.Bar(
        x=periods,
        y=[float(rev_series.get(p, 0.0)) for p in periods],
        name="Gross Revenue",
        marker_color="#1E3A8A"
    ))
    fig.add_trace(go.Scatter(
        x=periods,
        y=[float(ebitda_series.get(p, 0.0)) for p in periods],
        name="EBITDA",
        mode="lines+markers",
        line=dict(color="#F59E0B", width=3)
    ))
    fig.add_trace(go.Scatter(
        x=periods,
        y=[float(pat_series.get(p, 0.0)) for p in periods],
        name="Reported PAT",
        mode="lines+markers",
        line=dict(color="#10B981", width=2, dash="dot")
    ))

    fig.update_layout(
        title="Top-Line & Operating Earnings Trajectory",
        barmode="group",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white"
    )
    return fig


def build_margin_trend_chart(clean_num_ratios: pd.DataFrame):
    fig = go.Figure()
    if clean_num_ratios is None or clean_num_ratios.empty:
        fig.update_layout(title="No Ratio Data Available")
        return fig

    periods = [str(c) for c in clean_num_ratios.columns if str(c).lower() not in ["metric", "category", "line_item"]]

    for row_name in clean_num_ratios.index:
        clean_name = str(row_name).lower()
        if "margin" in clean_name:
            series = pd.to_numeric(clean_num_ratios.loc[row_name], errors="coerce").fillna(0.0)
            fig.add_trace(go.Scatter(
                x=periods,
                y=[float(series.get(p, 0.0)) for p in periods],
                name=str(row_name),
                mode="lines+markers"
            ))

    fig.update_layout(
        title="Margin Trends (%)",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white"
    )
    return fig


def build_cash_waterfall(df_metrics: pd.DataFrame, target_period: str):
    fig = go.Figure()
    if df_metrics is None or df_metrics.empty:
        fig.update_layout(title="No Cash Flow Data Available")
        return fig

    ebitda = float(_safe_get_series(df_metrics, "ebitda").get(target_period, 0.0))
    cfo = float(_safe_get_series(df_metrics, "cfo").get(target_period, 0.0))
    capex = float(_safe_get_series(df_metrics, "capex").get(target_period, 0.0))
    fcf = cfo - capex
    wc_movement = cfo - ebitda

    fig.add_trace(go.Waterfall(
        orientation="v",
        measure=["absolute", "relative", "total", "relative", "total"],
        x=["EBITDA", "WC & Tax Drift", "Operating CFO", "Reinvestment Capex", "Free Cash Flow"],
        textposition="outside",
        y=[ebitda, wc_movement, 0, -capex, 0],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        decreasing={"marker": {"color": "#EF4444"}},
        increasing={"marker": {"color": "#10B981"}},
        totals={"marker": {"color": "#3B82F6"}}
    ))

    fig.update_layout(
        title=f"Cash Conversion Walkway ({target_period})",
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=20),
        template="plotly_white"
    )
    return fig