-- stg_samples: clean per-sample bacterial data.
-- Drops nulls, clamps impossible negatives, derives year for joins.
--
-- TODO: confirm CFU unit column names once Discodata payload is inspected.

with source as (
    select * from {{ source('raw', 'samples') }}
    where sample_date is not null
      and bathing_water_id is not null
)

select
    sample_id,
    bathing_water_id,
    sample_date,
    extract(year from sample_date)::int as sample_year,
    nullif(greatest(ecoli_cfu, 0), null)        as ecoli_cfu,
    nullif(greatest(enterococci_cfu, 0), null)  as enterococci_cfu
from source
