-- Rolling 7-day and 30-day mean + stddev per (zone, hour) — the statistical baseline
-- Window is partitioned by zone and hour-of-day so comparisons are like-for-like
select
    zone_code,
    delivery_date,
    delivery_hour,
    price_eur_mwh,
    avg(price_eur_mwh) over w7  as baseline_mean_7d,
    stddev(price_eur_mwh) over w7  as baseline_std_7d,
    avg(price_eur_mwh) over w30 as baseline_mean_30d,
    stddev(price_eur_mwh) over w30 as baseline_std_30d
from {{ ref('stg_zone_prices') }}
window
    w7  as (partition by zone_code, delivery_hour
             order by delivery_date
             rows between 6 preceding and current row),
    w30 as (partition by zone_code, delivery_hour
             order by delivery_date
             rows between 29 preceding and current row)
