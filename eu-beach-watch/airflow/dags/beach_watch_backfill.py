"""
beach_watch_backfill — one-shot historical ingest DAG.

Loads the full per-sample bacterial history (2008–2024) from EEA Discodata
into raw.samples in 2-year chunks to bound memory usage. Run manually once;
the annual beach_watch_ingest DAG keeps the recent window fresh.
"""

import os
import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.hooks.base import BaseHook
from airflow.operators.python import PythonOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator

logger = logging.getLogger(__name__)

DAG_DIR = os.path.dirname(os.path.abspath(__file__))
DB_CONN_ID = "beach_watch_db"

DISCODATA_URL = "https://discodata.eea.europa.eu/sql"
DISCODATA_TABLE = "[WISE_BWD].[latest].[timeseries_MonitoringResult]"
DISCODATA_PAGE_SIZE = 1000

BACKFILL_START_YEAR = 2008
BACKFILL_END_YEAR = 2024
BACKFILL_CHUNK_YEARS = 2

from beach_watch_ingest import CREATE_SCHEMA_SQL  # noqa: E402


def backfill_samples(**context):
    """
    Ingest all per-sample readings from BACKFILL_START_YEAR to BACKFILL_END_YEAR
    in BACKFILL_CHUNK_YEARS windows. Upserts with ON CONFLICT DO NOTHING.
    """
    import requests
    import urllib.parse
    import psycopg2
    import psycopg2.extras

    conn = BaseHook.get_connection(DB_CONN_ID)
    pg = psycopg2.connect(
        host=conn.host, port=conn.port, dbname=conn.schema,
        user=conn.login, password=conn.password,
    )
    pg.autocommit = False

    upsert_sql = """
        INSERT INTO raw.samples (sample_id, bathing_water_id, sample_date, ecoli_cfu, enterococci_cfu, ingested_at)
        VALUES %s
        ON CONFLICT (sample_id) DO NOTHING
    """

    total_ingested = 0

    # Iterate over 2-year windows
    chunk_starts = range(BACKFILL_START_YEAR, BACKFILL_END_YEAR + 1, BACKFILL_CHUNK_YEARS)
    for chunk_start in chunk_starts:
        chunk_end = min(chunk_start + BACKFILL_CHUNK_YEARS - 1, BACKFILL_END_YEAR)
        logger.info("Backfilling years %d-%d", chunk_start, chunk_end)

        page = 1
        chunk_rows = 0

        base_query = (
            f"SELECT bathingWaterIdentifier, sampleDate, escherichiaColiValue, intestinalEnterococciValue "
            f"FROM {DISCODATA_TABLE} "
            f"WHERE YEAR(sampleDate) BETWEEN {chunk_start} AND {chunk_end} "
            f"ORDER BY bathingWaterIdentifier, sampleDate"
        )

        while True:
            encoded = urllib.parse.quote(base_query)
            url = f"{DISCODATA_URL}?query={encoded}&p={page}&nrOfHits={DISCODATA_PAGE_SIZE}"
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            if not results:
                break

            rows = []
            for i, rec in enumerate(results):
                bw_id = rec.get("bathingWaterIdentifier")
                sample_date = rec.get("sampleDate", "")[:10] if rec.get("sampleDate") else None
                if not bw_id or not sample_date:
                    continue

                sample_id = f"{bw_id}_{sample_date}_{chunk_start}_{page}_{i}"
                ecoli = rec.get("escherichiaColiValue")
                entero = rec.get("intestinalEnterococciValue")

                rows.append((
                    sample_id, bw_id, sample_date,
                    float(ecoli) if ecoli is not None else None,
                    float(entero) if entero is not None else None,
                    datetime.utcnow(),
                ))

            if rows:
                with pg.cursor() as cur:
                    psycopg2.extras.execute_values(cur, upsert_sql, rows, page_size=500)
                pg.commit()
                chunk_rows += len(rows)
                total_ingested += len(rows)

            logger.info("  Chunk %d-%d page %d: %d rows (total %d)",
                        chunk_start, chunk_end, page, len(results), total_ingested)

            if len(results) < DISCODATA_PAGE_SIZE:
                break
            page += 1

        logger.info("Chunk %d-%d done: %d rows", chunk_start, chunk_end, chunk_rows)

    pg.close()
    logger.info("Backfill complete. Total rows ingested: %d", total_ingested)


default_args = {
    "owner": "dataflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=15),
}

with DAG(
    dag_id="beach_watch_backfill",
    default_args=default_args,
    description="One-shot historical backfill of EEA per-sample data (2008-2024)",
    start_date=datetime(2024, 6, 1),
    schedule_interval=None,
    catchup=False,
    max_active_runs=1,
    tags=["eu-beach-watch", "backfill"],
) as dag:

    create_schema = SQLExecuteQueryOperator(
        task_id="create_schema",
        conn_id=DB_CONN_ID,
        sql=CREATE_SCHEMA_SQL,
        autocommit=True,
    )

    backfill = PythonOperator(
        task_id="backfill_samples",
        python_callable=backfill_samples,
    )

    create_schema >> backfill
