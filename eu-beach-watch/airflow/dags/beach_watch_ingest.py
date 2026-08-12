"""
beach_watch_ingest — annual ingest DAG for EU Beach Water Quality Monitor.

Runs each June when the European Environment Agency (EEA) publishes the new
bathing-season classifications. Ingests the full site layer, the recent
per-sample bacterial readings, identifies "interesting" (declining) sites and
enriches those with Open-Meteo rainfall, then runs the dbt transformation stack.

This DAG only ever upserts — it never wipes data. To reload everything from
scratch (e.g. after a schema change), run scripts/reload_all_data.py manually;
that logic intentionally lives outside Airflow.

Conventions (see .claude/rules/airflow.md):
  - Heavy imports (requests, pandas) live INSIDE task functions.
  - All paths resolved relative to this file via DAG_DIR — never absolute.
  - DB access via BaseHook.get_connection(DB_CONN_ID); never hardcode creds.
"""

import os
import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.hooks.base import BaseHook
from airflow.operators.python import PythonOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator

from beach_watch_common import CREATE_SCHEMA_SQL
from beach_watch_common import ingest_sites as _ingest_sites_impl
from beach_watch_common import ingest_samples as _ingest_samples_impl

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Config / constants
# --------------------------------------------------------------------------- #
DAG_DIR = os.path.dirname(os.path.abspath(__file__))
DBT_DIR = os.path.join(DAG_DIR, "dbt")

DB_CONN_ID = "beach_watch_db"

SAMPLE_START_YEAR = 2019  # demo window for the annual DAG; full 2008+ history
SAMPLE_END_YEAR = 2024    # is loaded once via scripts/reload_all_data.py

OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
RAINFALL_LOOKBACK_DAYS = 7
INTERESTING_SITES_LIMIT = 500


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _connect():
    import psycopg2
    conn = BaseHook.get_connection(DB_CONN_ID)
    return psycopg2.connect(
        host=conn.host, port=conn.port, dbname=conn.schema,
        user=conn.login, password=conn.password,
    )


def _dbt_env():
    conn = BaseHook.get_connection(DB_CONN_ID)
    env = os.environ.copy()
    env.update({
        "BEACH_WATCH_HOST":     conn.host or "",
        "BEACH_WATCH_PORT":     str(conn.port or 5432),
        "BEACH_WATCH_USER":     conn.login or "",
        "BEACH_WATCH_PASSWORD": conn.password or "",
        "BEACH_WATCH_DBNAME":   conn.schema or "",
    })
    return env


# --------------------------------------------------------------------------- #
# Task callables — thin Airflow wrappers around beach_watch_common, which
# holds the actual ingestion logic shared with scripts/reload_all_data.py.
# --------------------------------------------------------------------------- #
def ingest_sites(**context):
    pg = _connect()
    try:
        _ingest_sites_impl(pg)
    finally:
        pg.close()


def ingest_samples(**context):
    pg = _connect()
    try:
        _ingest_samples_impl(pg, SAMPLE_START_YEAR, SAMPLE_END_YEAR)
    finally:
        pg.close()


def identify_interesting_sites(**context):
    """
    Identify ~INTERESTING_SITES_LIMIT sites worth rainfall enrichment.
    Selects: (a) sites with declining 5-year classification trend,
             (b) sites with high E.coli variance.
    Pushes list of bathing_water_id to XCom.
    """
    import psycopg2.extras

    def score(cls):
        mapping = {"excellent": 4, "good": 3, "sufficient": 2, "poor": 1}
        return mapping.get((cls or "").lower(), None)

    pg = _connect()
    try:
        with pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT bathing_water_id,
                       class_2020, class_2021, class_2022, class_2023, class_2024
                FROM raw.bathing_sites
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            """)
            rows = cur.fetchall()

        if not rows:
            context["ti"].xcom_push(key="interesting_sites", value=[])
            return []

        scored = []
        for r in rows:
            s2020 = score(r["class_2020"])
            s2024 = score(r["class_2024"])
            if s2020 is not None and s2024 is not None:
                scored.append((r["bathing_water_id"], s2024 - s2020))

        scored.sort(key=lambda x: x[1])
        declining_ids = [bw_id for bw_id, _ in scored[:INTERESTING_SITES_LIMIT // 2]]

        with pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT bathing_water_id
                FROM raw.samples
                WHERE ecoli_cfu IS NOT NULL
                GROUP BY bathing_water_id
                ORDER BY stddev(ecoli_cfu) DESC NULLS LAST
                LIMIT %s
            """, (INTERESTING_SITES_LIMIT // 2,))
            high_var_ids = [r["bathing_water_id"] for r in cur.fetchall()]
    finally:
        pg.close()

    interesting_ids = list(set(declining_ids + high_var_ids))[:INTERESTING_SITES_LIMIT]
    logger.info("Identified %d interesting sites for rainfall enrichment", len(interesting_ids))
    context["ti"].xcom_push(key="interesting_sites", value=interesting_ids)
    return interesting_ids


def enrich_rainfall(**context):
    """
    Fetch 7-day cumulative rainfall from Open-Meteo for each interesting site,
    joined to that site's sample dates. Upserts into raw.site_rainfall.
    """
    import requests
    import psycopg2.extras
    import time
    from datetime import timedelta as td

    interesting_ids = context["ti"].xcom_pull(
        task_ids="identify_interesting_sites", key="interesting_sites"
    ) or []

    if not interesting_ids:
        logger.info("No interesting sites to enrich — skipping rainfall step")
        return

    db = BaseHook.get_connection(DB_CONN_ID)
    pg_conn = _connect()

    with pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT s.bathing_water_id, s.latitude, s.longitude,
                   array_agg(DISTINCT samp.sample_date ORDER BY samp.sample_date) AS sample_dates
            FROM raw.bathing_sites s
            JOIN raw.samples samp USING (bathing_water_id)
            WHERE s.bathing_water_id = ANY(%s)
              AND s.latitude IS NOT NULL
              AND samp.sample_date IS NOT NULL
            GROUP BY s.bathing_water_id, s.latitude, s.longitude
        """, (interesting_ids,))
        site_rows = cur.fetchall()

    # Close the read connection — we'll open a fresh one for writes so the
    # long HTTP loop below doesn't hold an idle connection open.
    pg_conn.close()

    upsert_sql = """
        INSERT INTO raw.site_rainfall (bathing_water_id, sample_date, precip_7d_mm, ingested_at)
        VALUES %s
        ON CONFLICT (bathing_water_id, sample_date) DO UPDATE SET
            precip_7d_mm = EXCLUDED.precip_7d_mm,
            ingested_at  = CURRENT_TIMESTAMP
    """

    enriched = 0
    errors = 0
    for row in site_rows:
        bw_id = row["bathing_water_id"]
        lat = float(row["latitude"])
        lon = float(row["longitude"])
        sample_dates = row["sample_dates"]
        if not sample_dates:
            continue

        min_date = min(sample_dates)
        max_date = max(sample_dates)
        start_str = str(min_date - td(days=RAINFALL_LOOKBACK_DAYS))
        end_str = str(max_date)

        time.sleep(0.5)  # stay within Open-Meteo free tier rate limits
        try:
            resp = requests.get(OPEN_METEO_URL, params={
                "latitude": lat,
                "longitude": lon,
                "start_date": start_str,
                "end_date": end_str,
                "daily": "precipitation_sum",
                "timezone": "UTC",
            }, timeout=30)
            if resp.status_code == 429:
                logger.warning("Rate limited by Open-Meteo, backing off 60s for %s", bw_id)
                time.sleep(60)
                resp = requests.get(OPEN_METEO_URL, params={
                    "latitude": lat, "longitude": lon,
                    "start_date": start_str, "end_date": end_str,
                    "daily": "precipitation_sum", "timezone": "UTC",
                }, timeout=30)
            resp.raise_for_status()
            meteo = resp.json()
        except Exception as e:
            logger.warning("Open-Meteo failed for %s: %s", bw_id, e)
            errors += 1
            continue

        daily_dates = meteo.get("daily", {}).get("time", [])
        daily_precip = meteo.get("daily", {}).get("precipitation_sum", [])
        precip_by_date = dict(zip(daily_dates, daily_precip))

        rows = []
        for sd in sample_dates:
            total = 0.0
            for d_offset in range(RAINFALL_LOOKBACK_DAYS):
                d = str(sd - td(days=d_offset))
                total += precip_by_date.get(d) or 0.0
            rows.append((bw_id, str(sd), round(total, 2), datetime.utcnow()))

        if rows:
            import psycopg2
            write_conn = psycopg2.connect(
                host=db.host, port=db.port, dbname=db.schema,
                user=db.login, password=db.password,
            )
            try:
                with write_conn.cursor() as cur:
                    psycopg2.extras.execute_values(cur, upsert_sql, rows)
                write_conn.commit()
                enriched += len(rows)
            finally:
                write_conn.close()

    logger.info("Rainfall enrichment complete. %d rows upserted, %d sites skipped", enriched, errors)


# --------------------------------------------------------------------------- #
# DAG definition
# --------------------------------------------------------------------------- #
default_args = {
    "owner": "dataflow",
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="beach_watch_ingest",
    default_args=default_args,
    description="Annual upsert of EEA bathing-water quality + rainfall enrichment",
    start_date=datetime(2024, 6, 1),
    schedule_interval="0 3 1 6 *",  # 03:00 on 1 June each year
    catchup=False,
    max_active_runs=1,
    tags=["eu-beach-watch"],
) as dag:

    create_schema = SQLExecuteQueryOperator(
        task_id="create_schema",
        conn_id=DB_CONN_ID,
        sql=CREATE_SCHEMA_SQL,
        autocommit=True,
    )

    sites = PythonOperator(
        task_id="ingest_sites",
        python_callable=ingest_sites,
    )

    samples = PythonOperator(
        task_id="ingest_samples",
        python_callable=ingest_samples,
    )

    interesting = PythonOperator(
        task_id="identify_interesting_sites",
        python_callable=identify_interesting_sites,
    )

    rainfall = PythonOperator(
        task_id="enrich_rainfall",
        python_callable=enrich_rainfall,
    )

    def _run_dbt(**context):
        import subprocess
        env = _dbt_env()
        result = subprocess.run(
            ["dbt", "run", "--profiles-dir", "."],
            cwd=DBT_DIR,
            env=env,
            capture_output=True,
            text=True,
        )
        logger.info(result.stdout)
        if result.returncode != 0:
            logger.error(result.stderr)
            raise RuntimeError(f"dbt run failed (exit {result.returncode})")

    run_dbt = PythonOperator(
        task_id="run_dbt",
        python_callable=_run_dbt,
    )

    create_schema >> [sites, samples]
    [sites, samples] >> interesting >> rainfall >> run_dbt
