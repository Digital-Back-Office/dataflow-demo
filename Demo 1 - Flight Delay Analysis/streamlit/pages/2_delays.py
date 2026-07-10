import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.queries import (
    get_hourly_avg_delay,
    get_top10_origin_airports_by_delay,
    get_weekday_avg_delay,
    get_airports,
)

st.set_page_config(page_title="Delay Analysis · Flight Delays", page_icon="⏱️", layout="wide")
st.title("⏱️ Delay Analysis")
st.caption("When are delays worst? Which airports and days should you avoid?")

# ── cached loaders ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_hourly():
    return pd.DataFrame(get_hourly_avg_delay())

@st.cache_data(ttl=300)
def load_top10():
    return pd.DataFrame(get_top10_origin_airports_by_delay())

@st.cache_data(ttl=300)
def load_dow():
    return pd.DataFrame(get_weekday_avg_delay())

@st.cache_data(ttl=300)
def load_airports():
    return get_airports()

with st.spinner("Loading…"):
    try:
        hourly_df    = load_hourly()
        top10_df     = load_top10()
        dow_df       = load_dow()
        airports_map = load_airports()
    except Exception:
        st.error("Could not load data. Check that the pipeline has run.")
        st.stop()

# resolve airport names
top10_df["airport_name"] = top10_df["origin_airport"].map(
    lambda c: airports_map.get(c, {}).get("airport", c)
)

# ── hourly heatmap (1-row colour strip) + line ───────────────────────────────
st.subheader("Average Departure Delay by Hour of Day")

fig_hour = px.bar(
    hourly_df.sort_values("hour"),
    x="hour",
    y="avg_departure_delay",
    color="avg_departure_delay",
    color_continuous_scale="RdYlGn_r",
    labels={"hour": "Hour (24h)", "avg_departure_delay": "Avg Dep Delay (min)"},
    template="plotly_dark",
)
fig_hour.update_layout(
    coloraxis_showscale=False,
    bargap=0.1,
    height=300,
    margin=dict(t=10, b=10),
)
st.plotly_chart(fig_hour, use_container_width=True)

st.caption(
    "Delays accumulate throughout the day — flights after 18:00 carry compounding lateness "
    "from earlier in the schedule."
)

st.divider()

# ── top 10 most delayed airports ─────────────────────────────────────────────
st.subheader("Top 10 Most Delayed Origin Airports")
fig_airports = px.bar(
    top10_df.sort_values("avg_departure_delay"),
    x="avg_departure_delay",
    y="airport_name",
    orientation="h",
    color="avg_departure_delay",
    color_continuous_scale="Reds",
    labels={"avg_departure_delay": "Avg Dep Delay (min)", "airport_name": ""},
    template="plotly_dark",
)
fig_airports.update_layout(coloraxis_showscale=False, height=420, margin=dict(t=10, b=10))
st.plotly_chart(fig_airports, use_container_width=True)

# ── day-of-week ───────────────────────────────────────────────────────────────
st.subheader("Average Delay by Day of the Week")
dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
dow_df["day_of_week"] = pd.Categorical(dow_df["day_of_week"], categories=dow_order, ordered=True)
dow_df = dow_df.sort_values("day_of_week")

fig_dow = go.Figure()
fig_dow.add_trace(go.Scatter(
    x=dow_df["day_of_week"],
    y=dow_df["avg_departure_delay"],
    name="Departure",
    mode="lines+markers",
    line=dict(color="#EF553B", width=2),
    marker=dict(size=8),
))
fig_dow.add_trace(go.Scatter(
    x=dow_df["day_of_week"],
    y=dow_df["avg_arrival_delay"],
    name="Arrival",
    mode="lines+markers",
    line=dict(color="#636EFA", width=2),
    marker=dict(size=8),
))
fig_dow.update_layout(
    template="plotly_dark",
    yaxis_title="Avg Delay (min)",
    xaxis_title="",
    legend_title="Delay Type",
    height=420,
    margin=dict(t=10, b=10),
)
st.plotly_chart(fig_dow, use_container_width=True)

# ── insight callout ───────────────────────────────────────────────────────────
st.divider()
worst_day  = dow_df.loc[dow_df["avg_departure_delay"].idxmax(), "day_of_week"]
best_day   = dow_df.loc[dow_df["avg_departure_delay"].idxmin(), "day_of_week"]
worst_port = top10_df.loc[top10_df["avg_departure_delay"].idxmax(), "airport_name"]

col1, col2, col3 = st.columns(3)
col1.metric("Worst day to fly", str(worst_day))
col2.metric("Best day to fly",  str(best_day))
col3.metric("Most delayed airport", worst_port)
