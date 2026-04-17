from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from database.db import SessionLocal
from database.models import Movie, Rating, UserGenre, UserLikedMovie
from services.tmdb_api import get_genres


def _movie_text(movie, genre_name_map):
    genre_names = [
        genre_name_map.get(int(genre_id), "")
        for genre_id in (movie.genres or "").split(",")
        if str(genre_id).strip().isdigit()
    ]
    return " ".join(
        part
        for part in [
            movie.title or "",
            movie.overview or "",
            " ".join(name for name in genre_names if name),
        ]
        if part
    )


def _load_user_profile(db, user_id):
    liked_movie_ids = {
        movie_id
        for (movie_id,) in db.query(UserLikedMovie.movie_id).filter(
            UserLikedMovie.user_id == user_id
        ).all()
    }
    ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
    user_genres = [
        genre
        for (genre,) in db.query(UserGenre.genre).filter(UserGenre.user_id == user_id).all()
    ]
    return liked_movie_ids, ratings, user_genres


def get_content_scores(user_id, top_n=20):
    db = SessionLocal()
    movies = db.query(Movie).all()
    liked_movie_ids, ratings, user_genres = _load_user_profile(db, user_id)
    db.close()

    if not movies:
        return []

    genre_name_map = get_genres()
    movie_texts = [_movie_text(movie, genre_name_map) for movie in movies]
    vectorizer = TfidfVectorizer(stop_words="english", max_features=4000, ngram_range=(1, 2))
    tfidf_matrix = vectorizer.fit_transform(movie_texts)

    movie_index = {movie.movie_id: idx for idx, movie in enumerate(movies)}
    preferred_indices = [movie_index[movie_id] for movie_id in liked_movie_ids if movie_id in movie_index]

    rating_weights = {}
    for rating in ratings:
        if rating.movie_id in movie_index:
            rating_weights[rating.movie_id] = max(float(rating.rating), 0.0)
            if float(rating.rating) >= 7:
                preferred_indices.append(movie_index[rating.movie_id])

    preferred_indices = list(dict.fromkeys(preferred_indices))
    if not preferred_indices:
        preferred_indices = list(range(min(5, len(movies))))

    base_vector = np.asarray(tfidf_matrix[preferred_indices].mean(axis=0))
    similarities = cosine_similarity(base_vector, tfidf_matrix).flatten()

    user_genre_tokens = {genre.lower() for genre in user_genres}
    favorite_titles = {
        movie.title
        for movie in movies
        if movie.movie_id in liked_movie_ids or rating_weights.get(movie.movie_id, 0) >= 8
    }
    top_genres = [genre for genre, _ in Counter(user_genres).most_common(2)]

    scored = []
    for idx, movie in enumerate(movies):
        if movie.movie_id in liked_movie_ids:
            continue

        genre_bonus = 0.0
        movie_genres = [
            genre_name_map.get(int(genre_id), "").lower()
            for genre_id in (movie.genres or "").split(",")
            if str(genre_id).strip().isdigit()
        ]
        if user_genre_tokens.intersection(movie_genres):
            genre_bonus = 0.08

        rating_bonus = 0.0
        if movie.movie_id in rating_weights:
            rating_bonus = min(rating_weights[movie.movie_id] / 100.0, 0.05)

        score = float(similarities[idx]) + genre_bonus + rating_bonus

        reasons = []
        if favorite_titles:
            reasons.append(f"because you liked {sorted(favorite_titles)[0]}")
        if top_genres:
            reasons.append(f"and prefer {' / '.join(top_genres)} movies")

        scored.append(
            {
                "movie": movie,
                "score": max(score, 0.0),
                "reason": "You might enjoy this movie " + " ".join(reasons) + "." if reasons else "",
                "content_similarity": float(similarities[idx]),
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_n]


def get_content_recommendations(user_id, top_n=10):
    return [item["movie"] for item in get_content_scores(user_id, top_n=top_n)]
