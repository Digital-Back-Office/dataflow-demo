"""
EU Beach Water Quality Monitor — Dash app.

Built for tourists planning a trip, not data analysts. Plain-language verdicts,
a search-first layout, and visual card grids instead of raw data tables.

Reads from the dbt marts (mart_site_scorecard, mart_country_rankings) and
from raw.samples / staging.stg_bathing_sites for the per-site history.

Deliberately uses a light, warm theme instead of the repo's usual DARKLY
convention — this is a travel-decision tool for non-technical visitors,
not an internal analytics dashboard, so it needs to read as trustworthy
and inviting rather than "developer console".
"""

import logging
import os

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd

logger = logging.getLogger(__name__)

DB_CONN_ID = "beach_watch_db"

# Plain-language classification copy — no jargon, no "class_score".
CLASS_INFO = {
    "Excellent":  {"emoji": "🟢", "color": "#1a9e5c", "bg": "#e8f8f0", "verdict": "Safe to swim",
                   "detail": "Consistently excellent water quality. A great choice."},
    "Good":       {"emoji": "🔵", "color": "#2176d2", "bg": "#e8f2fc", "verdict": "Safe to swim",
                   "detail": "Good water quality overall."},
    "Sufficient": {"emoji": "🟡", "color": "#c98a08", "bg": "#fdf3df", "verdict": "Generally OK",
                   "detail": "Meets the minimum standard — check conditions if it's rained recently."},
    "Poor":       {"emoji": "🔴", "color": "#d3402f", "bg": "#fbe9e7", "verdict": "Avoid swimming",
                   "detail": "Water quality has failed standards. Consider a different beach."},
    "Unknown":    {"emoji": "⚪", "color": "#8a8a8a", "bg": "#f1f1f1", "verdict": "No recent data",
                   "detail": "We don't have a recent classification for this site."},
}
CLASS_ORDER = ["Excellent", "Good", "Sufficient", "Poor"]
MAP_COLORS = {k: v["color"] for k, v in CLASS_INFO.items()}

TREND_COPY = {
    "improving": ("📈", "Getting better", "Water quality here has been improving over the last decade."),
    "stable":    ("➡️", "Staying steady", "Water quality here has stayed consistent over the last decade."),
    "degrading": ("📉", "Getting worse", "Water quality here has been declining — worth checking recent reports."),
}

DEFAULT_CENTER = {"lat": 48.5, "lon": 10.0}
DEFAULT_ZOOM = 3.4

# Below this zoom level, group nearby beaches into clusters instead of
# plotting every individual dot — at continent/country scale, 22,000
# unclustered points are unreadable and slow to render.
CLUSTER_ZOOM_THRESHOLD = 6.5
CLUSTER_BIN_DEGREES_FAR = 2.0    # zoom < 4
CLUSTER_BIN_DEGREES_NEAR = 0.6   # 4 <= zoom < threshold

WATER_TYPE_LABELS = {
    "coastal": "Sea beach",
    "river": "River",
    "lake": "Lake",
    "transitional": "Estuary",
}

COUNTRY_NAMES = {
    "AL": "Albania", "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "CH": "Switzerland",
    "CY": "Cyprus", "CZ": "Czechia", "DE": "Germany", "DK": "Denmark", "EE": "Estonia",
    "EL": "Greece", "ES": "Spain", "FI": "Finland", "FR": "France", "HR": "Croatia",
    "HU": "Hungary", "IE": "Ireland", "IT": "Italy", "LT": "Lithuania", "LU": "Luxembourg",
    "LV": "Latvia", "MT": "Malta", "NL": "Netherlands", "PL": "Poland", "PT": "Portugal",
    "RO": "Romania", "SE": "Sweden", "SI": "Slovenia", "SK": "Slovakia",
}


# --------------------------------------------------------------------------- #
# DB connection
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


def _read_sql(sql: str) -> pd.DataFrame:
    engine = get_engine()
    raw = engine.raw_connection()
    try:
        return pd.read_sql(sql, raw)
    finally:
        raw.close()


# --------------------------------------------------------------------------- #
# Data access
# --------------------------------------------------------------------------- #
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


from functools import lru_cache


@lru_cache(maxsize=64)
def _fetch_scorecard_cached(countries_key, water_types_key):
    countries = list(countries_key) if countries_key else None
    water_types = list(water_types_key) if water_types_key else None
    return fetch_scorecard(countries, water_types)


def get_scorecard(countries=None, water_types=None) -> pd.DataFrame:
    """Cached scorecard lookup — map pan/zoom re-renders shouldn't hit the DB."""
    c_key = tuple(sorted(countries)) if countries else None
    w_key = tuple(sorted(water_types)) if water_types else None
    return _fetch_scorecard_cached(c_key, w_key)


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


def fetch_top_picks(country=None, limit: int = 12) -> pd.DataFrame:
    """Best beaches to visit: Excellent + stable/improving, optionally in one country."""
    try:
        where = ["current_classification = 'Excellent'",
                 "trend_direction != 'degrading'"]
        if country:
            where.append(f"country_code = '{country}'")
        return _read_sql(f"""
            SELECT name, country_code, water_type, trend_direction, hidden_gem,
                   bathing_water_id, latitude, longitude
            FROM marts.mart_site_scorecard
            WHERE {' AND '.join(where)}
            ORDER BY hidden_gem DESC, name
            LIMIT {int(limit)}
        """)
    except Exception as e:
        logger.warning("fetch_top_picks failed: %s", e)
        return pd.DataFrame()


def fetch_country_summary() -> pd.DataFrame:
    try:
        return _read_sql("""
            SELECT country_code, pct_excellent, yoy_pct_excellent_change
            FROM marts.mart_country_rankings
            WHERE class_year = (SELECT MAX(class_year) FROM marts.mart_country_rankings)
            ORDER BY pct_excellent DESC NULLS LAST
        """)
    except Exception as e:
        logger.warning("fetch_country_summary failed: %s", e)
        return pd.DataFrame()


def search_sites(query: str, limit: int = 8) -> pd.DataFrame:
    try:
        safe_q = query.replace("'", "''").upper()
        return _read_sql(f"""
            SELECT bathing_water_id, name, country_code, current_classification,
                   latitude, longitude
            FROM marts.mart_site_scorecard
            WHERE UPPER(name) LIKE '%{safe_q}%'
            ORDER BY name
            LIMIT {int(limit)}
        """)
    except Exception as e:
        logger.warning("search_sites failed: %s", e)
        return pd.DataFrame()


# --------------------------------------------------------------------------- #
# Figure builders
# --------------------------------------------------------------------------- #
def empty_map():
    fig = go.Figure()
    fig.update_layout(
        mapbox_style="carto-positron",
        mapbox=dict(center=DEFAULT_CENTER, zoom=DEFAULT_ZOOM),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#f7f5f0",
    )
    return fig


def _cluster_sites(df: pd.DataFrame, zoom: float) -> pd.DataFrame:
    """Bin sites into a lat/lon grid and summarise each cell: count + dominant
    classification. Bin size shrinks as zoom increases so clusters break apart
    smoothly instead of jumping straight to individual pins.
    """
    bin_deg = CLUSTER_BIN_DEGREES_FAR if zoom < 4 else CLUSTER_BIN_DEGREES_NEAR
    d = df.copy()
    d["lat_bin"] = (d["latitude"] / bin_deg).round() * bin_deg
    d["lon_bin"] = (d["longitude"] / bin_deg).round() * bin_deg

    def dominant(s):
        m = s.mode()
        return m.iat[0] if not m.empty else "Unknown"

    grouped = d.groupby(["lat_bin", "lon_bin"]).agg(
        count=("bathing_water_id", "count"),
        dominant=("current_classification", dominant),
    ).reset_index()
    return grouped


def _add_highlight_marker(fig: go.Figure, highlight: dict) -> None:
    """Draw a distinct gold-ring marker over the selected search result so
    it's unmistakable among any other nearby dots.
    """
    if not highlight:
        return
    fig.add_trace(go.Scattermapbox(
        lat=[highlight["lat"]], lon=[highlight["lon"]],
        mode="markers",
        marker=dict(size=22, color="rgba(0,0,0,0)"),
        hoverinfo="skip",
        showlegend=False,
    ))
    # Outer ring + inner dot to make the selection pop without hiding colour.
    fig.add_trace(go.Scattermapbox(
        lat=[highlight["lat"]], lon=[highlight["lon"]],
        mode="markers",
        marker=dict(size=20, color="#f4b400", opacity=0.35),
        hoverinfo="skip",
        showlegend=False,
    ))


def build_map(df: pd.DataFrame, zoom: float = None, center: dict = None,
              highlight: dict = None) -> go.Figure:
    if df.empty:
        return empty_map()

    zoom = zoom if zoom is not None else DEFAULT_ZOOM
    center = center or DEFAULT_CENTER

    df = df.copy()
    df["current_classification"] = df["current_classification"].fillna("Unknown")

    if zoom < CLUSTER_ZOOM_THRESHOLD:
        # Zoomed out: show cluster markers, not 22,000 individual dots.
        clusters = _cluster_sites(df, zoom)
        sizes = 14 + (clusters["count"] ** 0.5) * 2.2
        sizes = sizes.clip(upper=46)
        colors = clusters["dominant"].map(lambda c: MAP_COLORS.get(c, MAP_COLORS["Unknown"]))

        fig = go.Figure(go.Scattermapbox(
            lat=clusters["lat_bin"], lon=clusters["lon_bin"],
            mode="markers+text",
            marker=dict(size=sizes, color=colors, opacity=0.85),
            text=clusters["count"].astype(str),
            textfont=dict(size=11, color="white", family="Inter, sans-serif"),
            hovertext=[f"{c} beaches nearby — mostly {d}"
                      for c, d in zip(clusters["count"], clusters["dominant"])],
            hoverinfo="text",
            customdata=[["cluster"]] * len(clusters),
        ))
        fig.update_layout(
            mapbox_style="carto-positron",
            mapbox=dict(center=center, zoom=zoom),
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="#f7f5f0",
            uirevision="stable",
            showlegend=False,
        )
        _add_highlight_marker(fig, highlight)
        return fig

    # Zoomed in: individual sites.
    fig = px.scatter_mapbox(
        df,
        lat="latitude",
        lon="longitude",
        color="current_classification",
        color_discrete_map=MAP_COLORS,
        category_orders={"current_classification": CLASS_ORDER},
        hover_name="name",
        hover_data={"country_code": True, "latitude": False, "longitude": False},
        custom_data=["bathing_water_id"],
        opacity=0.85,
    )
    for trace in fig.data:
        trace.customdata = [[cid, "site"] for cid in trace.customdata[:, 0]]
    fig.update_traces(marker={"size": 9})
    fig.update_layout(
        mapbox_style="carto-positron",
        mapbox=dict(center=center, zoom=zoom),
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(
            title="", orientation="h", yanchor="bottom", y=0.01,
            xanchor="left", x=0.01, bgcolor="rgba(255,255,255,0.9)",
            font=dict(size=12),
        ),
        uirevision="stable",
        paper_bgcolor="#f7f5f0",
    )
    _add_highlight_marker(fig, highlight)
    return fig


def build_timeline_chart(timeline: pd.DataFrame) -> go.Figure:
    if timeline.empty:
        fig = go.Figure()
        fig.update_layout(height=140, paper_bgcolor="white", plot_bgcolor="white",
                          margin=dict(l=10, r=10, t=10, b=10),
                          annotations=[dict(text="No history available", showarrow=False,
                                            font=dict(color="#999"))])
        return fig

    colors = [CLASS_INFO.get(c, CLASS_INFO["Unknown"])["color"] for c in timeline["classification"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timeline["class_year"], y=timeline["class_score"],
        mode="lines+markers",
        marker=dict(color=colors, size=11, line=dict(width=2, color="white")),
        line=dict(color="#cfcac0", width=2),
        text=timeline["classification"],
        hovertemplate="%{x}: %{text}<extra></extra>",
    ))
    fig.update_layout(
        height=150,
        margin=dict(l=10, r=10, t=10, b=20),
        paper_bgcolor="white", plot_bgcolor="white",
        yaxis=dict(tickvals=[1, 2, 3, 4],
                   ticktext=["Poor", "OK", "Good", "Excellent"],
                   range=[0.5, 4.5], gridcolor="#eee"),
        xaxis=dict(dtick=2, gridcolor="#eee"),
        showlegend=False,
        font=dict(family="Inter, sans-serif", size=11),
    )
    return fig


def build_country_strip(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure().update_layout(height=1)
    df = df.sort_values("pct_excellent", ascending=True).tail(15)
    fig = go.Figure(go.Bar(
        x=df["pct_excellent"], y=df["country_code"].map(lambda c: COUNTRY_NAMES.get(c, c)),
        orientation="h",
        marker_color="#1a9e5c",
        text=df["pct_excellent"].apply(lambda v: f"{v:.0f}%"),
        textposition="outside",
        hovertemplate="<b>%{y}</b>: %{x:.1f}%% excellent<extra></extra>",
    ))
    fig.update_layout(
        height=440,
        margin=dict(l=10, r=40, t=10, b=30),
        paper_bgcolor="white", plot_bgcolor="white",
        xaxis=dict(title="% of beaches rated Excellent", range=[0, 108], gridcolor="#eee"),
        yaxis=dict(title=""),
        font=dict(family="Inter, sans-serif", size=12),
    )
    return fig


# --------------------------------------------------------------------------- #
# UI component builders
# --------------------------------------------------------------------------- #
def verdict_card(site_row, timeline, hidden_gem=False, rainfall_sensitive=False):
    """The main answer card: is this beach safe to swim at, right now."""
    classification = (timeline.iloc[-1]["classification"]
                      if not timeline.empty else site_row.get("current_classification") or "Unknown")
    info = CLASS_INFO.get(classification, CLASS_INFO["Unknown"])
    trend = site_row.get("trend_direction") or "stable"
    t_emoji, t_label, t_detail = TREND_COPY.get(trend, TREND_COPY["stable"])

    badges = []
    if hidden_gem:
        badges.append(dbc.Badge("💎 Hidden gem", color="light", text_color="dark",
                                 className="me-2", style={"border": "1px solid #e0d8c8"}))
    if rainfall_sensitive:
        badges.append(dbc.Badge("🌧️ Rain-sensitive", color="light", text_color="dark",
                                 style={"border": "1px solid #e0d8c8"}))

    return html.Div([
        html.Div([
            html.Span(info["emoji"], style={"fontSize": "2.2rem", "marginRight": "12px"}),
            html.Div([
                html.Div(site_row.get("name", "").title(), style={
                    "fontSize": "1.15rem", "fontWeight": 700, "color": "#2b2823",
                    "lineHeight": "1.2",
                }),
                html.Div(COUNTRY_NAMES.get(site_row.get("country_code"), site_row.get("country_code", "")),
                         style={"fontSize": "0.85rem", "color": "#8a8477"}),
            ]),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "14px"}),

        html.Div([
            html.Div(info["verdict"], style={
                "fontSize": "1.5rem", "fontWeight": 800, "color": info["color"],
            }),
            html.Div(info["detail"], style={"fontSize": "0.9rem", "color": "#5c5648", "marginTop": "2px"}),
        ], style={
            "backgroundColor": info["bg"], "borderRadius": "12px",
            "padding": "16px 18px", "marginBottom": "14px",
        }),

        html.Div([
            html.Span(t_emoji, style={"fontSize": "1.1rem", "marginRight": "8px"}),
            html.Span(t_label, style={"fontWeight": 600, "color": "#2b2823"}),
        ], style={"marginBottom": "2px"}),
        html.Div(t_detail, style={"fontSize": "0.85rem", "color": "#8a8477", "marginBottom": "14px"}),

        html.Div(badges, className="mb-3") if badges else None,

        html.Div("Quality over the last 11 years", style={
            "fontSize": "0.8rem", "fontWeight": 600, "color": "#8a8477",
            "textTransform": "uppercase", "letterSpacing": "0.03em", "marginBottom": "4px",
        }),
        dcc.Graph(figure=build_timeline_chart(timeline), config={"displayModeBar": False}),
    ])


def welcome_panel():
    return html.Div([
        html.Div("🏖️", style={"fontSize": "3rem", "textAlign": "center", "marginBottom": "8px"}),
        html.Div("Click any beach on the map", style={
            "textAlign": "center", "fontWeight": 600, "color": "#2b2823", "fontSize": "1.05rem",
        }),
        html.Div("to see its swim safety rating and 11-year history.", style={
            "textAlign": "center", "color": "#8a8477", "fontSize": "0.9rem",
        }),
    ], style={"padding": "60px 20px"})


def beach_card(row):
    """A single card for the Top Picks card grid."""
    gem = " 💎" if row.get("hidden_gem") else ""
    return dbc.Col(
        html.Div([
            html.Div("🟢", style={"fontSize": "1.6rem"}),
            html.Div(f"{row['name'].title()}{gem}", style={
                "fontWeight": 700, "color": "#2b2823", "fontSize": "0.95rem",
                "marginTop": "6px", "lineHeight": "1.25", "minHeight": "2.4em",
            }),
            html.Div(COUNTRY_NAMES.get(row["country_code"], row["country_code"]),
                     style={"fontSize": "0.8rem", "color": "#8a8477"}),
            html.Div((row.get("water_type") or "").title(), style={
                "fontSize": "0.72rem", "color": "#b0aa9c", "marginTop": "2px",
            }),
        ], style={
            "backgroundColor": "white", "borderRadius": "14px", "padding": "16px",
            "border": "1px solid #eee6d8", "height": "100%",
        }),
        xs=6, sm=4, md=3, lg=2, className="mb-3",
    )


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
FONT_URL = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY, FONT_URL],
    suppress_callback_exceptions=True,
    title="EU Beach Watch",
)
server = app.server

app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body { font-family: 'Inter', sans-serif; background-color: #f7f5f0; }
            .nav-tabs .nav-link.active {
                color: #1a9e5c !important; border-bottom: 3px solid #1a9e5c !important;
                font-weight: 600;
            }
            .nav-tabs .nav-link { color: #8a8477; border: none; }
            .Select-control, .dash-dropdown .Select-control { border-radius: 10px !important; }
            .search-result-item:hover { background-color: #f7f5f0; }
            .search-result-item:last-child { border-bottom: none !important; }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>{%config%}{%scripts%}{%renderer%}</footer>
    </body>
</html>
"""

try:
    COUNTRY_OPTIONS = [
        {"label": COUNTRY_NAMES.get(c, c), "value": c} for c in fetch_all_countries()
    ]
except Exception:
    COUNTRY_OPTIONS = []


def header():
    return html.Div([
        dbc.Container([
            html.Div([
                html.Span("🏖️ ", style={"fontSize": "1.6rem"}),
                html.Span("EU Beach Watch", style={"fontSize": "1.4rem", "fontWeight": 800, "color": "#2b2823"}),
            ], className="d-flex align-items-center"),
            html.Div(
                "Water quality at 22,000+ European beaches, straight from official EEA monitoring data.",
                style={"color": "#8a8477", "fontSize": "0.9rem", "marginTop": "2px"},
            ),
        ], className="py-3"),
    ], style={"backgroundColor": "white", "borderBottom": "1px solid #eee6d8"})


def find_beach_tab():
    return html.Div([
        dbc.Row([
            dbc.Col([
                dbc.Label("Search by beach name", style={"fontWeight": 600, "fontSize": "0.85rem"}),
                html.Div([
                    dcc.Input(
                        id="search-box", type="text", placeholder="e.g. Nice, Palma, Zakynthos...",
                        debounce=True, autoComplete="off", style={
                            "width": "100%", "padding": "10px 14px", "borderRadius": "10px",
                            "border": "1px solid #ddd6c4", "fontSize": "0.95rem",
                        },
                    ),
                    html.Div(id="search-results", style={
                        "position": "absolute", "top": "calc(100% + 4px)", "left": 0, "right": 0,
                        "zIndex": 1000, "maxHeight": "320px", "overflowY": "auto",
                        "boxShadow": "0 8px 24px rgba(0,0,0,0.12)", "borderRadius": "10px",
                    }),
                ], style={"position": "relative"}),
            ], width=12, lg=5, className="mb-3"),
            dbc.Col([
                dbc.Label("Or browse by country", style={"fontWeight": 600, "fontSize": "0.85rem"}),
                dcc.Dropdown(
                    id="filter-country", options=COUNTRY_OPTIONS, multi=True,
                    placeholder="All countries",
                ),
            ], width=12, lg=7, className="mb-3"),
        ], className="mt-3"),

        dbc.Row([
            dbc.Col(
                dcc.Checklist(
                    id="filter-water-type",
                    options=[{"label": " Sea beaches only", "value": "coastal"}],
                    value=[],
                    inputStyle={"marginRight": "6px"},
                    style={"fontSize": "0.88rem", "color": "#5c5648"},
                ),
                width="auto",
            ),
            dbc.Col(
                html.Span(
                    "Includes river, lake and estuary bathing sites — tick to show sea beaches only.",
                    style={"fontSize": "0.8rem", "color": "#b0aa9c"},
                ),
                width="auto", className="d-flex align-items-center",
            ),
        ], className="mb-2 gx-2"),

        dbc.Row([
            dbc.Col(
                dbc.Spinner(dcc.Graph(id="site-map", style={"height": "62vh", "borderRadius": "14px"},
                                      config={"scrollZoom": True}), color="success"),
                width=12, lg=8,
            ),
            dbc.Col(
                html.Div(
                    dbc.Spinner(html.Div(id="site-detail-panel", children=welcome_panel())),
                    style={
                        "backgroundColor": "white", "borderRadius": "14px",
                        "border": "1px solid #eee6d8", "padding": "20px",
                        "height": "62vh", "overflowY": "auto",
                    },
                ),
                width=12, lg=4,
            ),
        ], className="g-3"),
    ])


def top_picks_tab():
    return html.Div([
        html.Div([
            html.Div("🏆 Great beaches to visit right now", style={
                "fontSize": "1.15rem", "fontWeight": 700, "color": "#2b2823", "marginTop": "20px",
            }),
            html.Div(
                "Excellent water quality that's held steady or improved over the years. 💎 marks a lesser-known spot.",
                style={"color": "#8a8477", "fontSize": "0.88rem", "marginBottom": "14px"},
            ),
        ]),
        dbc.Row(id="top-picks-grid", className="g-2"),

        html.Hr(style={"margin": "32px 0", "borderColor": "#eee6d8"}),

        html.Div([
            html.Div("🌧️ Good to know before you go", style={
                "fontSize": "1.15rem", "fontWeight": 700, "color": "#2b2823",
            }),
            html.Div(
                "At some beaches, water quality tends to dip for a day or two after heavy rain "
                "(rainwater run-off can carry bacteria into the water). If it's rained heavily in "
                "the last day or two, it's worth checking local advisories before swimming — "
                "especially at beaches flagged 🌧️ Rain-sensitive on their beach card.",
                style={"color": "#5c5648", "fontSize": "0.9rem", "marginTop": "6px", "maxWidth": "640px"},
            ),
        ], className="mb-4"),

        html.Div([
            html.Div("🗺️ How countries compare", style={
                "fontSize": "1.15rem", "fontWeight": 700, "color": "#2b2823",
            }),
            html.Div(
                "Share of monitored beaches rated Excellent, most recent season.",
                style={"color": "#8a8477", "fontSize": "0.88rem", "marginBottom": "10px"},
            ),
            dbc.Spinner(dcc.Graph(id="country-strip", config={"displayModeBar": False})),
        ], style={
            "backgroundColor": "white", "borderRadius": "14px", "border": "1px solid #eee6d8",
            "padding": "20px", "marginTop": "10px",
        }),
    ])


app.layout = html.Div([
    dcc.Store(id="selected-site"),
    header(),
    dbc.Container([
        dbc.Tabs([
            dbc.Tab(find_beach_tab(), label="Find a Beach", tab_id="tab-find"),
            dbc.Tab(top_picks_tab(), label="Top Picks", tab_id="tab-picks"),
        ], id="tabs", active_tab="tab-find", className="mt-2"),
    ], fluid="lg", className="pb-5"),
])


# --------------------------------------------------------------------------- #
# Callbacks
# --------------------------------------------------------------------------- #
@app.callback(
    Output("site-map", "figure"),
    Input("filter-country", "value"),
    Input("filter-water-type", "value"),
    Input("site-map", "relayoutData"),
    Input("selected-site", "data"),
)
def update_map(countries, water_types, relayout, selected_site):
    triggered = dash.ctx.triggered_id

    zoom, center = DEFAULT_ZOOM, DEFAULT_CENTER
    if triggered == "selected-site" and selected_site:
        zoom = 12.5
        center = {"lat": selected_site["lat"], "lon": selected_site["lon"]}
    elif relayout:
        if "mapbox.zoom" in relayout:
            zoom = relayout["mapbox.zoom"]
        if "mapbox.center" in relayout:
            center = relayout["mapbox.center"]

    df = get_scorecard(countries, water_types)
    return build_map(df, zoom=zoom, center=center, highlight=selected_site)


@app.callback(
    Output("site-detail-panel", "children"),
    Input("site-map", "clickData"),
    Input("selected-site", "data"),
)
def update_detail(click_data, selected_site):
    triggered = dash.ctx.triggered_id

    if triggered == "selected-site":
        if not selected_site:
            return welcome_panel()
        return _render_site_detail(selected_site["bathing_water_id"])

    if not click_data:
        return welcome_panel()
    try:
        point = click_data["points"][0]
        custom = point["customdata"]
        marker_type = custom[1] if len(custom) > 1 else "site"
    except (KeyError, IndexError):
        return welcome_panel()

    if marker_type == "cluster":
        return html.Div([
            html.Div("🔍", style={"fontSize": "2.2rem", "textAlign": "center"}),
            html.Div("Zoom in to see individual beaches", style={
                "textAlign": "center", "fontWeight": 600, "color": "#2b2823", "marginTop": "8px",
            }),
            html.Div("Scroll or pinch to zoom into this area on the map.", style={
                "textAlign": "center", "color": "#8a8477", "fontSize": "0.85rem",
            }),
        ], style={"padding": "60px 20px"})

    return _render_site_detail(custom[0])


def _render_site_detail(bw_id):
    scorecard = get_scorecard()
    site_row = scorecard[scorecard["bathing_water_id"] == bw_id]
    if site_row.empty:
        return welcome_panel()
    site_row = site_row.iloc[0]

    timeline, _ = fetch_site_detail(bw_id)
    return verdict_card(
        site_row, timeline,
        hidden_gem=bool(site_row.get("hidden_gem")),
        rainfall_sensitive=bool(site_row.get("rainfall_sensitive")),
    )


@app.callback(
    Output("search-results", "children"),
    Input("search-box", "value"),
)
def update_search(query):
    if not query or len(query) < 2:
        return None
    results = search_sites(query)
    if results.empty:
        return html.Div("No beaches found.", style={
            "backgroundColor": "white", "borderRadius": "10px", "border": "1px solid #eee6d8",
            "padding": "10px", "color": "#8a8477", "fontSize": "0.85rem",
        })

    items = []
    for _, r in results.iterrows():
        info = CLASS_INFO.get(r["current_classification"], CLASS_INFO["Unknown"])
        items.append(html.Div([
            html.Span(info["emoji"], className="me-2"),
            html.Span(r["name"].title(), style={"fontWeight": 600}),
            html.Span(f"  ·  {COUNTRY_NAMES.get(r['country_code'], r['country_code'])}",
                     style={"color": "#8a8477", "fontSize": "0.85rem"}),
        ], id={"type": "search-result", "index": r["bathing_water_id"]}, n_clicks=0, style={
            "padding": "10px 12px", "borderBottom": "1px solid #f0ece0", "cursor": "pointer",
        }, className="search-result-item"))

    return html.Div(items, style={
        "backgroundColor": "white", "borderRadius": "10px",
        "border": "1px solid #eee6d8",
    })


@app.callback(
    Output("selected-site", "data"),
    Output("search-box", "value"),
    Output("search-results", "children", allow_duplicate=True),
    Input({"type": "search-result", "index": dash.ALL}, "n_clicks"),
    State("search-results", "children"),
    prevent_initial_call=True,
)
def select_search_result(n_clicks_list, current_results):
    if not any(n_clicks_list) or not dash.ctx.triggered_id:
        return dash.no_update, dash.no_update, dash.no_update

    bw_id = dash.ctx.triggered_id["index"]
    scorecard = get_scorecard()
    row = scorecard[scorecard["bathing_water_id"] == bw_id]
    if row.empty:
        return dash.no_update, dash.no_update, dash.no_update
    row = row.iloc[0]

    return (
        {"bathing_water_id": bw_id, "lat": float(row["latitude"]), "lon": float(row["longitude"])},
        row["name"].title(),
        None,
    )


@app.callback(
    Output("top-picks-grid", "children"),
    Input("tabs", "active_tab"),
)
def update_top_picks(active_tab):
    if active_tab != "tab-picks":
        return dash.no_update
    df = fetch_top_picks(limit=18)
    if df.empty:
        return html.Div("No data available yet.", style={"color": "#8a8477"})
    return [beach_card(row) for _, row in df.iterrows()]


@app.callback(
    Output("country-strip", "figure"),
    Input("tabs", "active_tab"),
)
def update_country_strip(active_tab):
    if active_tab != "tab-picks":
        return dash.no_update
    df = fetch_country_summary()
    return build_country_strip(df)


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)
