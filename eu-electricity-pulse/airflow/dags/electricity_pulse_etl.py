import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.hooks.base import BaseHook
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator

_RUNTIME = os.environ.get("RUNTIME")
_DBT_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__),
    ".." if _RUNTIME else "../..",
    "dbt",
))

DB_CONN_ID = "euenergy_db"
API_SECRET_NAME = "euenergy_api_key"

BIDDING_ZONES = [
    ("AT", "Austria", "AT", "APG", 47.5, 14.5),
    ("BE", "Belgium", "BE", "Elia", 50.5, 4.5),
    ("BG", "Bulgaria", "BG", "ESO", 42.7, 25.5),
    ("CH", "Switzerland", "CH", "Swissgrid", 46.8, 8.2),
    ("CZ", "Czechia", "CZ", "CEPS", 49.8, 15.5),
    ("DE-LU", "Germany/Luxembourg", "DE", "50Hertz/Amprion/TenneT/TransnetBW", 51.5, 10.4),
    ("DK1", "Denmark West", "DK", "Energinet", 56.0, 9.5),
    ("DK2", "Denmark East", "DK", "Energinet", 55.5, 12.0),
    ("EE", "Estonia", "EE", "Elering", 58.6, 25.0),
    ("ES", "Spain", "ES", "REE", 40.4, -3.7),
    ("FI", "Finland", "FI", "Fingrid", 64.0, 26.0),
    ("FR", "France", "FR", "RTE", 46.5, 2.0),
    ("GR", "Greece", "GR", "ADMIE", 39.1, 21.8),
    ("HR", "Croatia", "HR", "HOPS", 45.1, 15.2),
    ("HU", "Hungary", "HU", "MAVIR", 47.2, 19.5),
    ("IT-NORTH", "Italy North", "IT", "Terna", 45.5, 9.2),
    ("IT-CNORTH", "Italy Centre-North", "IT", "Terna", 43.8, 11.2),
    ("IT-CSOUTH", "Italy Centre-South", "IT", "Terna", 41.9, 12.5),
    ("IT-SOUTH", "Italy South", "IT", "Terna", 40.6, 15.1),
    ("IT-Sardinia", "Italy Sardinia", "IT", "Terna", 40.1, 9.0),
    ("IT-Sicily", "Italy Sicily", "IT", "Terna", 37.6, 14.0),
    ("LT", "Lithuania", "LT", "Litgrid", 55.9, 23.9),
    ("LV", "Latvia", "LV", "AST", 56.9, 24.1),
    ("NL", "Netherlands", "NL", "TenneT", 52.4, 5.3),
    ("NO1", "Norway South-East", "NO", "Statnett", 59.9, 10.8),
    ("NO2", "Norway South-West", "NO", "Statnett", 58.8, 5.5),
    ("NO3", "Norway Middle", "NO", "Statnett", 63.4, 10.4),
    ("NO4", "Norway North", "NO", "Statnett", 68.5, 17.5),
    ("NO5", "Norway West", "NO", "Statnett", 60.4, 5.3),
    ("PL", "Poland", "PL", "PSE", 52.2, 21.0),
    ("PT", "Portugal", "PT", "REN", 39.5, -8.0),
    ("RO", "Romania", "RO", "Transelectrica", 45.9, 24.9),
    ("RS", "Serbia", "RS", "EMS", 44.0, 21.0),
    ("SE1", "Sweden North", "SE", "Svenska kraftnät", 67.8, 20.3),
    ("SE2", "Sweden North-Middle", "SE", "Svenska kraftnät", 63.8, 20.3),
    ("SE3", "Sweden South-Middle", "SE", "Svenska kraftnät", 59.3, 18.1),
    ("SE4", "Sweden South", "SE", "Svenska kraftnät", 55.6, 13.0),
    ("SI", "Slovenia", "SI", "ELES", 46.1, 14.5),
    ("SK", "Slovakia", "SK", "SEPS", 48.7, 19.7),
    ("UA-BEI", "Ukraine BEI", "UA", "Ukrenergo", 49.5, 31.3),
    ("UA-IPS", "Ukraine IPS", "UA", "Ukrenergo", 46.5, 30.7),
]

CREATE_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS dim;

CREATE TABLE IF NOT EXISTS dim.bidding_zones (
    zone_code TEXT PRIMARY KEY,
    zone_name TEXT NOT NULL,
    country   TEXT NOT NULL,
    tso       TEXT,
    latitude  DOUBLE PRECISION,
    longitude DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS raw.zone_prices_hourly (
    zone_code       TEXT NOT NULL,
    delivery_date   DATE NOT NULL,
    delivery_hour   SMALLINT NOT NULL,
    price_eur_mwh   DOUBLE PRECISION,
    currency        TEXT DEFAULT 'EUR/MWh',
    ingested_at     TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (zone_code, delivery_date, delivery_hour)
);
"""


def _get_conn():
    import psycopg2
    c = BaseHook.get_connection(DB_CONN_ID)
    return psycopg2.connect(
        host=c.host, port=c.port or 5432,
        dbname=c.schema, user=c.login, password=c.password
    )


def seed_zone_dimension(**ctx):
    from psycopg2.extras import execute_values
    with _get_conn() as conn, conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO dim.bidding_zones (zone_code, zone_name, country, tso, latitude, longitude)
            VALUES %s
            ON CONFLICT (zone_code) DO UPDATE
              SET zone_name = EXCLUDED.zone_name,
                  country   = EXCLUDED.country,
                  tso       = EXCLUDED.tso,
                  latitude  = EXCLUDED.latitude,
                  longitude = EXCLUDED.longitude
            """,
            BIDDING_ZONES,
        )
        conn.commit()
    print(f"Seeded {len(BIDDING_ZONES)} bidding zones")


def fetch_and_load_prices(**ctx):
    import requests
    import psycopg2
    from psycopg2.extras import execute_values
    """
    Fetch prices for both today and tomorrow in a single run.

    Day-ahead prices for D+1 are published by ENTSO-E around 11:00–12:00 UTC
    (earlier in summer/CEST, later in winter/CET). Running at 13:00 UTC means
    both today's delivery prices AND tomorrow's freshly-auctioned prices are
    available. Storing both makes the dashboard show up-to-date data even if
    one day's run is delayed or retried.
    """
    api_key = Variable.get(API_SECRET_NAME)
    headers = {"Authorization": f"Bearer {api_key}"}
    logical_date = ctx["logical_date"].date()

    # Fetch today (current delivery date) + tomorrow (just-published day-ahead)
    targets = [
        ("today",    logical_date),
        ("tomorrow", logical_date + timedelta(days=1)),
    ]

    total_rows, all_errors = 0, []

    for slot, delivery_date in targets:
        rows, errors = [], []
        for zone_code, *_ in BIDDING_ZONES:
            url = f"https://euenergy.live/api/v1/prices/{slot}?zone={zone_code}"
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                hours = data.get("hours", [])
                for item in hours:
                    ts    = item.get("ts", "")
                    price = item.get("price")
                    if ts and price is not None:
                        hour = int(ts[11:13])
                        rows.append((zone_code, delivery_date, hour, float(price), "EUR/MWh"))
            except Exception as e:
                errors.append(f"{zone_code}/{slot}: {e}")
                print(f"WARNING: failed to fetch {zone_code} ({slot}): {e}")

        if rows:
            with _get_conn() as conn, conn.cursor() as cur:
                execute_values(
                    cur,
                    """
                    INSERT INTO raw.zone_prices_hourly
                        (zone_code, delivery_date, delivery_hour, price_eur_mwh, currency)
                    VALUES %s
                    ON CONFLICT (zone_code, delivery_date, delivery_hour)
                    DO UPDATE SET price_eur_mwh = EXCLUDED.price_eur_mwh,
                                  ingested_at   = now()
                    """,
                    rows,
                )
                conn.commit()
            print(f"[{slot}] Loaded {len(rows)} rows for {delivery_date}.")
        else:
            print(f"[{slot}] No rows for {delivery_date} — skipping write. Errors: {errors}")

        total_rows += len(rows)
        all_errors += errors

    if total_rows == 0:
        raise ValueError(f"No price rows fetched at all. Errors: {all_errors}")

    print(f"Total loaded: {total_rows} rows. Errors: {all_errors or 'none'}")


with DAG(
    dag_id="electricity_pulse_etl",
    description="Daily ingest of EU day-ahead electricity prices from euenergy.live into PostgreSQL",
    # 13:30 UTC = 15:30 CEST / 14:30 CET.
    # ENTSO-E auction results land ~10:45–11:00 UTC (summer/CEST) or ~11:45–12:00 UTC (winter/CET).
    # euenergy.live has no public SLA for ingestion lag after ENTSO-E publishes.
    # 13:30 UTC gives ~2.5hr buffer in summer and ~1.5hr in winter — enough to cover
    # typical auction delays plus an undocumented euenergy.live ingestion window.
    schedule_interval="30 13 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=15),  # give euenergy.live time to ingest after ENTSO-E
        "owner": "dataflow",
    },
    tags=["electricity", "eu", "energy"],
) as dag:

    create_schema = SQLExecuteQueryOperator(
        task_id="create_schema",
        conn_id=DB_CONN_ID,
        sql=CREATE_SCHEMA_SQL,
    )

    seed_zones = PythonOperator(
        task_id="seed_zone_dimension",
        python_callable=seed_zone_dimension,
    )

    fetch_prices = PythonOperator(
        task_id="fetch_and_load_prices",
        python_callable=fetch_and_load_prices,
    )

    run_dbt = BashOperator(
        task_id="run_dbt",
        bash_command=f"cd {_DBT_DIR} && dbt run",
    )

    create_schema >> seed_zones >> fetch_prices >> run_dbt
