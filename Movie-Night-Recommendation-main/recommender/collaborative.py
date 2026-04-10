import pandas as pd
from surprise import Dataset, Reader, SVD

from database.db import SessionLocal
from database.models import Movie, Rating


def get_collaborative_scores(user_id, top_n=20):
    db = SessionLocal()
    ratings = db.query(Rating).all()
    movies = db.query(Movie).all()
    db.close()

    if len(ratings) < 6 or len({rating.user_id for rating in ratings}) < 2:
        return []

    df = pd.DataFrame(
        [(rating.user_id, rating.movie_id, float(rating.rating)) for rating in ratings],
        columns=["user_id", "movie_id", "rating"],
    )
    if df.empty:
        return []

    min_rating = float(df["rating"].min())
    max_rating = float(df["rating"].max())
    if min_rating == max_rating:
        max_rating = min_rating + 1.0

    reader = Reader(rating_scale=(min_rating, max_rating))
    dataset = Dataset.load_from_df(df[["user_id", "movie_id", "rating"]], reader)
    trainset = dataset.build_full_trainset()
    algo = SVD(random_state=42, n_factors=40, n_epochs=20)
    algo.fit(trainset)

    rated_movie_ids = set(df.loc[df["user_id"] == user_id, "movie_id"].tolist())
    if not rated_movie_ids:
        rated_movie_ids = set()

    predictions = []
    for movie in movies:
        if movie.movie_id in rated_movie_ids:
            continue
        estimate = algo.predict(user_id, movie.movie_id).est
        normalized = (estimate - min_rating) / (max_rating - min_rating)
        predictions.append(
            {
                "movie": movie,
                "score": max(0.0, min(float(normalized), 1.0)),
                "estimate": float(estimate),
            }
        )

    predictions.sort(key=lambda item: item["score"], reverse=True)
    return predictions[:top_n]


def get_collaborative_recommendations(user_id, top_n=10):
    return [item["movie"] for item in get_collaborative_scores(user_id, top_n=top_n)]
