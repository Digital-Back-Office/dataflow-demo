# from io import BytesIO
# import pdfplumber
# from app.database.supabase_client import get_supabase
# from app.config.settings import BUCKET_NAME


# def extract_pdf_text():
#     """
#     Extract full text from stored PDFs
#     """

#     supabase = get_supabase()

#     bills = (
#         supabase.table("uk_bills_main")
#         .select("*")
#         .eq("text_extracted", False)
#         .execute()
#     )

#     if not bills.data:
#         print("[Processing] No PDFs pending extraction.")
#         return

#     print(f"[Processing] Extracting text for {len(bills.data)} bills")

#     for bill in bills.data:

#         bill_id = bill["bill_id"]
#         file_path = bill["pdf_storage_path"]

#         try:
#             pdf_bytes = supabase.storage.from_(BUCKET_NAME).download(file_path)

#             with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
#                 full_text = ""
#                 for page in pdf.pages:
#                     text = page.extract_text()
#                     if text:
#                         full_text += text + "\n"

#             cleaned_text = full_text.replace("\x00", "").strip()

#             supabase.table("uk_bills_main").update(
#                 {
#                     "full_text": cleaned_text,
#                     "text_extracted": True
#                 }
#             ).eq("bill_id", bill_id).execute()

#             print(f"[Processing] Text extracted for bill {bill_id}")

#         except Exception as e:
#             print(f"[Processing] Error extracting {bill_id}: {e}")