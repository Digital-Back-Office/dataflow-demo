import streamlit as st

from components.movie_card import movie_card
from recommender.hybrid import get_hybrid_recommendations_with_details


def recommendations_page():
    if "user" not in st.session_state:
        st.error("Please login first")
        return

    user = st.session_state.user
    st.markdown('<div class="rate-page-title compact">Recommendations</div>', unsafe_allow_html=True)
    st.caption("Hybrid picks based on your likes, ratings, and broader popularity signals.")

    recommendations = get_hybrid_recommendations_with_details(user.user_id, top_n=16)
    if not recommendations:
        st.info("Recommendations are still warming up. Rate more movies to improve the feed.")
        return

    cols = st.columns(4)
    for index, item in enumerate(recommendations):
        movie = item["movie"]
        explanation = item["explanation"]
        badge = f"Score {item['final_score']:.2f}"
        with cols[index % 4]:
            movie_card(
                {
                    "id": movie.movie_id,
                    "title": movie.title,
                    "overview": movie.overview,
                    "poster_path": movie.poster_path,
                    "vote_average": movie.vote_average,
                },
                key_suffix=f"recommendations_{index}",
                explanation=explanation,
                badge=badge,
            )
