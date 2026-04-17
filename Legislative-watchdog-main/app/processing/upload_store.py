# import requests
# import time
# from app.database.supabase_client import get_supabase
# from app.config.settings import BUCKET_NAME


# def upload_and_store(bill_pdf_list):
#     """
#     Upload PDFs to Supabase Storage
#     Store metadata in uk_bills_main table
#     """

#     supabase = get_supabase()

#     for item in bill_pdf_list:

#         bill = item["bill"]
#         pdf_url = item["pdf_url"]
#         bill_id = bill["billId"]

#         try:
#             pdf_response = requests.get(pdf_url, timeout=40)
#             pdf_response.raise_for_status()

#             raw_title = bill.get("shortTitle", f"bill_{bill_id}")
#             safe_title = "".join(
#                 c for c in raw_title if c.isalnum() or c in (" ", "_")
#             ).strip().replace(" ", "_")

#             file_name = f"{safe_title}.pdf"
#             file_path = f"uk_bills/{file_name}"

#             supabase.storage.from_(BUCKET_NAME).upload(
#                 file_path,
#                 pdf_response.content,
#                 {"content-type": "application/pdf"}
#             )

#             public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)

#             supabase.table("uk_bills_main").upsert(
#                 {
#                     "bill_id": bill_id,
#                     "title": bill.get("shortTitle"),
#                     "introduced_date": bill.get("introducedDate"),
#                     "current_stage": bill.get("currentStage", {}).get("stage"),
#                     "sponsor": bill.get("sponsors", [{}])[0].get("name"),
#                     "pdf_storage_path": file_path,
#                     "pdf_public_url": public_url,
#                     "text_extracted": False
#                 },
#                 on_conflict="bill_id"
#             ).execute()

#             print(f"[Processing] Stored: {file_name}")
#             time.sleep(0.2)

#         except Exception as e:
#             print(f"[Processing] Error processing bill {bill_id}: {e}")