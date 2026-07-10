{{ config(
    materialized='table',
    pre_hook=["SET statement_timeout = 0"],
    post_hook=[
        "CREATE INDEX IF NOT EXISTS idx_ngrit_msoa_geom ON {{ this }} USING GIST (geom)",
        "ANALYZE {{ this }}"
    ]
) }}

WITH simplified_msoa AS (
  SELECT
    msoa_code,
    msoa_name,
    geom,
    ST_SimplifyPreserveTopology(geom, 0.001) AS geom_simpl
  FROM msoa_boundaries
),

base as (
  select b.msoa_code, b.msoa_name, b.geom, b.geom_simpl,
         coalesce(c.crime_count, 0)                                  as crime_count,
         h.avg_rating,
         coalesce(c.crime_count, 0) / nullif(ST_Area(b.geom::geography)/1e6, 0) as crime_per_km2
  from simplified_msoa b
  left join (
    select m.msoa_code, count(c.*) as crime_count
    from simplified_msoa m
    left join stg_crime c
      on c.geom && m.geom_simpl
      and ST_Contains(m.geom_simpl, ST_Centroid(c.geom))
    group by m.msoa_code
  ) c using (msoa_code)
  left join (
    select m.msoa_code, avg(h.rating_value) as avg_rating
    from simplified_msoa m
    left join stg_hygiene h
      on h.geom && m.geom_simpl
      and ST_Contains(m.geom_simpl, ST_Centroid(h.geom))
    group by m.msoa_code
  ) h using (msoa_code)
),
q as (
  select *,
    case when crime_count > 0 and avg_rating is not null then 'full'
         when crime_count > 0                            then 'crime_only'
         when avg_rating is not null                     then 'hygiene_only'
         else 'none' end as data_quality,
    case when crime_count > 0
         then percent_rank() over (order by crime_per_km2)
         end as p_crime,
    case when avg_rating is not null
         then percent_rank() over (order by (5 - avg_rating))
         end as p_hyg
  from base
),
idx as (
  select *,
    case data_quality
      when 'full'         then 0.7*p_crime + 0.3*p_hyg
      when 'crime_only'   then p_crime
      when 'hygiene_only' then p_hyg
    end as risk_index
  from q
),
scored as (
  select *,
    case when risk_index is not null
         then percent_rank() over (order by risk_index) end as grit_score,
    ST_AsGeoJSON(geom_simpl) as geom_geojson_simpl
  from idx
)
SELECT
  msoa_code, msoa_name, geom, geom_geojson_simpl,
  crime_count, crime_per_km2, avg_rating, grit_score, data_quality,
  case when grit_score is null then 'no_data'
       when grit_score < 0.4   then 'safest'
       when grit_score < 0.7   then 'safer'
       when grit_score < 0.9   then 'riskier'
       else                         'riskiest' end as grit_bucket
FROM scored
