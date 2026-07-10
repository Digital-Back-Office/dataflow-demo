---
paths: "**/dags/**/*.py"
---

# Airflow DAG conventions

## Imports
Always import in this order:
```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.hooks.base import BaseHook
from airflow.operators.python import PythonOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
# provider-specific imports as needed
import logging
```

For PostgreSQL specifically use `PostgresHook` from `airflow.providers.postgres.hooks.postgres`.

Heavy imports (pandas, requests, geopandas, etc.) go **inside** task functions, not at module level. This prevents import errors at DAG parse time.

## Connections and secrets
- Use `BaseHook.get_connection('conn_name')` to retrieve connection details
- Use `Variable.get('secret_name')` for API keys and secrets
- Connection and variable names: lowercase, letters/numbers/underscores only, project-specific (e.g. `flight_db`, `nasa_api_key`)
- Never hardcode credentials, passwords, or connection strings

## DAG definition
```python
default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='project_etl',
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval='@daily',   # or cron string
    catchup=False,
    tags=['project-name'],
) as dag:
```

Always set `catchup=False` unless historical backfill is explicitly required.

## Task functions
- Each task function does one thing: extract, transform, or load — not all three
- Use `**context` as parameter when XCom or execution date is needed
- Log progress with `logging.getLogger(__name__)` — not `print()`
- Return values are pushed to XCom automatically; pull with `context['ti'].xcom_pull(task_ids='task_name')`

## Database writes
Use `SQLExecuteQueryOperator` for DDL and simple inserts. For bulk inserts use `psycopg2.extras.execute_values` in a PythonOperator — it's significantly faster than row-by-row inserts.

Always `TRUNCATE` before reload unless implementing incremental/delta loading.

## Task dependencies
Define at the bottom of the file, after all task definitions:
```python
task_a >> task_b >> [task_c, task_d]
```

## What not to do
- No database connections at module level (breaks DAG parsing)
- No `time.sleep()` inside tasks (use sensors instead)
- No broad `except Exception: pass` — let tasks fail visibly
- No hardcoded file paths — use environment-aware path resolution
