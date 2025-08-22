import requests
from bs4 import BeautifulSoup
import os
import zipfile
import pandas as pd
import time
from io import BytesIO
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from datetime import datetime, timedelta
import logging

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

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_data_path():
    """Get the data directory path based on runtime environment"""
    if os.getenv("RUNTIME"):
        return "/opt/airflow/shared/flight-delay-analysis/flight-delay-data"
    else:
        # directory to be used ..../airflow/data/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        airflow_dir = os.path.dirname(current_dir)
        return os.path.join(airflow_dir, "data")

# Constants from BTS pipeline
FIELDS = [
    "ORIGIN_AIRPORT_ID",
    "ORIGIN_AIRPORT_SEQ_ID",
    "ORIGIN_CITY_MARKET_ID",
    "DEST_AIRPORT_ID",
    "DEST_AIRPORT_SEQ_ID",
    "DEST_CITY_MARKET_ID",
    "FL_DATE",
    "OP_UNIQUE_CARRIER",
    "ORIGIN",
    "DEST",
    "DEP_TIME",
    "DEP_DELAY",
    "CRS_DEP_TIME",
    "ARR_TIME",
    "CRS_ARR_TIME",
    "ARR_DELAY",
    "CRS_ELAPSED_TIME",
    "ACTUAL_ELAPSED_TIME"
]

SAVE_DIR = get_data_path()
os.makedirs(SAVE_DIR, exist_ok=True)

def parse_time(hhmm):
    if pd.isna(hhmm):
        return None
    try:
        hhmm = int(float(hhmm))
        hour = hhmm // 100
        minute = hhmm % 100
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02}:{minute:02}:00"
        return None
    except (ValueError, TypeError):
        return None

def process_bts_data(**kwargs):
    print("Starting BTS data processing...")
    print(f"Data will be saved to: {SAVE_DIR}")

    # Get execution date and calculate target month (4 months prior)
    execution_date = kwargs['execution_date']
    target_date = execution_date - timedelta(days=4 * 30)  # Approx 4 months
    target_year = target_date.year
    target_month = target_date.month  # No leading zeros
    print(f"Processing BTS data for {target_year}-{target_month}...")

    # Download and extract
    url = "https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGK&QO_fu146_anzr=b0-gvzr"
    session = requests.Session()
    res = session.get(url)
    if res.status_code != 200:
        raise Exception(f"Failed to load BTS page. Status Code: {res.status_code}")

    soup = BeautifulSoup(res.text, "html.parser")
    try:
        viewstate = soup.find("input", {"name": "__VIEWSTATE"})["value"]
        viewstategen = soup.find("input", {"name": "__VIEWSTATEGENERATOR"})["value"]
        eventvalidation = soup.find("input", {"name": "__EVENTVALIDATION"})["value"]
    except Exception as e:
        raise Exception(f"Failed to parse form fields: {e}")

    payload = {
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__LASTFOCUS": "",
        "__VIEWSTATE": viewstate,
        "__VIEWSTATEGENERATOR": viewstategen,
        "__EVENTVALIDATION": eventvalidation,
        "cboGeography": "All",
        "cboYear": str(target_year),
        "cboPeriod": str(target_month),
        "btnDownload": "Download"
    }

    for field in FIELDS:
        payload[field] = "on"

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": url,
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive"
    }
    try:
        start = time.time()
        time.sleep(1)
        res = session.post(url, data=payload, headers=headers, timeout=500)
        duration = time.time() - start
        print(f"POST took {duration:.2f} seconds")
    except requests.Timeout:
        raise Exception("Request timed out.")

    if res.status_code != 200 or res.content[:2] != b'PK':
        raise Exception(f"Failed to download ZIP. Status: {res.status_code}")

    print("Received ZIP file.")
    raw_csv_path = os.path.join(SAVE_DIR, f"bts_raw_data_{target_year}_{target_month}.csv")
    try:
        with zipfile.ZipFile(BytesIO(res.content), 'r') as zip_ref:
            csv_file = next((f for f in zip_ref.namelist() if f.endswith(".csv")), None)
            if not csv_file:
                raise Exception("No CSV found in ZIP.")
            with zip_ref.open(csv_file) as csv_file:
                df = pd.read_csv(csv_file)
                df.to_csv(raw_csv_path, index=False)
                print(f"Extracted and saved raw CSV to: {raw_csv_path}")
                if not os.path.exists(raw_csv_path):
                    raise Exception(f"Failed to verify saved CSV at: {raw_csv_path}")
                if not os.access(raw_csv_path, os.R_OK | os.W_OK):
                    raise Exception(f"No read/write permission for CSV at: {raw_csv_path}")
    except zipfile.BadZipFile:
        raise Exception("ZIP file was corrupted.")
    except Exception as e:
        raise Exception(f"Failed to save raw CSV: {e}")

    # Clean and append to single CSV
    print(f"Cleaning and appending CSV from: {raw_csv_path}")
    required_columns = [
        'FL_DATE', 'OP_UNIQUE_CARRIER', 'ORIGIN', 'DEST',
        'CRS_DEP_TIME', 'DEP_TIME', 'DEP_DELAY',
        'CRS_ARR_TIME', 'ARR_TIME', 'ARR_DELAY',
        'CRS_ELAPSED_TIME', 'ACTUAL_ELAPSED_TIME'
    ]
    
    chunk_size = 100000
    output_filename = "bts_flight_data.csv"  # Single output file
    output_path = os.path.join(SAVE_DIR, output_filename)
    file_exists = os.path.exists(output_path)
    
    try:
        for chunk in pd.read_csv(raw_csv_path, chunksize=chunk_size):
            print(f"Processing chunk with {len(chunk)} rows...")
            missing = [col for col in required_columns if col not in chunk.columns]
            if missing:
                raise Exception(f"Missing required columns: {missing}")

            chunk.dropna(subset=required_columns, inplace=True)

            df_clean = pd.DataFrame({
                "AIRLINE": chunk['OP_UNIQUE_CARRIER'],
                "ORIGIN_AIRPORT": chunk['ORIGIN'],
                "DESTINATION_AIRPORT": chunk['DEST'],
                "SCHEDULED_DEPARTURE": pd.to_datetime(chunk['FL_DATE']) + pd.to_timedelta(chunk['CRS_DEP_TIME'].apply(parse_time)),
                "DEPARTURE_TIME": chunk['DEP_TIME'].apply(parse_time),
                "DEPARTURE_DELAY": chunk['DEP_DELAY'],
                "SCHEDULED_ARRIVAL": chunk['CRS_ARR_TIME'].apply(parse_time),
                "ARRIVAL_TIME": chunk['ARR_TIME'].apply(parse_time),
                "ARRIVAL_DELAY": chunk['ARR_DELAY'],
                "SCHEDULED_TIME": chunk['CRS_ELAPSED_TIME'],
                "ELAPSED_TIME": chunk['ACTUAL_ELAPSED_TIME'],
            })

            mode = 'a'  # Always append
            header = not file_exists  # Write header only if file doesn't exist
            df_clean.to_csv(output_path, mode=mode, header=header, index=False)
            print(f"Processed chunky and appended to: {output_path}")
            file_exists = True  # Update flag after first write

        try:
            os.remove(raw_csv_path)
            print(f"Removed raw CSV: {raw_csv_path}")
        except OSError as e:
            print(f"Failed to remove raw CSV: {e}")

        print(f"Appended cleaned data to: {output_path}")
    except Exception as e:
        raise Exception(f"Failed to process CSV: {e}")

def run_transform_and_load(**kwargs):
    try:
        base_path = SAVE_DIR

        new_file = os.path.join(base_path, "bts_flight_data.csv")

        logger.info(f"Reading BTS flight data file: {new_file}")
        new_df = pd.read_csv(new_file)

        logger.info(f"✅ BTS data rows: {len(new_df)}")

        # Clean the data
        new_df.dropna(inplace=True)
        new_df.drop_duplicates(inplace=True)

        logger.info(f"🧹 Cleaned dataset rows: {len(new_df)}")

        airports = pd.read_csv(os.path.join(base_path, "airports.csv"))
        airlines = pd.read_csv(os.path.join(base_path, "airlines.csv"), sep='^')

        transforms = [
            get_delay_distribution(new_df),
            get_flight_statistics_summary(new_df),
            get_delay_vs_hour(new_df),
            get_hourly_avg_delay(new_df),
            get_top10_origin_airports_by_delay(new_df),
            get_weekday_avg_delay(new_df),
            get_origin_airport_stats(new_df),
            get_airline_performance_stats(new_df),
        ]

        logger.info("📊 Running transformations and generating SQL...")

        # Generate SQL statements instead of using engine
        sql_statements = []
        
        # Clear snapshot tables first
        sql_statements.append("DELETE FROM top10_origin_airports_by_delay;")
        sql_statements.append("DELETE FROM delay_distribution;")
        
        for table, rows in transforms:
            logger.info(f"➡️ Generating SQL for table: {table} | Rows: {len(rows)}")
            
            if not rows:
                continue
                
            # Get table columns
            columns = list(rows[0].keys())
            
            # Generate conflict clauses based on table
            conflict_clauses = {
                "flight_statistics_summary": "ON CONFLICT (airline) DO UPDATE SET total_flights=EXCLUDED.total_flights, avg_departure_delay=EXCLUDED.avg_departure_delay, avg_arrival_delay=EXCLUDED.avg_arrival_delay",
                "delay_distribution": "ON CONFLICT (bin_start) DO UPDATE SET bin_end=EXCLUDED.bin_end, count=EXCLUDED.count",
                "delay_vs_hour": "ON CONFLICT (hour, airline) DO UPDATE SET avg_departure_delay=EXCLUDED.avg_departure_delay",
                "hourly_avg_delay": "ON CONFLICT (hour) DO UPDATE SET avg_departure_delay=EXCLUDED.avg_departure_delay",
                "top10_origin_airports_by_delay": "ON CONFLICT (origin_airport) DO UPDATE SET avg_departure_delay=EXCLUDED.avg_departure_delay",
                "weekday_avg_delay": "ON CONFLICT (day_of_week) DO UPDATE SET avg_departure_delay=EXCLUDED.avg_departure_delay, avg_arrival_delay=EXCLUDED.avg_arrival_delay",
                "origin_airport_stats": "ON CONFLICT (origin_airport) DO UPDATE SET flight_count=EXCLUDED.flight_count, avg_departure_delay=EXCLUDED.avg_departure_delay",
                "airline_performance_stats": "ON CONFLICT (airline) DO UPDATE SET avg_departure_delay=EXCLUDED.avg_departure_delay, avg_arrival_delay=EXCLUDED.avg_arrival_delay, total_flights=EXCLUDED.total_flights, on_time_pct=EXCLUDED.on_time_pct"
            }
            
            conflict_clause = conflict_clauses.get(table, "")
            
            for row in rows:
                values = []
                for col in columns:
                    val = row[col]
                    if val is None:
                        values.append('NULL')
                    elif isinstance(val, str):
                        escaped_val = val.replace("'", "''")
                        values.append(f"'{escaped_val}'")
                    else:
                        values.append(str(val))
                
                sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(values)}) {conflict_clause};"
                sql_statements.append(sql)

        # Generate SQL for airport details
        logger.info("✈️ Generating SQL for airport details...")
        airports_renamed = airports.rename(columns={
            'IATA': 'iata_code',
            'AIRPORT': 'airport',
            'CITY': 'city',
            'STATE': 'state',
            'LATITUDE': 'latitude', 
            'LONGITUDE': 'longitude'
        })[['iata_code', 'airport', 'city', 'state', 'latitude', 'longitude']]
        
        for _, row in airports_renamed.iterrows():
            values = []
            for col in ['iata_code', 'airport', 'city', 'state', 'latitude', 'longitude']:
                val = row[col]
                if pd.isna(val):
                    values.append('NULL')
                elif col in ['latitude', 'longitude']:
                    values.append(str(val))
                else:
                    escaped_val = str(val).replace("'", "''")
                    values.append(f"'{escaped_val}'")
            
            sql = f"INSERT INTO airport_details (iata_code, airport, city, state, latitude, longitude) VALUES ({', '.join(values)}) ON CONFLICT (iata_code) DO UPDATE SET airport=EXCLUDED.airport, city=EXCLUDED.city, state=EXCLUDED.state, latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude;"
            sql_statements.append(sql)

        # Generate SQL for airlines
        logger.info("📦 Generating SQL for airline names...")
        airlines_renamed = airlines.rename(columns={'name': 'airline'})[['iata_code', 'airline']]
        
        for _, row in airlines_renamed.iterrows():
            iata_code = str(row['iata_code']).replace("'", "''")
            airline = str(row['airline']).replace("'", "''")
            sql = f"INSERT INTO airlines (iata_code, airline) VALUES ('{iata_code}', '{airline}') ON CONFLICT (iata_code) DO NOTHING;"
            sql_statements.append(sql)

        # Save SQL to file for the next task
        sql_file = os.path.join(base_path, "generated_sql.sql")
        with open(sql_file, 'w') as f:
            f.write('\n'.join(sql_statements))
        
        logger.info(f"✅ Generated {len(sql_statements)} SQL statements saved to {sql_file}")
        
        logger.info("✅ ETL pipeline execution complete")

    except Exception as e:
        logger.error(f"❌ ETL process failed: {e}")
        raise

def get_generated_sql(**kwargs):
    """Read the generated SQL file and return its contents""" 
    data_path = SAVE_DIR
    
    sql_file = os.path.join(data_path, "generated_sql.sql")
    print(f"Reading generated SQL from: {sql_file}")
    
    with open(sql_file, 'r') as f:
        sql_content = f.read()
    
    # Clean up the SQL file
    try:
        os.remove(sql_file)
        logger.info(f"🗑️ Cleaned up SQL file: {sql_file}")
    except OSError as e:
        logger.warning(f"⚠️ Failed to remove SQL file: {e}")
    
    return sql_content

# SQL for schema creation
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS flight_statistics_summary (
    airline TEXT PRIMARY KEY,
    total_flights INTEGER NOT NULL,
    avg_departure_delay FLOAT,
    avg_arrival_delay FLOAT
);

CREATE TABLE IF NOT EXISTS delay_distribution (
    bin_start INTEGER PRIMARY KEY,
    bin_end INTEGER NOT NULL,
    count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS delay_vs_hour (
    hour INTEGER NOT NULL,
    airline TEXT NOT NULL,
    avg_departure_delay FLOAT,
    PRIMARY KEY (hour, airline)
);

CREATE TABLE IF NOT EXISTS hourly_avg_delay (
    hour INT PRIMARY KEY,
    avg_departure_delay FLOAT
);

CREATE TABLE IF NOT EXISTS top10_origin_airports_by_delay (
    origin_airport TEXT PRIMARY KEY,
    avg_departure_delay FLOAT
);

CREATE TABLE IF NOT EXISTS weekday_avg_delay (
    day_of_week TEXT PRIMARY KEY,
    avg_departure_delay FLOAT,
    avg_arrival_delay FLOAT
);

CREATE TABLE IF NOT EXISTS origin_airport_stats (
    origin_airport TEXT PRIMARY KEY,
    flight_count INT,
    avg_departure_delay FLOAT
);

CREATE TABLE IF NOT EXISTS airport_details (
    iata_code TEXT PRIMARY KEY,
    airport TEXT,
    city TEXT,
    state TEXT,
    latitude FLOAT,
    longitude FLOAT
);

CREATE TABLE IF NOT EXISTS airline_performance_stats (
    airline TEXT PRIMARY KEY,
    avg_departure_delay FLOAT,
    avg_arrival_delay FLOAT,
    total_flights INT,
    on_time_pct FLOAT
);

CREATE TABLE IF NOT EXISTS airlines (
    iata_code VARCHAR PRIMARY KEY,
    airline VARCHAR
);
"""

# DAG Definition
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2024, 5, 1),
}

with DAG(
    'flight_delay_etl_pipeline',
    default_args=default_args,
    description='Comprehensive ETL pipeline for flight delay data',
    schedule_interval='0 0 1 * *',  # Run on the 1st of every month
    catchup=False,
    max_active_runs=1,
) as dag:

    # Use SQLExecuteQueryOperator for schema creation
    create_schema = SQLExecuteQueryOperator(
        task_id='create_schema',
        conn_id='demo-db',
        sql=CREATE_TABLES_SQL,
        autocommit=True,
    )

    # Process BTS data (download and clean)
    process_bts_task = PythonOperator(
        task_id='process_bts_data',
        python_callable=process_bts_data,
        provide_context=True,
    )

    # Transform and generate SQL
    transform_and_load = PythonOperator(
        task_id='transform_and_generate_sql',
        python_callable=run_transform_and_load,
    )

    # Load data using generated SQL
    load_data = SQLExecuteQueryOperator(
        task_id='load_data_to_db',
        conn_id='demo-db',
        sql=get_generated_sql,
        autocommit=True,
    )

    # DAG flow
    create_schema >> process_bts_task >> transform_and_load >> load_data
