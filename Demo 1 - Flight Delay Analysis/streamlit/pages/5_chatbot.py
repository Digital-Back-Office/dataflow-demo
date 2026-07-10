import streamlit as st
import google.generativeai as genai
import pandas as pd
import random
import time
import threading
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
    get_airports,
)

st.set_page_config(page_title="Flight Data Chatbot", layout="wide")

dataflow = Dataflow()
gemini_api_key = dataflow.secret("gemini_api_key")
genai.configure(api_key=gemini_api_key)

FUNNY_LOADING = [
    "Schlepping through flight logs",
    "Wrangling turbulent records",
    "Bribing the control tower",
    "Herding delayed passengers",
    "Interrogating departure boards",
    "Untangling runway spaghetti",
    "Decoding gate gobbledygook",
    "Rummaging through manifests",
    "Negotiating with jetstreams",
    "Cajoling the flight computer",
]

SUGGESTED_QUESTIONS = [
    "Which airline delays passengers the most?",
    "What's the best time of day to fly to avoid delays?",
    "Which airports have the worst delays?",
    "What day of the week is best for on-time flights?",
]

TABLE_DESCRIPTIONS = {
    "airline_performance_stats": "Per-airline stats: total flights, avg departure delay, avg arrival delay, on-time percentage.",
    "origin_airport_stats": "Per-origin-airport stats: total flights, avg departure delay, on-time percentage.",
    "airport_details": "Airport reference: IATA code, name, city, state, latitude, longitude.",
    "delay_distribution": "Histogram of departure delays bucketed by minutes (bin_start, bin_end, count).",
    "flight_statistics_summary": "Summary per airline and month: total flights, avg departure delay, avg arrival delay.",
    "delay_vs_hour": "Per airline and scheduled departure hour: avg departure delay.",
    "hourly_avg_delay": "Overall avg departure delay per scheduled departure hour.",
    "top10_origin_airports_by_delay": "Top 10 origin airports ranked by avg departure delay.",
    "weekday_avg_delay": "Avg departure delay by day of week (0=Monday, 6=Sunday).",
    "airlines": "Airlines reference mapping IATA code to full airline name.",
    "airports": "Airports reference mapping IATA code to name, city, state, lat/lon.",
}

SYSTEM_PROMPT = """You are a friendly travel assistant helping everyday travellers understand US flight delays.

CRITICAL RULES — follow these without exception:
1. NEVER mention table names, column names, dataset names, or anything technical. Words like "table", "dataset", "data", "column", "record", "source", "according to", "based on" are FORBIDDEN.
2. NEVER add notes or parenthetical comments about where information came from.
3. Just state the facts directly, as if you simply know them.

Tone: Plain, conversational English — like a well-travelled friend giving advice. Concise. Warm.

Format:
- One or two sentences for simple questions.
- A short bullet list only when comparing 3+ things.
- Numbers should sound natural ("about 67 minutes late on average", not "66.78 minutes").

BAD (never do this): "According to the top10_origin_airports_by_delay table, PAH has a delay of 66.78 min (Note: sourced from airport_details table)"
GOOD (always do this): "The most delayed airports are small regional ones — Paducah, KY and Johnstown, PA both average over an hour late."

Available information (use this silently — never reference it in your answer):
{context}
"""


@st.cache_data(ttl=300)
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


@st.cache_data(ttl=300)
def get_cached_context() -> str:
    chunks = []
    for name, data in load_all_data().items():
        desc = TABLE_DESCRIPTIONS.get(name, "")
        if isinstance(data, dict):
            rows = [{"key": k, "value": v} for k, v in data.items()]
            df = pd.DataFrame(rows)
        else:
            df = pd.DataFrame(data)
        chunks.append(f"### {name} — {desc} ###\n{df.to_csv(index=False)}")
    return "\n\n".join(chunks)


def get_or_create_chat():
    if "gemini_chat" not in st.session_state:
        context = get_cached_context()
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=SYSTEM_PROMPT.format(context=context),
        )
        st.session_state.gemini_chat = model.start_chat(history=[])
    return st.session_state.gemini_chat


# Pre-warm data cache and Gemini chat on page load so first response is fast
@st.cache_resource
def _prewarm():
    load_all_data()
    get_cached_context()
    return True

_prewarm()

# Pre-init chat session in the background on first page visit
if "gemini_chat" not in st.session_state:
    def _init_chat():
        get_or_create_chat()
    threading.Thread(target=_init_chat, daemon=True).start()

# ── Inline SVG plane icon ────────────────────────────────────────────────────
PLANE_SVG = (
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" '
    'xmlns="http://www.w3.org/2000/svg" '
    'style="vertical-align:middle;margin-right:7px;opacity:0.75">'
    '<path d="M22 16.5L13.5 12 22 7.5V2l-20 10 20 10v-5.5z" fill="#aaa"/>'
    '<path d="M2 12h11" stroke="#aaa" stroke-width="1.5" stroke-linecap="round"/>'
    "</svg>"
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Pill buttons */
div[data-testid="stHorizontalBlock"] .stButton > button {
    border-radius: 999px !important;
    border: 1px solid rgba(160,160,160,0.35) !important;
    background: transparent !important;
    color: #bbb !important;
    font-size: 0.78rem !important;
    padding: 4px 16px !important;
    height: auto !important;
    line-height: 1.5 !important;
    transition: border-color 0.2s, color 0.2s, background 0.2s;
}
div[data-testid="stHorizontalBlock"] .stButton > button:hover {
    border-color: rgba(200,200,200,0.7) !important;
    color: #fff !important;
    background: rgba(255,255,255,0.06) !important;
}

/* Breathing loader */
@keyframes breathe {
    0%, 100% { opacity: 0.2; }
    50%       { opacity: 0.9; }
}
.loader-wrap {
    animation: breathe 2s ease-in-out infinite;
    font-size: 0.85rem;
    color: #aaa;
    padding: 14px 0 6px 20px;
    display: flex;
    align-items: center;
    letter-spacing: 0.015em;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ────────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ── Header ───────────────────────────────────────────────────────────────────
st.title("💬 Flight Delay Chatbot")
st.caption("Ask anything about flight delays, airlines, and airports — plain answers for real travellers.")

# ── Chat history ─────────────────────────────────────────────────────────────
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ── Suggested pills (empty state only, just above chat input) ────────────────
# IMPORTANT: pills must be rendered BEFORE the pending_question pop so that
# button callbacks fire in the same script run that sets pending_question.
if not st.session_state.chat_history:
    picks = random.sample(SUGGESTED_QUESTIONS, 2)
    cols = st.columns([1] + [3] * len(picks) + [1])
    for i, q in enumerate(picks):
        with cols[i + 1]:
            if st.button(q, key=f"pill_{i}", use_container_width=True):
                st.session_state.pending_question = q

# Pop pending AFTER buttons so the button callback above can set it first
pending = st.session_state.pop("pending_question", None)

# ── Chat input (sticky at bottom by default) ─────────────────────────────────
user_input = st.chat_input("Ask about delays, airlines, airports...") or pending

if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Loader appears directly below the user message
    loader_slot = st.empty()

    result: dict = {"reply": None, "error": None, "done": False}

    def call_api():
        try:
            chat = get_or_create_chat()
            resp = chat.send_message(user_input)
            result["reply"] = resp.text.strip()
        except Exception as e:
            result["error"] = str(e)
        finally:
            result["done"] = True

    threading.Thread(target=call_api, daemon=True).start()

    while not result["done"]:
        word = random.choice(FUNNY_LOADING)
        loader_slot.markdown(
            f'<div class="loader-wrap">{PLANE_SVG}{word}…</div>',
            unsafe_allow_html=True,
        )
        time.sleep(2)

    loader_slot.empty()

    reply = (
        result["reply"]
        if not result["error"]
        else f"Sorry, couldn't get a response right now. ({result['error']})"
    )

    st.session_state.chat_history.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
        st.markdown(reply)

    st.rerun()
