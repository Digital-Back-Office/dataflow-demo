from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
from airflow.providers.postgres.hooks.postgres import PostgresHook
import pandas as pd
import os
import json

def get_data_path():
    """Get the data directory path based on runtime environment"""
    if os.getenv("RUNTIME"):
        return "/opt/airflow/shared/demo-projects/neighbourhood_score/data"
    else:
        return "/home/jovyan/shared/demo-projects/neighbourhood_score/data"

def load_lsoa_boundaries():
    """Load LSOA boundaries from GeoJSON into PostGIS."""
    import geopandas as gpd

    hook = PostgresHook(postgres_conn_id='ukns_db')
    conn = hook.get_conn()
    cursor = conn.cursor()
    print("Loading LSOA boundaries into PostGIS...")

    gdf = gpd.read_file(os.path.join(get_data_path(), 'lsoa_boundaries.geojson'))
    gdf = gdf[['LSOA21CD', 'LSOA21NM', 'geometry']].rename(columns={'LSOA21CD': 'lsoa_code', 'LSOA21NM': 'lsoa_name'})
    print(f"Loaded {len(gdf)} LSOA boundaries from GeoJSON.")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lsoa_boundaries (
            lsoa_code TEXT PRIMARY KEY,
            lsoa_name TEXT,
            geom GEOMETRY(MultiPolygon, 4326)
        );
        TRUNCATE lsoa_boundaries;
        CREATE INDEX IF NOT EXISTS idx_lsoa_geom ON lsoa_boundaries USING GIST (geom);
    """)
    conn.commit()
    print("LSOA boundaries table created/truncated.")

    from psycopg2.extras import execute_values
    
    batch_size = 1000
    data = []
    for _, row in gdf.iterrows():
        geojson_str = json.dumps(row['geometry'].__geo_interface__)
        data.append((row['lsoa_code'], row['lsoa_name'], geojson_str))
    
    # Insert in batches
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        execute_values(
            cursor,
            "INSERT INTO lsoa_boundaries (lsoa_code, lsoa_name, geom) VALUES %s",
            batch,
            template="(%s, %s, ST_Multi(ST_GeomFromGeoJSON(%s)))"
        )
        conn.commit()
        print(f"Inserted batch {i // batch_size + 1} ({len(batch)} rows)")
    cursor.close()
    conn.close()
    print("LSOA boundaries loaded.")


def load_msoa_boundaries():
    """Load MSOA boundaries from GeoJSON into PostGIS."""
    import geopandas as gpd

    hook = PostgresHook(postgres_conn_id='ukns_db')
    conn = hook.get_conn()
    cursor = conn.cursor()
    print("Loading MSOA boundaries into PostGIS...")

    # Load GeoJSON
    gdf = gpd.read_file(os.path.join(get_data_path(), 'msoa_boundaries.geojson'))
    gdf = gdf[['MSOA21CD', 'MSOA21NM', 'geometry']].rename(columns={'MSOA21CD': 'msoa_code', 'MSOA21NM': 'msoa_name'})
    print(f"Loaded {len(gdf)} MSOA boundaries from GeoJSON.")

    # Create table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS msoa_boundaries (
            msoa_code TEXT PRIMARY KEY,
            msoa_name TEXT,
            geom GEOMETRY(MultiPolygon, 4326)
        );
        TRUNCATE msoa_boundaries;
        CREATE INDEX IF NOT EXISTS idx_msoa_geom ON msoa_boundaries USING GIST (geom);
    """)
    conn.commit()
    print("MSOA boundaries table created/truncated.")

    from psycopg2.extras import execute_values
    
    # Prepare data as list of tuples
    batch_size = 1000
    data = []
    for _, row in gdf.iterrows():
        geojson_str = json.dumps(row['geometry'].__geo_interface__)
        data.append((row['msoa_code'], row['msoa_name'], geojson_str))
    
    # Insert in batches
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        execute_values(
            cursor,
            "INSERT INTO msoa_boundaries (msoa_code, msoa_name, geom) VALUES %s",
            batch,
            template="(%s, %s, ST_Multi(ST_GeomFromGeoJSON(%s)))"
        )
        conn.commit()
        print(f"Inserted batch {i // batch_size + 1} ({len(batch)} rows)")
    cursor.close()
    conn.close()
    print("MSOA boundaries loaded.")


def load_lad_boundaries():
    """Load LAD boundaries from GeoJSON into PostGIS."""
    import geopandas as gpd

    hook = PostgresHook(postgres_conn_id='ukns_db')
    conn = hook.get_conn()
    cursor = conn.cursor()
    print("Loading LAD boundaries into PostGIS...")

    gdf = gpd.read_file(os.path.join(get_data_path(), 'lad_boundaries.geojson'))
    gdf = gdf[['LAD21CD', 'LAD21NM', 'geometry']].rename(columns={'LAD21CD': 'lad_code', 'LAD21NM': 'lad_name'})
    print(f"Loaded {len(gdf)} LAD boundaries from GeoJSON.")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lad_boundaries (
            lad_code TEXT PRIMARY KEY,
            lad_name TEXT,
            geom GEOMETRY(MultiPolygon, 4326)
        );
        TRUNCATE lad_boundaries;
        CREATE INDEX IF NOT EXISTS idx_lad_geom ON lad_boundaries USING GIST (geom);
    """)
    conn.commit()
    print("LAD boundaries table created/truncated.")

    from psycopg2.extras import execute_values
    
    batch_size = 1000
    data = []
    for _, row in gdf.iterrows():
        geojson_str = json.dumps(row['geometry'].__geo_interface__)
        data.append((row['lad_code'], row['lad_name'], geojson_str))
    
    # Insert in batches
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        execute_values(
            cursor,
            "INSERT INTO lad_boundaries (lad_code, lad_name, geom) VALUES %s",
            batch,
            template="(%s, %s, ST_Multi(ST_GeomFromGeoJSON(%s)))"
        )
        conn.commit()
        print(f"Inserted batch {i // batch_size + 1} ({len(batch)} rows)")
    cursor.close()
    conn.close()
    print("LAD boundaries loaded.")


def download_crime_data():
    """Download latest crime data from Police.uk, extract, process, and save as CSV."""
    import requests
    import zipfile
    import glob

    data_dir = get_data_path()
    zip_path = os.path.join(data_dir, 'crime_latest.zip')
    extract_path = os.path.join(data_dir, 'crime_unzipped')
    output_csv = os.path.join(data_dir, 'crime_data.csv')

    # download and unzip
    url = "https://data.police.uk/data/archive/latest.zip"
    print("Downloading latest crime data zip...")
    response = requests.get(url, timeout=600)  # 10 min timeout
    if response.status_code != 200:
        raise Exception(f"Failed to download zip: {response.status_code}")
    with open(zip_path, 'wb') as f:
        f.write(response.content)
    print(f"Download complete")

    os.makedirs(extract_path, exist_ok=True)
    print("Unzipping...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)
    print("Unzipped.")

    # contains all month dirs, find latest
    dirs = [d for d in os.listdir(extract_path) if os.path.isdir(os.path.join(extract_path, d))]
    dirs.sort(reverse=True)
    latest_dir = dirs[0]
    latest_path = os.path.join(extract_path, latest_dir)
    print(f"Latest directory: {latest_dir}")

    # find street CSVs
    csv_pattern = os.path.join(latest_path, f"{latest_dir}-*-street.csv")
    csv_files = glob.glob(csv_pattern)
    print(f"Found {len(csv_files)} street CSV files.")

    dfs = []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file, dtype=str)
            dfs.append(df)
        except Exception as e:
            print(f"Error reading {csv_file}: {e}")
    if not dfs:
        raise Exception("No CSV data read.")
    crime_df = pd.concat(dfs, ignore_index=True)
    print(f"Total raw rows: {len(crime_df)}")

    # clean
    crime_df = crime_df.dropna(subset=['Latitude', 'Longitude'])
    crime_df['Latitude'] = pd.to_numeric(crime_df['Latitude'], errors='coerce')
    crime_df['Longitude'] = pd.to_numeric(crime_df['Longitude'], errors='coerce')
    crime_df = crime_df.dropna(subset=['Latitude', 'Longitude'])

    columns_to_keep = ['Month', 'Longitude', 'Latitude', 'Location', 'LSOA code', 'LSOA name', 'Crime type', 'Last outcome category']
    crime_df = crime_df[columns_to_keep]

    crime_df.rename(columns={
        'Month': 'month',
        'Longitude': 'longitude',
        'Latitude': 'latitude',
        'Location': 'street_name',
        'LSOA code': 'lsoa_code',
        'LSOA name': 'lsoa_name',
        'Crime type': 'category',
        'Last outcome category': 'outcome_category'
    }, inplace=True)

    # Drop LSOA columns (not in table) and reorder to match table schema
    crime_df.drop(columns=['lsoa_code', 'lsoa_name'], inplace=True)
    crime_df = crime_df[['category', 'latitude', 'longitude', 'street_name', 'month', 'outcome_category']]

    print(f"Cleaned rows: {len(crime_df)}")

    crime_df.to_csv(output_csv, index=False)
    print(f"Saved to {output_csv}")

    # Cleanup: remove zip and unzipped
    os.remove(zip_path)
    import shutil
    shutil.rmtree(extract_path)
    print("Cleanup done.")


def clean_hygiene_data():
    """Read raw hygiene_data_all.csv, filter/mapping per user rules, and write cleaned hygiene_data.csv.

    Rules implemented:
      - Ratings numeric (keep 5,4,3,2,1,0) converted to int
      - Map: 'Pass' -> 3, 'Pass and Eat Safe' -> 4, 'Improvement Required' -> 2
      - Exclude rows with RatingValue in ['AwaitingInspection','Awaiting Inspection','AwaitingPublication','Exempt']
      - Drop rows missing Latitude or Longitude
      - Output columns match existing dbt seed schema: fhrs_id,business_name,rating_value,latitude,longitude,hygiene_score,structural_score,confidence_score,distance
    """
    RAW = os.path.join(get_data_path(), 'hygiene_data_all.csv')
    OUT = os.path.join(get_data_path(), 'hygiene_data.csv')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    mapping = {
        'Pass': 3,
        'Pass and Eat Safe': 4,
        'Improvement Required': 2
    }
    exclude = set(['AwaitingInspection', 'Awaiting Inspection', 'AwaitingPublication', 'Exempt'])

    # Read selected columns
    cols_of_interest = ['FHRSID', 'BusinessName', 'RatingValue', 'Latitude', 'Longitude', 'Hygiene', 'Structural', 'ConfidenceInManagement']
    df = pd.read_csv(RAW, usecols=lambda c: c in cols_of_interest, dtype=str)

    # Drop rows missing lat/lon
    df = df[df['Latitude'].notna() & df['Longitude'].notna()]

    # Map and filter ratings
    def map_rating(rv):
        if pd.isna(rv):
            return None
        rv_str = str(rv).strip()
        if rv_str in exclude:
            return None
        if rv_str in mapping:
            return mapping[rv_str]
        # try numeric
        try:
            return int(float(rv_str))
        except Exception:
            return None

    df['rating_value_mapped'] = df['RatingValue'].map(map_rating)

    # Drop rows where mapping failed (including excluded statuses)
    df = df[df['rating_value_mapped'].notna()]

    # Build output DataFrame with expected seed columns
    out_df = pd.DataFrame()
    out_df['fhrs_id'] = df['FHRSID']
    out_df['business_name'] = df['BusinessName']
    out_df['rating_value'] = df['rating_value_mapped'].astype(int)
    out_df['latitude'] = df['Latitude'].astype(float)
    out_df['longitude'] = df['Longitude'].astype(float)
    out_df['hygiene_score'] = pd.to_numeric(df.get('Hygiene'), errors='coerce')
    out_df['structural_score'] = pd.to_numeric(df.get('Structural'), errors='coerce')
    out_df['confidence_score'] = pd.to_numeric(df.get('ConfidenceInManagement'), errors='coerce')
    out_df['distance'] = None

    out_df.to_csv(OUT, index=False)
    print(f'Cleaned hygiene data written to {OUT} with {len(out_df)} rows')


def load_seeds_to_db():
    """Bulk load CSV seeds into Postgres using COPY for speed."""
    hook = PostgresHook(postgres_conn_id='ukns_db')
    conn = hook.get_conn()
    cursor = conn.cursor()

    seeds_dir = '/home/jovyan/shared/neighbourhood_score/dbt/seeds'

    # Define table schemas and create/truncate SQL
    schemas = {
        'crime_data': """
            DROP TABLE IF EXISTS crime_data CASCADE;
            CREATE TABLE crime_data (
                category TEXT,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                street_name TEXT,
                month TEXT,
                outcome_category TEXT
            );
        """,
        'hygiene_data': """
            DROP TABLE IF EXISTS hygiene_data CASCADE;
            CREATE TABLE hygiene_data (
                fhrs_id INTEGER,
                business_name TEXT,
                rating_value INTEGER,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                hygiene_score DOUBLE PRECISION,
                structural_score DOUBLE PRECISION,
                confidence_score DOUBLE PRECISION,
                distance DOUBLE PRECISION
            );
        """
    }

    for table, create_sql in schemas.items():
        csv_path = os.path.join(seeds_dir, f'{table}.csv')
        if os.path.exists(csv_path):
            cursor.execute(create_sql)
            with open(csv_path, 'r') as f:
                cursor.copy_expert(f"COPY {table} FROM STDIN WITH CSV HEADER", f)
            print(f"Bulk loaded {table} from {csv_path}")

            # Add geometry column and populate
            if table == 'crime_data':
                cursor.execute("""
                    ALTER TABLE crime_data ADD COLUMN IF NOT EXISTS geom GEOMETRY(Point, 4326);
                    UPDATE crime_data SET geom = ST_SetSRID(ST_Point(longitude::float, latitude::float), 4326) WHERE geom IS NULL;
                    CREATE INDEX IF NOT EXISTS idx_crime_geom ON crime_data USING GIST (geom);
                """)
            elif table == 'hygiene_data':
                cursor.execute("""
                    ALTER TABLE hygiene_data ADD COLUMN IF NOT EXISTS geom GEOMETRY(Point, 4326);
                    UPDATE hygiene_data SET geom = ST_SetSRID(ST_Point(longitude::float, latitude::float), 4326) WHERE geom IS NULL;
                    CREATE INDEX IF NOT EXISTS idx_hygiene_geom ON hygiene_data USING GIST (geom);
                """)
        else:
            print(f"Warning: {csv_path} not found, skipping {table}")

    conn.commit()
    cursor.close()
    conn.close()


default_args = {
    'owner': 'neighbourhood_score',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'neighbourhood_score_pipeline',
    # default_args=default_args,
    description='Pipeline to pull data, process with dbt for Neighbourhood Score',
    # schedule_interval=timedelta(days=1),
    schedule_interval=None,
    catchup=False,
)

# Load LSOA boundaries (one-time or as needed)
load_lsoa = PythonOperator(
    task_id='load_lsoa_boundaries',
    python_callable=load_lsoa_boundaries,
    dag=dag,
)

# Load MSOA boundaries (one-time or as needed)
load_msoa = PythonOperator(
    task_id='load_msoa_boundaries',
    python_callable=load_msoa_boundaries,
    dag=dag,
)

# Load LAD boundaries (one-time or as needed)
load_lad = PythonOperator(
    task_id='load_lad_boundaries',
    python_callable=load_lad_boundaries,
    dag=dag,
)

# Download and process latest crime data
# download_crime = PythonOperator(
#     task_id='download_crime_data',
#     python_callable=download_crime_data,
#     dag=dag,
# )

# Clean hygiene data from raw full dataset
clean_hygiene = PythonOperator(
    task_id='clean_hygiene_data',
    python_callable=clean_hygiene_data,
    dag=dag,
)

# Bulk load seeds into DB
load_seeds = PythonOperator(
    task_id='load_seeds',
    python_callable=load_seeds_to_db,
    dag=dag,
)

dbt_run = BashOperator(
    task_id='dbt_run',
    bash_command='cd /home/jovyan/shared/neighbourhood_score/dbt && dbt run',
    dag=dag,
)

# Set dependencies
# load_lsoa >> download_crime >> clean_hygiene >> copy_to_seeds >> load_seeds >> dbt_run
load_lsoa >> clean_hygiene >> load_seeds >> dbt_run
load_msoa >> dbt_run
load_lad >> dbt_run