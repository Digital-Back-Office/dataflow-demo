-- stg_bathing_sites: clean & normalize the EEA site layer.
-- Unpivots the 11 wide class_YYYY columns (2014-2024) into long form
-- so downstream trend models can aggregate over years with regr_slope.

with source as (
    select * from {{ source('raw', 'bathing_sites') }}
    where latitude is not null and longitude is not null
),

sites as (
    select
        bathing_water_id,
        trim(name)                       as name,
        upper(country_code)              as country_code,
        lower(water_type)                as water_type,
        latitude,
        longitude
    from source
),

unpivoted as (
    {% set years = range(2014, 2025) %}
    {% for y in years %}
    select bathing_water_id, {{ y }} as class_year, class_{{ y }} as classification
    from source where class_{{ y }} is not null
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)

select
    s.bathing_water_id,
    s.name,
    s.country_code,
    s.water_type,
    s.latitude,
    s.longitude,
    u.class_year,
    case lower(u.classification)
        when 'excellent'  then 4
        when 'good'       then 3
        when 'sufficient' then 2
        when 'poor'       then 1
        else null
    end                              as class_score,
    u.classification
from sites s
join unpivoted u using (bathing_water_id)
