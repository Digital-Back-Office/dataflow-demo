-- Zone-to-zone price spread matrix for today's delivery date.
-- Prefers CURRENT_DATE, falls back to latest available so the mart works
-- before today's DAG run completes.
with target_date as (
    select
        case
            when max(delivery_date) >= current_date then current_date
            else max(delivery_date)
        end as target_date
    from {{ ref('stg_zone_prices') }}
),

prices as (
    select p.zone_code, p.delivery_hour, p.price_eur_mwh
    from {{ ref('stg_zone_prices') }} p
    join target_date td on p.delivery_date = td.target_date
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
