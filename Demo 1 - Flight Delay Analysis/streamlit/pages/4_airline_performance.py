import streamlit as st
import pandas as pd
import altair as alt
from utils.queries import get_airlines, get_airline_performance_stats

st.set_page_config(page_title="🛩️ Airline Performance", layout="wide")
st.title("🛩️ Airline Performance Analysis")

# --- Load precomputed data ---
stats_df = pd.DataFrame(get_airline_performance_stats())
airlines_map = get_airlines()
stats_df['airline_full'] = stats_df['airline'].map(airlines_map)

# --- Sidebar filter ---
st.sidebar.header("🔍 Filters")
min_flights = st.sidebar.slider("Minimum Flights", 0, 1000, 0)
stats_df = stats_df[stats_df['total_flights'] >= min_flights]

# --- Airline Delay Comparison ---
st.markdown("### 📊 Airline Delay Comparison")
delay_bar = alt.Chart(stats_df).transform_fold(
    ['avg_departure_delay', 'avg_arrival_delay'],
    as_=['delay_type', 'delay_value']
).mark_bar().encode(
    x=alt.X('airline_full:N', sort='-y', title="Airline"),
    y=alt.Y('delay_value:Q', title="Average Delay (min)"),
    color=alt.Color('delay_type:N', title="Delay Type"),
    tooltip=['airline_full:N', 'delay_type:N', 'delay_value:Q']
).properties(height=350)

st.altair_chart(delay_bar, use_container_width=True)

# --- Volume and On-Time Charts ---
st.markdown("### 🧮 Airline Volume and On-Time Performance")
cols = st.columns(2)

with cols[0]:
    st.markdown("#### ✈️ Flights per Airline")
    flight_chart = alt.Chart(stats_df).mark_bar().encode(
        y=alt.Y('airline_full:N', sort='-x', title=None),
        x=alt.X('total_flights:Q', title="Total Flights"),
        tooltip=['airline_full', 'total_flights']
    ).properties(height=350)
    st.altair_chart(flight_chart, use_container_width=True)

with cols[1]:
    st.markdown("#### ✅ On-Time Arrival %")
    ontime_chart = alt.Chart(stats_df).mark_bar().encode(
        y=alt.Y('airline_full:N', sort='-x', title=None),
        x=alt.X('on_time_pct:Q', title="On-Time %"),
        tooltip=['airline_full', 'on_time_pct']
    ).properties(height=350)
    st.altair_chart(ontime_chart, use_container_width=True)

















# import streamlit as st
# import pandas as pd
# import altair as alt
# from utils.queries import get_all_flights, get_airlines

# st.set_page_config(page_title="🛩️ Airline Performance", layout="wide")
# st.title("🛩️ Airline Performance Analysis")

# # --- Load data ---
# flights = pd.DataFrame(get_all_flights(limit=20000))
# airlines_map = get_airlines()
# flights['airline_full'] = flights['airline'].map(airlines_map)

# # --- Sidebar filter ---
# st.sidebar.header("🔍 Filters")
# min_flights = st.sidebar.slider("Minimum Flights", 0, 1000, 0)

# # --- Airline summary stats ---
# st.markdown("### 📊 Airline Delay Comparison")

# airline_stats = (
#     flights.groupby('airline_full')
#     .agg(
#         avg_dep_delay=('departure_delay', 'mean'),
#         avg_arr_delay=('arrival_delay', 'mean'),
#         total_flights=('airline_full', 'count'),
#         on_time_pct=('arrival_delay', lambda x: (x <= 0).sum() / len(x) * 100)
#     )
#     .reset_index()
# )

# airline_stats = airline_stats[airline_stats['total_flights'] >= min_flights]
# st.write(airline_stats)

# # --- Delay Comparison Bar Chart ---
# bar = alt.Chart(airline_stats).transform_fold(
#     ['avg_dep_delay', 'avg_arr_delay'],
#     as_=['delay_type', 'delay_value']
# ).mark_bar().encode(
#     x=alt.X('airline_full:N', sort='-y', title="Airline"),
#     y=alt.Y('delay_value:Q', title="Average Delay (min)"),
#     color=alt.Color('delay_type:N', title="Delay Type"),
#     tooltip=['airline_full:N', 'delay_type:N', 'delay_value:Q']
# ).properties(height=350)

# st.altair_chart(bar, use_container_width=True)

# # --- Flight Count & On-Time % ---
# st.markdown("### 🧮 Airline Volume and On-Time Performance")

# cols = st.columns(2)

# with cols[0]:
#     st.markdown("#### ✈️ Flights per Airline")
#     flight_chart = alt.Chart(airline_stats).mark_bar().encode(
#         y=alt.Y('airline_full:N', sort='-x', title=None),
#         x=alt.X('total_flights:Q', title="Total Flights"),
#         tooltip=['airline_full', 'total_flights']
#     ).properties(height=350)
#     st.altair_chart(flight_chart, use_container_width=True)

# with cols[1]:
#     st.markdown("#### ✅ On-Time Arrival %")
#     ontime_chart = alt.Chart(airline_stats).mark_bar().encode(
#         y=alt.Y('airline_full:N', sort='-x', title=None),
#         x=alt.X('on_time_pct:Q', title="On-Time %"),
#         tooltip=['airline_full', 'on_time_pct']
#     ).properties(height=350)
#     st.altair_chart(ontime_chart, use_container_width=True)
