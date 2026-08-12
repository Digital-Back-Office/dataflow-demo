-- mart_site_scorecard: one row per site — the map's backing table.
-- Combines site attributes, trend classification, rainfall sensitivity and a
-- "hidden gem" flag (Excellent every observed year in a non-obvious country).
--
-- TODO: define the "non-obvious country" allowlist (exclude ES/IT/GR/HR tourist
-- hotspots) once product decides the framing.

with sites as (
    select distinct
        bathing_water_id, name, country_code, water_type, latitude, longitude
    from {{ ref('stg_bathing_sites') }}
),

trends as (
    select * from {{ ref('int_site_trends') }}
),

rain as (
    select * from {{ ref('int_rainfall_correlation') }}
),

current_class as (
    -- latest year's textual classification per site
    select bathing_water_id, classification as current_classification
    from (
        select bathing_water_id, classification, class_year,
               row_number() over (partition by bathing_water_id
                                   order by class_year desc) as rn
        from {{ ref('stg_bathing_sites') }}
        where classification is not null
    ) x
    where rn = 1
),

all_excellent as (
    select bathing_water_id
    from {{ ref('stg_bathing_sites') }}
    group by bathing_water_id
    having bool_and(class_score = 4)
)

select
    s.bathing_water_id,
    s.name,
    s.country_code,
    s.water_type,
    s.latitude,
    s.longitude,
    c.current_classification,
    t.trend_direction,
    t.trend_slope,
    t.best_score,
    t.worst_score,
    r.rainfall_ecoli_corr,
    (r.rainfall_ecoli_corr > 0.3)                    as rainfall_sensitive,
    -- hidden gem: excellent every observed year AND lesser-known country
    (ae.bathing_water_id is not null
     and s.country_code not in ('ES', 'IT', 'GR', 'HR', 'FR')) as hidden_gem
from sites s
left join current_class c using (bathing_water_id)
left join trends t        using (bathing_water_id)
left join rain r          using (bathing_water_id)
left join all_excellent ae using (bathing_water_id)
