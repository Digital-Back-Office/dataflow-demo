{{ config(
    materialized='table',
    post_hook=[
        "CREATE INDEX IF NOT EXISTS idx_ngrit_lsoa_geom ON {{ this }} USING GIST (geom)",
        "ANALYZE {{ this }}"
    ]
) }}

with base as (
    select b.lsoa_code, b.lsoa_name, b.geom,
           coalesce(c.crime_count, 0)                                  as crime_count,
           h.avg_rating,
           coalesce(c.crime_count, 0) / nullif(ST_Area(b.geom::geography)/1e6, 0) as crime_per_km2
    from lsoa_boundaries b
    left join (
        select l.lsoa_code, count(c.category) as crime_count
        from {{ ref('stg_crime') }} c
        join lsoa_boundaries l on ST_Contains(l.geom, c.geom)
        group by l.lsoa_code
    ) c using (lsoa_code)
    left join (
        select l.lsoa_code, avg(h.rating_value) as avg_rating
        from {{ ref('stg_hygiene') }} h
        join lsoa_boundaries l on ST_Contains(l.geom, h.geom)
        group by l.lsoa_code
    ) h using (lsoa_code)
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
        ST_AsGeoJSON(geom) as geom_geojson
    from idx
)
select
    lsoa_code, lsoa_name, geom, geom_geojson,
    crime_count, crime_per_km2, avg_rating, grit_score, data_quality,
    case when grit_score is null then 'no_data'
         when grit_score < 0.4   then 'safest'
         when grit_score < 0.7   then 'safer'
         when grit_score < 0.9   then 'riskier'
         else                         'riskiest' end as grit_bucket
from scored