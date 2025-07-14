import streamlit as st
from utils.queries import (
    get_flight_statistics_summary,
    get_airline_performance_stats,
    get_origin_airport_stats,
)

st.set_page_config(page_title="Flight Dashboard", layout="wide")

st.title("✈️ Flights Dashboard")
st.markdown("Explore flight delays, airport stats, airline performance, and an ai chatbot to get answers for your quries.")

# --- Summary Stats ---
st.subheader("📊 Quick Summary")

try:
    stats = get_flight_statistics_summary()
    total_flights = sum(row["total_flights"] for row in stats)
    avg_dep_delay = sum(row["avg_departure_delay"] for row in stats) / len(stats)
    avg_arr_delay = sum(row["avg_arrival_delay"] for row in stats) / len(stats)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Flights", f"{total_flights:,}")
    col2.metric("Avg Departure Delay (min)", f"{avg_dep_delay:.2f}")
    col3.metric("Avg Arrival Delay (min)", f"{avg_arr_delay:.2f}")
except Exception as e:
    st.error(f"Failed to load summary: {e}")
