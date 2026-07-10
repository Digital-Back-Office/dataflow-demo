import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.queries import (
    get_flight_statistics_summary,
    get_delay_distribution,
    get_delay_vs_hour,
    get_airlines,
)

st.set_page_config(page_title="Statistics · Flight Delays", page_icon="📈", layout="wide")
st.title("📈 Flight Statistics")
st.caption("Delay distributions, hourly patterns, and airline-level breakdown.")

# ── cached loaders ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_summary():
    return pd.DataFrame(get_flight_statistics_summary())

@st.cache_data(ttl=300)
def load_delay_bins():
    return pd.DataFrame(get_delay_distribution())

@st.cache_data(ttl=300)
def load_hourly():
    return pd.DataFrame(get_delay_vs_hour())

@st.cache_data(ttl=300)
def load_airlines():
    return get_airlines()

with st.spinner("Loading…"):
    try:
        airlines_map  = load_airlines()
        summary_df    = load_summary()
        delay_bins    = load_delay_bins()
        hourly_df     = load_hourly()
    except Exception:
        st.error("Could not load data. Check that the pipeline has run.")
        st.stop()

summary_df["airline_full"] = summary_df["airline"].map(airlines_map)
hourly_df["airline_full"]  = hourly_df["airline"].map(airlines_map)

# ── sidebar filters ────────────────────────────────────────────────────────────
st.sidebar.header("Filters")
available_airlines = sorted(summary_df["airline_full"].dropna().unique())
selected = st.sidebar.multiselect("Airline", available_airlines, placeholder="All airlines")

if selected:
    summary_df = summary_df[summary_df["airline_full"].isin(selected)]
    hourly_df  = hourly_df[hourly_df["airline_full"].isin(selected)]

# ── KPIs ───────────────────────────────────────────────────────────────────────
k1, k2, k3 = st.columns(3)
k1.metric("Total Flights",         f"{summary_df['total_flights'].sum():,}")
k2.metric("Avg Departure Delay",   f"{summary_df['avg_departure_delay'].mean():.1f} min")
k3.metric("Avg Arrival Delay",     f"{summary_df['avg_arrival_delay'].mean():.1f} min")

st.divider()

# ── delay distribution histogram ──────────────────────────────────────────────
st.subheader("Departure Delay Distribution")
fig_hist = px.bar(
    delay_bins.sort_values("bin_start"),
    x="bin_start",
    y="count",
    labels={"bin_start": "Departure Delay (min)", "count": "Number of Flights"},
    color="count",
    color_continuous_scale="Blues",
    template="plotly_dark",
)
fig_hist.update_layout(coloraxis_showscale=False, bargap=0.05, margin=dict(t=10, b=10))
st.plotly_chart(fig_hist, use_container_width=True)

# ── hourly scatter ────────────────────────────────────────────────────────────
st.subheader("Avg Delay by Hour of Day")
fig_hour = px.scatter(
    hourly_df,
    x="hour",
    y="avg_departure_delay",
    color="airline_full",
    symbol="airline_full",
    size_max=10,
    opacity=0.7,
    labels={
        "hour": "Scheduled Departure Hour",
        "avg_departure_delay": "Avg Dep Delay (min)",
        "airline_full": "Airline",
    },
    template="plotly_dark",
)
fig_hour.update_layout(margin=dict(t=10, b=10), height=420)
st.plotly_chart(fig_hour, use_container_width=True)

# ── departure vs arrival by airline ───────────────────────────────────────────
st.subheader("Departure vs Arrival Delay by Airline")
melted = summary_df.melt(
    id_vars="airline_full",
    value_vars=["avg_departure_delay", "avg_arrival_delay"],
    var_name="delay_type",
    value_name="delay_minutes",
)
melted["delay_type"] = melted["delay_type"].map({
    "avg_departure_delay": "Departure",
    "avg_arrival_delay":   "Arrival",
})
fig_airline = px.bar(
    melted,
    x="airline_full",
    y="delay_minutes",
    color="delay_type",
    barmode="group",
    labels={
        "airline_full": "Airline",
        "delay_minutes": "Avg Delay (min)",
        "delay_type": "Type",
    },
    color_discrete_map={"Departure": "#EF553B", "Arrival": "#636EFA"},
    template="plotly_dark",
)
fig_airline.update_layout(xaxis_tickangle=-30, margin=dict(t=10, b=10), height=400)
st.plotly_chart(fig_airline, use_container_width=True)
