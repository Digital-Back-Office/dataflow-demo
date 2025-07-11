import streamlit as st
import pandas as pd
import altair as alt
from utils.queries import (
    get_hourly_avg_delay,
    get_top10_origin_airports_by_delay,
    get_weekday_avg_delay,
    get_airports,
    get_airlines
)

st.set_page_config(page_title="⏱️ Delay Analysis", layout="wide")
st.title("⏱️ Flight Delay Analysis")

# --- Load precomputed data ---
hourly_df = pd.DataFrame(get_hourly_avg_delay())
top10_airports = pd.DataFrame(get_top10_origin_airports_by_delay())
dow_delay = pd.DataFrame(get_weekday_avg_delay())

# Lookup tables
airports = get_airports()
airlines = get_airlines()

# --- Heatmap: Hour vs Delay ---
st.markdown("### 🕒 Heatmap of Average Departure Delay by Hour")

heatmap = alt.Chart(hourly_df).mark_rect().encode(
    x=alt.X('hour:O', title="Scheduled Hour"),
    y=alt.value(1),
    color=alt.Color('avg_departure_delay:Q', scale=alt.Scale(scheme='redyellowgreen', reverse=True), title="Avg Delay (min)"),
    tooltip=['hour', 'avg_departure_delay']
).properties(width=700, height=100)

st.altair_chart(heatmap, use_container_width=True)

# --- Top 10 Airports by Delay ---
st.markdown("### 🛫 Top 10 Origin Airports with Highest Avg Departure Delay")

top10_airports['origin_full'] = top10_airports['origin_airport'].map(
    lambda code: airports.get(code, {}).get('airport', code)
)

bar_chart = alt.Chart(top10_airports).mark_bar().encode(
    x=alt.X('avg_departure_delay:Q', title='Avg Departure Delay (min)'),
    y=alt.Y('origin_full:N', sort='-x', title='Airport'),
    tooltip=['origin_full', 'avg_departure_delay']
).properties(height=400)

st.altair_chart(bar_chart, use_container_width=True)

# --- Delay by Day of Week ---
st.markdown("### 📆 Average Delay by Day of the Week")

# Ensure order of days
dow_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
dow_delay['day_of_week'] = pd.Categorical(dow_delay['day_of_week'], categories=dow_order, ordered=True)
dow_delay = dow_delay.sort_values('day_of_week')

# Melt for line chart
dow_delay_melted = dow_delay.melt(
    id_vars='day_of_week',
    value_vars=['avg_departure_delay', 'avg_arrival_delay'],
    var_name='delay_type',
    value_name='delay'
)

line = alt.Chart(dow_delay_melted).mark_line(point=True).encode(
    x=alt.X('day_of_week:N', title='Day of Week'),
    y=alt.Y('delay:Q', title='Average Delay (min)'),
    color=alt.Color('delay_type:N', title='Type of Delay'),
    tooltip=['day_of_week:N', 'delay_type:N', 'delay:Q']
).properties(height=300)

st.altair_chart(line, use_container_width=True)






# import streamlit as st
# import pandas as pd
# import altair as alt
# from utils.queries import get_all_flights, get_airports, get_airlines

# st.set_page_config(page_title="⏱️ Delay Analysis", layout="wide")
# st.title("⏱️ Flight Delay Analysis")

# # --- Load and prep data ---
# flights = pd.DataFrame(get_all_flights(limit=10000))
# airports = get_airports()
# airlines = get_airlines()

# # Extract readable names from nested airport dict
# flights['origin_full'] = flights['origin_airport'].map(lambda x: airports.get(x, {}).get('airport', x))
# flights['destination_full'] = flights['destination_airport'].map(lambda x: airports.get(x, {}).get('airport', x))
# flights['airline_full'] = flights['airline'].map(airlines)
# flights['hour'] = pd.to_datetime(flights['scheduled_departure']).dt.hour
# flights['day_of_week'] = pd.to_datetime(flights['scheduled_departure']).dt.day_name()

# # --- Sidebar filters ---
# st.sidebar.header("🔍 Filters")
# selected_airport = st.sidebar.selectbox("Origin Airport", ["All"] + sorted(flights['origin_full'].dropna().unique()))
# selected_airline = st.sidebar.selectbox("Airline", ["All"] + sorted(flights['airline_full'].dropna().unique()))

# if selected_airport != "All":
#     flights = flights[flights['origin_full'] == selected_airport]
# if selected_airline != "All":
#     flights = flights[flights['airline_full'] == selected_airline]

# # --- Heatmap: Hour vs Delay ---
# st.markdown("### 🕒 Heatmap of Average Departure Delay by Hour")

# heatmap_data = flights.groupby('hour')['departure_delay'].mean().reset_index()

# heatmap = alt.Chart(heatmap_data).mark_rect().encode(
#     x=alt.X('hour:O', title="Scheduled Hour"),
#     y=alt.value(1),  # dummy Y to show just a horizontal bar
#     color=alt.Color('departure_delay:Q', scale=alt.Scale(scheme='redyellowgreen', reverse=True), title="Avg Delay (min)"),
#     tooltip=['hour', 'departure_delay']
# ).properties(width=700, height=100)

# st.altair_chart(heatmap, use_container_width=True)

# # --- Top 10 Airports by Delay ---
# st.markdown("### 🛫 Top 10 Origin Airports with Highest Avg Departure Delay")

# airport_delays = (
#     flights.groupby('origin_full')['departure_delay']
#     .mean()
#     .sort_values(ascending=False)
#     .head(10)
#     .reset_index()
# )

# bar_chart = alt.Chart(airport_delays).mark_bar().encode(
#     x=alt.X('departure_delay:Q', title='Avg Departure Delay (min)'),
#     y=alt.Y('origin_full:N', sort='-x', title='Airport'),
#     tooltip=['origin_full', 'departure_delay']
# ).properties(height=400)

# st.altair_chart(bar_chart, use_container_width=True)

# # --- Delay by Day of Week ---
# st.markdown("### 📆 Average Delay by Day of the Week")

# dow_delay = (
#     flights.groupby('day_of_week')[['departure_delay', 'arrival_delay']]
#     .mean()
#     .reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])
#     .reset_index()
# )

# dow_delay_melted = dow_delay.melt(
#     id_vars='day_of_week',
#     value_vars=['departure_delay', 'arrival_delay'],
#     var_name='delay_type',
#     value_name='delay'
# )

# line = alt.Chart(dow_delay_melted).mark_line(point=True).encode(
#     x=alt.X('day_of_week:N', sort=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']),
#     y=alt.Y('delay:Q', title='Average Delay (min)'),
#     color=alt.Color('delay_type:N', title='Type of Delay'),
#     tooltip=['day_of_week:N', 'delay_type:N', 'delay:Q']
# ).properties(height=300)

# st.altair_chart(line, use_container_width=True)
