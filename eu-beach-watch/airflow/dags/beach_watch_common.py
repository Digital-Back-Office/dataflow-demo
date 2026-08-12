"""
beach_watch_common — shared EEA ingestion logic.

Used by both the beach_watch_ingest Airflow DAG (upserts only) and the
standalone scripts/reload_all_data.py utility (full wipe + reload). Contains
no Airflow imports so it works in either context — callers pass in an open
psycopg2 connection.

Captures the FULL attribute set returned by both EEA source APIs, not just
the fields the app currently renders — more data now, more app features
later, without another schema migration.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Source APIs
# --------------------------------------------------------------------------- #
ARCGIS_URL = (
    "https://marine.discomap.eea.europa.eu/arcgis/rest/services/"
    "BathingWater/BathingWater_Dyna_WM_2024/MapServer/3/query"
)
ARCGIS_PAGE_SIZE = 1000

DISCODATA_URL = "https://discodata.eea.europa.eu/sql"
DISCODATA_TABLE = "[WISE_BWD].[latest].[timeseries_MonitoringResult]"
DISCODATA_PAGE_SIZE = 1000

# qualityStatus = 2024, qualityStatus_minus1 = 2023, ..., minus10 = 2014
QUAL_FIELD_TO_YEAR = {"qualityStatus": 2024}
for _i in range(1, 11):
    QUAL_FIELD_TO_YEAR[f"qualityStatus_minus{_i}"] = 2024 - _i


# --------------------------------------------------------------------------- #
# Schema DDL — CREATE for fresh installs, ALTER for upgrading existing ones.
# Both are idempotent so this can run before every ingest safely.
# --------------------------------------------------------------------------- #
CREATE_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.bathing_sites (
    bathing_water_id     TEXT PRIMARY KEY,
    name                 TEXT,
    country_code         TEXT,
    water_type           TEXT,
    latitude              DOUBLE PRECISION,
    longitude             DOUBLE PRECISION,
    class_2014 TEXT, class_2015 TEXT, class_2016 TEXT, class_2017 TEXT,
    class_2018 TEXT, class_2019 TEXT, class_2020 TEXT, class_2021 TEXT,
    class_2022 TEXT, class_2023 TEXT, class_2024 TEXT,
    ingested_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.samples (
    sample_id             TEXT PRIMARY KEY,
    bathing_water_id      TEXT,
    sample_date           DATE,
    ecoli_cfu             DOUBLE PRECISION,
    enterococci_cfu       DOUBLE PRECISION,
    ingested_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_samples_site ON raw.samples(bathing_water_id);
CREATE INDEX IF NOT EXISTS idx_samples_date ON raw.samples(sample_date);

CREATE TABLE IF NOT EXISTS raw.site_rainfall (
    bathing_water_id      TEXT,
    sample_date           DATE,
    precip_7d_mm          DOUBLE PRECISION,
    ingested_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (bathing_water_id, sample_date)
);

-- Extra EEA fields beyond the ones the app currently renders — captured for
-- future use (see beach_watch_common.py docstring).
ALTER TABLE raw.bathing_sites ADD COLUMN IF NOT EXISTS object_id INTEGER;
ALTER TABLE raw.bathing_sites ADD COLUMN IF NOT EXISTS country_name TEXT;
ALTER TABLE raw.bathing_sites ADD COLUMN IF NOT EXISTS is_eu27 TEXT;
ALTER TABLE raw.bathing_sites ADD COLUMN IF NOT EXISTS bw_profile_link TEXT;
ALTER TABLE raw.bathing_sites ADD COLUMN IF NOT EXISTS quality_status_order TEXT;

ALTER TABLE raw.samples ADD COLUMN IF NOT EXISTS season INTEGER;
ALTER TABLE raw.samples ADD COLUMN IF NOT EXISTS ecoli_status TEXT;
ALTER TABLE raw.samples ADD COLUMN IF NOT EXISTS enterococci_status TEXT;
ALTER TABLE raw.samples ADD COLUMN IF NOT EXISTS sample_status TEXT;
ALTER TABLE raw.samples ADD COLUMN IF NOT EXISTS remarks TEXT;
ALTER TABLE raw.samples ADD COLUMN IF NOT EXISTS metadata_version_id TEXT;
ALTER TABLE raw.samples ADD COLUMN IF NOT EXISTS metadata_begin_lifespan TEXT;
ALTER TABLE raw.samples ADD COLUMN IF NOT EXISTS metadata_end_lifespan TEXT;
ALTER TABLE raw.samples ADD COLUMN IF NOT EXISTS metadata_replaces TEXT;
ALTER TABLE raw.samples ADD COLUMN IF NOT EXISTS metadata_replaced_by TEXT;
ALTER TABLE raw.samples ADD COLUMN IF NOT EXISTS metadata_status_code TEXT;
ALTER TABLE raw.samples ADD COLUMN IF NOT EXISTS metadata_status_date TEXT;
ALTER TABLE raw.samples ADD COLUMN IF NOT EXISTS metadata_observation_status TEXT;
ALTER TABLE raw.samples ADD COLUMN IF NOT EXISTS metadata_statements TEXT;
"""


# --------------------------------------------------------------------------- #
# Site ingest — full EEA ArcGIS attribute set, upserted by bathing_water_id.
# --------------------------------------------------------------------------- #
def ingest_sites(pg_conn) -> int:
    import requests
    import psycopg2.extras

    upsert_sql = """
        INSERT INTO raw.bathing_sites (
            bathing_water_id, name, country_code, water_type,
            latitude, longitude,
            class_2014, class_2015, class_2016, class_2017, class_2018,
            class_2019, class_2020, class_2021, class_2022, class_2023, class_2024,
            object_id, country_name, is_eu27, bw_profile_link, quality_status_order,
            ingested_at
        ) VALUES %s
        ON CONFLICT (bathing_water_id) DO UPDATE SET
            name                 = EXCLUDED.name,
            country_code         = EXCLUDED.country_code,
            water_type           = EXCLUDED.water_type,
            latitude              = EXCLUDED.latitude,
            longitude             = EXCLUDED.longitude,
            class_2014 = EXCLUDED.class_2014, class_2015 = EXCLUDED.class_2015,
            class_2016 = EXCLUDED.class_2016, class_2017 = EXCLUDED.class_2017,
            class_2018 = EXCLUDED.class_2018, class_2019 = EXCLUDED.class_2019,
            class_2020 = EXCLUDED.class_2020, class_2021 = EXCLUDED.class_2021,
            class_2022 = EXCLUDED.class_2022, class_2023 = EXCLUDED.class_2023,
            class_2024 = EXCLUDED.class_2024,
            object_id            = EXCLUDED.object_id,
            country_name         = EXCLUDED.country_name,
            is_eu27               = EXCLUDED.is_eu27,
            bw_profile_link       = EXCLUDED.bw_profile_link,
            quality_status_order  = EXCLUDED.quality_status_order,
            ingested_at           = CURRENT_TIMESTAMP
    """

    offset = 0
    total = 0
    params = {
        "f": "json", "where": "1=1", "outFields": "*",
        "returnGeometry": "true", "outSR": "4326",
        "resultRecordCount": ARCGIS_PAGE_SIZE,
    }

    while True:
        params["resultOffset"] = offset
        resp = requests.get(ARCGIS_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            break

        rows = []
        for feat in features:
            attrs = feat.get("attributes", {})
            geom = feat.get("geometry", {})

            bw_id = attrs.get("bathingWaterIdentifier") or attrs.get("OBJECTID")
            if not bw_id:
                continue

            lat = attrs.get("latitude") or (geom.get("y") if geom else None)
            lon = attrs.get("longitude") or (geom.get("x") if geom else None)

            year_classes = {}
            for field, year in QUAL_FIELD_TO_YEAR.items():
                val = attrs.get(field)
                year_classes[year] = val.strip().title() if isinstance(val, str) else None

            rows.append((
                str(bw_id),
                attrs.get("bathingWaterName") or attrs.get("name") or "",
                (attrs.get("countryCode") or "").upper(),
                (attrs.get("bwWaterCategory") or attrs.get("waterBodyType") or "").lower(),
                lat, lon,
                year_classes.get(2014), year_classes.get(2015), year_classes.get(2016),
                year_classes.get(2017), year_classes.get(2018), year_classes.get(2019),
                year_classes.get(2020), year_classes.get(2021), year_classes.get(2022),
                year_classes.get(2023), year_classes.get(2024),
                attrs.get("OBJECTID"),
                attrs.get("countryName"),
                attrs.get("EU27"),
                attrs.get("bwProfileLink"),
                attrs.get("qualityStatus_order"),
                datetime.utcnow(),
            ))

        if rows:
            with pg_conn.cursor() as cur:
                psycopg2.extras.execute_values(cur, upsert_sql, rows, page_size=500)
            pg_conn.commit()
            total += len(rows)
            logger.info("Sites ingested so far: %d (offset %d)", total, offset)

        if not data.get("exceededTransferLimit", False):
            break
        offset += ARCGIS_PAGE_SIZE

    logger.info("Site ingest complete. Total rows: %d", total)
    return total


# --------------------------------------------------------------------------- #
# Sample ingest — full Discodata attribute set for a given year range.
# sample_id uses the source's own UID, which is stable across re-ingests —
# this makes upserts genuinely idempotent (the old bw_id+date+page+index
# scheme could shift between runs and silently create duplicate rows).
# --------------------------------------------------------------------------- #
def ingest_samples(pg_conn, start_year: int, end_year: int) -> int:
    import requests
    import urllib.parse
    import psycopg2.extras

    upsert_sql = """
        INSERT INTO raw.samples (
            sample_id, bathing_water_id, sample_date, ecoli_cfu, enterococci_cfu,
            season, ecoli_status, enterococci_status, sample_status, remarks,
            metadata_version_id, metadata_begin_lifespan, metadata_end_lifespan,
            metadata_replaces, metadata_replaced_by, metadata_status_code,
            metadata_status_date, metadata_observation_status, metadata_statements,
            ingested_at
        ) VALUES %s
        ON CONFLICT (sample_id) DO UPDATE SET
            bathing_water_id       = EXCLUDED.bathing_water_id,
            sample_date             = EXCLUDED.sample_date,
            ecoli_cfu               = EXCLUDED.ecoli_cfu,
            enterococci_cfu         = EXCLUDED.enterococci_cfu,
            season                  = EXCLUDED.season,
            ecoli_status             = EXCLUDED.ecoli_status,
            enterococci_status       = EXCLUDED.enterococci_status,
            sample_status            = EXCLUDED.sample_status,
            remarks                  = EXCLUDED.remarks,
            metadata_version_id      = EXCLUDED.metadata_version_id,
            metadata_begin_lifespan  = EXCLUDED.metadata_begin_lifespan,
            metadata_end_lifespan    = EXCLUDED.metadata_end_lifespan,
            metadata_replaces        = EXCLUDED.metadata_replaces,
            metadata_replaced_by     = EXCLUDED.metadata_replaced_by,
            metadata_status_code     = EXCLUDED.metadata_status_code,
            metadata_status_date     = EXCLUDED.metadata_status_date,
            metadata_observation_status = EXCLUDED.metadata_observation_status,
            metadata_statements      = EXCLUDED.metadata_statements,
            ingested_at              = CURRENT_TIMESTAMP
    """

    select_fields = (
        "UID, season, bathingWaterIdentifier, sampleDate, "
        "escherichiaColiValue, intestinalEnterococciValue, "
        "escherichiaColiStatus, intestinalEnterococciStatus, sampleStatus, remarks, "
        "metadata_versionId, metadata_beginLifeSpanVersion, metadata_endLifeSpanVersion, "
        "metadata_replaces, metadata_replacedBy, metadata_statusCode, "
        "metadata_statusDate, metadata_observationStatus, metadata_statements"
    )
    base_query = (
        f"SELECT {select_fields} FROM {DISCODATA_TABLE} "
        f"WHERE YEAR(sampleDate) BETWEEN {start_year} AND {end_year} "
        f"ORDER BY bathingWaterIdentifier, sampleDate"
    )

    page = 1
    total = 0

    while True:
        encoded = urllib.parse.quote(base_query)
        url = f"{DISCODATA_URL}?query={encoded}&p={page}&nrOfHits={DISCODATA_PAGE_SIZE}"
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        if not results:
            break

        rows = []
        for rec in results:
            uid = rec.get("UID")
            bw_id = rec.get("bathingWaterIdentifier")
            sample_date = rec.get("sampleDate", "")[:10] if rec.get("sampleDate") else None
            if uid is None or not bw_id or not sample_date:
                continue

            ecoli = rec.get("escherichiaColiValue")
            entero = rec.get("intestinalEnterococciValue")

            rows.append((
                str(uid), bw_id, sample_date,
                float(ecoli) if ecoli is not None else None,
                float(entero) if entero is not None else None,
                rec.get("season"),
                rec.get("escherichiaColiStatus"),
                rec.get("intestinalEnterococciStatus"),
                rec.get("sampleStatus"),
                rec.get("remarks"),
                rec.get("metadata_versionId"),
                rec.get("metadata_beginLifeSpanVersion"),
                rec.get("metadata_endLifeSpanVersion"),
                rec.get("metadata_replaces"),
                rec.get("metadata_replacedBy"),
                rec.get("metadata_statusCode"),
                rec.get("metadata_statusDate"),
                rec.get("metadata_observationStatus"),
                rec.get("metadata_statements"),
                datetime.utcnow(),
            ))

        if rows:
            with pg_conn.cursor() as cur:
                psycopg2.extras.execute_values(cur, upsert_sql, rows, page_size=500)
            pg_conn.commit()
            total += len(rows)
            logger.info("Samples ingested so far: %d (page %d)", total, page)

        if len(results) < DISCODATA_PAGE_SIZE:
            break
        page += 1

    logger.info("Sample ingest complete (%d-%d). Total rows: %d", start_year, end_year, total)
    return total
