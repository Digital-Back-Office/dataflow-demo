"""
EU Beach Water Quality Monitor — Dash app.

Interactive map of 22,000+ European bathing sites coloured by current water
quality classification, with a click-through site detail panel and four tabs:
map view, declining beaches leaderboard, hidden gems, country comparison.

Reads from the dbt marts (mart_site_scorecard, mart_country_rankings) and
from raw.samples for the per-site bacterial history sparkline.
"""

import logging
import os

import dash
from dash import dcc, html, Input, Output, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import plotly.express as px
import plotly.io as pio
import pandas as pd

pio.templates.default = "plotly_dark"
logger = logging.getLogger(__name__)

DB_CONN_ID = "beach_watch_db"

CLASS_COLORS = {
    "Excellent":  "#2ecc71",
    "Good":       "#3498db",
    "Sufficient": "#f39c12",
    "Poor":       "#e74c3c",
}
CLASS_ORDER = ["Excellent", "Good", "Sufficient", "Poor"]

DEFAULT_CENTER = {"lat": 48.5, "lon": 10.0}
DEFAULT_ZOOM = 3.5


# --------------------------------------------------------------------------- #
# DB connection — uses Airflow hook when available, DATABASE_URL fallback
# --------------------------------------------------------------------------- #
def get_engine():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        from sqlalchemy import create_engine
        return create_engine(db_url)
    try:
        from airflow.hooks.base import BaseHook
        from sqlalchemy import create_engine
        conn = BaseHook.get_connection(DB_CONN_ID)
        return create_engine(
            f"postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}"
        )
    except Exception:
        raise RuntimeError(
            "Set DATABASE_URL env var or configure Airflow connection 'beach_watch_db'"
        )


# --------------------------------------------------------------------------- #
# Data access
# --------------------------------------------------------------------------- #
def _read_sql(sql: str) -> pd.DataFrame:
    """Run a SQL string, using a raw DBAPI connection for pandas compatibility
    with SQLAlchemy 2.x (Engine no longer exposes .cursor() directly).
    """
    engine = get_engine()
    raw = engine.raw_connection()
    try:
        return pd.read_sql(sql, raw)
    finally:
        raw.close()


def fetch_scorecard(countries=None, water_types=None) -> pd.DataFrame:
    try:
        wheres = ["latitude IS NOT NULL", "longitude IS NOT NULL"]
        if countries:
            quoted = ",".join(f"'{c}'" for c in countries)
            wheres.append(f"country_code IN ({quoted})")
        if water_types:
            quoted = ",".join(f"'{t}'" for t in water_types)
            wheres.append(f"water_type IN ({quoted})")
        return _read_sql(f"""
            SELECT bathing_water_id, name, country_code, water_type,
                   latitude, longitude, current_classification,
                   trend_direction, trend_slope, rainfall_sensitive, hidden_gem
            FROM marts.mart_site_scorecard
            WHERE {' AND '.join(wheres)}
        """)
    except Exception as e:
        logger.warning("fetch_scorecard failed: %s", e)
        return pd.DataFrame()


def fetch_all_countries() -> list:
    try:
        df = _read_sql(
            "SELECT DISTINCT country_code FROM marts.mart_site_scorecard ORDER BY 1"
        )
        return df["country_code"].tolist()
    except Exception:
        return []


def fetch_site_detail(bathing_water_id: str):
    try:
        safe_id = bathing_water_id.replace("'", "''")
        timeline = _read_sql(f"""
            SELECT class_year, classification, class_score
            FROM staging.stg_bathing_sites
            WHERE bathing_water_id = '{safe_id}'
            ORDER BY class_year
        """)
        samples = _read_sql(f"""
            SELECT sample_date, ecoli_cfu, enterococci_cfu
            FROM raw.samples
            WHERE bathing_water_id = '{safe_id}'
              AND ecoli_cfu IS NOT NULL
            ORDER BY sample_date
        """)
        return timeline, samples
    except Exception as e:
        logger.warning("fetch_site_detail failed: %s", e)
        return pd.DataFrame(), pd.DataFrame()


def fetch_declining_leaderboard(limit: int = 50) -> pd.DataFrame:
    try:
        return _read_sql(f"""
            SELECT name, country_code, water_type,
                   current_classification, trend_slope
            FROM marts.mart_site_scorecard
            WHERE trend_direction = 'degrading'
            ORDER BY trend_slope ASC
            LIMIT {int(limit)}
        """)
    except Exception as e:
        logger.warning("fetch_declining_leaderboard failed: %s", e)
        return pd.DataFrame()


def fetch_hidden_gems(limit: int = 50) -> pd.DataFrame:
    try:
        return _read_sql(f"""
            SELECT name, country_code, water_type, latitude, longitude
            FROM marts.mart_site_scorecard
            WHERE hidden_gem IS TRUE
            ORDER BY country_code, name
            LIMIT {int(limit)}
        """)
    except Exception as e:
        logger.warning("fetch_hidden_gems failed: %s", e)
        return pd.DataFrame()


def fetch_country_rankings(year: int = 2024) -> pd.DataFrame:
    try:
        return _read_sql(f"""
            SELECT country_code, class_year, total_sites, excellent_sites,
                   pct_excellent, yoy_pct_excellent_change
            FROM marts.mart_country_rankings
            WHERE class_year = {int(year)}
            ORDER BY pct_excellent DESC NULLS LAST
        """)
    except Exception as e:
        logger.warning("fetch_country_rankings failed: %s", e)
        return pd.DataFrame()


# --------------------------------------------------------------------------- #
# Figure builders
# --------------------------------------------------------------------------- #
def empty_map():
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark",
        mapbox_style="carto-darkmatter",
        mapbox=dict(center=DEFAULT_CENTER, zoom=DEFAULT_ZOOM),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#1a1a2e",
    )
    return fig


def build_map(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_map()

    df = df.copy()
    df["current_classification"] = df["current_classification"].fillna("Unknown")

    fig = px.scatter_mapbox(
        df,
        lat="latitude",
        lon="longitude",
        color="current_classification",
        color_discrete_map=CLASS_COLORS,
        category_orders={"current_classification": CLASS_ORDER},
        hover_name="name",
        hover_data={
            "country_code": True,
            "water_type": True,
            "trend_direction": True,
            "latitude": False,
            "longitude": False,
        },
        custom_data=["bathing_water_id"],
        opacity=0.8,
        size_max=8,
    )
    fig.update_traces(marker={"size": 6})
    fig.update_layout(
        mapbox_style="carto-darkmatter",
        mapbox=dict(center=DEFAULT_CENTER, zoom=DEFAULT_ZOOM),
        margin=dict(l=0, r=0, t=0, b=0),
        legend_title_text="Classification",
        uirevision="stable",
        paper_bgcolor="#1a1a2e",
    )
    return fig


def build_timeline_chart(timeline: pd.DataFrame, site_name: str) -> go.Figure:
    if timeline.empty:
        fig = go.Figure()
        fig.update_layout(template="plotly_dark", height=160,
                          title="No classification history available")
        return fig

    colors = [CLASS_COLORS.get(c, "#888") for c in timeline["classification"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timeline["class_year"], y=timeline["class_score"],
        mode="lines+markers",
        marker=dict(color=colors, size=10, line=dict(width=1, color="#222")),
        line=dict(color="#aaa", width=2),
        text=timeline["classification"],
        hovertemplate="%{x}: %{text}<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_dark",
        height=180,
        margin=dict(l=10, r=10, t=30, b=10),
        title=dict(text="Classification 2014–2024", font=dict(size=13)),
        yaxis=dict(
            tickvals=[1, 2, 3, 4],
            ticktext=["Poor", "Sufficient", "Good", "Excellent"],
            range=[0.5, 4.5],
        ),
        xaxis=dict(dtick=2),
        showlegend=False,
    )
    return fig


def build_samples_chart(samples: pd.DataFrame) -> go.Figure:
    if samples.empty:
        fig = go.Figure()
        fig.update_layout(template="plotly_dark", height=160,
                          title="No sample data available")
        return fig

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=samples["sample_date"], y=samples["ecoli_cfu"],
        name="E.coli (CFU/100ml)", mode="markers",
        marker=dict(color="#e74c3c", size=4, opacity=0.7),
        hovertemplate="%{x}: %{y:.0f} CFU/100ml<extra>E.coli</extra>",
    ))
    if "enterococci_cfu" in samples.columns:
        fig.add_trace(go.Scatter(
            x=samples["sample_date"], y=samples["enterococci_cfu"],
            name="Enterococci (CFU/100ml)", mode="markers",
            marker=dict(color="#f39c12", size=4, opacity=0.7),
            hovertemplate="%{x}: %{y:.0f} CFU/100ml<extra>Enterococci</extra>",
        ))
    fig.update_layout(
        template="plotly_dark",
        height=180,
        margin=dict(l=10, r=10, t=30, b=10),
        title=dict(text="Bacterial Samples", font=dict(size=13)),
        yaxis=dict(title="CFU / 100ml"),
        showlegend=True,
        legend=dict(font=dict(size=10)),
    )
    return fig


def build_country_bar(df: pd.DataFrame, year: int) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.update_layout(template="plotly_dark", height=600,
                          title=f"No country data for {year}")
        return fig

    df = df.sort_values("pct_excellent", ascending=True)
    fig = go.Figure(go.Bar(
        x=df["pct_excellent"],
        y=df["country_code"],
        orientation="h",
        marker_color="#2ecc71",
        text=df["pct_excellent"].apply(lambda v: f"{v:.1f}%"),
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Excellent: %{x:.1f}%<br>"
            "Total sites: %{customdata[0]}<extra></extra>"
        ),
        customdata=df[["total_sites"]].values,
    ))
    fig.update_layout(
        template="plotly_dark",
        height=max(400, len(df) * 22),
        margin=dict(l=60, r=60, t=50, b=30),
        title=dict(text=f"% Excellent bathing sites by country — {year}", font=dict(size=14)),
        xaxis=dict(title="% Excellent", range=[0, 105]),
        yaxis=dict(title=""),
        paper_bgcolor="#1a1a2e",
    )
    return fig


def make_data_table(df: pd.DataFrame, id_: str) -> dash_table.DataTable:
    if df.empty:
        return html.P("No data available.", className="text-muted mt-3")
    return dash_table.DataTable(
        id=id_,
        columns=[{"name": c.replace("_", " ").title(), "id": c} for c in df.columns
                 if c != "bathing_water_id"],
        data=df.to_dict("records"),
        style_table={"overflowX": "auto"},
        style_cell={"backgroundColor": "#1a1a2e", "color": "#eee",
                    "border": "1px solid #333", "textAlign": "left",
                    "padding": "6px 10px", "fontSize": "13px"},
        style_header={"backgroundColor": "#16213e", "fontWeight": "bold",
                      "color": "#2ecc71", "border": "1px solid #444"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#16213e"},
        ],
        page_size=20,
        sort_action="native",
        filter_action="native",
    )


# --------------------------------------------------------------------------- #
# App layout & callbacks
# --------------------------------------------------------------------------- #
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True,
    title="EU Beach Water Quality Monitor",
)
server = app.server

try:
    COUNTRY_OPTIONS = [{"label": c, "value": c} for c in fetch_all_countries()]
except Exception:
    COUNTRY_OPTIONS = []

app.layout = html.Div([
    dbc.NavbarSimple(
        brand="🏖 EU Beach Water Quality Monitor",
        brand_style={"fontSize": "1.2rem"},
        color="dark",
        dark=True,
        className="mb-3",
    ),
    dbc.Container([
        # Filters row
        dbc.Row([
            dbc.Col([
                dbc.Label("Country", style={"fontSize": "12px", "color": "#aaa"}),
                dcc.Dropdown(
                    id="filter-country",
                    options=COUNTRY_OPTIONS,
                    multi=True,
                    placeholder="All countries",
                    style={"fontSize": "13px"},
                ),
            ], width=4),
            dbc.Col([
                dbc.Label("Water type", style={"fontSize": "12px", "color": "#aaa"}),
                dcc.Dropdown(
                    id="filter-water-type",
                    options=[
                        {"label": "Coastal", "value": "coastal"},
                        {"label": "River",   "value": "river"},
                        {"label": "Lake",    "value": "lake"},
                        {"label": "Transitional", "value": "transitional"},
                    ],
                    multi=True,
                    placeholder="All types",
                    style={"fontSize": "13px"},
                ),
            ], width=4),
            dbc.Col([
                html.Div(id="site-count", className="mt-4",
                         style={"color": "#aaa", "fontSize": "13px"}),
            ], width=4),
        ], className="mb-3"),

        dbc.Tabs([
            dbc.Tab(label="Map", tab_id="tab-map", children=[
                dbc.Row([
                    dbc.Col(
                        dbc.Spinner(
                            dcc.Graph(id="site-map", style={"height": "70vh"},
                                      config={"scrollZoom": True}),
                            color="success",
                        ),
                        width=8,
                    ),
                    dbc.Col(
                        dbc.Card([
                            dbc.CardHeader("Site detail", style={"color": "#2ecc71"}),
                            dbc.CardBody(
                                html.Div(
                                    "Click a beach on the map to see its history.",
                                    id="site-detail-panel",
                                    style={"color": "#aaa", "fontSize": "13px"},
                                ),
                                style={"overflowY": "auto", "maxHeight": "68vh"},
                            ),
                        ], style={"backgroundColor": "#16213e"}),
                        width=4,
                    ),
                ]),
            ]),
            dbc.Tab(label="Beaches getting worse", tab_id="tab-declining", children=[
                html.P(
                    "Bathing sites with the steepest decline in classification quality over 11 years.",
                    className="text-muted mt-3",
                ),
                dbc.Spinner(html.Div(id="declining-table"), color="warning"),
            ]),
            dbc.Tab(label="Hidden gems", tab_id="tab-gems", children=[
                html.P(
                    "Excellent water quality every year for 11 years — in lesser-known European countries.",
                    className="text-muted mt-3",
                ),
                dbc.Spinner(html.Div(id="gems-table"), color="success"),
            ]),
            dbc.Tab(label="Country comparison", tab_id="tab-country", children=[
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Year"),
                        dcc.Slider(
                            id="country-year", min=2014, max=2024, step=1, value=2024,
                            marks={y: str(y) for y in range(2014, 2025, 2)},
                        ),
                    ], width=8),
                ], className="mt-3 mb-2"),
                dbc.Spinner(
                    dcc.Graph(id="country-bar", style={"height": "70vh"}),
                    color="success",
                ),
            ]),
        ], id="tabs", active_tab="tab-map"),

        dcc.Store(id="selected-site"),
    ], fluid=True),
], style={"backgroundColor": "#0f0f23", "minHeight": "100vh"})


# --------------------------------------------------------------------------- #
# Callbacks
# --------------------------------------------------------------------------- #
@app.callback(
    Output("site-map", "figure"),
    Output("site-count", "children"),
    Input("filter-country", "value"),
    Input("filter-water-type", "value"),
)
def update_map(countries, water_types):
    df = fetch_scorecard(countries, water_types)
    count_txt = f"{len(df):,} sites" if not df.empty else "No data yet"
    return build_map(df), count_txt


@app.callback(
    Output("site-detail-panel", "children"),
    Input("site-map", "clickData"),
)
def update_detail(click_data):
    if not click_data:
        return html.Div(
            "Click a beach on the map to see its history.",
            style={"color": "#aaa", "fontSize": "13px"},
        )

    try:
        point = click_data["points"][0]
        bw_id = point["customdata"][0]
        site_name = point.get("hovertext", bw_id)
        country = point.get("customdata", ["", ""])[1] if len(point.get("customdata", [])) > 1 else ""
    except (KeyError, IndexError):
        return html.Div("Could not read site data.", style={"color": "#e74c3c"})

    timeline, samples = fetch_site_detail(bw_id)

    current_class = timeline.iloc[-1]["classification"] if not timeline.empty else "Unknown"
    badge_color = {
        "Excellent": "success", "Good": "primary",
        "Sufficient": "warning", "Poor": "danger",
    }.get(current_class, "secondary")

    return html.Div([
        html.H6(site_name, style={"color": "#fff", "marginBottom": "4px"}),
        html.Div([
            dbc.Badge(current_class, color=badge_color, className="me-2"),
            html.Span(country, style={"color": "#aaa", "fontSize": "12px"}),
        ], className="mb-3"),
        dcc.Graph(
            figure=build_timeline_chart(timeline, site_name),
            config={"displayModeBar": False},
        ),
        dcc.Graph(
            figure=build_samples_chart(samples),
            config={"displayModeBar": False},
        ),
    ])


@app.callback(
    Output("declining-table", "children"),
    Input("tabs", "active_tab"),
)
def update_declining(active_tab):
    if active_tab != "tab-declining":
        return dash.no_update
    df = fetch_declining_leaderboard()
    if not df.empty:
        df["trend_slope"] = df["trend_slope"].round(3)
    return make_data_table(df, "declining-dt")


@app.callback(
    Output("gems-table", "children"),
    Input("tabs", "active_tab"),
)
def update_gems(active_tab):
    if active_tab != "tab-gems":
        return dash.no_update
    df = fetch_hidden_gems()
    return make_data_table(df, "gems-dt")


@app.callback(
    Output("country-bar", "figure"),
    Input("country-year", "value"),
    Input("tabs", "active_tab"),
)
def update_country(year, active_tab):
    if active_tab != "tab-country":
        return dash.no_update
    df = fetch_country_rankings(year)
    return build_country_bar(df, year)


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)
