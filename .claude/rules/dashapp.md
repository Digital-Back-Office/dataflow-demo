---
paths: "**/dashapp/**/*.py"
---

# Dash app conventions

## Imports
```python
import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import plotly.express as px
import plotly.io as pio
import pandas as pd
from sqlalchemy import create_engine, text

pio.templates.default = "plotly_dark"
```

Use `dbc.themes.DARKLY` as the default Bootstrap theme — it matches the dark template and looks polished.

## App initialisation
```python
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True,
)
app.title = "Project Name"
```

## Database connection
Always use Airflow's connection hook — never hardcode credentials:
```python
from airflow.hooks.base import BaseHook
from sqlalchemy import create_engine

def get_engine():
    conn = BaseHook.get_connection('your_conn_name')
    return create_engine(
        f"postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}"
    )
```

For SQLite (local dev only): detect conn_type and handle separately, as in the NASA demo.

## Layout structure
Use a class to organise large apps:
```python
class ProjectDashboard:
    def __init__(self):
        self.app = dash.Dash(...)
        self.setup_database()
        self.setup_layout()
        self.setup_callbacks()

    def setup_layout(self): ...
    def setup_callbacks(self): ...
```

For simpler apps, module-level layout is fine.

## Caching
Cache expensive queries — Dash apps are multi-user:
```python
from dash import callback
from functools import lru_cache

@lru_cache(maxsize=32)
def fetch_data(param):
    with get_engine().connect() as conn:
        return pd.read_sql(text("SELECT ..."), conn)
```

For viewport-dependent data (maps), implement a TTL cache as in neighbourhood_scout: `QueryCache` class with `max_size` and `ttl_seconds`.

## Callbacks
- Keep callbacks thin — data fetching in separate functions, callbacks just call them
- Use `callback_context` to identify which input triggered
- Return `no_update` from `dash.no_update` when nothing should change
- Guard against empty DataFrames before building figures:
  ```python
  if df.empty:
      return go.Figure().update_layout(template="plotly_dark")
  ```

## Charts
- Always set `template="plotly_dark"` on every figure
- Set explicit `height` on figures — don't let them collapse
- Use `px` for simple charts, `go` for custom/composite charts
- Colour palette: use a consistent set per project, defined as constants at the top of the file

## Maps (dash-leaflet)
Follow the neighbourhood_scout pattern:
- `DEFAULT_CENTER` and `DEFAULT_ZOOM` as module constants
- Viewport-based data loading (load only what's visible, not the entire dataset)
- Stale-request guard using a threading lock and request ID counter
- `MAX_FEATURES` cap to prevent browser freeze

## Entry point
```python
if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)
```

Always `host="0.0.0.0"` so Dataflow can expose the port. Never `debug=True` in deployed apps.
