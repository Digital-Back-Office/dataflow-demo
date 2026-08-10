"""
beach_watch_ingest — annual ingest DAG for EU Beach Water Quality Monitor.

Runs each June when the European Environment Agency (EEA) publishes the new
bathing-season classifications. Ingests the full site layer, the recent
per-sample bacterial readings, identifies "interesting" (declining) sites and
enriches those with Open-Meteo rainfall, then runs the dbt transformation stack.

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
from airflow.operators.bash import BashOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Config / constants
# --------------------------------------------------------------------------- #
DAG_DIR = os.path.dirname(os.path.abspath(__file__))
DBT_DIR = os.path.join(DAG_DIR, "dbt")

DB_CONN_ID = "beach_watch_db"

# EEA ArcGIS REST — bathing water site layer (layer 3 of the 2024 MapServer).
ARCGIS_URL = (
    "https://marine.discomap.eea.europa.eu/arcgis/rest/services/"
    "BathingWater/BathingWater_Dyna_WM_2024/MapServer/3/query"
)
ARCGIS_PAGE_SIZE = 1000

# EEA Discodata SQL API — per-sample monitoring results.
DISCODATA_URL = "https://discodata.eea.europa.eu/sql"
DISCODATA_TABLE = "[WISE_BWD].[latest].[timeseries_MonitoringResult]"
DISCODATA_PAGE_SIZE = 1000
SAMPLE_START_YEAR = 2019
SAMPLE_END_YEAR = 2024

# Open-Meteo historical weather — free, no auth.
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
RAINFALL_LOOKBACK_DAYS = 7
INTERESTING_SITES_LIMIT = 500

# 11-year classification window: qualityStatus (2024) + minus1..minus10 (2023..2014)
CLASSIFICATION_YEARS = list(range(2014, 2025))  # 2014..2024 inclusive


# --------------------------------------------------------------------------- #
# Schema DDL
# --------------------------------------------------------------------------- #
CREATE_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.bathing_sites (
    bathing_water_id   TEXT PRIMARY KEY,
    name               TEXT,
    country_code       TEXT,
    water_type         TEXT,
    latitude           DOUBLE PRECISION,
    longitude          DOUBLE PRECISION,
    class_2014 TEXT, class_2015 TEXT, class_2016 TEXT, class_2017 TEXT,
    class_2018 TEXT, class_2019 TEXT, class_2020 TEXT, class_2021 TEXT,
    class_2022 TEXT, class_2023 TEXT, class_2024 TEXT,
    ingested_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.samples (
    sample_id          TEXT PRIMARY KEY,
    bathing_water_id   TEXT,
    sample_date        DATE,
    ecoli_cfu          DOUBLE PRECISION,
    enterococci_cfu    DOUBLE PRECISION,
    ingested_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_samples_site ON raw.samples(bathing_water_id);
CREATE INDEX IF NOT EXISTS idx_samples_date ON raw.samples(sample_date);

CREATE TABLE IF NOT EXISTS raw.site_rainfall (
    bathing_water_id   TEXT,
    sample_date        DATE,
    precip_7d_mm       DOUBLE PRECISION,
    ingested_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (bathing_water_id, sample_date)
);
"""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _get_conn_str():
    conn = BaseHook.get_connection(DB_CONN_ID)
    return f"postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}"



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
# Task callables
# --------------------------------------------------------------------------- #
def ingest_sites(**context):
    """
    Ingest the full EEA bathing-water site layer via the ArcGIS REST API.
    Paginates at 1,000 records per call (~23 calls for 22k sites).
    Upserts into raw.bathing_sites.
    """
    import requests
    import psycopg2
    import psycopg2.extras

    # ArcGIS attribute names -> our column names
    # qualityStatus = 2024, qualityStatus_minus1 = 2023, ..., minus10 = 2014
    QUAL_FIELD_TO_YEAR = {"qualityStatus": 2024}
    for i in range(1, 11):
        QUAL_FIELD_TO_YEAR[f"qualityStatus_minus{i}"] = 2024 - i  # 2023..2014

    conn = BaseHook.get_connection(DB_CONN_ID)
    pg = psycopg2.connect(
        host=conn.host, port=conn.port, dbname=conn.schema,
        user=conn.login, password=conn.password,
    )
    pg.autocommit = False

    upsert_sql = """
        INSERT INTO raw.bathing_sites (
            bathing_water_id, name, country_code, water_type,
            latitude, longitude,
            class_2014, class_2015, class_2016, class_2017, class_2018,
            class_2019, class_2020, class_2021, class_2022, class_2023, class_2024,
            ingested_at
        ) VALUES %s
        ON CONFLICT (bathing_water_id) DO UPDATE SET
            name               = EXCLUDED.name,
            country_code       = EXCLUDED.country_code,
            water_type         = EXCLUDED.water_type,
            latitude           = EXCLUDED.latitude,
            longitude          = EXCLUDED.longitude,
            class_2014 = EXCLUDED.class_2014, class_2015 = EXCLUDED.class_2015,
            class_2016 = EXCLUDED.class_2016, class_2017 = EXCLUDED.class_2017,
            class_2018 = EXCLUDED.class_2018, class_2019 = EXCLUDED.class_2019,
            class_2020 = EXCLUDED.class_2020, class_2021 = EXCLUDED.class_2021,
            class_2022 = EXCLUDED.class_2022, class_2023 = EXCLUDED.class_2023,
            class_2024 = EXCLUDED.class_2024,
            ingested_at        = CURRENT_TIMESTAMP
    """

    offset = 0
    total_ingested = 0
    params = {
        "f": "json",
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "resultRecordCount": ARCGIS_PAGE_SIZE,
    }

    while True:
        params["resultOffset"] = offset
        resp = requests.get(ARCGIS_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            break

        rows = []
        for feat in features:
            attrs = feat.get("attributes", {})
            geom = feat.get("geometry", {})

            bw_id = attrs.get("bathingWaterIdentifier") or attrs.get("OBJECTID")
            if not bw_id:
                continue

            # Coordinates: prefer attribute fields, fall back to geometry
            lat = attrs.get("latitude") or (geom.get("y") if geom else None)
            lon = attrs.get("longitude") or (geom.get("x") if geom else None)

            year_classes = {}
            for field, year in QUAL_FIELD_TO_YEAR.items():
                val = attrs.get(field)
                # Normalize: strip whitespace, title-case
                year_classes[year] = val.strip().title() if isinstance(val, str) else None

            rows.append((
                str(bw_id),
                attrs.get("bathingWaterName") or attrs.get("name") or "",
                (attrs.get("countryCode") or "").upper(),
                (attrs.get("bwWaterCategory") or attrs.get("waterBodyType") or "").lower(),
                lat, lon,
                year_classes.get(2014), year_classes.get(2015), year_classes.get(2016),
                year_classes.get(2017), year_classes.get(2018), year_classes.get(2019),
                year_classes.get(2020), year_classes.get(2021), year_classes.get(2022),
                year_classes.get(2023), year_classes.get(2024),
                datetime.utcnow(),
            ))

        if rows:
            with pg.cursor() as cur:
                psycopg2.extras.execute_values(cur, upsert_sql, rows, page_size=500)
            pg.commit()
            total_ingested += len(rows)
            logger.info("Sites ingested so far: %d (offset %d)", total_ingested, offset)

        if not data.get("exceededTransferLimit", False):
            break
        offset += ARCGIS_PAGE_SIZE

    pg.close()
    logger.info("Site ingest complete. Total rows: %d", total_ingested)


def ingest_samples(**context):
    """
    Ingest per-sample bacterial readings from the EEA Discodata SQL API.
    Paginated at 1,000 rows per call for years SAMPLE_START_YEAR..SAMPLE_END_YEAR.
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

    page = 1
    total_ingested = 0

    base_query = (
        f"SELECT bathingWaterIdentifier, sampleDate, escherichiaColiValue, intestinalEnterococciValue "
        f"FROM {DISCODATA_TABLE} "
        f"WHERE YEAR(sampleDate) BETWEEN {SAMPLE_START_YEAR} AND {SAMPLE_END_YEAR} "
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

            sample_id = f"{bw_id}_{sample_date}_{page}_{i}"
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
            total_ingested += len(rows)
            logger.info("Samples ingested: %d (page %d)", total_ingested, page)

        if len(results) < DISCODATA_PAGE_SIZE:
            break
        page += 1

    pg.close()
    logger.info("Sample ingest complete. Total rows: %d", total_ingested)


def identify_interesting_sites(**context):
    """
    Identify ~INTERESTING_SITES_LIMIT sites worth rainfall enrichment.
    Selects: (a) sites with declining 5-year classification trend,
             (b) sites with high E.coli variance.
    Pushes list of bathing_water_id to XCom.
    Uses raw psycopg2 throughout — no pandas/sqlalchemy mismatch.
    """
    import psycopg2
    import psycopg2.extras

    def score(cls):
        mapping = {"excellent": 4, "good": 3, "sufficient": 2, "poor": 1}
        return mapping.get((cls or "").lower(), None)

    conn = BaseHook.get_connection(DB_CONN_ID)
    pg = psycopg2.connect(
        host=conn.host, port=conn.port, dbname=conn.schema,
        user=conn.login, password=conn.password,
    )

    try:
        with pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # (a) Declining sites: score last 5 classification years
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

        # Most declined = most negative delta
        scored.sort(key=lambda x: x[1])
        declining_ids = [bw_id for bw_id, _ in scored[:INTERESTING_SITES_LIMIT // 2]]

        # (b) High E.coli variance sites
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
    import psycopg2
    import psycopg2.extras
    from datetime import timedelta as td

    interesting_ids = context["ti"].xcom_pull(
        task_ids="identify_interesting_sites", key="interesting_sites"
    ) or []

    if not interesting_ids:
        logger.info("No interesting sites to enrich — skipping rainfall step")
        return

    db = BaseHook.get_connection(DB_CONN_ID)
    pg_conn = psycopg2.connect(
        host=db.host, port=db.port, dbname=db.schema,
        user=db.login, password=db.password,
    )

    # Fetch site coords and their sample dates using raw psycopg2
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

    # Close the read connection — we'll open a fresh one for writes
    # so the long HTTP loop doesn't hold an idle connection open.
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

        try:
            resp = requests.get(OPEN_METEO_URL, params={
                "latitude": lat,
                "longitude": lon,
                "start_date": start_str,
                "end_date": end_str,
                "daily": "precipitation_sum",
                "timezone": "UTC",
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
            # Open a fresh connection per site — avoids idle timeout over long HTTP loops
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
    description="Annual ingest of EEA bathing-water quality + rainfall enrichment",
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
