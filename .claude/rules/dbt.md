---
paths: "**/dbt/**"
---

# dbt conventions

## Location when used with Airflow

When dbt is run via an Airflow DAG, the dbt project must live at `airflow/dags/dbt/` — co-located with the DAG files. Do **not** place it at the project root. The `profiles.yml` must use a relative path or the `DBT_PROFILES_DIR` env var pointing to that directory.

## Project structure
```
dbt/
├── dbt_project.yml
├── models/
│   ├── staging/      # materialized: view  — thin wrappers over raw tables, light cleaning only
│   └── marts/        # materialized: table — business logic, aggregations, final outputs
├── seeds/
├── tests/
└── macros/
```

## dbt_project.yml
```yaml
models:
  project_name:
    staging:
      materialized: view
    marts:
      materialized: table
```

Profile name must match the connection name used in the project (e.g. `ukns_db`, `flight_db`).

## Model naming
- `stg_<source>__<entity>.sql` for staging models (e.g. `stg_police__crimes.sql`)
- `<entity>_<description>.sql` for mart models (e.g. `lsoa_grit_scores.sql`)
- Lowercase, underscores only

## Staging models
- One staging model per raw source table
- Select all needed columns, rename to snake_case where needed
- Cast data types explicitly — don't rely on implicit casting
- No business logic, no joins across sources
- Materialized as views (no storage cost, always fresh)

## Mart models
- Business logic and aggregations live here
- Join staging models, never raw tables directly
- Materialized as tables (queried by the app — must be fast)
- Add indexes in post-hooks if the app filters on a column:
  ```sql
  {{ config(post_hook="CREATE INDEX IF NOT EXISTS idx_col ON {{ this }} (column_name)") }}
  ```

## SQL style
```sql
select
    lsoa_code,
    lsoa_name,
    count(*)        as crime_count,
    avg(score)      as avg_score
from {{ ref('stg_police__crimes') }}
where category = 'violent-crime'
group by 1, 2
```
- Lowercase keywords
- One column per line for selects with more than two columns
- Use `{{ ref() }}` for all model references — never raw table names
- Use `{{ source() }}` for raw source tables defined in `sources.yml`

## Testing
Add at minimum these tests in a `schema.yml` next to each model:
```yaml
models:
  - name: lsoa_grit_scores
    columns:
      - name: lsoa_code
        tests:
          - unique
          - not_null
```

## Validation commands
- `dbt parse` — fast syntax check, run before committing
- `dbt compile` — renders all SQL, catches Jinja errors
- `dbt run --select model_name` — runs a specific model
- `dbt test --select model_name` — runs tests for a model
