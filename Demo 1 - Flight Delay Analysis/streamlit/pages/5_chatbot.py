import streamlit as st
import google.generativeai as genai
import pandas as pd
from dataflow import Dataflow

from utils.queries import (
    get_airline_performance_stats,
    get_origin_airport_stats,
    get_airport_details,
    get_delay_distribution,
    get_flight_statistics_summary,
    get_delay_vs_hour,
    get_hourly_avg_delay,
    get_top10_origin_airports_by_delay,
    get_weekday_avg_delay,
    get_airlines,
    get_airports
)

dataflow = Dataflow()
gemini_api_key = dataflow.secret('gemini_api_key_new')

# --- Gemini Setup ---
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel("gemini-2.5-flash")

# --- Load all relevant data from DB ---
@st.cache_data
def load_all_data():
    return {
        "airline_performance_stats": get_airline_performance_stats(),
        "origin_airport_stats": get_origin_airport_stats(),
        "airport_details": get_airport_details(),
        "delay_distribution": get_delay_distribution(),
        "flight_statistics_summary": get_flight_statistics_summary(),
        "delay_vs_hour": get_delay_vs_hour(),
        "hourly_avg_delay": get_hourly_avg_delay(),
        "top10_origin_airports_by_delay": get_top10_origin_airports_by_delay(),
        "weekday_avg_delay": get_weekday_avg_delay(),
        "airlines": get_airlines(),
        "airports": get_airports(),
    }

_ = load_all_data()

def get_context_string(data_sources):
    chunks = []
    for name, data in data_sources.items():
        if isinstance(data, dict):
            rows = [{"key": k, "value": v} for k, v in data.items()]
            df = pd.DataFrame(rows)
        else:
            df = pd.DataFrame(data)
        chunks.append(f"### {name} ###\n" + df.head(20).to_csv(index=False))
    return "\n\n".join(chunks)

# --- Streamlit UI ---
st.set_page_config(page_title="Flight Data Chatbot", layout="centered")
st.title("💬 Flight Delay Data Chatbot")
st.caption("Ask questions about flight delays, airlines, or airports using live data.")

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Migrate old tuple-based chat history to dict format
if st.session_state.chat_history and isinstance(st.session_state.chat_history[0], tuple):
    st.session_state.chat_history = [
        {"role": "user", "content": pair[0]} if i % 2 == 0
        else {"role": "assistant", "content": pair[1]}
        for i, pair in enumerate(zip(*[iter(st.session_state.chat_history)]*2))
    ]

# --- Chat Interface ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input area
if prompt := st.chat_input("Ask your question..."):
    # Show user's message
    st.chat_message("user").markdown(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    # Generate response
    with st.spinner("Gemini is thinking..."):
        data_context = get_context_string(load_all_data())
        full_prompt = f"""
You are a flight data assistant. Use the following tables to answer user questions.

{data_context}

Question: {prompt}
"""
        response = model.generate_content(full_prompt)
        reply = response.text.strip()

    # Show assistant's reply
    st.chat_message("assistant").markdown(reply)
    st.session_state.chat_history.append({"role": "assistant", "content": reply})