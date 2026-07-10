{{ config(
    materialized='table',
    pre_hook=["SET statement_timeout = 0"]
) }}

WITH simplified_msoa AS (
  SELECT 
    msoa_code,
    msoa_name,
    geom,
    ST_SimplifyPreserveTopology(geom, 0.001) AS geom_simpl
  FROM msoa_boundaries
),

crime_agg AS (
  SELECT 
    m.msoa_code, 
    COUNT(c.*) AS crime_count
  FROM simplified_msoa m
  LEFT JOIN stg_crime c
    ON c.geom && m.geom_simpl
   AND ST_Contains(m.geom_simpl, ST_Centroid(c.geom))
  GROUP BY m.msoa_code
),

hygiene_agg AS (
  SELECT 
    m.msoa_code, 
    AVG(h.rating_value) AS avg_rating
  FROM simplified_msoa m
  LEFT JOIN stg_hygiene h
    ON h.geom && m.geom_simpl
   AND ST_Contains(m.geom_simpl, ST_Centroid(h.geom))
  GROUP BY m.msoa_code
)

SELECT
  m.msoa_code,
  m.msoa_name,

  -- ORIGINAL GEOMETRY
  m.geom,

  -- ORIGINAL GEOJSON
  ST_AsGeoJSON(m.geom) AS geom_geojson,

  -- SIMPLIFIED GEOJSON (RESTORED)
  ST_AsGeoJSON(m.geom_simpl) AS geom_geojson_simpl,

  -- METRICS
  COALESCE(c.crime_count, 0) AS crime_count,
  COALESCE(h.avg_rating, 0) AS avg_rating,

  -- SCORE
  (COALESCE(c.crime_count, 0) / 100.0) 
  + (5 - COALESCE(h.avg_rating, 0)) AS grit_score

FROM simplified_msoa m
LEFT JOIN crime_agg c USING (msoa_code)
LEFT JOIN hygiene_agg h USING (msoa_code)
