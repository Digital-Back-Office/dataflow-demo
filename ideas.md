# Project Ideas

Generated: 2026-07-22

---

## 1. FIFA World Cup 2026 Data Vault
**Status:** Not started

The 2026 World Cup final (Spain 1–0 Argentina) was played on July 19. Peak search interest right now. Ingests all 104 match results and computes advanced metrics — xG proxies, upset scores, team form ratings, and a "chaos index" per group. Full bracket visualization + leaderboard in Dash.

- **Data:** football-data.org (free, confirmed WC2026 coverage) + openfootball/worldcup.json (public domain)
- **Stack:** Airflow + dbt + Dash
- **Pipeline:** football-data.org API → Airflow (matches, scorers, standings) → dbt staging (normalize events) → dbt intermediate (form, upset scores) → dbt mart (tournament_summary, team_rankings, scorer_leaderboard) → Dash multi-page dashboard

---

## 2. Global Wildfire Intelligence Platform
**Status:** Not started

Live satellite fire data fetched every 3 hours, aggregated into country-level burn severity with anomaly detection vs 5-year baselines. Animated globe with active fire clusters and a top-10 countries leaderboard by fire radiative power.

- **Data:** NASA FIRMS API (free MAP_KEY, near-real-time VIIRS/MODIS detections)
- **Stack:** Airflow + dbt + Dash
- **Pipeline:** FIRMS API → Airflow ingest (raw hotspots) → dbt staging (deduplicate by satellite pass) → dbt intermediate (country/date aggregates, FRP totals) → dbt mart (ranked_countries, anomaly_alerts) → Dash globe + leaderboard

---

## 3. USGS Seismic Pulse — Earthquake Risk Monitor
**Status:** Not started

Ingests every M1.0+ earthquake globally every 30 minutes and computes rolling regional risk scores comparing current 30-day activity to each region's 10-year baseline. Interactive globe with magnitude-scaled dots + risk leaderboard for elevated fault zones.

- **Data:** USGS Earthquake Catalog API (free, no key, real-time GeoJSON)
- **Stack:** Airflow + dbt + Dash
- **Pipeline:** USGS GeoJSON → Airflow upsert (raw_earthquakes) → dbt staging (normalize magnitude/depth, add region label) → dbt intermediate (1-degree grid cell rolling aggregates) → dbt mart (regional_risk_scores) → Dash globe + sidebar

---

## 4. City Air Quality Ranker
**Status:** Not started

Daily rankings of 200+ cities by AQI with trend direction (getting better vs worse) and weather-adjusted pollution spikes. City comparison selector lets users pick up to 5 cities and compare PM2.5, NO2, and O3 trends side-by-side.

- **Data:** OpenAQ API (free, 300 calls/5 min, 100+ countries) + Open-Meteo Air Quality API (free, no key)
- **Stack:** Airflow + dbt + Streamlit
- **Pipeline:** OpenAQ + Open-Meteo → Airflow (raw_measurements, raw_weather) → dbt staging (deduplicate, normalize units) → dbt intermediate (rolling AQIs, weather-adjusted AQI) → dbt mart (city_rankings, spike_events) → Streamlit explorer

---

## 5. FRED Macro Pulse — US Economic Stress Monitor
**Status:** Not started

20+ Federal Reserve indicators (yield curve, unemployment claims, CPI, housing starts, credit card delinquency, etc.) distilled into a single composite stress index with recession probability. Main gauge + per-indicator sparklines with z-scores + yield curve shape chart updated daily.

- **Data:** FRED API (free key, 800,000+ series, 120 req/min)
- **Stack:** Airflow + dbt + Dash
- **Pipeline:** FRED API → Airflow (raw_fred_series) → dbt staging (normalize to date spine) → dbt intermediate (z-scores, NBER recession labels) → dbt mart (stress_index_daily, indicator_dashboard) → Dash gauges + multi-chart layout

---

## 6. EU Inflation Divergence Tracker
**Status:** Not started

The ECB sets one interest rate for 27 economies diverging by 3–5 percentage points. Shows exactly how — country by country, category by category (food, energy, services, housing). Every European follows inflation; the "one-rate-fits-none" story is in the news constantly. No clean visual tool currently shows all 27 countries side by side by category.

- **Data:** ECB SDMX 2.1 API (free, no key, HICP dataset, monthly, history to 1999)
- **Stack:** Airflow + dbt + Dash
- **Pipeline:** ECB SDMX API → Airflow (raw monthly HICP series per country × category) → dbt staging (normalize, parse XML) → dbt intermediate (deviation from EA average, divergence score, anomaly flags) → dbt mart (country_rankings, category_breakdown) → Dash choropleth + time-series

---

## 7. EU City Air Quality Monitor
**Status:** Not started

Daily ranking of 50+ European cities by PM2.5, NO2, and ozone from Copernicus satellite model data, updated every morning. WHO threshold breach counts, 7/30-day rolling averages, seasonal deviation from baseline. Animated EU map with city dots coloured by AQI + worst cities leaderboard.

- **Data:** Open-Meteo Air Quality API sourced from CAMS/Copernicus (free, no key, hourly, 3-year archive)
- **Stack:** Airflow + dbt + Dash
- **Note:** IQAir/AirVisual cover this space for consumers — strongest angle is the pipeline transparency and multi-year trend analysis

---

## 8. European Labour Market Tightness Index
**Status:** Not started

Country-by-country Beveridge curve for Europe — combining job vacancy rates and unemployment to show which EU economies are running hot (Netherlands, Belgium) vs which have slack (Spain, youth unemployment 25%+). Classified into quadrants: tight/loose × improving/deteriorating. Novel analysis no public tool presents as a Beveridge chart.

- **Data:** Eurostat job vacancies API `jvs_q_r21` (quarterly) + unemployment API `une_rt_m` (monthly) — both free, no registration
- **Stack:** Airflow + dbt + Streamlit
- **Pipeline:** Two Airflow DAGs (different schedules) → separate raw tables → dbt join + tightness ratio + quadrant classification → Streamlit scatter plot with time slider + country selector
