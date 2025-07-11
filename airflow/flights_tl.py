from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import pandas as pd
import os
import logging
from sqlalchemy import create_engine
from helpers.transform import (
    get_delay_distribution,
    get_flight_statistics_summary,
    get_delay_vs_hour,
    get_hourly_avg_delay,
    get_top10_origin_airports_by_delay,
    get_weekday_avg_delay,
    get_origin_airport_stats,
    get_airline_performance_stats,
)
from helpers.loaders import (
    load_to_db,
    load_airport_details,
    load_airlines
)
from helpers.schema_creator import create_tables_if_not_exists
from airflow.models.connection import Connection

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_db_engine():
    try:
        conn = Connection.get_connection_from_secrets("demo_db")
        conn.conn_type = "postgresql"
        engine = create_engine(conn.get_uri())
        logger.info("✅ DB engine created successfully")
        return engine
    except Exception as e:
        logger.error(f"❌ Failed to create DB engine: {e}")
        raise

def create_schema():
    try:
        engine = get_db_engine()
        create_tables_if_not_exists(engine)
        logger.info("✅ Tables ensured via schema creation")
    except Exception as e:
        logger.error(f"❌ Schema creation failed: {e}")
        raise

def run_transform_and_load():
    try:
        if os.getenv("RUNTIME"):
            base_path = "/opt/airflow/shared/flight-delay-analysis/flight-delay-data"
        else:
            base_path = "/home/jovyan/shared/flight-delay-analysis/flight-delay-data"
        base_file = os.path.join(base_path, "cleaned_flight_data.csv")
        new_file = os.path.join(base_path, "bts_flight_data.csv")

        logger.info("📥 Reading base and new flight data files...")
        cleaned_df = pd.read_csv(base_file)
        new_df = pd.read_csv(new_file)

        logger.info(f"✅ Base rows: {len(cleaned_df)}, New rows: {len(new_df)}")

        full_df = pd.concat([cleaned_df, new_df], ignore_index=True)
        full_df.dropna(inplace=True)
        full_df.drop_duplicates(inplace=True)

        logger.info(f"🧹 Cleaned combined dataset rows: {len(full_df)}")
        full_df.to_csv(base_file, index=False)
        logger.info(f"💾 Updated {base_file} saved")

        airports = pd.read_csv(os.path.join(base_path, "airports.csv"))
        airlines = pd.read_csv(os.path.join(base_path, "airlines.csv"), sep='^')

        engine = get_db_engine()

        transforms = [
            get_delay_distribution(full_df),
            get_flight_statistics_summary(full_df),
            get_delay_vs_hour(full_df),
            get_hourly_avg_delay(full_df),
            get_top10_origin_airports_by_delay(full_df),
            get_weekday_avg_delay(full_df),
            get_origin_airport_stats(full_df),
            get_airline_performance_stats(full_df),
        ]

        logger.info("📊 Running transformations and loading results...")

        for table, rows in transforms:
            logger.info(f"➡️ Loading table: {table} | Rows: {len(rows)}")
            load_to_db(engine, table, rows)

        logger.info("✈️ Loading airport details...")
        load_airport_details(engine, airports)

        logger.info("📦 Loading airline names...")
        load_airlines(engine, airlines)
        
        logger.info("✅ ETL pipeline execution complete")

    except Exception as e:
        logger.error(f"❌ ETL process failed: {e}")
        raise

with DAG(
    "flight_etl_pipeline",
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,
    catchup=False,
    description="ETL pipeline for flight delay analytics",
) as dag:

    schema_creation = PythonOperator(
        task_id='create_schema',
        python_callable=create_schema,
    )

    transform_and_load = PythonOperator(
        task_id='transform_and_load',
        python_callable=run_transform_and_load,
    )

    # DAG flow
    schema_creation >> transform_and_load
