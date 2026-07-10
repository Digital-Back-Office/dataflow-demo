-- Full long-format time series for multi-zone line chart comparison
select
    p.zone_code,
    p.delivery_date,
    p.delivery_hour,
    p.price_eur_mwh,
    p.delivery_ts,
    bz.zone_name,
    bz.country
from {{ ref('stg_zone_prices') }} p
join {{ source('dim', 'bidding_zones') }} bz using (zone_code)
order by p.zone_code, p.delivery_ts
