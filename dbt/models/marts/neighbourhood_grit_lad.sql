{{ config(materialized='table') }}

with crime_lad as (
    select
        l.lad_code,
        l.lad_name,
        count(c.category) as crime_count
    from {{ ref('stg_crime') }} c
    join lad_boundaries l on ST_Contains(l.geom, c.geom)
    group by l.lad_code, l.lad_name
),

hygiene_lad as (
    select
        l.lad_code,
        avg(h.rating_value) as avg_rating
    from {{ ref('stg_hygiene') }} h
    join lad_boundaries l on ST_Contains(l.geom, h.geom)
    group by l.lad_code
)

select
    l.lad_code,
    l.lad_name,
    l.geom,
    -- Precompute simplified geometry for faster rendering at coarse zooms
    ST_SimplifyPreserveTopology(l.geom, 0.005) as geom_simpl,
    ST_AsGeoJSON(ST_SimplifyPreserveTopology(l.geom, 0.005)) as geom_geojson_simpl,
    ST_AsGeoJSON(l.geom) as geom_geojson,
    coalesce(c.crime_count, 0) as crime_count,
    coalesce(h.avg_rating, 0) as avg_rating,
     LN(1 + coalesce(c.crime_count, 0)) / LN(1 + 3528.4) + (5 - coalesce(h.avg_rating, 0)) as grit_score
from lad_boundaries l
left join crime_lad c on l.lad_code = c.lad_code
left join hygiene_lad h on l.lad_code = h.lad_code