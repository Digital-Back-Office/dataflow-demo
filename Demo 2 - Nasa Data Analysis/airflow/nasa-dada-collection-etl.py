from datetime import datetime, timedelta
from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.hooks.base import BaseHook
import json
import logging
import sys

DB_CONN_ID = "demo_db"

default_args = {
    'owner': 'space_data_team',
    'depends_on_past': False,
    'start_date': datetime(2025, 7, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'catchup': False
}

dag = DAG(
    'nasa_space_data_etl_pipeline',
    default_args=default_args,
    description='Daily ETL pipeline to fetch NASA space data and store in database',
    schedule_interval='0 8 * * *',
    max_active_runs=1,
    tags=['etl', 'nasa', 'space', 'daily']
)


def normalize_db_type(conn_type: str) -> str:
    """Normalize Airflow connection types to supported values."""
    conn_type = (conn_type or '').lower()
    if conn_type.startswith('postgres'):
        return 'postgres'
    if conn_type.startswith('sqlite'):
        return 'sqlite'
    return conn_type

def fetch_apod_data(**context):
    """
    Fetch Astronomy Picture of the Day data from NASA API for the past 15 days
    """
    import requests

    try:
        NASA_API_KEY = Variable.get("nasa_api_key")
        apod_records = []
        execution_date = datetime.strptime(context['ds'], '%Y-%m-%d')
        
        for days_back in range(15):
            current_date = execution_date - timedelta(days=days_back)
            date_str = current_date.strftime('%Y-%m-%d')
            
            url = "https://api.nasa.gov/planetary/apod"
            params = {
                'api_key': NASA_API_KEY,
                'date': date_str,
                'hd': True
            }
            
            logging.info(f"Fetching APOD data for date: {date_str}")
            
            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                if 'date' not in data:
                    logging.warning(f"APOD response missing required 'date' field for {date_str}, skipping")
                    continue
                
                apod_record = {
                    'date': data.get('date'),
                    'title': data.get('title', ''),
                    'explanation': data.get('explanation', ''),
                    'url': data.get('url', ''),
                    'media_type': data.get('media_type', 'image'),
                    'hdurl': data.get('hdurl', ''),
                    'copyright': data.get('copyright', ''),
                    'service_version': data.get('service_version', ''),
                    'created_at': datetime.now().isoformat()
                }
                
                apod_records.append(apod_record)
                logging.info(f"Successfully fetched APOD data for {date_str}: {apod_record['title']}")
                
            except requests.exceptions.RequestException as req_error:
                logging.warning(f"HTTP error fetching APOD data for {date_str}: {str(req_error)}")
                continue
            except json.JSONDecodeError as json_error:
                logging.warning(f"JSON decode error for APOD data for {date_str}: {str(json_error)}")
                continue
            except Exception as error:
                logging.warning(f"Unexpected error fetching APOD data for {date_str}: {str(error)}")
                continue
        
        if not apod_records:
            raise ValueError("Failed to fetch any APOD data for the past 15 days")
            
        logging.info(f"Successfully fetched {len(apod_records)} APOD records for the past 15 days")
        return json.dumps(apod_records)
        
    except Exception as e:
        logging.error(f"Error in APOD batch collection: {str(e)}")
        raise

def fetch_iss_location(**context):
    """
    Fetch multiple ISS location data points over a time interval
    to provide better sampling for visualization.
    Each DAG run collects new data points that build up a complete
    24-hour ISS tracking path in the database.
    Data points are deduplicated by timestamp when inserted into the database.
    """
    import requests

    try:
        url = "http://api.open-notify.org/iss-now.json"
        iss_records = []
        
        num_data_points = 30
        interval_seconds = 5
        logging.info(f"Starting ISS location data collection: {num_data_points} new points with {interval_seconds}s intervals")
        
        for i in range(num_data_points):
            try:
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                data = response.json()
                
                if data.get('message') == 'success':
                    iss_record = {
                        'timestamp': datetime.fromtimestamp(data['timestamp']).isoformat(),
                        'latitude': float(data['iss_position']['latitude']),
                        'longitude': float(data['iss_position']['longitude']),
                        'altitude': 408.0,  # Approximate ISS altitude in km
                        'velocity': 27600.0,  # Approximate ISS velocity in km/h
                        'created_at': datetime.now().isoformat()
                    }
                    iss_records.append(iss_record)
                    logging.info(f"Collected ISS data point {i+1}/{num_data_points}")
                    
                    if i < num_data_points - 1:
                        from time import sleep
                        sleep(interval_seconds)
                else:
                    logging.warning(f"ISS API returned unexpected message: {data.get('message')}")
            except Exception as point_error:
                logging.warning(f"Error collecting ISS data point {i+1}: {str(point_error)}")
                continue
        
        if not iss_records:
            raise ValueError("Failed to collect any ISS location data points")
        
        if len(iss_records) < 10:
            logging.warning("Collected fewer than 10 ISS data points. Will attempt to create interpolated points.")
            if len(iss_records) >= 2:
                iss_records.sort(key=lambda x: x['timestamp'])
                interpolated_records = []
                
                for i in range(len(iss_records) - 1):
                    pt1 = iss_records[i]
                    pt2 = iss_records[i+1]
                    
                    t1 = datetime.fromisoformat(pt1['timestamp'].replace('Z', '+00:00'))
                    t2 = datetime.fromisoformat(pt2['timestamp'].replace('Z', '+00:00'))
                    
                    time_diff = (t2 - t1).total_seconds()
                    
                    if 0 < time_diff < 300:
                        for j in range(1, 4):
                            factor = j / 4.0
                            
                            timestamp = t1 + timedelta(seconds=time_diff * factor)
                            lat = pt1['latitude'] + (pt2['latitude'] - pt1['latitude']) * factor
                            lon = pt1['longitude'] + (pt2['longitude'] - pt1['longitude']) * factor
                            
                            interp_record = {
                                'timestamp': timestamp.isoformat(),
                                'latitude': lat,
                                'longitude': lon,
                                'altitude': 408.0,
                                'velocity': 27600.0,
                                'created_at': datetime.now().isoformat(),
                                'is_interpolated': True
                            }
                            interpolated_records.append(interp_record)
                
                iss_records.extend(interpolated_records)
                logging.info(f"Added {len(interpolated_records)} interpolated ISS data points")
        
        logging.info(f"Successfully fetched/generated {len(iss_records)} ISS location data points")
        return json.dumps(iss_records)
            
    except Exception as e:
        logging.error(f"Error in ISS location batch collection: {str(e)}")
        raise

def fetch_asteroid_data(**context):
    """
    Fetch Near Earth Objects (Asteroids) data from NASA API
    """
    import requests

    try:
        from datetime import datetime, timedelta
        NASA_API_KEY = Variable.get("nasa_api_key")
        
        start_date = datetime.strptime(context['ds'], '%Y-%m-%d')
        asteroid_records = []
        
        for i in range(0, 5):
            current_start = start_date + timedelta(days=i*6)
            current_end = min(current_start + timedelta(days=6), start_date + timedelta(days=29))
            
            current_start_str = current_start.strftime('%Y-%m-%d')
            current_end_str = current_end.strftime('%Y-%m-%d')
            
            logging.info(f"Fetching asteroid data for period {i+1}/5: {current_start_str} to {current_end_str}")
            
            url = "https://api.nasa.gov/neo/rest/v1/feed"
            params = {
                'api_key': NASA_API_KEY,
                'start_date': current_start_str,
                'end_date': current_end_str
            }
            
            # Add delay between API calls to avoid rate limiting
            if i > 0:
                from time import sleep
                sleep(1)  # 1 second delay between calls
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'near_earth_objects' in data:
                for date_str, asteroids in data['near_earth_objects'].items():
                    for asteroid in asteroids:
                        for approach in asteroid.get('close_approach_data', []):
                            asteroid_record = {
                                'neo_id': asteroid.get('id'),
                                'name': asteroid.get('name', '').replace("'", "''"),
                                'approach_date': approach.get('close_approach_date'),
                                'estimated_diameter_min': float(asteroid.get('estimated_diameter', {}).get('kilometers', {}).get('estimated_diameter_min', 0)),
                                'estimated_diameter_max': float(asteroid.get('estimated_diameter', {}).get('kilometers', {}).get('estimated_diameter_max', 0)),
                                'relative_velocity': float(approach.get('relative_velocity', {}).get('kilometers_per_hour', 0)),
                                'miss_distance': float(approach.get('miss_distance', {}).get('kilometers', 0)),
                                'is_potentially_hazardous': asteroid.get('is_potentially_hazardous_asteroid', False),
                                'absolute_magnitude': float(asteroid.get('absolute_magnitude_h', 0)),
                                'nasa_jpl_url': asteroid.get('nasa_jpl_url', ''),
                                'orbiting_body': approach.get('orbiting_body', 'Earth'),
                                'created_at': datetime.now().isoformat()
                            }
                            asteroid_records.append(asteroid_record)
        
        end_date = (datetime.strptime(context['ds'], '%Y-%m-%d') + timedelta(days=29)).strftime('%Y-%m-%d')
        logging.info(f"Successfully fetched {len(asteroid_records)} asteroid records for 30-day period from {context['ds']} to {end_date}")
        return json.dumps(asteroid_records)
        
    except Exception as e:
        logging.error(f"Error fetching asteroid data: {str(e)}")
        raise

def fetch_space_missions(**context):
    """
    Fetch upcoming space missions data from The Space Devs API
    """
    import requests
    
    try:
        url = "https://ll.thespacedevs.com/2.2.0/launch/"
        params = {
            'limit': 50,
            'net__gte': context['ds'],
            'ordering': 'net'
        }
        
        logging.info(f"Fetching space missions from date: {context['ds']}")
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        mission_records = []
        
        for mission in data.get('results', []):
            try:
                rocket_name = ''
                if mission.get('rocket') and mission['rocket'].get('configuration'):
                    rocket_name = mission['rocket']['configuration'].get('name', '')
                
                mission_type = ''
                if mission.get('mission'):
                    mission_type = mission['mission'].get('type', '')
                
                launch_location = ''
                if mission.get('pad') and mission['pad'].get('location'):
                    launch_location = mission['pad']['location'].get('name', '')
                
                status = ''
                if mission.get('status'):
                    status = mission['status'].get('name', '')
                
                launch_service_provider = ''
                if mission.get('launch_service_provider'):
                    launch_service_provider = mission['launch_service_provider'].get('name', '')
                
                mission_description = ''
                if mission.get('mission') and mission['mission'].get('description'):
                    mission_description = mission['mission']['description'][:1000]
                
                mission_record = {
                    'mission_id': str(mission.get('id', '')),
                    'name': mission.get('name', ''),
                    'launch_date': mission.get('net', ''),
                    'rocket_name': rocket_name,
                    'mission_type': mission_type,
                    'launch_location': launch_location,
                    'status': status,
                    'probability': mission.get('probability', 0) or 0,
                    'launch_service_provider': launch_service_provider,
                    'image_url': mission.get('image', ''),
                    'webcast_live': mission.get('webcast_live', False),
                    'mission_description': mission_description,
                    'created_at': datetime.now().isoformat()
                }
                mission_records.append(mission_record)
                
            except Exception as mission_error:
                logging.warning(f"Error processing mission {mission.get('id', 'unknown')}: {mission_error}")
                continue
        
        logging.info(f"Successfully fetched {len(mission_records)} space mission records")
        return json.dumps(mission_records)
        
    except requests.exceptions.RequestException as e:
        logging.error(f"HTTP error fetching space missions: {str(e)}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error for space missions: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error fetching space missions: {str(e)}")
        raise

def prepare_apod_insert_query(**context):
    """
    Prepare SQL upsert (insert or update) query for multiple APOD data records 
    with proper error handling and deduplication based on date
    """
    try:
        conn = BaseHook.get_connection(DB_CONN_ID)
        db_type = normalize_db_type(conn.conn_type)
        
        task_instance = context['task_instance']
        apod_data = task_instance.xcom_pull(task_ids='fetch_apod_data')
        
        if not apod_data:
            logging.warning("No APOD data received from fetch task")
            return ["SELECT 1;"]
        
        records = json.loads(apod_data)
        
        if not isinstance(records, list):
            logging.warning("Expected list of APOD records but received single record. Converting to list.")
            records = [records]
            
        if not records:
            logging.warning("Empty APOD records list")
            return ["SELECT 1;"]
        
        # Limit records for SQLite to reduce insert time
        if db_type == 'sqlite':
            print("Limiting APOD records to 5 for SQLite to avoid long insert times")
            records = records[:5]
        
        logging.info(f"Preparing APOD inserts for {len(records)} records on {db_type}")
        
        def escape_sql_string(value):
            if value is None:
                return ''
            return str(value).replace("'", "''")
        
        insert_statements = []
        
        for i, data in enumerate(records):
            try:
                date_val = escape_sql_string(data.get('date', ''))
                title_val = escape_sql_string(data.get('title', ''))
                explanation_val = escape_sql_string(data.get('explanation', ''))[:2000]
                url_val = escape_sql_string(data.get('url', ''))
                media_type_val = escape_sql_string(data.get('media_type', 'image'))
                hdurl_val = escape_sql_string(data.get('hdurl', ''))
                copyright_val = escape_sql_string(data.get('copyright', ''))
                service_version_val = escape_sql_string(data.get('service_version', ''))
                created_at_val = escape_sql_string(data.get('created_at', datetime.now().isoformat()))
                
                if db_type == 'postgres':
                    print(f"Preparing upsert for APOD record {i+1}/{len(records)}: {date_val} - {title_val[:30]}...")
                    insert_sql = f"""
                    INSERT INTO apod_images (
                        date, title, explanation, url, media_type, hdurl, copyright, service_version, created_at
                    ) VALUES (
                        '{date_val}',
                        '{title_val}',
                        '{explanation_val}',
                        '{url_val}',
                        '{media_type_val}',
                        '{hdurl_val}',
                        '{copyright_val}',
                        '{service_version_val}',
                        '{created_at_val}'
                    )
                    ON CONFLICT (date) 
                    DO UPDATE SET
                        title = EXCLUDED.title,
                        explanation = EXCLUDED.explanation,
                        url = EXCLUDED.url,
                        media_type = EXCLUDED.media_type,
                        hdurl = EXCLUDED.hdurl,
                        copyright = EXCLUDED.copyright,
                        service_version = EXCLUDED.service_version;
                    """
                else:  # sqlite
                    print(f"db type is sqlite, preparing insert (will replace existing record with same date if exists) for APOD record {i+1}/{len(records)}: {date_val} - {title_val[:30]}...")
                    insert_sql = f"""
                    INSERT OR REPLACE INTO apod_images (
                        date, title, explanation, url, media_type, hdurl, copyright, service_version, created_at
                    ) VALUES (
                        '{date_val}',
                        '{title_val}',
                        '{explanation_val}',
                        '{url_val}',
                        '{media_type_val}',
                        '{hdurl_val}',
                        '{copyright_val}',
                        '{service_version_val}',
                        '{created_at_val}'
                    );
                    """
                
                insert_statements.append(insert_sql)
                
            except Exception as record_error:
                logging.error(f"Error processing APOD record {i}: {record_error}")
                logging.error(f"Problematic record: {data}")
                continue
        
        if not insert_statements:
            logging.warning("No valid APOD records to insert")
            return ["SELECT 1;"]
            
        logging.info(f"APOD upsert query prepared with {len(insert_statements)} records (will insert new or update existing)")
        return insert_statements
        
    except Exception as e:
        logging.error(f"Error preparing APOD insert query: {str(e)}")
        logging.error(f"Raw APOD data: {apod_data}")
        raise

def prepare_iss_insert_query(**context):
    """
    Prepare SQL upsert (insert or update) query for multiple ISS location data points 
    with proper error handling and deduplication based on timestamp
    """
    try:
        conn = BaseHook.get_connection(DB_CONN_ID)
        db_type = normalize_db_type(conn.conn_type)
        
        task_instance = context['task_instance']
        iss_data = task_instance.xcom_pull(task_ids='fetch_iss_location')
        
        if not iss_data:
            logging.warning("No ISS data received from fetch task")
            return ["SELECT 1;"]
        
        records = json.loads(iss_data)
        
        if not isinstance(records, list):
            logging.warning("Expected list of ISS records but received single record. Converting to list.")
            records = [records]
            
        if not records:
            logging.warning("Empty ISS records list")
            return ["SELECT 1;"]
        
        # Limit records for SQLite
        if db_type == 'sqlite':
            records = records[:10]  # Allow more for ISS as it's frequent
        
        logging.info(f"Preparing ISS insert for {len(records)} data points on {db_type}")
        
        insert_statements = []
        
        if db_type == 'postgres':
            column_check_sql = """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name='iss_location' AND column_name='is_interpolated'
                ) THEN
                    ALTER TABLE iss_location ADD COLUMN is_interpolated BOOLEAN DEFAULT FALSE;
                END IF;
            END $$;
            """
            insert_statements.append(column_check_sql)
        
        for i, data in enumerate(records):
            try:
                latitude = float(data.get('latitude', 0))
                longitude = float(data.get('longitude', 0))
                altitude = float(data.get('altitude', 408.0))
                velocity = float(data.get('velocity', 27600.0))
                
                timestamp_val = str(data.get('timestamp', '')).replace("'", "''")
                created_at_val = str(data.get('created_at', datetime.now().isoformat())).replace("'", "''")
                
                is_interpolated = 1 if bool(data.get('is_interpolated', False)) else 0
                
                if db_type == 'postgres':
                    insert_sql = f"""
                    INSERT INTO iss_location (
                        timestamp, latitude, longitude, altitude, velocity, created_at, 
                        is_interpolated
                    ) VALUES (
                        '{timestamp_val}',
                        {latitude},
                        {longitude},
                        {altitude},
                        {velocity},
                        '{created_at_val}',
                        {is_interpolated}
                    )
                    ON CONFLICT (timestamp) 
                    DO UPDATE SET
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude,
                        altitude = EXCLUDED.altitude,
                        velocity = EXCLUDED.velocity,
                        is_interpolated = EXCLUDED.is_interpolated;
                    """
                else:  # sqlite
                    insert_sql = f"""
                    INSERT OR REPLACE INTO iss_location (
                        timestamp, latitude, longitude, altitude, velocity, created_at, 
                        is_interpolated
                    ) VALUES (
                        '{timestamp_val}',
                        {latitude},
                        {longitude},
                        {altitude},
                        {velocity},
                        '{created_at_val}',
                        {is_interpolated}
                    );
                    """
                insert_statements.append(insert_sql)
                
            except Exception as record_error:
                logging.error(f"Error processing ISS record {i}: {record_error}")
                logging.error(f"Problematic record: {data}")
                continue
        
        if len(insert_statements) <= (1 if db_type == 'postgres' else 0):
            logging.warning("No valid ISS records to insert")
            return ["SELECT 1;"]
            
        logging.info(f"ISS upsert query prepared with {len(insert_statements) - (1 if db_type == 'postgres' else 0)} records")
        return insert_statements
        
    except Exception as e:
        logging.error(f"Error preparing ISS insert query: {str(e)}")
        logging.error(f"Raw ISS data: {iss_data}")
        raise

def prepare_asteroids_insert_query(**context):
    """
    Prepare SQL upsert (insert or update) query for asteroid data 
    with proper error handling and deduplication based on neo_id and approach_date
    """
    try:
        conn = BaseHook.get_connection(DB_CONN_ID)
        db_type = normalize_db_type(conn.conn_type)
        
        task_instance = context['task_instance']
        asteroid_data = task_instance.xcom_pull(task_ids='fetch_asteroid_data')
        
        if not asteroid_data:
            logging.warning("No asteroid data received from fetch task")
            return ["SELECT 1;"]
        
        data = json.loads(asteroid_data)
        
        if not data:
            logging.info("No asteroids found for this date")
            return ["SELECT 1;"]
        
        # Limit records for SQLite
        if db_type == 'sqlite':
            data = data[:5]
        
        logging.info(f"Preparing asteroid inserts for {len(data)} records on {db_type}")
        
        def escape_sql_string(value):
            if value is None:
                return ''
            return str(value).replace("'", "''")
        
        def safe_float(value, default=0.0):
            try:
                return float(value) if value is not None else default
            except (ValueError, TypeError):
                return default
        
        def safe_bool(value):
            return 1 if bool(value) else 0
        
        insert_statements = []
        
        for i, record in enumerate(data):
            try:
                neo_id = escape_sql_string(record.get('neo_id', ''))
                name = escape_sql_string(record.get('name', ''))
                approach_date = escape_sql_string(record.get('approach_date', ''))
                estimated_diameter_min = safe_float(record.get('estimated_diameter_min'))
                estimated_diameter_max = safe_float(record.get('estimated_diameter_max'))
                relative_velocity = safe_float(record.get('relative_velocity'))
                miss_distance = safe_float(record.get('miss_distance'))
                is_potentially_hazardous = safe_bool(record.get('is_potentially_hazardous'))
                absolute_magnitude = safe_float(record.get('absolute_magnitude'))
                nasa_jpl_url = escape_sql_string(record.get('nasa_jpl_url', ''))
                orbiting_body = escape_sql_string(record.get('orbiting_body', 'Earth'))
                created_at = escape_sql_string(record.get('created_at', datetime.now().isoformat()))
                
                if db_type == 'postgres':
                    insert_sql = f"""
                    INSERT INTO asteroids (
                        neo_id, name, approach_date, estimated_diameter_min, estimated_diameter_max,
                        relative_velocity, miss_distance, is_potentially_hazardous, absolute_magnitude,
                        nasa_jpl_url, orbiting_body, created_at
                    ) VALUES (
                        '{neo_id}',
                        '{name}',
                        '{approach_date}',
                        {estimated_diameter_min},
                        {estimated_diameter_max},
                        {relative_velocity},
                        {miss_distance},
                        {is_potentially_hazardous},
                        {absolute_magnitude},
                        '{nasa_jpl_url}',
                        '{orbiting_body}',
                        '{created_at}'
                    )
                    ON CONFLICT (neo_id, approach_date) 
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        estimated_diameter_min = EXCLUDED.estimated_diameter_min,
                        estimated_diameter_max = EXCLUDED.estimated_diameter_max,
                        relative_velocity = EXCLUDED.relative_velocity,
                        miss_distance = EXCLUDED.miss_distance,
                        is_potentially_hazardous = EXCLUDED.is_potentially_hazardous,
                        absolute_magnitude = EXCLUDED.absolute_magnitude;
                    """
                else:  # sqlite
                    insert_sql = f"""
                    INSERT OR REPLACE INTO asteroids (
                        neo_id, name, approach_date, estimated_diameter_min, estimated_diameter_max,
                        relative_velocity, miss_distance, is_potentially_hazardous, absolute_magnitude,
                        nasa_jpl_url, orbiting_body, created_at
                    ) VALUES (
                        '{neo_id}',
                        '{name}',
                        '{approach_date}',
                        {estimated_diameter_min},
                        {estimated_diameter_max},
                        {relative_velocity},
                        {miss_distance},
                        {is_potentially_hazardous},
                        {absolute_magnitude},
                        '{nasa_jpl_url}',
                        '{orbiting_body}',
                        '{created_at}'
                    );
                    """
                insert_statements.append(insert_sql)
                
            except Exception as record_error:
                logging.error(f"Error processing asteroid record {i}: {record_error}")
                logging.error(f"Problematic record: {record}")
                continue
        
        if not insert_statements:
            logging.warning("No valid asteroid records to insert")
            return ["SELECT 1;"]
        
        logging.info(f"Asteroid upsert query prepared with {len(insert_statements)} records (will insert new or update existing)")
        return insert_statements
        
    except Exception as e:
        logging.error(f"Error preparing asteroid insert query: {str(e)}")
        logging.error(f"Raw asteroid data: {asteroid_data}")
        raise

def prepare_missions_insert_query(**context):
    """
    Prepare SQL upsert (insert or update) query for space missions data 
    with proper error handling and deduplication based on mission_id
    """
    try:
        conn = BaseHook.get_connection(DB_CONN_ID)
        db_type = normalize_db_type(conn.conn_type)
        
        task_instance = context['task_instance']
        missions_data = task_instance.xcom_pull(task_ids='fetch_space_missions')
        
        if not missions_data:
            logging.warning("No missions data received from fetch task")
            return ["SELECT 1;"]
        
        data = json.loads(missions_data)
        
        if not data:
            logging.info("No missions found for this timeframe")
            return ["SELECT 1;"]
        
        # Limit records for SQLite
        if db_type == 'sqlite':
            data = data[:5]
        
        logging.info(f"Preparing mission inserts for {len(data)} records on {db_type}")
        
        def escape_sql_string(value):
            if value is None:
                return ''
            return str(value).replace("'", "''")
        
        def safe_int(value, default=0):
            try:
                return int(value) if value is not None else default
            except (ValueError, TypeError):
                return default
        
        def safe_bool(value):
            return 1 if bool(value) else 0
        
        insert_statements = []
        
        for i, record in enumerate(data):
            try:
                mission_id = escape_sql_string(record.get('mission_id', ''))
                name = escape_sql_string(record.get('name', ''))
                launch_date = escape_sql_string(record.get('launch_date', ''))
                rocket_name = escape_sql_string(record.get('rocket_name', ''))
                mission_type = escape_sql_string(record.get('mission_type', ''))
                launch_location = escape_sql_string(record.get('launch_location', ''))
                status = escape_sql_string(record.get('status', ''))
                probability = safe_int(record.get('probability', 0))
                launch_service_provider = escape_sql_string(record.get('launch_service_provider', ''))
                image_url = escape_sql_string(record.get('image_url', ''))
                webcast_live = safe_bool(record.get('webcast_live', False))
                mission_description = escape_sql_string(record.get('mission_description', ''))[:1000]
                created_at = escape_sql_string(record.get('created_at', datetime.now().isoformat()))
                
                if db_type == 'postgres':
                    insert_sql = f"""
                    INSERT INTO space_missions (
                        mission_id, name, launch_date, rocket_name, mission_type, launch_location,
                        status, probability, launch_service_provider, image_url, webcast_live,
                        mission_description, created_at
                    ) VALUES (
                        '{mission_id}',
                        '{name}',
                        '{launch_date}',
                        '{rocket_name}',
                        '{mission_type}',
                        '{launch_location}',
                        '{status}',
                        {probability},
                        '{launch_service_provider}',
                        '{image_url}',
                        {webcast_live},
                        '{mission_description}',
                        '{created_at}'
                    )
                    ON CONFLICT (mission_id) 
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        launch_date = EXCLUDED.launch_date,
                        rocket_name = EXCLUDED.rocket_name,
                        mission_type = EXCLUDED.mission_type,
                        launch_location = EXCLUDED.launch_location,
                        status = EXCLUDED.status,
                        probability = EXCLUDED.probability,
                        launch_service_provider = EXCLUDED.launch_service_provider,
                        image_url = EXCLUDED.image_url,
                        webcast_live = EXCLUDED.webcast_live,
                        mission_description = EXCLUDED.mission_description;
                    """
                else:  # sqlite
                    insert_sql = f"""
                    INSERT OR REPLACE INTO space_missions (
                        mission_id, name, launch_date, rocket_name, mission_type, launch_location,
                        status, probability, launch_service_provider, image_url, webcast_live,
                        mission_description, created_at
                    ) VALUES (
                        '{mission_id}',
                        '{name}',
                        '{launch_date}',
                        '{rocket_name}',
                        '{mission_type}',
                        '{launch_location}',
                        '{status}',
                        {probability},
                        '{launch_service_provider}',
                        '{image_url}',
                        {webcast_live},
                        '{mission_description}',
                        '{created_at}'
                    );
                    """
                insert_statements.append(insert_sql)
                
            except Exception as record_error:
                logging.error(f"Error processing mission record {i}: {record_error}")
                logging.error(f"Problematic record: {record}")
                continue
        
        if not insert_statements:
            logging.warning("No valid mission records to insert")
            return ["SELECT 1;"]
        
        logging.info(f"Mission upsert query prepared with {len(insert_statements)} records (will insert new or update existing)")
        return insert_statements
        
    except Exception as e:
        logging.error(f"Error preparing mission insert query: {str(e)}")
        logging.error(f"Raw mission data: {missions_data}")
        raise

# Task 1: Create all necessary tables
def create_tables_if_not_exist(**context):
    """
    Create database tables if they don't exist, with database-specific syntax
    """
    try:
        conn = BaseHook.get_connection(DB_CONN_ID)
        db_type = normalize_db_type(conn.conn_type)
        
        logging.info(f"Creating tables for database type: {db_type}")
        
        # Define table creation SQL based on database type
        if db_type == 'sqlite':
            id_column = "INTEGER PRIMARY KEY AUTOINCREMENT"
            if_not_exists = "IF NOT EXISTS"
        elif db_type == 'postgres':
            id_column = "SERIAL PRIMARY KEY"
            if_not_exists = "IF NOT EXISTS"
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
        
        create_table_sqls = [
            f"""
            CREATE TABLE {if_not_exists} apod_images (
                id {id_column},
                date DATE UNIQUE NOT NULL,
                title VARCHAR(500),
                explanation TEXT,
                url TEXT,
                media_type VARCHAR(50),
                hdurl TEXT,
                copyright VARCHAR(200),
                service_version VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            f"""
            CREATE TABLE {if_not_exists} iss_location (
                id {id_column},
                timestamp TIMESTAMP NOT NULL UNIQUE,
                latitude DECIMAL(10,6),
                longitude DECIMAL(10,6),
                altitude DECIMAL(10,2),
                velocity DECIMAL(10,2),
                is_interpolated INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            f"""
            CREATE TABLE {if_not_exists} asteroids (
                id {id_column},
                neo_id VARCHAR(50),
                name VARCHAR(200),
                approach_date DATE,
                estimated_diameter_min DECIMAL(15,6),
                estimated_diameter_max DECIMAL(15,6),
                relative_velocity DECIMAL(15,2),
                miss_distance DECIMAL(20,2),
                is_potentially_hazardous INTEGER,
                absolute_magnitude DECIMAL(8,2),
                nasa_jpl_url TEXT,
                orbiting_body VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(neo_id, approach_date)
            );
            """,
            f"""
            CREATE TABLE {if_not_exists} space_missions (
                id {id_column},
                mission_id VARCHAR(50) UNIQUE,
                name VARCHAR(300),
                launch_date TIMESTAMP,
                rocket_name VARCHAR(200),
                mission_type VARCHAR(100),
                launch_location VARCHAR(200),
                status VARCHAR(50),
                probability INTEGER,
                launch_service_provider VARCHAR(200),
                image_url TEXT,
                webcast_live INTEGER,
                mission_description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_apod_date ON apod_images(date);",
            "CREATE INDEX IF NOT EXISTS idx_iss_timestamp ON iss_location(timestamp);",
            "CREATE INDEX IF NOT EXISTS idx_asteroids_approach_date ON asteroids(approach_date);",
            "CREATE INDEX IF NOT EXISTS idx_asteroids_hazardous ON asteroids(is_potentially_hazardous);",
            "CREATE INDEX IF NOT EXISTS idx_missions_launch_date ON space_missions(launch_date);",
            "CREATE INDEX IF NOT EXISTS idx_missions_status ON space_missions(status);"
        ]
        
        # Execute the table creation statements
        hook = BaseHook.get_hook(conn_id=DB_CONN_ID)
        
        for sql in create_table_sqls:
            if sql.strip():
                logging.info(f"Executing: {sql[:100]}...")
                hook.run(sql)
        
        logging.info("Database tables created/verified successfully")
        return "Tables created successfully"
        
    except Exception as e:
        logging.error(f"Error creating tables: {e}")
        raise

create_tables = PythonOperator(
    task_id='create_tables',
    python_callable=create_tables_if_not_exist,
    dag=dag
)

# Task 2: Fetch APOD data
fetch_apod_task = PythonOperator(
    task_id='fetch_apod_data',
    python_callable=fetch_apod_data,
    dag=dag
)

# Task 3: Fetch ISS location
fetch_iss_task = PythonOperator(
    task_id='fetch_iss_location',
    python_callable=fetch_iss_location,
    dag=dag
)

# Task 4: Fetch asteroid data
fetch_asteroids_task = PythonOperator(
    task_id='fetch_asteroid_data',
    python_callable=fetch_asteroid_data,
    dag=dag
)

# Task 5: Fetch space missions
fetch_missions_task = PythonOperator(
    task_id='fetch_space_missions',
    python_callable=fetch_space_missions,
    dag=dag
)

def execute_sql_list(task_id, **context):
    """
    Execute a list of SQL statements pulled from xcom
    """
    sql_list = context['task_instance'].xcom_pull(task_ids=task_id)
    if not sql_list:
        logging.warning(f"No SQL list received from {task_id}")
        return
    
    from airflow.hooks.base import BaseHook
    hook = BaseHook.get_hook(conn_id=DB_CONN_ID)
    
    for sql in sql_list:
        if sql.strip():
            logging.info(f"Executing SQL: {sql[:100]}...")
            hook.run(sql, autocommit=True)

# Task 6: Insert APOD data
insert_apod_task = PythonOperator(
    task_id='insert_apod_data',
    python_callable=execute_sql_list,
    op_kwargs={'task_id': 'prepare_apod_query'},
    dag=dag
)

# Task 7: Insert ISS data
insert_iss_task = PythonOperator(
    task_id='insert_iss_data',
    python_callable=execute_sql_list,
    op_kwargs={'task_id': 'prepare_iss_query'},
    dag=dag
)

# Task 8: Insert asteroid data
insert_asteroids_task = PythonOperator(
    task_id='insert_asteroids_data',
    python_callable=execute_sql_list,
    op_kwargs={'task_id': 'prepare_asteroids_query'},
    dag=dag
)

# Task 9: Insert missions data
insert_missions_task = PythonOperator(
    task_id='insert_missions_data',
    python_callable=execute_sql_list,
    op_kwargs={'task_id': 'prepare_missions_query'},
    dag=dag
)

# Task 10-13: Prepare queries
prepare_apod_query = PythonOperator(
    task_id='prepare_apod_query',
    python_callable=prepare_apod_insert_query,
    dag=dag
)

prepare_iss_query = PythonOperator(
    task_id='prepare_iss_query',
    python_callable=prepare_iss_insert_query,
    dag=dag
)

prepare_asteroids_query = PythonOperator(
    task_id='prepare_asteroids_query',
    python_callable=prepare_asteroids_insert_query,
    dag=dag
)

prepare_missions_query = PythonOperator(
    task_id='prepare_missions_query',
    python_callable=prepare_missions_insert_query,
    dag=dag
)

# Task 14: Data quality validation
validate_data_quality = SQLExecuteQueryOperator(
    task_id='validate_data_quality',
    conn_id=DB_CONN_ID,
    autocommit=True,
    sql="""
    -- Simple record count check for each table
    SELECT 'APOD' as table_name, COUNT(*) as total_records FROM apod_images
    UNION ALL
    SELECT 'ISS' as table_name, COUNT(*) as total_records FROM iss_location
    UNION ALL
    SELECT 'Asteroids' as table_name, COUNT(*) as total_records FROM asteroids
    UNION ALL
    SELECT 'Missions' as table_name, COUNT(*) as total_records FROM space_missions;
    """,
    dag=dag
)

def cleanup_old_data(**context):
    """
    Cleanup old data based on database type
    """
    from airflow.hooks.base import BaseHook
    conn = BaseHook.get_connection(DB_CONN_ID)
    db_type = normalize_db_type(conn.conn_type)
    
    hook = BaseHook.get_hook(conn_id=DB_CONN_ID)
    
    if db_type == 'postgres':
        sql_statements = [
            "DELETE FROM iss_location WHERE timestamp < NOW() - INTERVAL '24 hours';",
            "DELETE FROM asteroids WHERE approach_date < CURRENT_DATE - INTERVAL '15 days';",
            "DELETE FROM space_missions WHERE launch_date < CURRENT_DATE - INTERVAL '15 days' AND status IN ('Launch Successful', 'Launch Failure');"
        ]
    else:  # sqlite
        sql_statements = [
            "DELETE FROM iss_location WHERE timestamp < datetime('now', '-24 hours');",
            "DELETE FROM asteroids WHERE approach_date < date('now', '-15 days');",
            "DELETE FROM space_missions WHERE launch_date < date('now', '-15 days') AND status IN ('Launch Successful', 'Launch Failure');"
        ]
    
    logging.info(f"Executing cleanup SQL for {db_type}")
    for sql in sql_statements:
        if sql.strip():
            logging.info(f"Executing: {sql}")
            hook.run(sql, autocommit=True)

# Task 15: Cleanup old data
cleanup_old_data_task = PythonOperator(
    task_id='cleanup_old_data',
    python_callable=cleanup_old_data,
    dag=dag
)

# Task dependencies - create_tables runs first
create_tables >> [fetch_apod_task, fetch_iss_task, fetch_asteroids_task, fetch_missions_task]

fetch_apod_task >> prepare_apod_query >> insert_apod_task
fetch_iss_task >> prepare_iss_query >> insert_iss_task
fetch_asteroids_task >> prepare_asteroids_query >> insert_asteroids_task
fetch_missions_task >> prepare_missions_query >> insert_missions_task

[insert_apod_task, insert_iss_task, insert_asteroids_task, insert_missions_task] >> validate_data_quality >> cleanup_old_data_task