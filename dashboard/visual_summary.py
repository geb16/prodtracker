# visual_summary.py
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def render_performance_corner(metrics: dict, work_start="09:00", work_end="17:00"):
    """
    Renders a compact performance widget:
    1. Pie chart for productivity vs noise.
    2. Timeline for working hours vs actual productive events.

    metrics: dict containing 'signal', 'noise', optionally 'trend' with timestamps
    work_start/work_end: standard working hours in HH:MM format
    """

    signal = metrics.get("signal", 0)
    noise = metrics.get("noise", 0)
    total = signal + noise
    productivity = (signal / total * 100) if total > 0 else 0
    wasted = (noise / total * 100) if total > 0 else 0

    # --- Pie chart ---
    df_pie = pd.DataFrame({"Category": ["Productive", "Noise"], "Percentage": [productivity, wasted]})
    fig_pie = px.pie(
        df_pie,
        values="Percentage",
        names="Category",
        hole=0.5,
        color="Category",
        color_discrete_map={"Productive": "#00C853", "Noise": "#ff1744"},
        template="plotly_dark",
    )
    fig_pie.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        showlegend=True,
        height=250,
        width=250,
    )

    # --- Working hours timeline ---
    start_dt = datetime.combine(datetime.today(), datetime.strptime(work_start, "%H:%M").time())
    end_dt = datetime.combine(datetime.today(), datetime.strptime(work_end, "%H:%M").time())

    # Use trend if available, else simulate hourly distribution
    if metrics.get("trend"):
        trend_df = pd.DataFrame(metrics["trend"])
        trend_df["timestamp"] = pd.to_datetime(trend_df["timestamp"])
        trend_df = trend_df.set_index("timestamp").resample("30min").sum().reset_index()
        trend_df["Productive_pct"] = trend_df["signal"] / (trend_df["signal"] + trend_df["noise"]) * 100
    else:
        trend_df = pd.DataFrame(
            {
                "timestamp": pd.date_range(start=start_dt, end=end_dt, freq="30min"),
                "Productive_pct": productivity,
            }
        )

    # Timeline bar chart
    fig_timeline = go.Figure()
    fig_timeline.add_trace(
        go.Bar(
            x=trend_df["timestamp"],
            y=trend_df["Productive_pct"],
            name="Productive %",
            marker_color="#00C853",
        )
    )
    fig_timeline.update_layout(
        template="plotly_dark",
        height=150,
        margin=dict(t=0, b=0, l=0, r=0),
        xaxis_title="Time",
        yaxis_title="Productivity %",
        yaxis=dict(range=[0, 100]),
    )

    # --- Display in Streamlit ---
    st.markdown("### ⚡ Performance vs Working Hours")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.plotly_chart(fig_pie, width="stretch")
        st.markdown(f"**Signal:** {signal} | **Noise:** {noise} | **Productivity:** {productivity:.1f}%")
    with col2:
        st.plotly_chart(fig_timeline, width="stretch")
    st.divider()
