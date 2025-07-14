from sqlalchemy import text

def create_tables_if_not_exists(db):
    ddl_statements = [
        # One row per airline; airline is primary key.
        """
        CREATE TABLE IF NOT EXISTS flight_statistics_summary (
            airline TEXT PRIMARY KEY,
            total_flights INTEGER NOT NULL,
            avg_departure_delay FLOAT,
            avg_arrival_delay FLOAT
        );
        """,

        # One row per bin_start; bin_start is primary key (no overlap).
        """
        CREATE TABLE IF NOT EXISTS delay_distribution (
            bin_start INTEGER PRIMARY KEY,
            bin_end INTEGER NOT NULL,
            count INTEGER NOT NULL
        );
        """,

        # One row per (hour, airline) pair.
        """
        CREATE TABLE IF NOT EXISTS delay_vs_hour (
            hour INTEGER NOT NULL,
            airline TEXT NOT NULL,
            avg_departure_delay FLOAT,
            PRIMARY KEY (hour, airline)
        );
        """,

        # One row per hour across all flights.
        """
        CREATE TABLE IF NOT EXISTS hourly_avg_delay (
            hour INT PRIMARY KEY,
            avg_departure_delay FLOAT
        );
        """,

        # Top 10 rows per run — this is snapshot data, so we truncate before insert.
        """
        CREATE TABLE IF NOT EXISTS top10_origin_airports_by_delay (
            origin_airport TEXT PRIMARY KEY,
            avg_departure_delay FLOAT
        );
        """,

        # One row per weekday name (Monday, Tuesday, ...).
        """
        CREATE TABLE IF NOT EXISTS weekday_avg_delay (
            day_of_week TEXT PRIMARY KEY,
            avg_departure_delay FLOAT,
            avg_arrival_delay FLOAT
        );
        """,

        # One row per origin airport.
        """
        CREATE TABLE IF NOT EXISTS origin_airport_stats (
            origin_airport TEXT PRIMARY KEY,
            flight_count INT,
            avg_departure_delay FLOAT
        );
        """,

        # Static table of airport metadata; iata_code is unique.
        """
        CREATE TABLE IF NOT EXISTS airport_details (
            iata_code TEXT PRIMARY KEY,
            airport TEXT,
            city TEXT,
            state TEXT,
            latitude FLOAT,
            longitude FLOAT
        );
        """,

        # One row per airline.
        """
        CREATE TABLE IF NOT EXISTS airline_performance_stats (
            airline TEXT PRIMARY KEY,
            avg_departure_delay FLOAT,
            avg_arrival_delay FLOAT,
            total_flights INT,
            on_time_pct FLOAT
        );
        """

        """
        CREATE TABLE IF NOT EXISTS airlines (
            iata_code VARCHAR PRIMARY KEY,
            airline VARCHAR
        );
        """
    ]

    with db.begin():
        for ddl in ddl_statements:
            db.execute(text(ddl))
