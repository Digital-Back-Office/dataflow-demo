import faiss
import numpy as np

from database.db import SessionLocal
from database.models import Movie
from semantic_search.embeddings import create_embedding, create_movie_embedding
from services.tmdb_api import get_genres, get_popular_movies, normalize_movie_payload


class VectorStore:
    def __init__(self):
        self.index = None
        self.movies = []

    def _ensure_seed_movies(self):
        db = SessionLocal()
        movie_count = db.query(Movie).count()
        if movie_count > 0:
            db.close()
            return

        for movie_data in get_popular_movies(limit=30):
            db.merge(
                Movie(
                    movie_id=movie_data["id"],
                    title=movie_data["title"],
                    overview=movie_data.get("overview"),
                    poster_path=movie_data.get("poster_path"),
                    release_date=movie_data.get("release_date"),
                    vote_average=movie_data.get("vote_average"),
                    genres=",".join(str(genre_id) for genre_id in movie_data.get("genre_ids", [])),
                )
            )
        db.commit()
        db.close()

    def rebuild(self):
        self._ensure_seed_movies()
        db = SessionLocal()
        movies = db.query(Movie).all()
        db.close()

        if not movies:
            self.index = None
            self.movies = []
            return

        genre_map = get_genres()
        embedding_rows = []
        indexed_movies = []
        for movie in movies:
            genre_names = [
                genre_map.get(int(genre_id), "")
                for genre_id in (movie.genres or "").split(",")
                if str(genre_id).strip().isdigit()
            ]
            payload = normalize_movie_payload(
                {
                    "id": movie.movie_id,
                    "title": movie.title,
                    "overview": movie.overview,
                    "poster_path": movie.poster_path,
                    "vote_average": movie.vote_average,
                    "release_date": movie.release_date,
                    "genre_ids": [
                        int(genre_id)
                        for genre_id in (movie.genres or "").split(",")
                        if str(genre_id).strip().isdigit()
                    ],
                }
            )
            payload["genre_names"] = [name for name in genre_names if name]
            embedding_rows.append(create_movie_embedding(payload))
            indexed_movies.append(payload)

        embeddings = np.array(embedding_rows, dtype="float32")
        faiss.normalize_L2(embeddings)
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)
        self.movies = indexed_movies

    def search(self, query, k=12):
        if self.index is None or not self.movies:
            self.rebuild()
        if self.index is None:
            return []

        query_embedding = np.array([create_embedding(query)], dtype="float32")
        faiss.normalize_L2(query_embedding)
        distances, indices = self.index.search(query_embedding, min(k, len(self.movies)))

        results = []
        for distance, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.movies):
                continue
            movie = dict(self.movies[idx])
            movie["semantic_score"] = float(distance)
            results.append(movie)
        return results


vector_store = VectorStore()


def rebuild_vector_store():
    vector_store.rebuild()


def search_similar_movies(query, k=12):
    return vector_store.search(query, k=k)
