{{ config(materialized='table') }}

with msoa_grit as (
    select
        substring(msoa_code, 1, 3) as la_code,
        msoa_name,
        geom,
        crime_count,
        avg_rating,
        grit_score
    from {{ ref('neighbourhood_grit_msoa') }}
)

select
    la_code,
    min(msoa_name) as la_name,  -- Placeholder; ideally use LA name if available
    ST_Simplify(ST_MakeValid(ST_Union(ST_MakeValid(geom))), 0.1) as geom,
    ST_AsGeoJSON(ST_Simplify(ST_MakeValid(ST_Union(ST_MakeValid(geom))), 0.1)) as geom_geojson,
    sum(crime_count) as crime_count,
    avg(avg_rating) as avg_rating,
    avg(grit_score) as grit_score
from msoa_grit
group by la_code