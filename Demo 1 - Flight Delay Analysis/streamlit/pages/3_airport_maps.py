import streamlit as st
import pandas as pd
import plotly.express as px
from utils.queries import get_airports, get_origin_airport_stats

st.set_page_config(page_title="🗺️ Airport Map", layout="wide")
st.title("🗺️ Airport Map & Statistics")

# --- Load precomputed data ---
airports_dict = get_airports()
origin_stats = pd.DataFrame(get_origin_airport_stats())

# Convert airports_dict to DataFrame
airports_df = pd.DataFrame([
    {'iata_code': code, **details}
    for code, details in airports_dict.items()
])

# Merge airport info with stats
merged_df = pd.merge(
    origin_stats,
    airports_df,
    left_on='origin_airport',
    right_on='iata_code',
    how='inner'
)

# --- Visualization ---
st.markdown("### ✈️ US Airports — Size = Traffic, Color = Avg Delay")

def delay_to_color_plotly(delay):
    return max(0, min(100, delay))  # Normalize for color scale

merged_df['color_value'] = merged_df['avg_departure_delay'].apply(delay_to_color_plotly)
merged_df['size'] = merged_df['flight_count'] * 2

fig = px.scatter_mapbox(
    merged_df,
    lat="latitude",
    lon="longitude",
    size="size",
    color="color_value",
    color_continuous_scale="Reds",
    hover_name="airport",
    hover_data={
        "flight_count": True,
        "avg_departure_delay": ":.1f",
        "color_value": False,
        "size": False
    },
    mapbox_style="open-street-map",
    zoom=3,
    center={"lat": 39.5, "lon": -98.35},
    title="Airport Flight Delays"
)

fig.update_layout(height=600)
st.plotly_chart(fig, use_container_width=True)

# --- Top 10 Busiest Airports ---
st.markdown("### 🔝 Top 10 Busiest Origin Airports")
top_busiest = merged_df.sort_values("flight_count", ascending=False).head(10)
st.dataframe(top_busiest[['airport', 'city', 'state', 'flight_count']])

# --- Top 10 Delayed Airports ---
st.markdown("### ⌛ Top 10 Origin Airports with Highest Delays")
top_delayed = merged_df.sort_values("avg_departure_delay", ascending=False).head(10)
st.dataframe(top_delayed[['airport', 'city', 'state', 'avg_departure_delay']])














# import streamlit as st
# import pandas as pd
# import pydeck as pdk
# from utils.queries import get_airports, get_all_flights

# st.set_page_config(page_title="🗺️ Airport Map", layout="wide")
# st.title("🗺️ Airport Map & Statistics")

# # --- Load data ---
# airports_dict = get_airports()
# airports_df = pd.DataFrame([
#     {'iata_code': code, **details}
#     for code, details in airports_dict.items()
# ])

# flights_df = pd.DataFrame(get_all_flights(limit=20000))

# # --- Preprocess flight counts and delay per airport ---
# origin_stats = flights_df.groupby('origin_airport').agg(
#     flight_count=('origin_airport', 'count'),
#     avg_delay=('departure_delay', 'mean')
# ).reset_index()

# # --- Merge airport info ---
# merged_df = pd.merge(
#     origin_stats,
#     airports_df,
#     left_on='origin_airport',
#     right_on='iata_code',
#     how='inner'
# )

# # # --- Interactive Map: Airport Size = Traffic, Color = Delay ---
# st.markdown("### ✈️ US Airports — Size = Traffic, Color = Avg Delay")

# import plotly.express as px

# # Create the color scale
# def delay_to_color_plotly(delay):
#     return max(0, min(100, delay))  # Normalize for color scale

# merged_df['color_value'] = merged_df['avg_delay'].apply(delay_to_color_plotly)
# merged_df['size'] = merged_df['flight_count'] * 2  # Adjust size multiplier

# fig = px.scatter_mapbox(
#     merged_df,
#     lat="latitude",
#     lon="longitude",
#     size="size",
#     color="color_value",
#     color_continuous_scale="Reds",
#     hover_name="airport",
#     hover_data={
#         "flight_count": True,
#         "avg_delay": ":.1f",
#         "color_value": False,
#         "size": False
#     },
#     mapbox_style="open-street-map",
#     zoom=3,
#     center={"lat": 39.5, "lon": -98.35},
#     title="Airport Flight Delays"
# )

# fig.update_layout(height=600)
# st.plotly_chart(fig, use_container_width=True)

# # --- Top 10 busiest airports ---
# st.markdown("### 🔝 Top 10 Busiest Origin Airports")
# top_busiest = merged_df.sort_values("flight_count", ascending=False).head(10)
# st.dataframe(top_busiest[['airport', 'city', 'state', 'flight_count']])

# # --- Top 10 worst delayed origin airports ---
# st.markdown("### ⌛ Top 10 Origin Airports with Highest Delays")
# top_delayed = merged_df.sort_values("avg_delay", ascending=False).head(10)
# st.dataframe(top_delayed[['airport', 'city', 'state', 'avg_delay']])