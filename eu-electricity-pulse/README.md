# EU Electricity Price Pulse

A live dashboard tracking hour-by-hour day-ahead electricity prices across all 41 European ENTSO-E bidding zones. Shows how renewable intermittency and cross-border capacity drive real-time price spreads — and where prices are behaving abnormally.

## Architecture

```
euenergy.live API (day-ahead auction prices)
        │  daily at 13:00 CEST — 41 zones × 24 hours
        ▼
Airflow DAG: electricity_pulse_etl
        │  upsert → raw.zone_prices_hourly
        ▼
dbt models
        │  staging → mart_current_prices, mart_hourly_timeline,
        │            mart_zone_spreads, mart_price_baselines,
        │            mart_price_anomalies, mart_clean_hours
        ▼
Dash app (4 pages)
  1. Price Map     — animated choropleth, zone prices by hour
  2. Timeline      — multi-zone price curve comparison
  3. Spreads       — 41×41 zone-pair arbitrage heatmap
  4. Anomalies     — ±2σ spike/dip detection vs 30-day baseline
```

## Prerequisites

### Dataflow Console — Connections

| Name | Type | Purpose |
|---|---|---|
| `euenergy_db` | PostgreSQL | Stores raw prices, zone dimension, and dbt mart tables |

### Dataflow Console — Secrets

| Name | Purpose |
|---|---|
| `euenergy_api_key` | euenergy.live API token (free at https://euenergy.live — register with your email) |

> **Note:** In the Airflow DAG the API key is read via `Variable.get("euenergy_api_key")`. In the Dash app it is read via `dataflow.secret("euenergy_api_key")`. Dataflow automatically syncs secrets to both.

## Starting each component

### Airflow
Upload `airflow/dags/electricity_pulse_etl.py` to your Dataflow Airflow environment. The DAG runs daily at 13:00 CEST. Trigger it manually for the first run.

### dbt
```bash
cd dbt
dbt run --profiles-dir .
```
The dbt profile reads connection details from environment variables set by Dataflow when running inside Airflow (`EUENERGY_DB_HOST`, `EUENERGY_DB_PORT`, `EUENERGY_DB_NAME`, `EUENERGY_DB_USER`, `EUENERGY_DB_PASSWORD`).

### Dash app
```bash
cd dashapp
pip install -r ../requirements.txt
python app.py
```
The app runs on port 8050. Dataflow exposes this automatically.

## Notes on data accumulation

- **Price map and timeline** work from day 1.
- **Spread heatmap** works from day 1.
- **Anomaly detection** requires ≥30 days of data to compute meaningful 30-day baselines. The anomalies page will be empty initially — this is expected.
- **euenergy.live** only exposes today's day-ahead prices. Historical data accumulates as the DAG runs each day.
