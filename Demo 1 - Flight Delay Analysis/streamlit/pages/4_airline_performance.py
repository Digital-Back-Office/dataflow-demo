import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.queries import get_airlines, get_airline_performance_stats

st.set_page_config(page_title="Airline Performance · Flight Delays", page_icon="🛩️", layout="wide")
st.title("🛩️ Airline Performance")
st.caption("On-time rates, delay averages, and volume comparison across all carriers.")

# ── cached loaders ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_perf():
    return pd.DataFrame(get_airline_performance_stats())

@st.cache_data(ttl=300)
def load_airlines():
    return get_airlines()

with st.spinner("Loading…"):
    try:
        stats_df    = load_perf()
        airlines_map = load_airlines()
    except Exception:
        st.error("Could not load data. Check that the pipeline has run.")
        st.stop()

stats_df["airline_full"] = stats_df["airline"].map(airlines_map).fillna(stats_df["airline"])

# ── sidebar filters ────────────────────────────────────────────────────────────
st.sidebar.header("Filters")
min_flights = st.sidebar.slider(
    "Min flights (filter out small carriers)", 0,
    int(stats_df["total_flights"].max()), 0,
)
stats_df = stats_df[stats_df["total_flights"] >= min_flights]

# ── KPIs ───────────────────────────────────────────────────────────────────────
best_ontime  = stats_df.loc[stats_df["on_time_pct"].idxmax()]
worst_delay  = stats_df.loc[stats_df["avg_departure_delay"].idxmax()]
best_delay   = stats_df.loc[stats_df["avg_departure_delay"].idxmin()]

k1, k2, k3, k4 = st.columns(4)
k1.metric("Airlines tracked",      len(stats_df))
k2.metric("Best on-time carrier",  best_ontime["airline_full"], f"{best_ontime['on_time_pct']:.1f}% on time")
k3.metric("Most punctual (delay)", best_delay["airline_full"],  f"{best_delay['avg_departure_delay']:.1f} min avg")
k4.metric("Most delayed carrier",  worst_delay["airline_full"], f"{worst_delay['avg_departure_delay']:.1f} min avg")

st.divider()

# ── main comparison chart ─────────────────────────────────────────────────────
st.subheader("Departure vs Arrival Delay — All Airlines")

melted = stats_df.melt(
    id_vars="airline_full",
    value_vars=["avg_departure_delay", "avg_arrival_delay"],
    var_name="delay_type",
    value_name="delay_minutes",
)
melted["delay_type"] = melted["delay_type"].map({
    "avg_departure_delay": "Departure",
    "avg_arrival_delay":   "Arrival",
})

fig_bar = px.bar(
    melted,
    x="airline_full",
    y="delay_minutes",
    color="delay_type",
    barmode="group",
    color_discrete_map={"Departure": "#EF553B", "Arrival": "#636EFA"},
    labels={"airline_full": "Airline", "delay_minutes": "Avg Delay (min)", "delay_type": "Type"},
    template="plotly_dark",
)
sorted_airlines = stats_df.sort_values("avg_departure_delay", ascending=False)["airline_full"].tolist()
fig_bar.update_layout(
    xaxis=dict(categoryorder="array", categoryarray=sorted_airlines, tickangle=-30),
    height=380,
    margin=dict(t=10, b=10),
    legend_title="Delay Type",
)
st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ── flights per airline ───────────────────────────────────────────────────────
st.subheader("Flights per Airline")
fig_vol = px.bar(
    stats_df.sort_values("total_flights", ascending=True),
    x="total_flights",
    y="airline_full",
    orientation="h",
    color="total_flights",
    color_continuous_scale="Blues",
    labels={"total_flights": "Total Flights", "airline_full": ""},
    template="plotly_dark",
)
fig_vol.update_layout(coloraxis_showscale=False, height=420, margin=dict(t=10, b=10))
st.plotly_chart(fig_vol, use_container_width=True)

# ── on-time rate ──────────────────────────────────────────────────────────────
st.subheader("On-Time Arrival Rate (%)")
fig_ontime = px.bar(
    stats_df.sort_values("on_time_pct", ascending=True),
    x="on_time_pct",
    y="airline_full",
    orientation="h",
    color="on_time_pct",
    color_continuous_scale="RdYlGn",
    labels={"on_time_pct": "On-Time Arrival %", "airline_full": ""},
    template="plotly_dark",
)
fig_ontime.update_layout(coloraxis_showscale=False, height=420, margin=dict(t=10, b=10))
st.plotly_chart(fig_ontime, use_container_width=True)

# ── quadrant: delay vs on-time ────────────────────────────────────────────────
st.divider()
st.subheader("Delay vs On-Time Rate — Performance Quadrant")
st.caption("Bottom-right = worst carriers. Top-left = best carriers.")

fig_quad = px.scatter(
    stats_df,
    x="avg_departure_delay",
    y="on_time_pct",
    text="airline_full",
    size="total_flights",
    color="avg_departure_delay",
    color_continuous_scale="RdYlGn_r",
    labels={
        "avg_departure_delay": "Avg Departure Delay (min)",
        "on_time_pct": "On-Time Arrival %",
        "total_flights": "Total Flights",
    },
    template="plotly_dark",
)
fig_quad.update_traces(textposition="top center", textfont_size=9)
fig_quad.update_layout(coloraxis_showscale=False, height=450, margin=dict(t=10, b=10))
# median reference lines
med_delay  = stats_df["avg_departure_delay"].median()
med_ontime = stats_df["on_time_pct"].median()
fig_quad.add_vline(x=med_delay,  line_dash="dash", line_color="gray", opacity=0.5)
fig_quad.add_hline(y=med_ontime, line_dash="dash", line_color="gray", opacity=0.5)
st.plotly_chart(fig_quad, use_container_width=True)
