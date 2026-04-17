import streamlit as st
import random
from database.db import SessionLocal, sync_movies
from database.models import Movie, UserGenre, UserLikedMovie
from services.tmdb_api import get_genres, get_movies_by_genre
from components.movie_card import movie_card

GENRES = ["Action", "Sci-Fi", "Comedy", "Thriller", "Drama", "Adventure", "Horror", "Romance", "Mystery", "Fantasy", "Animation", "Crime"]

ONBOARDING_SET_SIZE = 10
ONBOARDING_COLUMNS = 5

def _sync_movie_records(movies):
    db = SessionLocal()
    sync_movies(db, movies)
    db.close()

def _build_movie_pool(selected_genres):
    genre_ids = {name: genre_id for genre_id, name in get_genres().items()}
    unique_movies = {}
    for genre in selected_genres:
        genre_id = genre_ids.get(genre)
        if not genre_id:
            continue
        for movie in get_movies_by_genre(genre_id)[:10]:
            unique_movies[movie["id"]] = movie
    return list(unique_movies.values())

def _get_displayed_movies(selected_genres, force_refresh=False):
    pool_key = "onboarding_movie_pool"
    display_key = "onboarding_displayed_movies"
    pool_signature = tuple(sorted(selected_genres))

    if (
        force_refresh
        or st.session_state.get("onboarding_pool_signature") != pool_signature
        or pool_key not in st.session_state
    ):
        st.session_state[pool_key] = _build_movie_pool(selected_genres)
        st.session_state["onboarding_pool_signature"] = pool_signature

    movie_pool = st.session_state.get(pool_key, [])
    if not movie_pool:
        st.session_state[display_key] = []
        return []

    if force_refresh or display_key not in st.session_state:
        sample_size = min(ONBOARDING_SET_SIZE, len(movie_pool))
        current_ids = {
            movie["id"] for movie in st.session_state.get(display_key, [])
        }
        next_set = random.sample(movie_pool, sample_size)
        if force_refresh and len(movie_pool) > sample_size:
            for _ in range(5):
                next_ids = {movie["id"] for movie in next_set}
                if next_ids != current_ids:
                    break
                next_set = random.sample(movie_pool, sample_size)
        st.session_state[display_key] = next_set

    return st.session_state[display_key]

def _toggle_selected_movie(movie_id):
    selected_ids = set(st.session_state.get("onboarding_selected_ids", []))
    if movie_id in selected_ids:
        selected_ids.remove(movie_id)
    else:
        selected_ids.add(movie_id)
    st.session_state["onboarding_selected_ids"] = list(selected_ids)

def _toggle_selected_genre(genre):
    selected_genres = set(st.session_state.get("onboarding_genres_draft", []))
    if genre in selected_genres:
        selected_genres.remove(genre)
    else:
        selected_genres.add(genre)
    st.session_state["onboarding_genres_draft"] = list(selected_genres)

def _reset_genre_selection(user_id):
    db = SessionLocal()
    db.query(UserGenre).filter(UserGenre.user_id == user_id).delete()
    db.commit()
    db.close()
    st.session_state.pop("onboarding_movie_pool", None)
    st.session_state.pop("onboarding_displayed_movies", None)
    st.session_state.pop("onboarding_pool_signature", None)
    st.session_state.pop("onboarding_selected_ids", None)

def onboarding_page():
    if 'user' not in st.session_state:
        st.error("Please login first")
        return
    
    user = st.session_state.user
    
    db = SessionLocal()
    user_genres = db.query(UserGenre).filter(UserGenre.user_id == user.user_id).all()
    db.close()
    
    if not user_genres:
        # Step 1: Select genres
        st.header("Step 1: Select Your Favorite Genres")
        selected_genres = set(st.session_state.get("onboarding_genres_draft", []))
        cols = st.columns(3)
        for i, genre in enumerate(GENRES):
            with cols[i % 3]:
                clicked = st.button(
                    genre,
                    key=f"genre_{genre}",
                    use_container_width=True,
                    type="primary" if genre in selected_genres else "secondary",
                )
                if clicked:
                    _toggle_selected_genre(genre)
                    st.rerun()
        
        if st.button("Proceed to Movie Selection"):
            selected_genres = st.session_state.get("onboarding_genres_draft", [])
            if not selected_genres:
                st.warning("Select at least one genre to continue.")
                return
            db = SessionLocal()
            for genre in selected_genres:
                ug = UserGenre(user_id=user.user_id, genre=genre)
                db.add(ug)
            db.commit()
            db.close()
            st.session_state.pop("onboarding_genres_draft", None)
            st.rerun()
    else:
        # Step 2: Select movies
        st.header("Step 2: Select Movies You Like (at least 5)")
        selected_genres = [ug.genre for ug in user_genres]
        top_actions = st.columns([1, 1, 4])

        with top_actions[0]:
            shuffle_requested = st.button("Shuffle Movies", use_container_width=True)
        with top_actions[1]:
            change_genres = st.button("Change Genres", use_container_width=True)
        if change_genres:
            _reset_genre_selection(user.user_id)
            st.session_state["onboarding_genres_draft"] = selected_genres
            st.rerun()

        selected_movies = _get_displayed_movies(
            selected_genres,
            force_refresh=shuffle_requested,
        )
        displayed_ids = {movie["id"] for movie in selected_movies}
        selected_ids = {
            movie_id
            for movie_id in st.session_state.get("onboarding_selected_ids", [])
            if movie_id in displayed_ids
        }
        st.session_state["onboarding_selected_ids"] = list(selected_ids)

        if not selected_movies:
            st.error("No movies were found for the selected genres.")
            st.info("Choose different genres and try again.")
            if st.button("Go Back to Genres", use_container_width=True):
                _reset_genre_selection(user.user_id)
                st.session_state["onboarding_genres_draft"] = selected_genres
                st.rerun()
            return

        cols = st.columns(ONBOARDING_COLUMNS)
        for i, movie in enumerate(selected_movies):
            with cols[i % ONBOARDING_COLUMNS]:
                movie_id = movie["id"]
                is_selected = movie_id in selected_ids
                clicked = movie_card(
                    movie,
                    selected=is_selected,
                    key_suffix=str(movie_id),
                    action_label="Selected" if is_selected else "Select",
                )
                if clicked:
                    _toggle_selected_movie(movie_id)
                    st.rerun()

        st.caption(f"Showing {len(selected_movies)} movies in 2 rows of up to 5.")

        liked = st.session_state.get("onboarding_selected_ids", [])
        if len(liked) >= 5:
            if st.button("Proceed"):
                _sync_movie_records(selected_movies)
                db = SessionLocal()
                for movie_id in liked:
                    already_liked = db.query(UserLikedMovie).filter(
                        UserLikedMovie.user_id == user.user_id,
                        UserLikedMovie.movie_id == movie_id,
                    ).first()
                    if not already_liked:
                        db.add(UserLikedMovie(user_id=user.user_id, movie_id=movie_id))
                db.commit()
                db.close()
                st.session_state.current_page = "Recommendations"
                st.session_state.onboarding_complete = True
                st.success("Onboarding complete!")
                st.rerun()
        else:
            st.write(f"Select at least 5 movies. Currently selected: {len(liked)}")
