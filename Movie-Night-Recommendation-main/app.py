import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv(override=False)

import streamlit as st

from database.db import create_tables
from components.search_bar import search_bar
from pages.login import login_page
from pages.onboarding import onboarding_page
from pages.home import home_page
from pages.recommendations import recommendations_page
from pages.rate_movies import rate_movies_page
from pages.groups import groups_page

# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="Movie Night Recommender",
    page_icon=":clapper:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------- THEME --------------------
if "theme_toggle" not in st.session_state:
    st.session_state.theme_toggle = False

theme = "light" if st.session_state.theme_toggle else "dark"
st.session_state.theme = theme

# -------------------- ✅ FINAL API KEY HANDLING --------------------
API_KEY = os.environ.get("TMDB_API_KEY")

# Debug logs (check in DataFlow logs)
print("DEBUG ENV TMDB_API_KEY:", API_KEY)

# 🔥 FALLBACK (guaranteed fix if DataFlow fails)
if not API_KEY:
    print("⚠️ Using fallback TMDB key")
    API_KEY = "3ce27cdc94bd97e1616c9c202937e7d4"   # <-- PUT YOUR REAL KEY HERE

# Final safety
if not API_KEY:
    st.error(
        "TMDB API Key not configured.\n\n"
        "Fix:\n"
        "- Add TMDB_API_KEY in DataFlow Secrets\n"
        "- Enable 'Set as ENV'\n"
        "- Restart environment"
    )
    st.stop()

# -------------------- DATABASE --------------------
create_tables()

# -------------------- LOAD CSS --------------------
with open("assets/styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# -------------------- THEME CSS --------------------
LIGHT_THEME_CSS = """
body, .stApp { background: #f3f6fb !important; color: #0b1220 !important; }
"""

DARK_THEME_CSS = """
body, .stApp { background-color: #0f172a !important; color: #f8fafc !important; }
"""

st.markdown(
    f"<style>{LIGHT_THEME_CSS if theme == 'light' else DARK_THEME_CSS}</style>",
    unsafe_allow_html=True,
)

# -------------------- APP FLOW --------------------
if 'user' not in st.session_state:
    st.markdown(
        '<style>[data-testid="stSidebar"] { display: none !important; }</style>',
        unsafe_allow_html=True
    )
    login_page()

else:
    user = st.session_state.user

    from database.db import SessionLocal
    from database.models import UserLikedMovie

    db = SessionLocal()
    liked = db.query(UserLikedMovie).filter(
        UserLikedMovie.user_id == user.user_id
    ).all()
    db.close()

    if not liked:
        onboarding_page()

    else:
        if "current_page" not in st.session_state:
            st.session_state.current_page = "Home"

        st.markdown(
            '<style>[data-testid="stSidebar"] { display: block !important; }</style>',
            unsafe_allow_html=True
        )

        with st.sidebar:
            st.markdown("## 🎬 Movie Night")

            st.toggle("Light theme", key="theme_toggle")

            for label in ["Home", "Recommendations", "Rate Movies", "Groups"]:
                if st.button(
                    label,
                    key=f"nav_{label}",
                    use_container_width=True,
                    type="primary" if st.session_state.current_page == label else "secondary",
                ):
                    st.session_state.current_page = label
                    st.rerun()

        page = st.session_state.current_page

        if page != "Rate Movies":
            search_bar()

        if page == "Home":
            home_page()
        elif page == "Recommendations":
            recommendations_page()
        elif page == "Rate Movies":
            rate_movies_page()
        elif page == "Groups":
            groups_page()

        if st.sidebar.button("Logout"):
            del st.session_state.user
            st.rerun()