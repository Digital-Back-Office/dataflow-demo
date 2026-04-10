import streamlit as st
import streamlit.components.v1 as components
from html import escape
from services.tmdb_api import POSTER_BASE_URL

def trending_carousel(movies):
    """
    Display an auto-sliding carousel of trending movies.
    """
    if not movies:
        st.info("Trending movies are unavailable right now.")
        return

    cards = []
    for movie in movies[:12]:
        poster_url = (
            f"{POSTER_BASE_URL}{movie.get('poster_path', '')}"
            if movie.get('poster_path')
            else "https://via.placeholder.com/300x450?text=No+Image"
        )
        title = escape(movie.get("title", "Untitled"))
        cards.append(
            f"""
            <div class="trending-card">
                <img src="{poster_url}" alt="{title} poster" />
                <div class="trending-card-title">{title}</div>
            </div>
            """
        )

    track = "".join(cards)
    components.html(
        f"""
        <style>
            body {{
                margin: 0;
                background: transparent;
                overflow: hidden;
            }}
            .trending-carousel-shell {{
                position: relative;
                overflow: hidden;
                width: 100%;
                padding: 0.35rem 0 1rem;
                mask-image: linear-gradient(to right, transparent, black 6%, black 94%, transparent);
                -webkit-mask-image: linear-gradient(to right, transparent, black 6%, black 94%, transparent);
            }}
            .trending-carousel-track {{
                display: flex;
                gap: 1rem;
                width: max-content;
                animation: auto-slide 38s linear infinite;
            }}
            .trending-card {{
                width: 176px;
                flex: 0 0 auto;
                background: linear-gradient(180deg, rgba(30, 41, 59, 0.98), rgba(15, 23, 42, 0.98));
                border: 1px solid rgba(148, 163, 184, 0.16);
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 10px 28px rgba(2, 6, 23, 0.32);
            }}
            .trending-card img {{
                display: block;
                width: 100%;
                aspect-ratio: 2 / 2.75;
                object-fit: cover;
            }}
            .trending-card-title {{
                padding: 0.75rem 0.85rem 0.8rem;
                color: #e2e8f0;
                font-size: 0.88rem;
                font-weight: 600;
                line-height: 1.3;
                min-height: 2.9rem;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }}
            @keyframes auto-slide {{
                from {{
                    transform: translateX(0);
                }}
                to {{
                    transform: translateX(-50%);
                }}
            }}
        </style>
        <div class="trending-carousel-shell">
            <div class="trending-carousel-track">
                {track}
                {track}
            </div>
        </div>
        """,
        height=340,
        scrolling=False,
    )
