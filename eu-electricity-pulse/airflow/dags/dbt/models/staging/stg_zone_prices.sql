with source as (
    select * from {{ source('raw', 'zone_prices_hourly') }}
    where price_eur_mwh is not null
)

select
    zone_code,
    delivery_date,
    delivery_hour,
    price_eur_mwh,
    currency,
    ingested_at,
    (delivery_date + (delivery_hour || ' hours')::interval) as delivery_ts
from source
