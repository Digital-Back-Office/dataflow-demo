-- mart_country_rankings: % Excellent by country per year, with YoY change.
-- Backs the country-comparison tab.

with by_country_year as (
    select
        country_code,
        class_year,
        count(*)                                              as total_sites,
        count(*) filter (where class_score = 4)               as excellent_sites,
        round(100.0 * count(*) filter (where class_score = 4)
              / nullif(count(*), 0), 1)                       as pct_excellent
    from {{ ref('stg_bathing_sites') }}
    group by country_code, class_year
)

select
    country_code,
    class_year,
    total_sites,
    excellent_sites,
    pct_excellent,
    pct_excellent - lag(pct_excellent) over (
        partition by country_code order by class_year
    ) as yoy_pct_excellent_change
from by_country_year
