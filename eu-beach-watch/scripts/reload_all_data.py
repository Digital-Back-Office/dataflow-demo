#!/usr/bin/env python3
"""
reload_all_data.py — standalone, manually-run utility to wipe and reload
the EU Beach Watch dataset from scratch.

This is NOT an Airflow DAG on purpose — the Airflow pipeline (beach_watch_ingest)
only ever upserts, so a full wipe-and-reload is a deliberate manual operation
run by a human, not something that should be schedulable or auto-triggered.

What it does:
  1. Ensures the schema/tables exist and have the current column set
     (idempotent — safe to run against a fresh or existing database).
  2. TRUNCATEs raw.bathing_sites and raw.samples.
  3. Re-ingests the full EEA site layer (~22,000 sites) with every attribute
     the ArcGIS API returns, not just the fields the app currently uses.
  4. Re-ingests samples for the SAME demo window the ingest DAG uses
     (imported from beach_watch_ingest.py, currently 2019-2024 — NOT the
     full 2008+ history, which is far more data than this project needs),
     but now capturing every attribute the API returns per sample.
  5. Leaves raw.site_rainfall untouched — that's an Airflow-owned enrichment
     step (enrich_rainfall) that will repopulate itself on the next DAG run.

Run manually:
    cd eu-beach-watch
    DATABASE_URL=postgresql://user:pass@host:port/dbname python scripts/reload_all_data.py

Or, if run inside the same environment as Airflow (so BaseHook works):
    python scripts/reload_all_data.py
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("reload_all_data")

# Make beach_watch_common importable — it lives alongside the DAGs.
DAGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "airflow", "dags")
sys.path.insert(0, os.path.normpath(DAGS_DIR))

from beach_watch_common import (  # noqa: E402
    CREATE_SCHEMA_SQL, ingest_sites, ingest_samples,
    SAMPLE_START_YEAR, SAMPLE_END_YEAR,
)


def get_connection_params():
    """DATABASE_URL env var first; falls back to the Airflow connection if
    this script happens to run in an environment where Airflow is importable.
    """
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        return {
            "host": parsed.hostname,
            "port": parsed.port or 5432,
            "dbname": parsed.path.lstrip("/"),
            "user": parsed.username,
            "password": parsed.password,
        }
    try:
        from airflow.hooks.base import BaseHook
        conn = BaseHook.get_connection("beach_watch_db")
        return {
            "host": conn.host, "port": conn.port, "dbname": conn.schema,
            "user": conn.login, "password": conn.password,
        }
    except Exception as e:
        raise RuntimeError(
            "Could not resolve DB connection. Set DATABASE_URL or run where "
            "the Airflow 'beach_watch_db' connection is available."
        ) from e


def confirm(prompt: str) -> bool:
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    return answer == "y"


def main():
    import psycopg2

    params = get_connection_params()
    logger.info("Connecting to %s:%s/%s", params["host"], params["port"], params["dbname"])

    if not confirm(
        f"This will DELETE all rows in raw.bathing_sites and raw.samples, then "
        f"re-download and reload everything from EEA (~22k sites, samples for "
        f"{SAMPLE_START_YEAR}-{SAMPLE_END_YEAR} — roughly 1-1.5M rows, not the "
        f"full 2008+ history). This can take 10-20 minutes. Continue?"
    ):
        logger.info("Aborted.")
        return

    pg = psycopg2.connect(**params)
    pg.autocommit = True

    logger.info("Ensuring schema/columns are up to date...")
    with pg.cursor() as cur:
        cur.execute(CREATE_SCHEMA_SQL)

    logger.info("Truncating raw.bathing_sites and raw.samples...")
    with pg.cursor() as cur:
        cur.execute("TRUNCATE TABLE raw.bathing_sites")
        cur.execute("TRUNCATE TABLE raw.samples")

    pg.autocommit = False

    logger.info("Re-ingesting all EEA bathing sites (full attribute set)...")
    site_count = ingest_sites(pg)
    logger.info("Sites reloaded: %d", site_count)

    logger.info(
        "Re-ingesting samples, %d-%d (full attribute set) — this is the slow part...",
        SAMPLE_START_YEAR, SAMPLE_END_YEAR,
    )
    sample_count = ingest_samples(pg, SAMPLE_START_YEAR, SAMPLE_END_YEAR)
    logger.info("Samples reloaded: %d", sample_count)

    pg.close()
    logger.info(
        "Done. Trigger the beach_watch_ingest DAG (or wait for its next scheduled "
        "run) to rebuild dbt marts and refresh rainfall enrichment for the app."
    )


if __name__ == "__main__":
    main()
