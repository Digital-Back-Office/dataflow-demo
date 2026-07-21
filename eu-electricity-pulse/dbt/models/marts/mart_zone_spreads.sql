-- Zone-to-zone price spread matrix for a chosen delivery date and hour
-- Used to power the 41×41 arbitrage heatmap
with latest as (
    select max(delivery_date) as max_date
    from {{ ref('stg_zone_prices') }}
),

prices as (
    select p.zone_code, p.delivery_hour, p.price_eur_mwh
    from {{ ref('stg_zone_prices') }} p
    join latest l on p.delivery_date = l.max_date
)

select
    a.zone_code   as zone_a,
    b.zone_code   as zone_b,
    a.delivery_hour,
    a.price_eur_mwh as price_a,
    b.price_eur_mwh as price_b,
    (a.price_eur_mwh - b.price_eur_mwh) as spread_eur_mwh
from prices a
join prices b on a.delivery_hour = b.delivery_hour
where a.zone_code <> b.zone_code
