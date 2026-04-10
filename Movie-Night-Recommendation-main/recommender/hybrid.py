from collections import defaultdict

from database.db import SessionLocal
from database.models import GroupMember, GroupRating, Movie, Rating, UserLikedMovie
# from recommender.collaborative import get_collaborative_scores
from recommender.content_based import get_content_scores


def _movie_popularity_score(movie):
    vote_average = float(movie.vote_average or 0.0) / 10.0
    return max(0.0, min(vote_average, 1.0))


def _merge_scores(content_scores, collaborative_scores, top_n):
    merged = defaultdict(
        lambda: {
            "movie": None,
            "content_similarity": 0.0,
            "collaborative_score": 0.0,
            "popularity_score": 0.0,
            "explanation": "",
        }
    )

    for item in content_scores:
        movie = item["movie"]
        merged[movie.movie_id]["movie"] = movie
        merged[movie.movie_id]["content_similarity"] = float(item["score"])
        merged[movie.movie_id]["popularity_score"] = _movie_popularity_score(movie)
        merged[movie.movie_id]["explanation"] = item.get("reason", "")

    for item in collaborative_scores:
        movie = item["movie"]
        merged[movie.movie_id]["movie"] = movie
        merged[movie.movie_id]["collaborative_score"] = float(item["score"])
        merged[movie.movie_id]["popularity_score"] = _movie_popularity_score(movie)

    ranked = []
    for movie_id, payload in merged.items():
        movie = payload["movie"]
        if not movie:
            continue

        final_score = (
            0.5 * payload["content_similarity"]
            + 0.3 * payload["collaborative_score"]
            + 0.2 * payload["popularity_score"]
        )
        ranked.append(
            {
                "movie": movie,
                "movie_id": movie_id,
                "final_score": final_score,
                "content_similarity": payload["content_similarity"],
                "collaborative_score": payload["collaborative_score"],
                "popularity_score": payload["popularity_score"],
                "explanation": payload["explanation"]
                or f"Recommended because {movie.title} balances your taste, community ratings, and overall popularity.",
            }
        )

    ranked.sort(key=lambda item: item["final_score"], reverse=True)
    return ranked[:top_n]


def get_hybrid_recommendations_with_details(user_id, top_n=12):
    db = SessionLocal()
    excluded_movie_ids = {
        movie_id for (movie_id,) in db.query(UserLikedMovie.movie_id).filter(UserLikedMovie.user_id == user_id).all()
    }
    excluded_movie_ids.update(
        movie_id for (movie_id,) in db.query(Rating.movie_id).filter(Rating.user_id == user_id).all()
    )
    db.close()

    content_scores = get_content_scores(user_id, top_n=top_n * 3)
    # collaborative_scores = get_collaborative_scores(user_id, top_n=top_n * 3)
    collaborative_scores = []  # Disabled due to library compatibility issues
    merged = _merge_scores(content_scores, collaborative_scores, top_n=top_n * 3)
    filtered = [item for item in merged if item["movie_id"] not in excluded_movie_ids]
    return filtered[:top_n]


def get_hybrid_recommendations(user_id, top_n=10):
    return [item["movie"] for item in get_hybrid_recommendations_with_details(user_id, top_n=top_n)]


def get_smart_tonight_recommendation(user_id):
    recommendations = get_hybrid_recommendations_with_details(user_id, top_n=20)
    if not recommendations:
        return None

    best = sorted(
        recommendations,
        key=lambda item: (
            item["final_score"],
            item["popularity_score"],
            item["content_similarity"],
        ),
        reverse=True,
    )[0]
    return best


def get_surprise_me_recommendation(user_id):
    recommendations = get_hybrid_recommendations_with_details(user_id, top_n=20)
    if not recommendations:
        return None
    middle_band = recommendations[: min(8, len(recommendations))]
    return middle_band[user_id % len(middle_band)]


def get_group_recommendations(group_id, top_n=10):
    db = SessionLocal()
    member_ids = [
        user_id for (user_id,) in db.query(GroupMember.user_id).filter(GroupMember.group_id == group_id).all()
    ]
    if not member_ids:
        db.close()
        return []

    group_rated_ids = {
        movie_id for (movie_id,) in db.query(GroupRating.movie_id).filter(GroupRating.group_id == group_id).all()
    }
    liked_ids = {
        movie_id
        for (movie_id,) in db.query(UserLikedMovie.movie_id).filter(UserLikedMovie.user_id.in_(member_ids)).all()
    }
    rated_ids = {
        movie_id
        for (movie_id,) in db.query(Rating.movie_id).filter(Rating.user_id.in_(member_ids)).all()
    }
    db.close()

    member_recommendation_sets = [get_hybrid_recommendations_with_details(member_id, top_n=top_n * 3) for member_id in member_ids]
    aggregated = defaultdict(
        lambda: {
            "movie": None,
            "score_sum": 0.0,
            "contributors": 0,
        }
    )
    for member_recommendations in member_recommendation_sets:
        for item in member_recommendations:
            movie = item["movie"]
            if movie.movie_id in group_rated_ids:
                continue
            aggregated[movie.movie_id]["movie"] = movie
            aggregated[movie.movie_id]["score_sum"] += item["final_score"]
            aggregated[movie.movie_id]["contributors"] += 1

    ranked = []
    for payload in aggregated.values():
        movie = payload["movie"]
        if not movie:
            continue
        consensus_bonus = payload["contributors"] / max(len(member_ids), 1)
        affinity_bonus = 0.05 if movie.movie_id in liked_ids else 0.0
        familiarity_penalty = -0.03 if movie.movie_id in rated_ids else 0.0
        score = (payload["score_sum"] / max(payload["contributors"], 1)) + consensus_bonus + affinity_bonus + familiarity_penalty
        ranked.append(
            {
                "movie": movie,
                "final_score": score,
                "explanation": f"Recommended for the group because it aligns with {payload['contributors']} member taste profile(s).",
            }
        )

    ranked.sort(key=lambda item: item["final_score"], reverse=True)
    return ranked[:top_n]
