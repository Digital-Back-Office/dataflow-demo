import random
from html import escape
from textwrap import dedent

import streamlit as st

from database.db import SessionLocal
from database.models import Movie, Rating
from services.tmdb_api import POSTER_BASE_URL, get_trending_movies, search_movies

STAR_SCALE = 10
STAR_ICON = "\u2605"


def _normalize_rating_value(value):
    if not value:
        return 0
    return max(0.0, min(float(value), float(STAR_SCALE)))


def _persist_movie(db, movie_data):
    movie = db.query(Movie).filter(Movie.movie_id == movie_data["id"]).first()
    if movie:
        movie.title = movie_data["title"]
        movie.overview = movie_data.get("overview")
        movie.poster_path = movie_data.get("poster_path")
        movie.vote_average = movie_data.get("vote_average")
        movie.release_date = movie_data.get("release_date")
        movie.genres = ",".join([str(g) for g in movie_data.get("genre_ids", [])])
        return movie

    movie = Movie(
        movie_id=movie_data["id"],
        title=movie_data["title"],
        overview=movie_data.get("overview"),
        poster_path=movie_data.get("poster_path"),
        vote_average=movie_data.get("vote_average"),
        release_date=movie_data.get("release_date"),
        genres=",".join([str(g) for g in movie_data.get("genre_ids", [])]),
    )
    db.add(movie)
    return movie


def _save_user_rating(db, user_id, movie_id, rating_value):
    existing_rating = db.query(Rating).filter(
        Rating.user_id == user_id,
        Rating.movie_id == movie_id,
    ).first()
    if existing_rating:
        existing_rating.rating = rating_value
    else:
        db.add(Rating(user_id=user_id, movie_id=movie_id, rating=rating_value))
    db.commit()


def _get_user_rated_movies(db, user_id):
    return (
        db.query(Movie, Rating)
        .join(Rating, Rating.movie_id == Movie.movie_id)
        .filter(Rating.user_id == user_id)
        .order_by(Rating.id.desc())
        .all()
    )


def _query_param_scalar(query_params, key):
    value = query_params.get(key)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _queue_rating_update(movie_id, value):
    st.session_state.pending_rating_update = {
        "movie_id": int(movie_id),
        "value": float(value),
    }


def _consume_pending_rating_update(db, user_id):
    pending_update = st.session_state.pop("pending_rating_update", None)
    if pending_update:
        _save_user_rating(
            db,
            user_id,
            int(pending_update["movie_id"]),
            float(pending_update["value"]),
        )
        st.rerun()
        return

    query_params = st.query_params
    rating_target = _query_param_scalar(query_params, "set_rating")
    rating_value = _query_param_scalar(query_params, "value")

    if not rating_target or not rating_value:
        return

    try:
        movie_id = int(rating_target)
        normalized_value = float(rating_value)
    except ValueError:
        query_params.clear()
        st.rerun()
        return

    _save_user_rating(db, user_id, movie_id, normalized_value)
    query_params.clear()
    st.rerun()


def _render_rating_bar(movie_id, current_rating, compact=False):
    normalized_rating = _normalize_rating_value(current_rating)
    selected_value = int(round(normalized_rating))
    current_label = f"{selected_value}/10" if selected_value else "Not rated"
    st.markdown(
        dedent(
            f"""
        <div class="star-rating-widget{' compact' if compact else ''}">
            <div class="star-rating-head">
                <div class="star-rating-copy">
                    <span class="star-rating-caption">Your Rating</span>
                    <span class="star-rating-value">{escape(current_label)}</span>
                </div>
                <div class="star-rating-note">Hover and click to rate</div>
            </div>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )
    star_cols = st.columns(STAR_SCALE, gap="small")
    for index, value in enumerate(range(STAR_SCALE, 0, -1)):
        with star_cols[index]:
            st.button(
                STAR_ICON,
                key=f"rate_{'compact' if compact else 'main'}_{movie_id}_{value}",
                type="primary" if value <= selected_value else "secondary",
                on_click=_queue_rating_update,
                args=(movie_id, value),
                help=f"Rate {value} out of {STAR_SCALE}",
            )


def _render_rated_movies_view(db, user_id):
    header_cols = st.columns([1, 2, 1], gap="small")
    with header_cols[0]:
        if st.button(
            "Back to Rate Movies",
            key="back_to_rate_movies",
            use_container_width=True,
            type="secondary",
        ):
            st.session_state.rate_movies_view = "browse"
            st.rerun()
    with header_cols[1]:
        st.markdown('<div class="rate-page-title compact centered">Your Rated Movies</div>', unsafe_allow_html=True)

    rated_items = _get_user_rated_movies(db, user_id)
    st.markdown('<div class="rated-panel-shell"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        if not rated_items:
            st.info("You have not rated any movies yet.")
        else:
            for movie, rating in rated_items:
                item_cols = st.columns([1.6, 1.4], gap="medium")
                with item_cols[0]:
                    st.markdown(
                        f"""
                        <div class="rated-item-card">
                            <div class="rated-item-title">{escape(movie.title)}</div>
                            <div class="rated-item-sub">Current rating: {int(round(_normalize_rating_value(rating.rating)))}/10</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with item_cols[1]:
                    _render_rating_bar(movie.movie_id, rating.rating, compact=True)


def rate_movies_page():
    if "user" not in st.session_state:
        st.error("Please login first")
        return

    user = st.session_state.user
    if "rate_movies_view" not in st.session_state:
        st.session_state.rate_movies_view = "browse"

    db = SessionLocal()
    _consume_pending_rating_update(db, user.user_id)

    if st.session_state.rate_movies_view == "rated":
        _render_rated_movies_view(db, user.user_id)
        db.close()
        return

    header_cols = st.columns([3.2, 1], gap="small")
    with header_cols[0]:
        st.markdown('<div class="rate-page-title compact">Rate Movies</div>', unsafe_allow_html=True)
    with header_cols[1]:
        if st.button(
            "Your Ratings",
            key="open_rated_movies",
            use_container_width=True,
            type="secondary",
        ):
            st.session_state.rate_movies_view = "rated"
            st.rerun()

    search_query = st.text_input(
        "Search and rate a movie",
        key="rate_search_query",
        placeholder="Search by title...",
        label_visibility="collapsed",
    ).strip()

    if search_query:
        movies = search_movies(search_query)[:8]
        section_label = f"Search Results for '{search_query}'"
    else:
        movies = get_trending_movies()
        if movies:
            random.shuffle(movies)
            movies = movies[:8]
        section_label = "Movies to Rate"

    st.markdown(
        f'<div class="rate-section-label">{section_label}</div>',
        unsafe_allow_html=True,
    )

    if not movies:
        st.info("No movies are available to rate right now.")
        db.close()
        return

    for movie_data in movies:
        movie = _persist_movie(db, movie_data)
        db.commit()

        existing_rating = db.query(Rating).filter(
            Rating.user_id == user.user_id,
            Rating.movie_id == movie.movie_id,
        ).first()
        other_ratings = db.query(Rating).filter(
            Rating.movie_id == movie.movie_id,
            Rating.user_id != user.user_id,
        ).all()

        average_other_rating = 0
        if other_ratings:
            average_other_rating = sum(
                _normalize_rating_value(rating.rating) for rating in other_ratings
            ) / len(other_ratings)

        poster_url = (
            f"{POSTER_BASE_URL}{movie.poster_path}"
            if movie.poster_path
            else "https://via.placeholder.com/300x450?text=No+Image"
        )
        summary = movie.overview or "No summary available."
        current_rating = existing_rating.rating if existing_rating else 0
        safe_title = escape(movie.title)
        safe_summary = escape(summary)

        st.markdown('<div class="rate-row-shell"></div>', unsafe_allow_html=True)
        with st.container(border=True):
            row_cols = st.columns([0.88, 1.82], gap="large")
            with row_cols[0]:
                st.markdown(
                    f"""
                    <div class="rate-poster-card">
                        <img src="{poster_url}" alt="{safe_title} poster">
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with row_cols[1]:
                st.markdown(
                    f"""
                    <div class="rate-movie-title">{safe_title}</div>
                    <div class="rate-summary">{safe_summary}</div>
                    <div class="rate-detail-divider"></div>
                    """,
                    unsafe_allow_html=True,
                )

                info_cols = st.columns([1, 1], gap="medium")
                with info_cols[0]:
                    st.markdown(
                        f"""
                        <div class="rate-meta-block">
                            <div class="rating-stat-label">Other Users</div>
                            <div class="rating-stat-value">{"No ratings" if not other_ratings else f"{average_other_rating:.1f}/10"}</div>
                            <div class="rating-stat-sub">{"Be the first to rate" if not other_ratings else f"{len(other_ratings)} rating(s)"}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                with info_cols[1]:
                    st.markdown(
                        f"""
                        <div class="rate-meta-block">
                            <div class="rating-stat-label">Your Rating</div>
                            <div class="rating-stat-value">{int(round(_normalize_rating_value(current_rating))) if current_rating else "-"}/10</div>
                            <div class="rating-stat-sub">Choose from 1 to {STAR_SCALE}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                _render_rating_bar(movie.movie_id, current_rating)

        st.markdown("---")

    db.close()
