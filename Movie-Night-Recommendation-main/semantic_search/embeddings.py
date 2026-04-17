from functools import lru_cache

from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_embedding_model():
    return SentenceTransformer(MODEL_NAME)


def create_embedding(text):
    model = get_embedding_model()
    return model.encode(text or "", normalize_embeddings=True)


def create_movie_embedding(movie):
    title = movie.get("title", "")
    overview = movie.get("overview", "")
    genres = " ".join(movie.get("genre_names", []))
    keywords = " ".join(movie.get("keywords", []))
    text = f"{title}. {overview}. {genres}. {keywords}".strip()
    return create_embedding(text)
