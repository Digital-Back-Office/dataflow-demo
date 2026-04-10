from html import escape
from textwrap import dedent

import streamlit as st

from services.tmdb_api import POSTER_BASE_URL


def movie_card(
    movie,
    selected=False,
    key_suffix="",
    action_label=None,
    explanation=None,
    badge=None,
    variant=None,
):
    poster_url = (
        f"{POSTER_BASE_URL}{movie.get('poster_path', '')}"
        if movie.get("poster_path")
        else "https://via.placeholder.com/300x450?text=No+Image"
    )
    title = movie.get("title", "Unknown")
    rating = float(movie.get("vote_average", 0) or 0)
    overview = movie.get("overview", "")
    selected_class = " is-selected" if selected else ""
    variant_class = f" movie-card--{variant}" if variant else ""
    safe_title = escape(title)
    safe_overview = escape(overview or "No summary available.")
    safe_badge = escape(str(badge)) if badge else ""
    safe_explanation = escape(str(explanation)) if explanation else ""

    badge_html = f'<div class="movie-card-badge">{safe_badge}</div>' if safe_badge else ""
    explanation_html = f'<div class="movie-explanation">{safe_explanation}</div>' if safe_explanation else ""

    # Important: avoid leading indentation, otherwise Markdown renders this as a code block.
    html = dedent(
        f"""\
<div class="movie-card{variant_class}{selected_class}">
  {badge_html}
  <div class="movie-poster-wrap">
    <img class="movie-poster" src="{poster_url}" alt="{safe_title} poster">
    <div class="movie-overview-hover">{safe_overview}</div>
  </div>
  <div class="movie-meta">
    <div class="movie-title">{safe_title}</div>
    <div class="movie-rating">TMDB Rating: {rating:.1f}/10</div>
    {explanation_html}
  </div>
</div>
"""
    )
    st.markdown(html, unsafe_allow_html=True)

    if not action_label:
        return False

    return st.button(
        action_label,
        key=f"card_action_{movie['id']}_{key_suffix}",
        use_container_width=True,
        type="primary" if selected else "secondary",
    )
