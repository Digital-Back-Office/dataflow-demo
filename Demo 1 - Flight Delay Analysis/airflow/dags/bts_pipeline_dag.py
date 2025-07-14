import requests
from bs4 import BeautifulSoup
import os
import zipfile
import pandas as pd
import time
from io import BytesIO
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from airflow.utils.dates import days_ago

# Constants
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

if os.getenv("RUNTIME"):
    SAVE_DIR = "/opt/airflow/shared/flight-delay-analysis/flight-delay-data"
else:
    SAVE_DIR = "/home/jovyan/shared/flight-delay-analysis/flight-delay-data/"

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
    # Get execution date and calculate target month (4 months prior)
    execution_date = kwargs['execution_date']
    target_date = execution_date - timedelta(days=4 * 30)  # Approx 4 months
    target_year = target_date.year
    target_month = target_date.month  # No leading zeros
    print(f"🚀 Processing BTS data for {target_year}-{target_month}...")

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
        print(f"⏱️ POST took {duration:.2f} seconds")
    except requests.Timeout:
        raise Exception("Request timed out.")

    if res.status_code != 200 or res.content[:2] != b'PK':
        raise Exception(f"Failed to download ZIP. Status: {res.status_code}")

    print("✅ Received ZIP file.")
    raw_csv_path = os.path.join(SAVE_DIR, f"bts_raw_data_{target_year}_{target_month}.csv")
    try:
        with zipfile.ZipFile(BytesIO(res.content), 'r') as zip_ref:
            csv_file = next((f for f in zip_ref.namelist() if f.endswith(".csv")), None)
            if not csv_file:
                raise Exception("No CSV found in ZIP.")
            with zip_ref.open(csv_file) as csv_file:
                df = pd.read_csv(csv_file)
                df.to_csv(raw_csv_path, index=False)
                print(f"✅ Extracted and saved raw CSV to: {raw_csv_path}")
                if not os.path.exists(raw_csv_path):
                    raise Exception(f"Failed to verify saved CSV at: {raw_csv_path}")
                if not os.access(raw_csv_path, os.R_OK | os.W_OK):
                    raise Exception(f"No read/write permission for CSV at: {raw_csv_path}")
    except zipfile.BadZipFile:
        raise Exception("ZIP file was corrupted.")
    except Exception as e:
        raise Exception(f"Failed to save raw CSV: {e}")

    # Clean and append to single CSV
    print(f"🧹 Cleaning and appending CSV from: {raw_csv_path}")
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
            print(f"✅ Processed chunky and appended to: {output_path}")
            file_exists = True  # Update flag after first write

        try:
            os.remove(raw_csv_path)
            print(f"🗑️ Removed raw CSV: {raw_csv_path}")
        except OSError as e:
            print(f"⚠️ Failed to remove raw CSV: {e}")

        print(f"✅ Appended cleaned data to: {output_path}")
    except Exception as e:
        raise Exception(f"Failed to process CSV: {e}")

# DAG Definition
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2024, 5, 1),  # Start from May 2024
}

with DAG(
    'bts_flight_data_pipeline',
    default_args=default_args,
    description='BTS flight data pipeline for one month (4 months prior) starting May 2024',
    schedule_interval='0 0 1 * *',  # Run on the 1st of every month
    catchup=False,  # Process all months from May 2024 to current
) as dag:

    process_task = PythonOperator(
        task_id='process_bts_data',
        python_callable=process_bts_data,
        provide_context=True,
    )
