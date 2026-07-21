-- Latest delivery day prices per zone, joined with zone dimension for map rendering
with latest_date as (
    select max(delivery_date) as max_date
    from {{ ref('stg_zone_prices') }}
),

latest_prices as (
    select
        p.zone_code,
        p.delivery_date,
        p.delivery_hour,
        p.price_eur_mwh,
        p.delivery_ts
    from {{ ref('stg_zone_prices') }} p
    join latest_date ld on p.delivery_date = ld.max_date
)

select
    lp.zone_code,
    lp.delivery_date,
    lp.delivery_hour,
    lp.price_eur_mwh,
    lp.delivery_ts,
    bz.zone_name,
    bz.country,
    bz.tso,
    bz.latitude,
    bz.longitude
from latest_prices lp
join {{ source('dim', 'bidding_zones') }} bz using (zone_code)
