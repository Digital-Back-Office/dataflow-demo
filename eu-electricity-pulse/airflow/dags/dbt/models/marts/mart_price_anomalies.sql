-- Hours where price deviates >2σ from the 30-day same-hour baseline
with base as (
    select * from {{ ref('mart_price_baselines') }}
    where baseline_std_30d is not null and baseline_std_30d > 0
)

select
    zone_code,
    delivery_date,
    delivery_hour,
    price_eur_mwh,
    baseline_mean_30d,
    baseline_std_30d,
    (price_eur_mwh - baseline_mean_30d) / baseline_std_30d as z_score,
    case
        when price_eur_mwh > baseline_mean_30d + 2 * baseline_std_30d then 'spike'
        when price_eur_mwh < baseline_mean_30d - 2 * baseline_std_30d then 'dip'
    end as anomaly_type
from base
where abs((price_eur_mwh - baseline_mean_30d) / baseline_std_30d) > 2
