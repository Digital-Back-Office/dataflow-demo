# import json
# import time
# from groq import Groq
# from airflow.models import Variable
# from app.database.supabase_client import get_supabase
# from app.config.settings import GROQ_MODEL


# def generate_industry_tags():

#     client = Groq(api_key=Variable.get("GROQ_API_KEY"))
#     supabase = get_supabase()

#     bills = (
#         supabase.table("uk_bills_main")
#         .select("bill_id, summary")
#         .is_("industry_tags", None)
#         .not_.is_("summary", None)
#         .limit(10)
#         .execute()
#     )

#     if not bills.data:
#         print("[Processing] No bills pending industry tagging.")
#         return

#     for bill in bills.data:

#         bill_id = bill["bill_id"]
#         summary = bill["summary"]

#         try:
#             response = client.chat.completions.create(
#                 model=GROQ_MODEL,
#                 messages=[
#                     {
#                         "role": "system",
#                         "content": (
#                             "Return ONLY a raw JSON array of lowercase snake_case industry tags."
#                         )
#                     },
#                     {
#                         "role": "user",
#                         "content": f"Classify this bill:\n\n{summary}"
#                     }
#                 ],
#                 temperature=0
#             )

#             raw_output = response.choices[0].message.content.strip()

#             if raw_output.startswith("```"):
#                 raw_output = raw_output.split("```")[1].strip()

#             tags = json.loads(raw_output)

#             tags = list({
#                 tag.lower().replace(" ", "_")
#                 for tag in tags if isinstance(tag, str)
#             })

#             supabase.table("uk_bills_main").update(
#                 {"industry_tags": tags}
#             ).eq("bill_id", bill_id).execute()

#             print(f"[Processing] Tags stored for {bill_id}")
#             time.sleep(2)

#         except Exception as e:
#             print(f"[Processing] Tagging failed for {bill_id}: {e}")