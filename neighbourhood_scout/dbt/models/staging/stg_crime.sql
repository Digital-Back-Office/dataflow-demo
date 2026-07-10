{{ config(materialized='view') }}

select
    category,
    cast(latitude as float) as latitude,
    cast(longitude as float) as longitude,
    street_name,
    month,
    outcome_category,
    geom
from {{ ref('crime_data') }}