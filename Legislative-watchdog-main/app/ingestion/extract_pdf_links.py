# import requests
# import time
# from app.config.settings import BASE_URL
# from app.database.supabase_client import get_supabase


# def extract_main_pdf(bills):
#     """
#     For each bill, fetch publications and extract ONE main PDF URL.
#     Skips bills already stored in Supabase.
#     Returns list of dictionaries: {bill, pdf_url}
#     """

#     supabase = get_supabase()
#     bill_pdf_list = []

#     for bill in bills:

#         bill_id = bill["billId"]

#         # Check if already exists
#         existing = (
#             supabase.table("uk_bills_main")
#             .select("bill_id")
#             .eq("bill_id", bill_id)
#             .execute()
#         )

#         if existing.data:
#             print(f"[Ingestion] Skipping bill {bill_id} (already exists)")
#             continue

#         try:
#             pub_url = f"{BASE_URL}/Bills/{bill_id}/Publications"
#             response = requests.get(pub_url, timeout=20)
#             response.raise_for_status()

#             publications = response.json().get("publications", [])
#             main_pdf_url = None

#             for pub in publications:
#                 for file in pub.get("files", []):
#                     if file.get("contentType") == "application/pdf":

#                         publication_id = pub.get("id")
#                         document_id = file.get("id")

#                         if publication_id and document_id:
#                             main_pdf_url = (
#                                 f"{BASE_URL}/Publications/"
#                                 f"{publication_id}/Documents/"
#                                 f"{document_id}/Download"
#                             )
#                             break

#                 if main_pdf_url:
#                     break

#             if main_pdf_url:
#                 bill_pdf_list.append({
#                     "bill": bill,
#                     "pdf_url": main_pdf_url
#                 })

#             time.sleep(0.2)

#         except Exception as e:
#             print(f"[Ingestion] Error for bill {bill_id}: {e}")

#     print(f"[Ingestion] Extracted PDFs for {len(bill_pdf_list)} bills")

#     return bill_pdf_list