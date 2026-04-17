import streamlit as st

from components.carousel import trending_carousel
from components.movie_card import movie_card
from database.db import SessionLocal, sync_movies
from recommender.hybrid import get_hybrid_recommendations_with_details, get_smart_tonight_recommendation
from services.tmdb_api import discover_movies, get_genres, get_trending_movies


def _render_recommendation_grid(items, empty_message):
    if not items:
        st.info(empty_message)
        return

    cols = st.columns(4)
    for index, item in enumerate(items):
        movie = item["movie"] if "movie" in item else item
        explanation = item.get("explanation") if isinstance(item, dict) else None
        with cols[index % 4]:
            movie_card(
                {
                    "id": movie.movie_id if hasattr(movie, "movie_id") else movie.get("id"),
                    "title": movie.title if hasattr(movie, "title") else movie.get("title"),
                    "overview": movie.overview if hasattr(movie, "overview") else movie.get("overview"),
                    "poster_path": movie.poster_path if hasattr(movie, "poster_path") else movie.get("poster_path"),
                    "vote_average": movie.vote_average if hasattr(movie, "vote_average") else movie.get("vote_average"),
                },
                key_suffix=f"home_{index}",
                explanation=explanation,
            )


def home_page():
    if "user" not in st.session_state:
        st.error("Please login first")
        return

    user = st.session_state.user

    st.markdown('<div class="hero-heading">Movie Night Recommender</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="hero-subheading">Welcome back, {user.name}. Here are the best picks for tonight.</div>',
        unsafe_allow_html=True,
    )

    trending_movies = get_trending_movies(limit=18)
    if trending_movies:
        db = SessionLocal()
        sync_movies(db, trending_movies)
        db.close()

    feature_cols = st.columns([1, 1], gap="large")
    smart_pick = get_smart_tonight_recommendation(user.user_id)
    surprise_candidates = get_hybrid_recommendations_with_details(user.user_id, top_n=8)
    surprise_seed = st.session_state.get("home_surprise_seed", 0)
    surprise_pick = surprise_candidates[surprise_seed % len(surprise_candidates)] if surprise_candidates else None

    with feature_cols[0]:
        smart_header_cols = st.columns([2, 3])
        with smart_header_cols[0]:
            st.markdown('<div class="home-section-title">Smart Tonight</div>', unsafe_allow_html=True)
        with smart_header_cols[1]:
            # Keep the same header height/alignment as the Surprise column (real button).
            # We hide this via CSS but keep its layout box so the cards align.
            st.button(
                "Pick Something Unexpected",
                key="smart_dummy",
                use_container_width=True,
                disabled=True,
            )

        if smart_pick:
            movie = smart_pick["movie"]
            movie_card(
                {
                    "id": movie.movie_id,
                    "title": movie.title,
                    "overview": movie.overview,
                    "poster_path": movie.poster_path,
                    "vote_average": movie.vote_average,
                },
                key_suffix="smart_tonight",
                explanation=smart_pick["explanation"],
                badge="Tonight's Best Fit",
                variant="feature",
            )
        else:
            st.info("Rate a few more movies to unlock a stronger Smart Tonight pick.")


    with feature_cols[1]:
        surprise_header_cols = st.columns([2, 3])
        with surprise_header_cols[0]:
            st.markdown('<div class="home-section-title">Surprise Me</div>', unsafe_allow_html=True)
        with surprise_header_cols[1]:
            if st.button("Pick Something Unexpected", key="surprise_me", use_container_width=True):
                st.session_state.home_surprise_seed = st.session_state.get("home_surprise_seed", 0) + 1
                st.rerun()

        if surprise_pick:
            movie = surprise_pick["movie"]
            movie_card(
                {
                    "id": movie.movie_id,
                    "title": movie.title,
                    "overview": movie.overview,
                    "poster_path": movie.poster_path,
                    "vote_average": movie.vote_average,
                },
                key_suffix=f"surprise_{surprise_seed}",
                explanation=surprise_pick["explanation"],
                badge="Surprise Pick",
                variant="feature",
            )
        else:
            st.info("No surprise candidate is available yet.")

    st.markdown('<div class="home-section-title">Trending Movies</div>', unsafe_allow_html=True)
    trending_carousel(trending_movies)

    st.markdown('<div class="home-section-title">Curated For You Tonight</div>', unsafe_allow_html=True)
    personalized = get_hybrid_recommendations_with_details(user.user_id, top_n=8)
    _render_recommendation_grid(
        personalized,
        "Your recommendation feed is still warming up. Complete onboarding and rate more movies.",
    )

    genre_map = get_genres()
    spotlight_rows = [
        ("Action Picks", "Action"),
        ("Sci-Fi Picks", "Science Fiction"),
        ("Comedy Picks", "Comedy"),
        ("Drama Picks", "Drama"),
    ]

    for row_title, genre_name in spotlight_rows:
        genre_id = next((gid for gid, name in genre_map.items() if name.lower() == genre_name.lower()), None)
        if not genre_id:
            continue

        row_movies = discover_movies(with_genres=[genre_id], limit=8)
        if row_movies:
            db = SessionLocal()
            sync_movies(db, row_movies)
            db.close()

        st.markdown(f'<div class="home-section-title">{row_title}</div>', unsafe_allow_html=True)
        cols = st.columns(4)
        for index, movie in enumerate(row_movies[:8]):
            with cols[index % 4]:
                movie_card(
                    movie,
                    key_suffix=f"{genre_name}_{index}",
                    explanation=f"Fresh {genre_name.lower()} pick for tonight.",
                )
