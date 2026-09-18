import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

def build_growth_trajectory_chart(df_metrics: pd.DataFrame) -> go.Figure:
    periods = df_metrics.columns.tolist()
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=periods,
        y=df_metrics.loc["revenue"],
        name="Revenue (₹ Cr)",
        marker_color="#1E3A8A"
    ))
    
    fig.add_trace(go.Scatter(
        x=periods,
        y=df_metrics.loc["ebitda"],
        name="EBITDA (₹ Cr)",
        mode="lines+markers",
        line=dict(color="#0D9488", width=3),
        marker=dict(size=8)
    ))

    fig.update_layout(
        title="Revenue & Operating Profit (EBITDA) Multi-Year Trend",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def build_margin_trend_chart(df_ratios: pd.DataFrame) -> go.Figure:
    periods = df_ratios.columns.tolist()
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=periods,
        y=df_ratios.loc["EBITDA Margin (%)"],
        name="EBITDA Margin (%)",
        line=dict(color="#2563EB", width=3)
    ))
    
    fig.add_trace(go.Scatter(
        x=periods,
        y=df_ratios.loc["PAT Margin (%)"],
        name="PAT Margin (%)",
        line=dict(color="#10B981", width=3, dash="dot")
    ))

    fig.update_layout(
        title="Margin Trajectory (EBITDA % vs. PAT %)",
        yaxis_title="Margin (%)",
        template="plotly_white",
        hovermode="x unified"
    )
    return fig

def build_cash_waterfall(df_metrics: pd.DataFrame, period: str) -> go.Figure:
    """Waterfall chart showing PAT to FCF reconciliation."""
    pat = df_metrics.loc["pat", period]
    cfo = df_metrics.loc["cfo", period]
    capex = df_metrics.loc["capex", period]
    fcf = cfo - capex
    wc_delta = cfo - pat  # Simplified proxy for working capital & non-cash adjustments

    fig = go.Figure(go.Waterfall(
        name="Cash Trajectory",
        orientation="v",
        measure=["relative", "relative", "total", "relative", "total"],
        x=["Reported PAT", "Working Capital / Non-cash", "Operating CF (CFO)", "Capex Reinvestment", "Free Cash Flow (FCF)"],
        textposition="outside",
        text=[f"₹{pat:,.0f}", f"₹{wc_delta:,.0f}", f"₹{cfo:,.0f}", f"-₹{capex:,.0f}", f"₹{fcf:,.0f}"],
        y=[pat, wc_delta, cfo, -capex, fcf],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
    ))

    fig.update_layout(
        title=f"Cash Flow Conversion Waterfall ({period})",
        template="plotly_white",
        showlegend=False
    )
    return fig