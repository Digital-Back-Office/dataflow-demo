-- Cheapest hours per zone per day, ranked by price percentile within that day
select
    zone_code,
    delivery_date,
    delivery_hour,
    price_eur_mwh,
    percent_rank() over (
        partition by zone_code, delivery_date
        order by price_eur_mwh asc
    ) as cheapness_rank,
    rank() over (
        partition by zone_code, delivery_date
        order by price_eur_mwh asc
    ) as hour_rank
from {{ ref('stg_zone_prices') }}
