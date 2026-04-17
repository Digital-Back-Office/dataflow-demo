# from airflow import DAG
# from airflow.decorators import task
# from datetime import datetime, timedelta

# from app.ingestion.fetch_bills import fetch_latest_bills
# from app.ingestion.extract_pdf_links import extract_main_pdf
# from app.processing.upload_store import upload_and_store
# from app.processing.pdf_text_extractor import extract_pdf_text
# from app.processing.summarizer import generate_summary
# from app.processing.industry_classifier import generate_industry_tags
# from app.processing.embeddings_generator import generate_embeddings


# DEFAULT_ARGS = {
#     "owner": "airflow",
#     "retries": 2,
#     "retry_delay": timedelta(minutes=2),
# }


# with DAG(
#     dag_id="uk_bills_single_pdf_ingestion",
#     default_args=DEFAULT_ARGS,
#     start_date=datetime(2026, 1, 1),
#     schedule_interval=None,
#     catchup=False,
#     tags=["uk_parliament", "bills"],
# ) as dag:

#     # ---------------------------
#     # 1️⃣ Fetch Latest Bills
#     # ---------------------------
#     @task
#     def get_latest_bills():
#         return fetch_latest_bills()

#     # ---------------------------
#     # 2️⃣ Extract Main PDF Links
#     # ---------------------------
#     @task
#     def extract_main_pdf_task(bills):
#         return extract_main_pdf(bills)

#     # ---------------------------
#     # 3️⃣ Upload & Store Metadata
#     # ---------------------------
#     @task
#     def upload_and_store_task(pdfs):
#         upload_and_store(pdfs)

#     # ---------------------------
#     # 4️⃣ Extract PDF Text
#     # ---------------------------
#     @task
#     def extract_pdf_text_task():
#         extract_pdf_text()

#     # ---------------------------
#     # 5️⃣ Generate Summary
#     # ---------------------------
#     @task
#     def generate_summary_task():
#         generate_summary()

#     # ---------------------------
#     # 6️⃣ Generate Industry Tags
#     # ---------------------------
#     @task
#     def generate_industry_tags_task():
#         generate_industry_tags()

#     # ---------------------------
#     # 7️⃣ Generate Embeddings
#     # ---------------------------
#     @task
#     def generate_embeddings_task():
#         generate_embeddings()

#     # DAG Flow
#     bills = get_latest_bills()
#     pdfs = extract_main_pdf_task(bills)
#     stored = upload_and_store_task(pdfs)
#     text = extract_pdf_text_task()
#     summary = generate_summary_task()
#     tags = generate_industry_tags_task()
#     embeddings = generate_embeddings_task()

#     bills >> pdfs >> stored >> text >> summary >> tags >> embeddings




