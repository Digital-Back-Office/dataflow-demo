# from sentence_transformers import SentenceTransformer
# from app.database.supabase_client import get_supabase
# from app.config.settings import EMBEDDING_MODEL

# # ---------------------------------------------------
# # Global cached model (loaded only once)
# # ---------------------------------------------------
# _model = None


# def _get_model():
#     """
#     Lazy-load embedding model only once.
#     Prevents reloading model for every call.
#     """
#     global _model
#     if _model is None:
#         print("[Embedding] Loading model...")
#         _model = SentenceTransformer(EMBEDDING_MODEL)
#     return _model


# # ---------------------------------------------------
# # 1️⃣ Batch Embedding (Airflow pipeline use)
# # ---------------------------------------------------
# def generate_embeddings():
#     """
#     Generate embeddings for bills that don't yet have them.
#     Used inside Airflow DAG.
#     """

#     supabase = get_supabase()
#     model = _get_model()

#     bills = (
#         supabase.table("uk_bills_main")
#         .select("bill_id, summary")
#         .not_.is_("summary", None)
#         .is_("embedding", None)
#         .limit(50)
#         .execute()
#     )

#     if not bills.data:
#         print("[Processing] No bills pending embedding.")
#         return

#     print(f"[Processing] Generating embeddings for {len(bills.data)} bills")

#     for bill in bills.data:

#         bill_id = bill["bill_id"]
#         summary = bill["summary"]

#         try:
#             embedding = model.encode(summary).tolist()

#             supabase.table("uk_bills_main").update(
#                 {"embedding": embedding}
#             ).eq("bill_id", bill_id).execute()

#             print(f"[Processing] Embedding stored for {bill_id}")

#         except Exception as e:
#             print(f"[Processing] Embedding failed for {bill_id}: {e}")


# # ---------------------------------------------------
# # 2️⃣ Single Query Embedding (Streamlit semantic search)
# # ---------------------------------------------------
# def generate_embedding(text: str):
#     """
#     Generate embedding for a single query string.
#     Used in Streamlit semantic search.
#     """

#     if not text or not text.strip():
#         return []

#     model = _get_model()
#     return model.encode(text).tolist()