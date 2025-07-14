import streamlit as st
import pandas as pd
import altair as alt
from utils.queries import (
    get_flight_statistics_summary,
    get_delay_distribution,
    get_delay_vs_hour,
    get_airlines
)

st.set_page_config(page_title="📈 Statistics", layout="wide")
st.title("📈 Flight Statistics Dashboard")

# --- Load data ---
airlines_map = get_airlines()
summary_df = pd.DataFrame(get_flight_statistics_summary())
delay_bins = pd.DataFrame(get_delay_distribution())
hourly_delay_df = pd.DataFrame(get_delay_vs_hour())

summary_df['airline_full'] = summary_df['airline'].map(airlines_map)
hourly_delay_df['airline_full'] = hourly_delay_df['airline'].map(airlines_map)

# --- Sidebar filters ---
st.sidebar.header("🔍 Filters")
available_airlines = sorted(summary_df['airline_full'].dropna().unique())
selected_airlines = st.sidebar.multiselect("Filter by Airline", available_airlines)

if selected_airlines:
    summary_df = summary_df[summary_df['airline_full'].isin(selected_airlines)]
    hourly_delay_df = hourly_delay_df[hourly_delay_df['airline_full'].isin(selected_airlines)]

# --- Metrics ---
st.markdown("### ✈️ Overview Metrics")
col1, col2, col3 = st.columns(3)
col1.metric("Total Flights", f"{summary_df['total_flights'].sum():,}")
col2.metric("Avg Departure Delay", f"{summary_df['avg_departure_delay'].mean():.2f} min")
col3.metric("Avg Arrival Delay", f"{summary_df['avg_arrival_delay'].mean():.2f} min")

# --- Histogram: Departure Delay Distribution ---
st.markdown("### 🕒 Departure Delay Distribution")
delay_chart = alt.Chart(delay_bins).mark_bar().encode(
    alt.X("bin_start:Q", bin=alt.Bin(step=10), title="Departure Delay (min)"),
    alt.Y("count:Q", title="Number of Flights"),
    tooltip=["count"]
).properties(height=300)

st.altair_chart(delay_chart, use_container_width=True)

# --- Time of Day vs Delay Scatter ---
st.markdown("### 📊 Scheduled Departure vs. Delay")

scatter = alt.Chart(hourly_delay_df).mark_circle(size=10, opacity=0.3).encode(
    x=alt.X('hour:O', title='Scheduled Hour of Departure'),
    y=alt.Y('avg_departure_delay:Q', title='Avg Departure Delay (min)'),
    color=alt.Color('airline_full:N', title="Airline"),
    tooltip=['airline_full:N', 'hour:O', 'avg_departure_delay:Q']
).properties(height=400).interactive()

st.altair_chart(scatter, use_container_width=True)

# --- Airline-Wise Delay Summary ---
st.markdown("### 🛫 Airline-Wise Delay Summary")
bar = alt.Chart(summary_df).transform_fold(
    ['avg_departure_delay', 'avg_arrival_delay'],
    as_=['delay_type', 'delay_value']
).mark_bar().encode(
    x=alt.X('airline_full:N', sort='-y', title="Airline"),
    y=alt.Y('delay_value:Q', title="Average Delay (min)"),
    color=alt.Color('delay_type:N', title="Delay Type"),
    tooltip=['airline_full:N', 'delay_type:N', 'delay_value:Q']
).properties(height=350)

st.altair_chart(bar, use_container_width=True)





# import streamlit as st
# import pandas as pd
# import altair as alt
# from utils.queries import get_all_flights, get_airlines

# st.set_page_config(page_title="📈 Statistics", layout="wide")

# st.title("📈 Flight Statistics Dashboard")

# # --- Load data ---
# flights = pd.DataFrame(get_all_flights(limit=10000))  # Adjust as needed
# airlines_map = get_airlines()
# flights['airline_full'] = flights['airline'].map(airlines_map)

# # --- Sidebar filters ---
# st.sidebar.header("🔍 Filters")
# selected_airlines = st.sidebar.multiselect("Filter by Airline", sorted(flights['airline_full'].dropna().unique()))
# if selected_airlines:
#     flights = flights[flights['airline_full'].isin(selected_airlines)]

# # --- Metrics ---
# st.markdown("### ✈️ Overview Metrics")
# col1, col2, col3 = st.columns(3)
# col1.metric("Total Flights", f"{len(flights):,}")
# col2.metric("Avg Departure Delay", f"{flights['departure_delay'].mean():.2f} min")
# col3.metric("Avg Arrival Delay", f"{flights['arrival_delay'].mean():.2f} min")

# # --- Histogram: Departure Delay Distribution ---
# st.markdown("### 🕒 Departure Delay Distribution")
# delay_chart = alt.Chart(flights).mark_bar().encode(
#     alt.X("departure_delay", bin=alt.Bin(maxbins=60), title="Departure Delay (min)"),
#     alt.Y("count()", title="Number of Flights"),
#     tooltip=["count()"]
# ).properties(height=300).interactive()

# st.altair_chart(delay_chart, use_container_width=True)

# # --- Time of Day vs Delay Scatter ---
# st.markdown("### 📊 Scheduled Departure vs. Delay")
# flights['hour'] = pd.to_datetime(flights['scheduled_departure']).dt.hour

# scatter = alt.Chart(flights).mark_circle(size=10, opacity=0.3).encode(
#     x=alt.X('hour', title='Scheduled Hour of Departure'),
#     y=alt.Y('departure_delay', title='Departure Delay (min)'),
#     color=alt.Color('airline_full', title="Airline"),
#     tooltip=['airline_full', 'hour', 'departure_delay']
# ).properties(height=400).interactive()

# st.altair_chart(scatter, use_container_width=True)

# # --- Airline-Wise Delay Summary ---
# st.markdown("### 🛫 Airline-Wise Delay Summary")
# airline_stats = flights.groupby('airline_full')[['departure_delay', 'arrival_delay']].mean().reset_index()
# airline_stats = airline_stats.sort_values('departure_delay', ascending=False)

# bar = alt.Chart(airline_stats).transform_fold(
#     ['departure_delay', 'arrival_delay'],
#     as_=['delay_type', 'delay_value']
# ).mark_bar().encode(
#     x=alt.X('airline_full:N', sort='-y', title="Airline"),
#     y=alt.Y('delay_value:Q', title="Average Delay (min)"),
#     color=alt.Color('delay_type:N', title="Delay Type"),
#     tooltip=['airline_full:N', 'delay_type:N', 'delay_value:Q']
# ).properties(height=350).interactive()

# st.altair_chart(bar, use_container_width=True)


# st.altair_chart(bar, use_container_width=True)
