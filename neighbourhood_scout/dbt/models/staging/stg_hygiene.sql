{{ config(materialized='view') }}

select
    fhrs_id,
    business_name,
    cast(rating_value as int) as rating_value,
    cast(latitude as float) as latitude,
    cast(longitude as float) as longitude,
    cast(hygiene_score as float) as hygiene_score,
    cast(structural_score as float) as structural_score,
    cast(confidence_score as float) as confidence_score,
    cast(distance as float) as distance,
    geom
from {{ ref('hygiene_data') }}