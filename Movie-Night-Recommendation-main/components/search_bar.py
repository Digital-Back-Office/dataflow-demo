import streamlit as st

from components.movie_card import movie_card
from database.db import SessionLocal, sync_movies
from services.tmdb_api import search_movies as tmdb_search_movies

try:
    from semantic_search.vector_store import rebuild_vector_store, search_similar_movies
except Exception:  # pragma: no cover - fallback when optional deps aren't installed
    rebuild_vector_store = None
    search_similar_movies = None


def search_bar():
    st.markdown('<div class="global-search-shell">', unsafe_allow_html=True)
    with st.form("global_search_form", clear_on_submit=False, border=False):
        input_col, button_col = st.columns([7, 2], gap="small")
        with input_col:
            query = st.text_input(
                "Search movies",
                key="global_search",
                placeholder="Try: space adventure, time travel movies, funny romance...",
                label_visibility="collapsed",
            ).strip()
        with button_col:
            # `key` isn't accepted by some Streamlit versions for form_submit_button;
            # keep the call minimal to avoid TypeError while preserving the label.
            submitted = st.form_submit_button("Search")

    if not query or not submitted:
        st.markdown("</div>", unsafe_allow_html=True)
        return

    results = []
    used_semantic = False

    if search_similar_movies:
        used_semantic = True
        results = search_similar_movies(query, k=12)

    # If the semantic index is empty (fresh DB), seed from TMDB results, sync locally, then rebuild.
    if used_semantic and not results:
        seed_results = tmdb_search_movies(query, limit=30)
        if seed_results:
            db = SessionLocal()
            sync_movies(db, seed_results)
            db.close()
            if rebuild_vector_store:
                rebuild_vector_store()
            results = search_similar_movies(query, k=12) if search_similar_movies else []

    # Fallback to plain TMDB keyword search if semantic search isn't available.
    if not used_semantic:
        results = tmdb_search_movies(query)

    st.markdown('<div class="search-section-title">Search Results</div>', unsafe_allow_html=True)
    if used_semantic:
        st.caption("Semantic matches from your local movie library.")

    if not results:
        st.info("No matching movies were found.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    cols = st.columns(4)
    for index, movie in enumerate(results[:8]):
        with cols[index % 4]:
            movie_card(
                movie,
                key_suffix=f"search_{index}",
                badge=f"Semantic {movie.get('semantic_score', 0.0):.2f}" if used_semantic else None,
            )

    st.markdown("</div>", unsafe_allow_html=True)

