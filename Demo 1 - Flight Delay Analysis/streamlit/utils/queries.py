from sqlalchemy import text
from data.db_connection import get_db

# --- New Queries ---

def get_airline_performance_stats():
    db = get_db()
    result = db.execute(text("SELECT * FROM airline_performance_stats;")).mappings()
    return [dict(row) for row in result]

def get_origin_airport_stats():
    db = get_db()
    result = db.execute(text("SELECT * FROM origin_airport_stats;")).mappings()
    return [dict(row) for row in result]

def get_airport_details():
    db = get_db()
    result = db.execute(text("SELECT * FROM airport_details;")).mappings()
    return [dict(row) for row in result]

def get_delay_distribution():
    db = get_db()
    result = db.execute(text("SELECT * FROM delay_distribution;")).mappings()
    return [dict(row) for row in result]

def get_flight_statistics_summary():
    db = get_db()
    result = db.execute(text("SELECT * FROM flight_statistics_summary;")).mappings()
    return [dict(row) for row in result]

def get_delay_vs_hour():
    db = get_db()
    result = db.execute(text("SELECT * FROM delay_vs_hour;")).mappings()
    return [dict(row) for row in result]

def get_hourly_avg_delay():
    db = get_db()
    result = db.execute(text("SELECT * FROM hourly_avg_delay;")).mappings()
    return [dict(row) for row in result]

def get_top10_origin_airports_by_delay():
    db = get_db()
    result = db.execute(
        text("SELECT * FROM top10_origin_airports_by_delay ORDER BY avg_departure_delay DESC LIMIT 10;")
    ).mappings()
    return [dict(row) for row in result]

def get_weekday_avg_delay():
    db = get_db()
    result = db.execute(text("SELECT * FROM weekday_avg_delay;")).mappings()
    return [dict(row) for row in result]

# --- Existing Reference Tables (Airports / Airlines) ---

def get_airports():
    db = get_db()
    result = db.execute(text("SELECT * FROM airport_details;")).mappings()
    return {
        row['iata_code']: {
            'airport': row['airport'],
            'city': row['city'],
            'state': row['state'],
            'latitude': row['latitude'],
            'longitude': row['longitude'],
        }
        for row in result
    }

def get_airlines():
    db = get_db()
    result = db.execute(text("SELECT * FROM airlines;")).mappings()
    return {row['iata_code']: row['airline'] for row in result}











# from sqlalchemy import text
# from data.db_connection import get_db

# def get_all_flights(limit=1000):
#     db = get_db()
#     result = db.execute(text(f'SELECT * FROM flights LIMIT {limit};'))
#     return [dict(row) for row in result]

# def get_airports():
#     db = get_db()
#     result = db.execute(text('SELECT * FROM airports;'))
#     return {
#         row['iata_code']: {
#             'airport': row['airport'],
#             'city': row['city'],
#             'state': row['state'],
#             'latitude': row['latitude'],
#             'longitude': row['longitude'],
#         }
#         for row in result
#     }


# def get_airlines():
#     db = get_db()
#     result = db.execute(text('SELECT * FROM airlines;'))
#     return {row['iata_code']: row['airline'] for row in result}
