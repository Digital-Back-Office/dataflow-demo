---
paths: "**/streamlit/**/*.py"
---

# Streamlit app conventions

## Imports
```python
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
from sqlalchemy import create_engine, text
```

## Page config — always first
```python
st.set_page_config(
    page_title="Project Name",
    page_icon="🔍",           # relevant emoji
    layout="wide",
    initial_sidebar_state="expanded",
)
```

`layout="wide"` always — narrow layout wastes screen space in demos.

## Database connection
```python
from airflow.hooks.base import BaseHook
from sqlalchemy import create_engine

@st.cache_resource
def get_engine():
    conn = BaseHook.get_connection('your_conn_name')
    return create_engine(
        f"postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}"
    )
```

Use `@st.cache_resource` for the engine (created once, shared across sessions).
Use `@st.cache_data` for query results (cached per unique arguments, refreshes on TTL):
```python
@st.cache_data(ttl=300)
def fetch_summary():
    with get_engine().connect() as conn:
        return pd.read_sql(text("SELECT ..."), conn)
```

## Structure
- `app.py` is the entry point and home page
- Multi-page apps go in `pages/` — filenames become page names (use numeric prefixes for ordering: `1_overview.py`, `2_detail.py`)
- Shared utilities go in `utils/` as importable modules

## UI patterns
- Open with a clear header and one-sentence description — the user should know what the app does within 3 seconds
- Use `st.metric()` for KPI tiles at the top of dashboards
- Use `st.columns()` to lay out metrics and charts side by side
- Use `st.spinner()` around slow data fetches
- Use `st.sidebar` for filters that apply across the whole page
- Never dump a raw DataFrame with `st.dataframe()` as the primary output — use charts, metrics, or a styled table

## Charts
- Prefer Plotly (`px` or `go`) over st.bar_chart/st.line_chart for visual quality
- Always set a dark theme on Plotly figures: `fig.update_layout(template="plotly_dark")`
- Pass figures to `st.plotly_chart(fig, use_container_width=True)` always

## Session state
Use `st.session_state` for anything that should persist across reruns (user selections, loaded data that shouldn't re-fetch on every widget interaction):
```python
if 'data' not in st.session_state:
    st.session_state.data = fetch_data()
```

## Error handling
Show user-friendly errors, not tracebacks:
```python
try:
    df = fetch_data()
except Exception as e:
    st.error("Could not load data. Check that the pipeline has run.")
    st.stop()
```

## Entry point
Streamlit is launched with `streamlit run app.py --server.port 8501 --server.address 0.0.0.0`.
Do not add `if __name__ == "__main__"` blocks — Streamlit handles execution.
Always use `0.0.0.0` so Dataflow can expose the port.
