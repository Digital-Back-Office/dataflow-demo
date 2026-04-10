# import numpy as np
# from sentence_transformers import SentenceTransformer
# from app.database.supabase_client import get_supabase
# from app.config.settings import EMBEDDING_MODEL


# def cosine_similarity(a, b):
#     return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


# def search_similar_bills(query: str, top_k: int = 5):
#     """
#     Perform vector similarity search against stored bill embeddings.
#     """

#     supabase = get_supabase()
#     model = SentenceTransformer(EMBEDDING_MODEL)

#     # Embed query
#     query_embedding = model.encode(query)

#     # Fetch all stored embeddings
#     bills = (
#         supabase.table("uk_bills_main")
#         .select("bill_id, title, summary, embedding")
#         .not_.is_("embedding", None)
#         .execute()
#     )

#     if not bills.data:
#         print("No embeddings available.")
#         return []

#     results = []

#     for bill in bills.data:
#         bill_embedding = bill.get("embedding")

#         if not bill_embedding:
#             continue

#         score = cosine_similarity(
#             np.array(query_embedding),
#             np.array(bill_embedding)
#         )

#         results.append({
#             "bill_id": bill["bill_id"],
#             "title": bill["title"],
#             "summary": bill["summary"],
#             "score": float(score)
#         })

#     # Sort by similarity score
#     results = sorted(results, key=lambda x: x["score"], reverse=True)

#     return results[:top_k]