-- int_site_trends: classify each site's 11-year trajectory.
-- Fits a simple slope of class_score vs class_year and buckets into
-- improving / stable / degrading; also surfaces best/worst year.
--
-- TODO: tune slope thresholds after seeing the real distribution.

with scored as (
    select bathing_water_id, class_year, class_score, classification
    from {{ ref('stg_bathing_sites') }}
    where class_score is not null
),

agg as (
    select
        bathing_water_id,
        count(*)                                          as years_observed,
        -- least-squares slope of class_score over class_year
        regr_slope(class_score, class_year)               as trend_slope,
        min(class_score)                                  as worst_score,
        max(class_score)                                  as best_score,
        -- current = latest observed year's score
        (array_agg(class_score order by class_year desc))[1] as current_score,
        min(class_year)                                   as first_year,
        max(class_year)                                   as last_year
    from scored
    group by bathing_water_id
)

select
    bathing_water_id,
    years_observed,
    trend_slope,
    current_score,
    best_score,
    worst_score,
    case
        when trend_slope >  0.05 then 'improving'
        when trend_slope < -0.05 then 'degrading'
        else 'stable'
    end as trend_direction
from agg
