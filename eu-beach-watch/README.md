# EU Beach Water Quality Monitor

Tracks 22,000+ European bathing sites using European Environment Agency (EEA)
open data. Shows 11 years of annual water-quality classifications per site,
flags beaches trending better or worse, surfaces "hidden gems", and correlates
water quality with pre-sample rainfall.

## Overview

- **Airflow** ingests the EEA site layer, per-sample bacterial readings and
  Open-Meteo rainfall, then runs dbt.
- **dbt** transforms raw data into per-site scorecards and country rankings.
- **Dash** presents an interactive map, leaderboards and country comparison.

## Architecture

```
EEA ArcGIS REST (site layer, 11yr classifications) ─┐
EEA Discodata SQL (per-sample E.coli/enterococci) ──┤→ Airflow → Postgres (raw.*)
Open-Meteo Archive (7-day pre-sample rainfall) ─────┘        │
                                                             ▼
                                            dbt (staging → intermediate → marts)
                                                             │
                                                             ▼
                                        marts.mart_site_scorecard / _country_rankings
                                                             │
                                                             ▼
                                                    Dash app (map + tabs)
```

### DAGs
- `beach_watch_ingest` — annual (`0 3 1 6 *`, 1 June). Ingests sites + recent
  samples (2019–2024), selects ~500 interesting sites, enriches with rainfall,
  runs dbt.
- `beach_watch_backfill` — manual one-shot. Full per-sample history 2008–2024.

### dbt models
```
staging/stg_bathing_sites   staging/stg_samples
            │                        │
            ├──────────► int_site_trends
            │            int_rainfall_correlation
            ▼
   marts/mart_site_scorecard   marts/mart_country_rankings
```

## Prerequisites (Dataflow console)

**Connections:**
- `beach_watch_db` — PostgreSQL database storing raw ingested data, dbt marts,
  and serving the Dash app.

**Secrets / Variables:**
- None. All three data sources (EEA ArcGIS, EEA Discodata, Open-Meteo Archive)
  are public and require no API key.

## Running

### Airflow
Deploy the `airflow/` folder. dbt lives at `airflow/dags/dbt/` and is invoked by
the `run_dbt` task via `dbt run --profiles-dir .`; credentials are passed as
env vars derived from the `beach_watch_db` connection (no hardcoded secrets).
Trigger `beach_watch_backfill` once, then let `beach_watch_ingest` run annually.

<!-- TODO: add Dataflow-specific deploy/start commands -->

### dbt (standalone, optional)
```
cd airflow/dags/dbt
export BEACH_WATCH_HOST=... BEACH_WATCH_PORT=5432 BEACH_WATCH_USER=... \
       BEACH_WATCH_PASSWORD=... BEACH_WATCH_DBNAME=...
dbt run --profiles-dir .
```

### Dash app
```
cd dashapp
python app.py          # serves on 0.0.0.0:8050
```
<!-- TODO: add Dataflow-specific app start command -->
