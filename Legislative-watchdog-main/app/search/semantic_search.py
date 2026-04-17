# from .vector_search import search_similar_bills as _vector_search_similar


# def search_similar_bills(query: str, max_results: int = 5):
#     """
#     Compatibility wrapper for existing `vector_search.search_similar_bills`.

#     app.py imports `search_similar_bills(query, max_results)` from
#     `app.search.semantic_search`. The actual implementation lives in
#     `vector_search.py` where the parameter is named `top_k`.

#     This thin wrapper adapts the parameter name and returns the same
#     results so existing imports keep working.
#     """

#     return _vector_search_similar(query, top_k=max_results)
