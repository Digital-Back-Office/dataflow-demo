-- int_rainfall_correlation: does rain precede worse water?
-- Joins each enriched sample to its 7-day pre-sample precip and computes a
-- per-site correlation between rainfall and E. coli counts.
--
-- TODO: only sites present in raw.site_rainfall (the ~500 enriched) will score;
-- others get a null correlation (rainfall_sensitive = false downstream).

with joined as (
    select
        s.bathing_water_id,
        s.sample_date,
        s.ecoli_cfu,
        r.precip_7d_mm
    from {{ ref('stg_samples') }} s
    join {{ source('raw', 'site_rainfall') }} r
      on r.bathing_water_id = s.bathing_water_id
     and r.sample_date = s.sample_date
    where s.ecoli_cfu is not null
      and r.precip_7d_mm is not null
)

select
    bathing_water_id,
    count(*)                              as paired_samples,
    corr(precip_7d_mm, ecoli_cfu)         as rainfall_ecoli_corr
from joined
group by bathing_water_id
having count(*) >= 5   -- need enough pairs for a meaningful correlation
