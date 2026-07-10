{{ config(materialized='table') }}

with crime_lsoa as (
    select
        l.lsoa_code,
        l.lsoa_name,
        count(c.category) as crime_count
    from {{ ref('stg_crime') }} c
    join lsoa_boundaries l on ST_Contains(l.geom, c.geom)
    group by l.lsoa_code, l.lsoa_name
),

hygiene_lsoa as (
    select
        l.lsoa_code,
        avg(h.rating_value) as avg_rating
    from {{ ref('stg_hygiene') }} h
    join lsoa_boundaries l on ST_Contains(l.geom, h.geom)
    group by l.lsoa_code
)

select
    l.lsoa_code,
    l.lsoa_name,
    l.geom,
    ST_AsGeoJSON(l.geom) as geom_geojson,
    coalesce(c.crime_count, 0) as crime_count,
    coalesce(h.avg_rating, 0) as avg_rating,
    (coalesce(c.crime_count, 0) / 26.0) + (5 - coalesce(h.avg_rating, 0)) as grit_score
from lsoa_boundaries l
left join crime_lsoa c on l.lsoa_code = c.lsoa_code
left join hygiene_lsoa h on l.lsoa_code = h.lsoa_code