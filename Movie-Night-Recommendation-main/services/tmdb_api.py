import os
from functools import lru_cache

import requests

BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"
BACKDROP_BASE_URL = "https://image.tmdb.org/t/p/original"

DEFAULT_LANGUAGE = "en-US"
DEFAULT_TIMEOUT = 12


def _safe_get(path, params=None):
    api_key = os.environ.get("TMDB_API_KEY")
    # Temporary debug print to confirm the key is available in the runtime
    print("API KEY:", os.environ.get("TMDB_API_KEY"))
    if not api_key:
        raise ValueError("TMDB_API_KEY not found")

    merged_params = {
        "api_key": api_key,
        "language": DEFAULT_LANGUAGE,
    }
    if params:
        merged_params.update(params)

    try:
        response = requests.get(
            f"{BASE_URL}{path}",
            params=merged_params,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def normalize_movie_payload(movie):
    if not movie:
        return {}

    genre_ids = movie.get("genre_ids")
    if genre_ids is None:
        genre_ids = [genre.get("id") for genre in movie.get("genres", []) if genre.get("id")]

    return {
        "id": movie.get("id"),
        "title": movie.get("title") or movie.get("name") or "Untitled",
        "overview": movie.get("overview") or "",
        "poster_path": movie.get("poster_path"),
        "backdrop_path": movie.get("backdrop_path"),
        "vote_average": float(movie.get("vote_average") or 0.0),
        "vote_count": int(movie.get("vote_count") or 0),
        "release_date": movie.get("release_date") or "",
        "genre_ids": [genre_id for genre_id in genre_ids or [] if genre_id is not None],
        "popularity": float(movie.get("popularity") or 0.0),
        "runtime": movie.get("runtime"),
        "keywords": movie.get("keywords", []),
    }


def _normalize_result_list(data):
    if not data:
        return []
    return [normalize_movie_payload(item) for item in data.get("results", [])]


@lru_cache(maxsize=1)
def get_genres():
    data = _safe_get("/genre/movie/list")
    if not data:
        return {}
    return {genre["id"]: genre["name"] for genre in data.get("genres", [])}


def get_genre_name_map():
    return get_genres()


def get_trending_movies(limit=20):
    return _normalize_result_list(_safe_get("/trending/movie/day"))[:limit]


def get_popular_movies(limit=20, page=1):
    return _normalize_result_list(_safe_get("/movie/popular", {"page": page}))[:limit]


def get_now_playing_movies(limit=20, page=1):
    return _normalize_result_list(_safe_get("/movie/now_playing", {"page": page}))[:limit]


def search_movies(query, limit=20):
    if not query:
        return []
    return _normalize_result_list(_safe_get("/search/movie", {"query": query}))[:limit]


def get_movie_details(movie_id):
    data = _safe_get(
        f"/movie/{movie_id}",
        {"append_to_response": "keywords,credits"},
    )
    return normalize_movie_payload(data) if data else None


def get_movie_keywords(movie_id):
    data = _safe_get(f"/movie/{movie_id}/keywords")
    if not data:
        return []
    return [item["name"] for item in data.get("keywords", []) if item.get("name")]


def get_movies_by_genre(genre_id, page=1, limit=20):
    data = _safe_get(
        "/discover/movie",
        {
            "with_genres": genre_id,
            "page": page,
            "sort_by": "popularity.desc",
            "vote_count.gte": 50,
        },
    )
    return _normalize_result_list(data)[:limit]


def discover_movies(with_genres=None, sort_by="popularity.desc", page=1, limit=20):
    params = {
        "sort_by": sort_by,
        "page": page,
        "vote_count.gte": 50,
    }
    if with_genres:
        params["with_genres"] = ",".join(str(genre_id) for genre_id in with_genres)
    return _normalize_result_list(_safe_get("/discover/movie", params))[:limit]


def get_similar_movies(movie_id, limit=12):
    return _normalize_result_list(_safe_get(f"/movie/{movie_id}/similar"))[:limit]


def get_recommendations_for_movie(movie_id, limit=12):
    return _normalize_result_list(_safe_get(f"/movie/{movie_id}/recommendations"))[:limit]


def get_smart_tonight_candidates(limit=30):
    candidates = []
    for movie in get_trending_movies(limit=limit):
        details = get_movie_details(movie["id"])
        if not details:
            continue
        runtime = details.get("runtime") or 0
        if 80 <= runtime <= 140:
            candidates.append(details)
    return candidates
