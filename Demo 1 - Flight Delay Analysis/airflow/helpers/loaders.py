from sqlalchemy import text

# Tables that should be cleared on each run
SNAPSHOT_TABLES = {"top10_origin_airports_by_delay", "delay_distribution"}

# Table-specific primary keys for ON CONFLICT handling
CONFLICT_KEYS = {
    "flight_statistics_summary": ["airline"],
    "delay_distribution": ["bin_start"],
    "delay_vs_hour": ["hour", "airline"],
    "hourly_avg_delay": ["hour"],
    "top10_origin_airports_by_delay": ["origin_airport"],  # cleared before insert
    "weekday_avg_delay": ["day_of_week"],
    "origin_airport_stats": ["origin_airport"],
    "airport_details": ["iata_code"],
    "airline_performance_stats": ["airline"],
}

def load_to_db(engine, table, rows):
    if not rows:
        return

    if table not in CONFLICT_KEYS:
        raise ValueError(f"No conflict keys defined for table: {table}")

    keys = rows[0].keys()
    columns = ', '.join(keys)
    placeholders = ', '.join([f":{k}" for k in keys])
    conflict_keys = CONFLICT_KEYS[table]

    # Only update columns that aren't part of conflict keys
    update_assignments = ', '.join([f"{k}=EXCLUDED.{k}" for k in keys if k not in conflict_keys])

    insert_stmt = text(f"""
        INSERT INTO {table} ({columns}) VALUES ({placeholders})
        ON CONFLICT ({', '.join(conflict_keys)}) DO UPDATE SET {update_assignments}
    """)

    with engine.begin() as conn:
        if table in SNAPSHOT_TABLES:
            conn.execute(text(f"DELETE FROM {table}"))

        for row in rows:
            conn.execute(insert_stmt, row)

def load_airport_details(engine, airports_df):
    rows = airports_df.rename(columns={
        'IATA': 'iata_code',
        'AIRPORT': 'airport',
        'CITY': 'city',
        'STATE': 'state',
        'LATITUDE': 'latitude', 
        'LONGITUDE': 'longitude'
    })[['iata_code', 'airport', 'city', 'state', 'latitude', 'longitude']].to_dict(orient='records')

    load_to_db(engine, "airport_details", rows)

def load_airlines(engine, airlines_df):
    records = airlines_df.rename(columns={
        'name': 'airline'
    })[['iata_code', 'airline']].to_dict('records')

    insert_sql = """
    INSERT INTO airlines (iata_code, airline)
    VALUES (:iata_code, :airline)
    ON CONFLICT (iata_code) DO NOTHING;
    """
    with engine.begin() as conn:
        conn.execute(text(insert_sql), records)
