{{ config(materialized='table') }}

-- Level 5: Finest grid (~20k cells, 0.02° grid)
-- Each grid cell is approximately 2.2km x 1.4km at UK latitudes

with grid_cells as (
    select
        floor(longitude / 0.02) as grid_x,
        floor(latitude / 0.02) as grid_y,
        concat('G5_', floor(longitude / 0.02)::text, '_', floor(latitude / 0.02)::text) as grid_code
    from {{ ref('stg_crime') }}
    where latitude is not null and longitude is not null
    union
    select
        floor(longitude / 0.02) as grid_x,
        floor(latitude / 0.02) as grid_y,
        concat('G5_', floor(longitude / 0.02)::text, '_', floor(latitude / 0.02)::text) as grid_code
    from {{ ref('stg_hygiene') }}
    where latitude is not null and longitude is not null
),

distinct_grids as (
    select distinct grid_code, grid_x, grid_y from grid_cells
),

crime_stats as (
    select
        concat('G5_', floor(longitude / 0.02)::text, '_', floor(latitude / 0.02)::text) as grid_code,
        count(*) as crime_count
    from {{ ref('stg_crime') }}
    where latitude is not null and longitude is not null
    group by 1
),

hygiene_stats as (
    select
        concat('G5_', floor(longitude / 0.02)::text, '_', floor(latitude / 0.02)::text) as grid_code,
        avg(rating_value) as avg_rating,
        count(*) as hygiene_count
    from {{ ref('stg_hygiene') }}
    where latitude is not null and longitude is not null and rating_value is not null
    group by 1
)

select
    g.grid_code,
    g.grid_x,
    g.grid_y,
    -- Create grid cell polygon (0.02° x 0.02°)
    ST_MakeEnvelope(
        g.grid_x * 0.02, 
        g.grid_y * 0.02, 
        (g.grid_x + 1) * 0.02, 
        (g.grid_y + 1) * 0.02, 
        4326
    ) as geom,
    ST_AsGeoJSON(ST_MakeEnvelope(
        g.grid_x * 0.02, 
        g.grid_y * 0.02, 
        (g.grid_x + 1) * 0.02, 
        (g.grid_y + 1) * 0.02, 
        4326
    )) as geom_geojson,
    coalesce(c.crime_count, 0) as crime_count,
    coalesce(h.avg_rating, 0) as avg_rating,
    coalesce(h.hygiene_count, 0) as hygiene_count,
    (coalesce(c.crime_count, 0) / 100.0) + (5 - coalesce(h.avg_rating, 0)) as grit_score
from distinct_grids g
left join crime_stats c on g.grid_code = c.grid_code
left join hygiene_stats h on g.grid_code = h.grid_code
