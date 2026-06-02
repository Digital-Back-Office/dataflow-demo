def get_delay_distribution(df):
    import pandas as pd
    bins = list(range(-60, 301, 10))
    df['delay_bin'] = pd.cut(df['DEPARTURE_DELAY'], bins=bins, right=False)
    hist = df['delay_bin'].value_counts().sort_index()

    rows = [{
        "bin_start": int(interval.left),
        "bin_end": int(interval.right),
        "count": int(count)
    } for interval, count in hist.items()]
    return "delay_distribution", rows

def get_flight_statistics_summary(df):
    summary_df = df.groupby('AIRLINE').agg(
        total_flights=('AIRLINE', 'count'),
        avg_departure_delay=('DEPARTURE_DELAY', 'mean'),
        avg_arrival_delay=('ARRIVAL_DELAY', 'mean')
    ).reset_index()
    rows = summary_df.to_dict(orient='records')
    return "flight_statistics_summary", rows

def get_delay_vs_hour(df):
    import pandas as pd
    df['hour'] = pd.to_datetime(df['SCHEDULED_DEPARTURE']).dt.hour
    hourly_df = df.groupby(['hour', 'AIRLINE']).agg(
        avg_departure_delay=('DEPARTURE_DELAY', 'mean')
    ).reset_index()
    return "delay_vs_hour", hourly_df.to_dict(orient='records')

def get_hourly_avg_delay(df):
    import pandas as pd
    df['hour'] = pd.to_datetime(df['SCHEDULED_DEPARTURE']).dt.hour
    agg = df.groupby('hour')['DEPARTURE_DELAY'].mean().reset_index(name='avg_departure_delay')
    return "hourly_avg_delay", agg.to_dict(orient='records')

def get_top10_origin_airports_by_delay(df):
    agg = df.groupby('ORIGIN_AIRPORT')['DEPARTURE_DELAY'] \
        .mean().sort_values(ascending=False).head(10) \
        .reset_index(name='avg_departure_delay')
    return "top10_origin_airports_by_delay", agg.to_dict(orient='records')

def get_weekday_avg_delay(df):
    import pandas as pd
    df['day_of_week'] = pd.to_datetime(df['SCHEDULED_DEPARTURE']).dt.day_name()
    agg = df.groupby('day_of_week')[['DEPARTURE_DELAY', 'ARRIVAL_DELAY']].mean().reset_index()
    agg.columns = ['day_of_week', 'avg_departure_delay', 'avg_arrival_delay']
    return "weekday_avg_delay", agg.to_dict(orient='records')

def get_origin_airport_stats(df):
    agg = df.groupby('ORIGIN_AIRPORT').agg(
        flight_count=('ORIGIN_AIRPORT', 'count'),
        avg_departure_delay=('DEPARTURE_DELAY', 'mean')
    ).reset_index()
    return "origin_airport_stats", agg.to_dict(orient='records')

def get_airline_performance_stats(df):
    agg = df.groupby('AIRLINE').agg(
        avg_departure_delay=('DEPARTURE_DELAY', 'mean'),
        avg_arrival_delay=('ARRIVAL_DELAY', 'mean'),
        total_flights=('AIRLINE', 'count'),
        on_time_pct=('ARRIVAL_DELAY', lambda x: (x <= 0).sum() / len(x) * 100)
    ).reset_index()
    return "airline_performance_stats", agg.to_dict(orient='records')
