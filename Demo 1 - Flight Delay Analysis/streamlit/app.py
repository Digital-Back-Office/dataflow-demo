import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.queries import (
    get_flight_statistics_summary,
    get_airline_performance_stats,
    get_origin_airport_stats,
    get_airports,
)

st.set_page_config(
    page_title="Flight Delay Dashboard",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── cached loaders ────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_summary():
    return pd.DataFrame(get_flight_statistics_summary())

@st.cache_data(ttl=300)
def load_airline_perf():
    return pd.DataFrame(get_airline_performance_stats())

@st.cache_data(ttl=300)
def load_origin_stats():
    return pd.DataFrame(get_origin_airport_stats())

@st.cache_data(ttl=300)
def load_airports():
    return get_airports()

# ── load data ─────────────────────────────────────────────────────────────────
with st.spinner("Loading data…"):
    try:
        summary_df   = load_summary()
        airline_df   = load_airline_perf()
        origin_df    = load_origin_stats()
        airports_map = load_airports()
    except Exception as e:
        st.error("Could not load data. Make sure the pipeline has run and the database is reachable.")
        st.stop()

# ── derive headline numbers ───────────────────────────────────────────────────
total_flights   = int(summary_df["total_flights"].sum())
avg_dep_delay   = float(summary_df["avg_departure_delay"].mean())
avg_arr_delay   = float(summary_df["avg_arrival_delay"].mean())
on_time_pct     = float(airline_df["on_time_pct"].mean())
worst_airline   = airline_df.loc[airline_df["avg_departure_delay"].idxmax(), "airline"]
best_airline    = airline_df.loc[airline_df["avg_departure_delay"].idxmin(), "airline"]

# ── header ────────────────────────────────────────────────────────────────────
st.markdown(
    "<h1 style='margin-bottom:0'>✈️ US Flight Delay Dashboard</h1>"
    "<p style='color:#aaa;margin-top:4px'>Bureau of Transportation Statistics · live pipeline on Dataflow</p>",
    unsafe_allow_html=True,
)
st.divider()

# ── KPI row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Flights", f"{total_flights:,}")
k2.metric("Avg Departure Delay", f"{avg_dep_delay:.1f} min")
k3.metric("Avg Arrival Delay",   f"{avg_arr_delay:.1f} min")
k4.metric("On-Time Arrival Rate", f"{on_time_pct:.1f}%")
k5.metric("Most Delayed Airline", worst_airline)

st.divider()

# ── main charts ───────────────────────────────────────────────────────────────
st.subheader("Avg Departure Delay by Airline")
airline_sorted = airline_df.sort_values("avg_departure_delay", ascending=False)
fig_bar = px.bar(
    airline_sorted,
    x="airline",
    y="avg_departure_delay",
    color="avg_departure_delay",
    color_continuous_scale="Reds",
    labels={"airline": "Airline", "avg_departure_delay": "Avg Delay (min)"},
    template="plotly_dark",
)
fig_bar.update_layout(
    coloraxis_showscale=False,
    margin=dict(t=10, b=10),
    xaxis_tickangle=-30,
    height=380,
)
st.plotly_chart(fig_bar, use_container_width=True)

st.subheader("On-Time vs Delay — All Airlines")
fig_scatter = px.scatter(
    airline_df,
    x="avg_departure_delay",
    y="on_time_pct",
    text="airline",
    size="total_flights",
    color="avg_departure_delay",
    color_continuous_scale="RdYlGn_r",
    labels={
        "avg_departure_delay": "Avg Dep Delay (min)",
        "on_time_pct": "On-Time Arrival %",
        "total_flights": "Flights",
    },
    template="plotly_dark",
)
fig_scatter.update_traces(textposition="top center", textfont_size=10)
fig_scatter.update_layout(coloraxis_showscale=False, margin=dict(t=10, b=10), height=420)
st.plotly_chart(fig_scatter, use_container_width=True)

# ── top 5 delayed airports ────────────────────────────────────────────────────
st.subheader("Top 10 Most Delayed Origin Airports")
top_delayed = origin_df.sort_values("avg_departure_delay", ascending=False).head(10).copy()
top_delayed["airport_name"] = top_delayed["origin_airport"].map(
    lambda c: airports_map.get(c, {}).get("airport", c)
)
fig_airports = px.bar(
    top_delayed,
    x="avg_departure_delay",
    y="airport_name",
    orientation="h",
    color="avg_departure_delay",
    color_continuous_scale="Reds",
    labels={"avg_departure_delay": "Avg Dep Delay (min)", "airport_name": ""},
    template="plotly_dark",
)
fig_airports.update_layout(
    yaxis=dict(autorange="reversed"),
    coloraxis_showscale=False,
    margin=dict(t=10, b=10),
    height=350,
)
st.plotly_chart(fig_airports, use_container_width=True)

st.divider()

# ── page navigation teasers ───────────────────────────────────────────────────
st.subheader("Explore the Dashboard")
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown("**📈 Statistics**  \nDelay distributions, hourly scatter, and airline breakdowns.")
    st.page_link("pages/1_statistics.py", label="Go to Statistics →")
with c2:
    st.markdown("**⏱️ Delay Analysis**  \nDay-of-week trends and worst-performing airports.")
    st.page_link("pages/2_delays.py", label="Go to Delay Analysis →")
with c3:
    st.markdown("**🗺️ Airport Map**  \nUS map sized by traffic and coloured by delay severity.")
    st.page_link("pages/3_airport_maps.py", label="Go to Airport Map →")
with c4:
    st.markdown("**🛩️ Airline Performance**  \nOn-time rates and head-to-head delay comparison.")
    st.page_link("pages/4_airline_performance.py", label="Go to Airline Performance →")
