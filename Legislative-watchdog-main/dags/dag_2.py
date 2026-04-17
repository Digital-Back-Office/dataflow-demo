from airflow import DAG
from airflow.decorators import task
from airflow.models import Variable
from datetime import datetime, timedelta
import requests
import time
from supabase import create_client
from io import BytesIO
import pdfplumber
from groq import Groq


DEFAULT_ARGS = {
    "owner": "airflow",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}

BASE_URL = "https://bills-api.parliament.uk/api/v1"
MAX_BILLS = 50

with DAG(
    dag_id="uk_bills_single_pdf_ingestion",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["uk_parliament", "bills"],
) as dag:

    # ---------------------------------------------------
    # 1️⃣ Fetch Latest Bills
    # ---------------------------------------------------
    @task
    def get_latest_bills():

        all_bills = []
        page = 1
        page_size = 50

        while len(all_bills) < MAX_BILLS:

            url = f"{BASE_URL}/Bills"
            params = {
                "SortOrder": "DateUpdatedDescending",
                "Page": page,
                "Take": page_size
            }

            print(f"Fetching page {page}")

            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()

            items = response.json().get("items", [])
            if not items:
                break

            all_bills.extend(items)
            page += 1
            time.sleep(0.2)

        selected = all_bills[:MAX_BILLS]
        print(f"Collected {len(selected)} bills")
        return selected

    # ---------------------------------------------------
    # 2️⃣ Extract ONE Main PDF per Bill
    # ---------------------------------------------------
    @task
    def extract_main_pdf(bills):

        supabase = create_client(
            Variable.get("SUPABASE_URL"),
            Variable.get("SUPABASE_SERVICE_ROLE_KEY")
        )

        bill_pdf_list = []

        for bill in bills:

            bill_id = bill["billId"]

            existing = supabase.table("uk_bills_main") \
                .select("bill_id") \
                .eq("bill_id", bill_id) \
                .execute()

            if existing.data:
                print(f"Skipping bill {bill_id} (already exists)")
                continue

            try:
                pub_url = f"{BASE_URL}/Bills/{bill_id}/Publications"
                response = requests.get(pub_url, timeout=20)
                response.raise_for_status()

                publications = response.json().get("publications", [])
                main_pdf_url = None

                for pub in publications:
                    for file in pub.get("files", []):
                        if file.get("contentType") == "application/pdf":

                            publication_id = pub.get("id")
                            document_id = file.get("id")

                            if publication_id and document_id:
                                main_pdf_url = (
                                    f"{BASE_URL}/Publications/"
                                    f"{publication_id}/Documents/"
                                    f"{document_id}/Download"
                                )
                                break
                    if main_pdf_url:
                        break

                if main_pdf_url:
                    bill_pdf_list.append({
                        "bill": bill,
                        "pdf_url": main_pdf_url
                    })

                time.sleep(0.2)

            except Exception as e:
                print(f"Error for bill {bill_id}: {e}")

        return bill_pdf_list

    # ---------------------------------------------------
    # 3️⃣ Upload PDF + Store Metadata
    # ---------------------------------------------------
    @task
    def upload_and_store(bill_pdf_list):

        supabase = create_client(
            Variable.get("SUPABASE_URL"),
            Variable.get("SUPABASE_SERVICE_ROLE_KEY")
        )

        bucket_name = "legislative-pdfs"

        for item in bill_pdf_list:

            bill = item["bill"]
            pdf_url = item["pdf_url"]
            bill_id = bill["billId"]

            try:
                pdf_response = requests.get(pdf_url, timeout=40)
                pdf_response.raise_for_status()

                raw_title = bill.get("shortTitle", f"bill_{bill_id}")
                safe_title = "".join(
                    c for c in raw_title if c.isalnum() or c in (" ", "_")
                ).strip().replace(" ", "_")

                file_name = f"{safe_title}.pdf"
                file_path = f"uk_bills/{file_name}"

                supabase.storage.from_(bucket_name).upload(
                    file_path,
                    pdf_response.content,
                    {"content-type": "application/pdf"}
                )

                public_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
                last_update_raw = bill.get("lastUpdate")
                introduced_date = last_update_raw[:10] if last_update_raw else None

                supabase.table("uk_bills_main").upsert(
                    {
                        "bill_id": bill_id,
                        "title": bill.get("shortTitle"),
                        "introduced_date": bill.get("introducedDate"),
                        "current_stage": bill.get("currentStage", {}).get("stage"),
                        "sponsor": bill.get("sponsors", [{}])[0].get("name"),
                        "pdf_storage_path": file_path,
                        "pdf_public_url": public_url,
                        "text_extracted": False
                    },
                    on_conflict="bill_id"
                ).execute()

                print(f"Stored: {file_name}")
                time.sleep(0.2)

            except Exception as e:
                print(f"Error processing bill {bill_id}: {e}")

    # ---------------------------------------------------
    # 4️⃣ Extract Text from PDFs
    # ---------------------------------------------------
    @task
    def extract_pdf_text():

        supabase = create_client(
            Variable.get("SUPABASE_URL"),
            Variable.get("SUPABASE_SERVICE_ROLE_KEY")
        )

        bucket_name = "legislative-pdfs"

        bills = supabase.table("uk_bills_main") \
            .select("*") \
            .eq("text_extracted", False) \
            .execute()

        if not bills.data:
            print("No PDFs pending extraction.")
            return

        print(f"Extracting text for {len(bills.data)} bills")

        for bill in bills.data:

            bill_id = bill["bill_id"]
            file_path = bill["pdf_storage_path"]

            try:
                pdf_bytes = supabase.storage.from_(bucket_name).download(file_path)

                with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                    full_text = ""
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            full_text += text + "\n"

                cleaned_text = full_text.replace("\x00", "").strip()

                supabase.table("uk_bills_main").update(
                    {
                        "full_text": cleaned_text,
                        "text_extracted": True
                    }
                ).eq("bill_id", bill_id).execute()

                print(f"Text extracted for bill {bill_id}")

            except Exception as e:
                print(f"Error extracting {bill_id}: {e}")

    # ---------------------------------------------------
    # 5️⃣ Generate Summary 
    # ---------------------------------------------------
    @task
    def generate_summary():

        from groq import Groq
        import time

        client = Groq(
            api_key=Variable.get("GROQ_API_KEY")
        )

        supabase = create_client(
            Variable.get("SUPABASE_URL"),
            Variable.get("SUPABASE_SERVICE_ROLE_KEY")
        )

        bills = supabase.table("uk_bills_main") \
            .select("bill_id, full_text") \
            .eq("text_extracted", True) \
            .is_("summary", None) \
            .limit(20) \
            .execute()

        if not bills.data:
            print("No bills pending summarization.")
            return

        print(f"Generating summaries for {len(bills.data)} bills")

        for bill in bills.data:

            bill_id = bill["bill_id"]
            full_text = bill["full_text"]

            if not full_text or len(full_text.strip()) == 0:
                print(f"Skipping empty text for bill {bill_id}")
                continue

            try:
                trimmed_text = full_text[:12000]

                response = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a UK legal policy analyst. "
                                "Summarize legislation clearly for business leaders."
                            )
                        },
                        {
                            "role": "user",
                            "content": f"""
                            Summarize this UK Parliament bill in plain English.

                            Provide:
                            1. Short Overview (5–7 lines)
                            2. Key Changes (bullet points)
                            3. Who Is Affected
                            4. Business Impact
                            5. Important Dates (if mentioned)

                            Bill Text:
                            {trimmed_text}
                            """
                        }
                    ],
                    temperature=0.3
                )

                summary = response.choices[0].message.content.strip()

                supabase.table("uk_bills_main").update(
                    {"summary": summary}
                ).eq("bill_id", bill_id).execute()

                print(f"Summary stored for bill {bill_id}")

                time.sleep(2)

            except Exception as e:
                error_message = str(e)

                if "429" in error_message:
                    print("Groq rate limit hit. Sleeping 10 seconds...")
                    time.sleep(10)
                    continue

                print(f"Groq summary failed for {bill_id}: {e}")
                continue

    @task
    def generate_industry_tags():
        import json
        import time
        from groq import Groq
        
        client = Groq(api_key=Variable.get("GROQ_API_KEY"))
        supabase = create_client(
            Variable.get("SUPABASE_URL"),
            Variable.get("SUPABASE_SERVICE_ROLE_KEY")
        )

        bills = supabase.table("uk_bills_main") \
            .select("bill_id, summary") \
            .is_("industry_tags", None) \
            .not_.is_("summary", None) \
            .limit(10) \
            .execute()

        if not bills.data:
            print("No bills pending industry tagging.")
            return

        for bill in bills.data:
            bill_id = bill["bill_id"]
            summary = bill["summary"]

            try:
                response = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a regulatory industry classifier for UK Parliament bills. "
                                "Identify which industries or policy domains are most relevant to the bill. "
                                "Return ONLY a raw JSON array of short, lowercase, snake_case industry tags. "
                                "No explanation. No markdown. Just the array."
                            )
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Classify the following UK Parliament bill summary into relevant industry tags.\n\n"
                                f"Rules:\n"
                                f"- Return a JSON array of short, lowercase, snake_case tags (e.g. [\"fintech\", \"data_protection\"]).\n"
                                f"- Include as many relevant tags as needed.\n"
                                f"- If nothing is relevant, return [].\n\n"
                                f"Summary:\n{summary}"
                            )
                        }
                    ],
                    temperature=0
                )

                raw_output = response.choices[0].message.content.strip()
                print(f"Raw tag output for {bill_id}: {raw_output}")

                # Strip markdown code fences if present
                if raw_output.startswith("```"):
                    raw_output = raw_output.split("```")[1]
                    if raw_output.startswith("json"):
                        raw_output = raw_output[4:]
                    raw_output = raw_output.strip()

                try:
                    tags = json.loads(raw_output)
                except json.JSONDecodeError:
                    print(f"Invalid JSON for bill {bill_id}: {raw_output}")
                    continue

                # Normalise tags: lowercase + snake_case spaces
                tags = list({
                    tag.lower().strip().replace(" ", "_")
                    for tag in tags
                    if isinstance(tag, str) and tag.strip()
                })

                supabase.table("uk_bills_main").update(
                    {"industry_tags": tags}
                ).eq("bill_id", bill_id).execute()

                print(f"Tags stored for bill {bill_id}: {tags}")
                time.sleep(2)

            except Exception as e:
                error_message = str(e)
                if "429" in error_message:
                    print("Groq rate limit hit. Sleeping 10 seconds...")
                    time.sleep(10)
                    continue
                print(f"Groq tagging failed for {bill_id}: {e}")
                continue


    @task
    def generate_embeddings():
        from sentence_transformers import SentenceTransformer

        supabase = create_client(
            Variable.get("SUPABASE_URL"),
            Variable.get("SUPABASE_SERVICE_ROLE_KEY")
        )

        model = SentenceTransformer("all-MiniLM-L6-v2")

        bills = supabase.table("uk_bills_main") \
            .select("bill_id, summary") \
            .not_.is_("summary", None) \
            .is_("embedding", None) \
            .limit(50) \
            .execute()

        if not bills.data:
            print("No bills pending embedding.")
            return

        print(f"Generating embeddings for {len(bills.data)} bills")

        for bill in bills.data:
            bill_id = bill["bill_id"]
            summary = bill["summary"]

            try:
                embedding = model.encode(summary).tolist()

                supabase.table("uk_bills_main").update(
                    {"embedding": embedding}
                ).eq("bill_id", bill_id).execute()

                print(f"Embedding stored for bill {bill_id}")

            except Exception as e:
                print(f"Embedding failed for bill {bill_id}: {e}")
                continue

    # DAG FLOW
    bills = get_latest_bills()
    pdfs = extract_main_pdf(bills)
    stored = upload_and_store(pdfs)
    text = extract_pdf_text()
    summary = generate_summary()
    tags = generate_industry_tags()
    embeddings = generate_embeddings()

    bills >> pdfs >> stored >> text >> summary >> tags >> embeddings
