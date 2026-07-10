import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.queries import get_airports, get_origin_airport_stats

st.set_page_config(page_title="Airport Map · Flight Delays", page_icon="🗺️", layout="wide")
st.title("🗺️ Airport Map")
st.caption("Every US origin airport — bubble size = traffic volume, colour = average departure delay.")

# ── cached loaders ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_airports():
    return get_airports()

@st.cache_data(ttl=300)
def load_origin_stats():
    return pd.DataFrame(get_origin_airport_stats())

with st.spinner("Loading airport data…"):
    try:
        airports_map = load_airports()
        origin_df    = load_origin_stats()
    except Exception:
        st.error("Could not load data. Check that the pipeline has run.")
        st.stop()

airports_df = pd.DataFrame([
    {"iata_code": code, **details}
    for code, details in airports_map.items()
])

merged = pd.merge(
    origin_df,
    airports_df,
    left_on="origin_airport",
    right_on="iata_code",
    how="inner",
)

# ── sidebar controls ───────────────────────────────────────────────────────────
st.sidebar.header("Filters")
delay_threshold = st.sidebar.slider(
    "Min avg delay to highlight (min)", 0, 60, 0,
    help="Airports below this threshold are shown at reduced opacity.",
)
show_top_n = st.sidebar.slider("Show top N airports by traffic", 10, len(merged), len(merged))

display_df = merged.sort_values("flight_count", ascending=False).head(show_top_n)
display_df = display_df.copy()
display_df["delay_label"] = display_df["avg_departure_delay"].round(1).astype(str) + " min"
display_df["highlight"] = display_df["avg_departure_delay"] >= delay_threshold

# ── map ────────────────────────────────────────────────────────────────────────
fig_map = px.scatter_mapbox(
    display_df,
    lat="latitude",
    lon="longitude",
    size="flight_count",
    size_max=40,
    color="avg_departure_delay",
    color_continuous_scale="RdYlGn_r",
    range_color=[0, display_df["avg_departure_delay"].quantile(0.95)],
    hover_name="airport",
    hover_data={
        "city": True,
        "state": True,
        "flight_count": True,
        "avg_departure_delay": ":.1f",
        "latitude": False,
        "longitude": False,
    },
    labels={
        "flight_count": "Flights",
        "avg_departure_delay": "Avg Dep Delay (min)",
    },
    mapbox_style="carto-darkmatter",
    zoom=3,
    center={"lat": 39.5, "lon": -98.35},
    template="plotly_dark",
)
fig_map.update_layout(
    height=560,
    margin=dict(t=10, b=10, l=0, r=0),
    coloraxis_colorbar=dict(title="Avg Delay (min)", thickness=14),
)
st.plotly_chart(fig_map, use_container_width=True)

st.divider()

# ── busiest airports ──────────────────────────────────────────────────────────
st.subheader("Top 10 Busiest Airports")
busiest = display_df.sort_values("flight_count", ascending=False).head(10)
fig_busy = px.bar(
    busiest,
    x="flight_count",
    y="airport",
    orientation="h",
    color="avg_departure_delay",
    color_continuous_scale="RdYlGn_r",
    labels={"flight_count": "Total Flights", "airport": ""},
    template="plotly_dark",
)
fig_busy.update_layout(
    yaxis=dict(autorange="reversed"),
    coloraxis_colorbar=dict(title="Avg Delay"),
    height=420,
    margin=dict(t=10, b=10),
)
st.plotly_chart(fig_busy, use_container_width=True)

# ── most delayed airports ─────────────────────────────────────────────────────
st.subheader("Top 10 Most Delayed Airports")
delayed = display_df.sort_values("avg_departure_delay", ascending=False).head(10)
fig_del = px.bar(
    delayed,
    x="avg_departure_delay",
    y="airport",
    orientation="h",
    color="avg_departure_delay",
    color_continuous_scale="Reds",
    labels={"avg_departure_delay": "Avg Dep Delay (min)", "airport": ""},
    template="plotly_dark",
)
fig_del.update_layout(
    yaxis=dict(autorange="reversed"),
    coloraxis_showscale=False,
    height=420,
    margin=dict(t=10, b=10),
)
st.plotly_chart(fig_del, use_container_width=True)

# ── scatter: volume vs delay ───────────────────────────────────────────────────
st.subheader("Traffic Volume vs Average Delay")
st.caption("Busy airports are not necessarily the most delayed — smaller regional hubs often perform worse.")

fig_vs = px.scatter(
    display_df,
    x="flight_count",
    y="avg_departure_delay",
    color="avg_departure_delay",
    color_continuous_scale="RdYlGn_r",
    size="flight_count",
    size_max=30,
    hover_name="airport",
    hover_data={"city": True, "state": True, "flight_count": True},
    labels={
        "flight_count": "Total Flights",
        "avg_departure_delay": "Avg Dep Delay (min)",
    },
    template="plotly_dark",
)
fig_vs.update_layout(coloraxis_showscale=False, height=400, margin=dict(t=10, b=10))
st.plotly_chart(fig_vs, use_container_width=True)
