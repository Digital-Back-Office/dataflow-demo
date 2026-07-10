{{ config(materialized='table') }}

with crime_agg as (
    select
        count(*) as total_crimes,
        avg(case when category = 'violent-crime' then 1 else 0 end) as violent_crime_ratio
    from {{ ref('stg_crime') }}
),

hygiene_agg as (
    select
        avg(cast(rating_value as float)) as avg_rating,
        avg(hygiene_score) as avg_hygiene_score
    from {{ ref('stg_hygiene') }}
)

select
    c.total_crimes,
    c.violent_crime_ratio,
    h.avg_rating,
    h.avg_hygiene_score,
    -- Simple Grit Score: Normalize crime (higher = worse) and hygiene (lower rating = worse)
    (c.total_crimes / 100.0) + (5 - h.avg_rating) as grit_score
from crime_agg c
cross join hygiene_agg h