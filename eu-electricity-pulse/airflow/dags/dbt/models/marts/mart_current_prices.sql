-- Today's delivery prices per zone, joined with zone dimension for map rendering.
-- Uses CURRENT_DATE when data exists, falls back to the latest available date
-- so the mart still works before today's DAG run completes.
with target_date as (
    select
        case
            when max(delivery_date) >= current_date then current_date
            else max(delivery_date)
        end as target_date
    from {{ ref('stg_zone_prices') }}
),

current_prices as (
    select
        p.zone_code,
        p.delivery_date,
        p.delivery_hour,
        p.price_eur_mwh,
        p.delivery_ts
    from {{ ref('stg_zone_prices') }} p
    join target_date td on p.delivery_date = td.target_date
)

select
    cp.zone_code,
    cp.delivery_date,
    cp.delivery_hour,
    cp.price_eur_mwh,
    cp.delivery_ts,
    bz.zone_name,
    bz.country,
    bz.tso,
    bz.latitude,
    bz.longitude
from current_prices cp
join {{ source('dim', 'bidding_zones') }} bz using (zone_code)
