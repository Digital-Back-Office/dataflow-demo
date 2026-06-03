from airflow import DAG
from airflow.decorators import task
from airflow.hooks.base import BaseHook
from airflow.models import Variable
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from datetime import datetime, timedelta
import json
import os
import time


DEFAULT_ARGS = {
    "owner": "airflow",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}

BASE_URL = "https://bills-api.parliament.uk/api/v1"
MAX_BILLS = 50
DB_CONN_ID = "demo_db"


def get_data_path():
    if os.getenv("RUNTIME"):
        return "/opt/airflow/shared/legislative-watchdog/uk-bills-data"

    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(current_dir)
    return os.path.join(repo_root, "data")


DATA_DIR = get_data_path()
PDF_DIR = os.path.join(DATA_DIR, "uk_bills")
os.makedirs(PDF_DIR, exist_ok=True)


def get_db_hook():
    return BaseHook.get_hook(conn_id=DB_CONN_ID)


def run_query(sql, params=None, fetch=False):
    conn = get_db_hook().get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            rows = cursor.fetchall() if fetch else None
        conn.commit()
        return rows
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def sanitize_pdf_filename(raw_title, bill_id):
    safe_title = "".join(
        c for c in raw_title if c.isalnum() or c in (" ", "_")
    ).strip().replace(" ", "_")
    safe_title = safe_title[:80].strip("_")
    if not safe_title:
        safe_title = f"bill_{bill_id}"
    return f"{bill_id}_{safe_title}.pdf"


CREATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS uk_bills_main (
    bill_id TEXT PRIMARY KEY,
    title TEXT,
    introduced_date DATE,
    current_stage TEXT,
    sponsor TEXT,
    pdf_storage_path TEXT,
    pdf_public_url TEXT,
    full_text TEXT,
    summary TEXT,
    industry_tags JSONB,
    embedding JSONB,
    text_extracted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_uk_bills_main_text_extracted
    ON uk_bills_main (text_extracted);

CREATE INDEX IF NOT EXISTS idx_uk_bills_main_summary
    ON uk_bills_main (summary);

CREATE INDEX IF NOT EXISTS idx_uk_bills_main_industry_tags
    ON uk_bills_main (industry_tags);

CREATE INDEX IF NOT EXISTS idx_uk_bills_main_embedding
    ON uk_bills_main (embedding);
"""


with DAG(
    dag_id="uk_bills_single_pdf_ingestion",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["uk_parliament", "bills"],
) as dag:

    create_schema = SQLExecuteQueryOperator(
        task_id="create_schema",
        conn_id=DB_CONN_ID,
        sql=[stmt.strip() for stmt in CREATE_SCHEMA_SQL.split(";") if stmt.strip()],
        autocommit=True,
    )

    # ---------------------------------------------------
    # 1️⃣ Fetch Latest Bills
    # ---------------------------------------------------
    @task
    def get_latest_bills():
        import requests

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
        import requests
        from supabase import create_client

        bill_pdf_list = []

        for bill in bills:

            bill_id = str(bill["billId"])

            existing = run_query(
                "SELECT pdf_storage_path FROM uk_bills_main WHERE bill_id = %s",
                (bill_id,),
                fetch=True,
            )

            if existing:
                existing_path = existing[0][0]
                if existing_path and os.path.exists(existing_path):
                    print(f"Skipping bill {bill_id} (already exists)")
                    continue
                print(f"Rebuilding bill {bill_id} because the stored PDF is missing")

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
        import requests
        from supabase import create_client

        for item in bill_pdf_list:

            bill = item["bill"]
            pdf_url = item["pdf_url"]
            bill_id = str(bill["billId"])

            try:
                pdf_response = requests.get(pdf_url, timeout=40)
                pdf_response.raise_for_status()

                raw_title = bill.get("shortTitle", f"bill_{bill_id}")
                file_name = sanitize_pdf_filename(raw_title, bill_id)
                file_path = os.path.join(PDF_DIR, file_name)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                with open(file_path, "wb") as f:
                    f.write(pdf_response.content)

                public_url = file_path
                introduced_date = bill.get("introducedDate") or None
                current_stage = (bill.get("currentStage") or {}).get("stage")
                sponsors = bill.get("sponsors") or [{}]
                sponsor = sponsors[0].get("name")

                run_query(
                    """
                    INSERT INTO uk_bills_main (
                        bill_id,
                        title,
                        introduced_date,
                        current_stage,
                        sponsor,
                        pdf_storage_path,
                        pdf_public_url,
                        full_text,
                        summary,
                        industry_tags,
                        embedding,
                        text_extracted,
                        created_at,
                        updated_at
                    ) VALUES (
                        %s,
                        %s,
                        %s::date,
                        %s,
                        %s,
                        %s,
                        %s,
                        NULL,
                        NULL,
                        NULL,
                        NULL,
                        FALSE,
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (bill_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        introduced_date = EXCLUDED.introduced_date,
                        current_stage = EXCLUDED.current_stage,
                        sponsor = EXCLUDED.sponsor,
                        pdf_storage_path = EXCLUDED.pdf_storage_path,
                        pdf_public_url = EXCLUDED.pdf_public_url,
                        full_text = NULL,
                        summary = NULL,
                        industry_tags = NULL,
                        embedding = NULL,
                        text_extracted = FALSE,
                        updated_at = NOW();
                    """,
                    (
                        bill_id,
                        raw_title,
                        introduced_date,
                        current_stage,
                        sponsor,
                        file_path,
                        public_url,
                    ),
                )

                print(f"Stored: {file_name}")
                time.sleep(0.2)

            except Exception as e:
                print(f"Error processing bill {bill_id}: {e}")

    # ---------------------------------------------------
    # 4️⃣ Extract Text from PDFs
    # ---------------------------------------------------
    @task
    def extract_pdf_text():
        from supabase import create_client
        import pdfplumber

        bills = run_query(
            """
            SELECT bill_id, pdf_storage_path
            FROM uk_bills_main
            WHERE text_extracted = FALSE
              AND pdf_storage_path IS NOT NULL
            """,
            fetch=True,
        )

        if not bills:
            print("No PDFs pending extraction.")
            return

        print(f"Extracting text for {len(bills)} bills")

        for bill_id, file_path in bills:

            try:
                if not file_path or not os.path.exists(file_path):
                    print(f"Error extracting {bill_id}: missing PDF at {file_path}")
                    continue

                with pdfplumber.open(file_path) as pdf:
                    full_text = ""
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            full_text += text + "\n"

                cleaned_text = full_text.replace("\x00", "").strip()

                run_query(
                    """
                    UPDATE uk_bills_main
                    SET full_text = %s,
                        text_extracted = TRUE,
                        updated_at = NOW()
                    WHERE bill_id = %s
                    """,
                    (cleaned_text, bill_id),
                )

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
        from supabase import create_client

        client = Groq(
            api_key=Variable.get("GROQ_API_KEY")
        )

        bills = run_query(
            """
            SELECT bill_id, full_text
            FROM uk_bills_main
            WHERE text_extracted = TRUE
              AND summary IS NULL
            LIMIT 20
            """,
            fetch=True,
        )

        if not bills:
            print("No bills pending summarization.")
            return

        print(f"Generating summaries for {len(bills)} bills")

        for bill_id, full_text in bills:

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

                run_query(
                    """
                    UPDATE uk_bills_main
                    SET summary = %s,
                        updated_at = NOW()
                    WHERE bill_id = %s
                    """,
                    (summary, bill_id),
                )

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

    # ---------------------------------------------------
    # 6️⃣ Generate Industry Tags
    # ---------------------------------------------------
    @task
    def generate_industry_tags():
        import json
        import time
        from groq import Groq
        from supabase import create_client
        
        client = Groq(api_key=Variable.get("GROQ_API_KEY"))

        bills = run_query(
            """
            SELECT bill_id, summary
            FROM uk_bills_main
            WHERE industry_tags IS NULL
              AND summary IS NOT NULL
            LIMIT 10
            """,
            fetch=True,
        )

        if not bills:
            print("No bills pending industry tagging.")
            return

        for bill_id, summary in bills:
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

                if raw_output.startswith("```"):
                    raw_output = raw_output.split("```", 1)[1]
                    if raw_output.startswith("json"):
                        raw_output = raw_output[4:]
                    raw_output = raw_output.strip()

                try:
                    tags = json.loads(raw_output)
                except json.JSONDecodeError:
                    print(f"Invalid JSON for bill {bill_id}: {raw_output}")
                    continue

                tags = list({
                    tag.lower().strip().replace(" ", "_")
                    for tag in tags
                    if isinstance(tag, str) and tag.strip()
                })

                run_query(
                    """
                    UPDATE uk_bills_main
                    SET industry_tags = %s::jsonb,
                        updated_at = NOW()
                    WHERE bill_id = %s
                    """,
                    (json.dumps(tags), bill_id),
                )

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

    # ---------------------------------------------------
    # 7️⃣ Generate Embeddings
    # ---------------------------------------------------
    @task
    def generate_embeddings():
        from sentence_transformers import SentenceTransformer
        from supabase import create_client

        model = SentenceTransformer("all-MiniLM-L6-v2")

        bills = run_query(
            """
            SELECT bill_id, summary
            FROM uk_bills_main
            WHERE summary IS NOT NULL
              AND embedding IS NULL
            LIMIT 50
            """,
            fetch=True,
        )

        if not bills:
            print("No bills pending embedding.")
            return

        print(f"Generating embeddings for {len(bills)} bills")

        for bill_id, summary in bills:
            try:
                embedding = model.encode(summary).tolist()

                run_query(
                    """
                    UPDATE uk_bills_main
                    SET embedding = %s::jsonb,
                        updated_at = NOW()
                    WHERE bill_id = %s
                    """,
                    (json.dumps(embedding), bill_id),
                )

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

    create_schema >> bills >> pdfs >> stored >> text >> summary >> tags >> embeddings
