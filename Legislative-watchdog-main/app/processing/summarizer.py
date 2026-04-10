# import time
# from groq import Groq
# from airflow.models import Variable
# from app.database.supabase_client import get_supabase
# from app.config.settings import GROQ_MODEL


# def generate_summary():

#     client = Groq(api_key=Variable.get("GROQ_API_KEY"))
#     supabase = get_supabase()

#     bills = (
#         supabase.table("uk_bills_main")
#         .select("bill_id, full_text")
#         .eq("text_extracted", True)
#         .is_("summary", None)
#         .limit(20)
#         .execute()
#     )

#     if not bills.data:
#         print("[Processing] No bills pending summarization.")
#         return

#     for bill in bills.data:

#         bill_id = bill["bill_id"]
#         full_text = bill["full_text"]

#         if not full_text:
#             continue

#         try:
#             trimmed_text = full_text[:12000]

#             response = client.chat.completions.create(
#                 model=GROQ_MODEL,
#                 messages=[
#                     {
#                         "role": "system",
#                         "content": "You are a UK legal policy analyst."
#                     },
#                     {
#                         "role": "user",
#                         "content": f"Summarize this UK Parliament bill:\n\n{trimmed_text}"
#                     }
#                 ],
#                 temperature=0.3
#             )

#             summary = response.choices[0].message.content.strip()

#             supabase.table("uk_bills_main").update(
#                 {"summary": summary}
#             ).eq("bill_id", bill_id).execute()

#             print(f"[Processing] Summary stored for bill {bill_id}")
#             time.sleep(2)

#         except Exception as e:
#             print(f"[Processing] Summary failed for {bill_id}: {e}")