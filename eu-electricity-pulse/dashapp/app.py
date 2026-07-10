"""
EU Electricity Price Pulse — Dash app
Shows day-ahead electricity prices across 41 European bidding zones sourced
from euenergy.live via a daily Airflow pipeline → dbt marts → this UI.

All 4 pages are rendered in the DOM at startup and toggled with CSS display,
so Dash callbacks always find their target components.
"""
import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import numpy as np

# ── DB ─────────────────────────────────────────────────────────────────────
# Dash runs in the web environment — use dataflow SDK + raw psycopg2,
# same pattern as neighbourhood_scout.
def get_conn():
    from dataflow import Dataflow
    import psycopg2
    c = Dataflow().connection('euenergy_db', mode='dict')
    return psycopg2.connect(
        host=c['host'], port=c.get('port', 5432),
        dbname=c['schema'], user=c['login'], password=c['password'],
    )

def q(sql, **params):
    conn = get_conn()
    try:
        # mogrify-style substitution: replace :key with %(key)s for psycopg2
        pg_sql = sql
        for key in params:
            pg_sql = pg_sql.replace(f':{key}', f'%({key})s')
        return pd.read_sql(pg_sql, conn, params=params if params else None)
    finally:
        conn.close()

# ── DESIGN TOKENS ──────────────────────────────────────────────────────────
BG       = "#0a0e1a"
SURFACE  = "#111827"
SURFACE2 = "#1a2236"
BORDER   = "#1e2d45"
TEXT     = "#e8edf5"
MUTED    = "#6b7a99"
ACCENT   = "#3b82f6"
CHEAP    = "#22d3ee"
PRICEY   = "#f87171"
SPIKE_C  = "#f87171"
DIP_C    = "#34d399"
CAT      = ["#3b82f6","#f87171","#34d399","#facc15","#a78bfa","#22d3ee","#fb923c","#4ade80"]

def base_layout(**overrides):
    layout = dict(
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family="Inter,sans-serif", color=TEXT, size=12),
        margin=dict(l=52, r=16, t=24, b=44),
        xaxis=dict(gridcolor=BORDER, zeroline=False, linecolor=BORDER,
                   tickfont=dict(color=MUTED, size=11)),
        yaxis=dict(gridcolor=BORDER, zeroline=False, linecolor=BORDER,
                   tickfont=dict(color=MUTED, size=11)),
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=BORDER, font=dict(size=11)),
        hoverlabel=dict(bgcolor=SURFACE2, bordercolor=BORDER,
                        font=dict(family="Inter", size=12, color=TEXT)),
    )
    layout.update(overrides)
    return layout

# ── LOAD INITIAL DATA ───────────────────────────────────────────────────────
def load_dates():
    df = q("SELECT DISTINCT delivery_date FROM public_marts.mart_current_prices ORDER BY delivery_date DESC LIMIT 30")
    return df["delivery_date"].astype(str).tolist() if not df.empty else []

def load_zone_options():
    df = q("SELECT DISTINCT zone_code, zone_name FROM public_marts.mart_hourly_timeline ORDER BY zone_code")
    return [{"label": f"{r['zone_code']} – {r['zone_name']}", "value": r["zone_code"]}
            for _, r in df.iterrows()] if not df.empty else []

# ── COMPONENTS ─────────────────────────────────────────────────────────────
def kpi(kpi_id, label):
    return html.Div(style={
        "background": SURFACE2, "border": f"1px solid {BORDER}",
        "borderRadius": "12px", "padding": "18px 20px", "flex": "1",
        "borderTop": f"2px solid {ACCENT}",
    }, children=[
        html.Div(label, style={"fontSize":"0.7rem","fontWeight":"600","letterSpacing":"0.08em",
                               "textTransform":"uppercase","color":MUTED,"marginBottom":"6px"}),
        html.Div(id=kpi_id, style={"fontSize":"1.55rem","fontWeight":"700","color":TEXT}),
    ])

def card(children, style=None):
    s = {"background": SURFACE2, "border": f"1px solid {BORDER}",
         "borderRadius": "14px", "padding": "22px 24px", "marginBottom": "18px"}
    if style:
        s.update(style)
    return html.Div(style=s, children=children)

def dropdown(id_, options=None, value=None, multi=False, width="160px", placeholder=""):
    return dcc.Dropdown(
        id=id_, options=options or [], value=value, multi=multi,
        clearable=False if not multi else True,
        placeholder=placeholder,
        style={"width": width, "fontSize": "0.83rem", "color": "#000"},
    )

def label(text):
    return html.Div(text, style={"fontSize":"0.7rem","fontWeight":"600","letterSpacing":"0.06em",
                                  "textTransform":"uppercase","color":MUTED,"marginBottom":"5px"})

def graph(id_, height=460):
    return dcc.Loading(
        dcc.Graph(id=id_, style={"height": f"{height}px"},
                  config={"displayModeBar": False, "responsive": True}),
        color=ACCENT,
    )

# ── PAGES ──────────────────────────────────────────────────────────────────
dates       = load_dates()
zone_opts   = load_zone_options()
latest_date = dates[0] if dates else None

def page_map():
    return html.Div([
        html.Div([
            html.H2("⚡ Day-Ahead Price Map", style={"margin":"0 0 4px","fontSize":"1.3rem","fontWeight":"700"}),
            html.P("Hourly electricity prices across 41 ENTSO-E bidding zones. "
                   "The bubble size and colour show how expensive each zone is. "
                   "Hit ▶ Play to watch prices shift as demand rises and falls through the day.",
                   style={"margin":"0 0 20px","color":MUTED,"fontSize":"0.85rem"}),
        ]),
        # KPI strip
        html.Div(style={"display":"flex","gap":"14px","marginBottom":"20px"}, children=[
            kpi("kpi-min",    "Min Price"),
            kpi("kpi-max",    "Max Price"),
            kpi("kpi-avg",    "EU Average"),
            kpi("kpi-spread", "Zone Spread"),
        ]),
        card([
            html.Div(style={"display":"flex","justifyContent":"space-between","alignItems":"flex-end",
                            "marginBottom":"16px","flexWrap":"wrap","gap":"12px"}, children=[
                html.Div([
                    html.Span("Showing all 41 bidding zones · ",
                              style={"color":MUTED,"fontSize":"0.8rem"}),
                    html.Span(id="map-date-label",
                              style={"color":ACCENT,"fontSize":"0.8rem","fontWeight":"600"}),
                ]),
                html.Div(style={"display":"flex","gap":"8px","alignItems":"flex-end"}, children=[
                    html.Div([label("Date"), dropdown("map-date", options=[{"label":d,"value":d} for d in dates], value=latest_date)]),
                ]),
            ]),
            graph("price-map", 620),
        ]),
        html.Div([
            html.Div(style={"fontSize":"0.7rem","fontWeight":"600","letterSpacing":"0.06em",
                            "textTransform":"uppercase","color":MUTED,"marginBottom":"10px"},
                     children="All zones · cheapest → most expensive"),
            html.Div(id="zone-ticker", style={"display":"flex","flexWrap":"wrap","gap":"8px"}),
        ]),
    ])

def page_timeline():
    return html.Div([
        html.H2("📈 Hourly Price Timeline", style={"margin":"0 0 4px","fontSize":"1.3rem","fontWeight":"700"}),
        html.P("Select zones to compare how their price curves move through the day. "
               "Renewable zones like Norway (NO1–NO5) and Sweden (SE1–SE2) often look very different from "
               "thermal-heavy zones like Italy or Poland.",
               style={"margin":"0 0 20px","color":MUTED,"fontSize":"0.85rem"}),
        card([
            html.Div(style={"display":"flex","gap":"14px","marginBottom":"20px","flexWrap":"wrap"}, children=[
                html.Div([label("Date"),
                          dropdown("tl-date", options=[{"label":d,"value":d} for d in dates],
                                   value=latest_date, width="160px")]),
                html.Div([label("Zones (max 8)"),
                          dropdown("tl-zones", options=zone_opts,
                                   value=["DE-LU","FR","ES","NO1"],
                                   multi=True, width="480px", placeholder="Pick zones…")]),
            ]),
            graph("tl-chart", 480),
        ]),
    ])

def page_spreads():
    return html.Div([
        html.H2("↔ Zone Spread Heatmap", style={"margin":"0 0 4px","fontSize":"1.3rem","fontWeight":"700"}),
        html.P("Price of the row zone minus the column zone (EUR/MWh). "
               "A red cell means the row zone is more expensive — exactly the signal a power trader "
               "watches for arbitrage across interconnectors. Use the hour slider to step through the day.",
               style={"margin":"0 0 20px","color":MUTED,"fontSize":"0.85rem"}),
        card([
            html.Div(style={"display":"flex","gap":"24px","alignItems":"flex-end","marginBottom":"20px","flexWrap":"wrap"}, children=[
                html.Div(style={"flex":"1","minWidth":"260px"}, children=[
                    label("Delivery Hour"),
                    dcc.Slider(id="spread-hour", min=0, max=23, step=1, value=12,
                               marks={h: {"label":str(h),"style":{"color":MUTED,"fontSize":"0.7rem"}}
                                      for h in range(0,24,3)},
                               tooltip={"placement":"bottom"}),
                ]),
                html.Div(id="spread-badge", style={
                    "background":"rgba(59,130,246,0.12)","color":ACCENT,
                    "border":f"1px solid rgba(59,130,246,0.3)","borderRadius":"6px",
                    "padding":"4px 12px","fontSize":"0.85rem","fontWeight":"600","whiteSpace":"nowrap",
                }),
                html.Div(style={"fontSize":"0.75rem","color":MUTED}, children=[
                    html.Span("🔵 row cheaper  "),
                    html.Span("⚪ same  "),
                    html.Span("🔴 row pricier"),
                ]),
            ]),
            graph("spread-heatmap", 650),
        ]),
    ])

def page_anomalies():
    return html.Div([
        html.H2("🔔 Price Anomaly Explorer", style={"margin":"0 0 4px","fontSize":"1.3rem","fontWeight":"700"}),
        html.P("Hours where a zone's price is more than 2 standard deviations from its 30-day same-hour average. "
               "Spikes often signal a supply crunch or interconnector outage; dips appear when wind or solar floods the grid. "
               "This page populates after 30 days of data has accumulated.",
               style={"margin":"0 0 20px","color":MUTED,"fontSize":"0.85rem"}),
        html.Div(style={"display":"flex","gap":"14px","marginBottom":"20px"}, children=[
            kpi("anom-total",  "Total Anomalies"),
            kpi("anom-spikes", "Price Spikes (+2σ)"),
            kpi("anom-dips",   "Price Dips (−2σ)"),
            kpi("anom-worst",  "Worst Z-score"),
        ]),
        card([
            html.Div(style={"marginBottom":"16px"}, children=[
                label("Filter by Zone"),
                dcc.Dropdown(id="anom-zone", options=[], value=None,
                             clearable=True, placeholder="All zones",
                             style={"width":"200px","fontSize":"0.83rem","color":"#000"}),
            ]),
            graph("anom-chart", 460),
        ]),
    ])

# ── APP LAYOUT — all pages in DOM, toggled by display ──────────────────────
app = dash.Dash(__name__, suppress_callback_exceptions=True,
                meta_tags=[{"name":"viewport","content":"width=device-width,initial-scale=1"}])
app.title = "EU Electricity Price Pulse"
server = app.server

NAV = [("map","⚡ Price Map"),("timeline","📈 Timeline"),("spreads","↔ Spreads"),("anomalies","🔔 Anomalies")]

def nav_btn(pid, label_text):
    return html.Button(label_text, id=f"nav-{pid}", n_clicks=0, style={
        "padding":"7px 16px","borderRadius":"6px","fontSize":"0.85rem","fontWeight":"500",
        "border":"none","cursor":"pointer","background":"none","color":MUTED,
        "transition":"all 0.15s",
    })

app.layout = html.Div(style={"background":BG,"minHeight":"100vh","fontFamily":"Inter,sans-serif","color":TEXT}, children=[
    dcc.Store(id="active-page", data="map"),

    # Navbar
    html.Nav(style={
        "background":SURFACE,"borderBottom":f"1px solid {BORDER}",
        "padding":"0 28px","height":"58px","display":"flex","alignItems":"center",
        "justifyContent":"space-between","position":"sticky","top":"0","zIndex":"100",
    }, children=[
        html.Div(style={"display":"flex","alignItems":"center","gap":"10px"}, children=[
            html.Span("⚡", style={"fontSize":"1.3rem","color":"#facc15"}),
            html.Span("EU Electricity Pulse", style={"fontWeight":"700","fontSize":"1rem","letterSpacing":"0.02em"}),
            html.Span("LIVE", style={
                "fontSize":"0.65rem","fontWeight":"700","background":"rgba(34,211,238,0.15)",
                "color":CHEAP,"border":"1px solid rgba(34,211,238,0.3)","borderRadius":"4px",
                "padding":"1px 6px","letterSpacing":"0.1em","marginLeft":"4px",
            }),
        ]),
        html.Div(style={"display":"flex","gap":"4px"}, children=[nav_btn(pid, lbl) for pid, lbl in NAV]),
    ]),

    # Page container — all pages rendered, only active one visible
    html.Div(style={"maxWidth":"1360px","margin":"0 auto","padding":"28px 24px"}, children=[
        html.Div(id="page-map",       children=page_map(),       style={"display":"block"}),
        html.Div(id="page-timeline",  children=page_timeline(),  style={"display":"none"}),
        html.Div(id="page-spreads",   children=page_spreads(),   style={"display":"none"}),
        html.Div(id="page-anomalies", children=page_anomalies(), style={"display":"none"}),
    ]),
])

# ── ROUTING ────────────────────────────────────────────────────────────────
@callback(Output("active-page","data"),
          [Input(f"nav-{pid}","n_clicks") for pid,_ in NAV],
          prevent_initial_call=True)
def switch_page(*_):
    ctx = dash.callback_context
    if not ctx.triggered:
        return "map"
    return ctx.triggered[0]["prop_id"].split(".")[0].replace("nav-","")

# Toggle page visibility + nav active style
@callback(
    [Output(f"page-{pid}","style") for pid,_ in NAV] +
    [Output(f"nav-{pid}","style") for pid,_ in NAV],
    Input("active-page","data"),
)
def toggle_pages(active):
    page_styles = [{"display":"block"} if pid==active else {"display":"none"} for pid,_ in NAV]
    nav_styles = []
    for pid,_ in NAV:
        if pid == active:
            nav_styles.append({"padding":"7px 16px","borderRadius":"6px","fontSize":"0.85rem",
                                "fontWeight":"500","border":"none","cursor":"pointer",
                                "background":"rgba(59,130,246,0.12)","color":ACCENT,"transition":"all 0.15s"})
        else:
            nav_styles.append({"padding":"7px 16px","borderRadius":"6px","fontSize":"0.85rem",
                                "fontWeight":"500","border":"none","cursor":"pointer",
                                "background":"none","color":MUTED,"transition":"all 0.15s"})
    return page_styles + nav_styles

# ── MAP ─────────────────────────────────────────────────────────────────────
@callback(
    Output("price-map","figure"),
    Output("kpi-min","children"), Output("kpi-max","children"),
    Output("kpi-avg","children"), Output("kpi-spread","children"),
    Output("zone-ticker","children"), Output("map-date-label","children"),
    Input("map-date","value"),
)
def update_map(date):
    empty = go.Figure().update_layout(**base_layout())
    if not date:
        return empty, "—", "—", "—", "—", [], ""

    df = q("SELECT * FROM public_marts.mart_current_prices WHERE delivery_date = :d ORDER BY delivery_hour", d=date)
    if df.empty:
        return empty, "—", "—", "—", "—", [], date

    mn  = df["price_eur_mwh"].min()
    mx  = df["price_eur_mwh"].max()
    avg = df["price_eur_mwh"].mean()
    spd = mx - mn

    fig = px.scatter_geo(
        df, lat="latitude", lon="longitude",
        color="price_eur_mwh", size="price_eur_mwh", size_max=34,
        hover_name="zone_name",
        hover_data={"price_eur_mwh":":.1f","zone_code":True,"country":True,
                    "latitude":False,"longitude":False},
        animation_frame="delivery_hour",
        color_continuous_scale=[[0,CHEAP],[0.5,ACCENT],[1,PRICEY]],
        range_color=[df["price_eur_mwh"].quantile(0.05), df["price_eur_mwh"].quantile(0.95)],
        labels={"price_eur_mwh":"EUR/MWh","delivery_hour":"Hour"},
    )
    fig.update_geos(
        # Wide crop: narrow lat range (cut Arctic) + wide lon = landscape aspect ratio
        lataxis_range=[34, 62],
        lonaxis_range=[-15, 42],
        projection_type="mercator",
        showland=True,  landcolor="#161f2e",
        showocean=True, oceancolor="#0d1420",
        showcoastlines=True, coastlinecolor="#2a3a56",
        showcountries=True,  countrycolor="#2a3a56",
        showframe=False, bgcolor=SURFACE,
        domain=dict(x=[0, 1], y=[0, 1]),
    )
    fig.update_layout(
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family="Inter,sans-serif", color=TEXT),
        margin=dict(l=0, r=80, t=0, b=40),
        coloraxis_colorbar=dict(
            title=dict(text="EUR/MWh", font=dict(size=11, color=MUTED)),
            tickfont=dict(size=10, color=MUTED), len=0.7, thickness=12,
            x=1.0, xanchor="left",
            bgcolor="rgba(0,0,0,0)", bordercolor=BORDER,
        ),
        hoverlabel=dict(bgcolor=SURFACE2, bordercolor=BORDER,
                        font=dict(family="Inter", size=12, color=TEXT)),
        updatemenus=[dict(
            type="buttons", showactive=False,
            y=-0.06, x=0.5, xanchor="center",
            bgcolor=SURFACE2, bordercolor=BORDER, font=dict(color=TEXT, size=12),
            buttons=[
                dict(label="▶  Play",  method="animate",
                     args=[None, {"frame": {"duration": 700, "redraw": True}, "fromcurrent": True}]),
                dict(label="⏸ Pause", method="animate",
                     args=[[None], {"frame": {"duration": 0}, "mode": "immediate"}]),
            ],
        )],
    )

    # Zone ticker — snapshot at latest hour, sorted cheapest → priciest
    latest = df["delivery_hour"].max()
    snap   = df[df["delivery_hour"]==latest].sort_values("price_eur_mwh")

    chips = []
    for _, row in snap.iterrows():
        p   = row["price_eur_mwh"]
        col = CHEAP if p < avg*0.8 else (PRICEY if p > avg*1.2 else ACCENT)
        chips.append(html.Div(style={
            "display":"flex","alignItems":"center","gap":"6px",
            "background":SURFACE,"border":f"1px solid {BORDER}",
            "borderRadius":"20px","padding":"4px 10px 4px 8px","fontSize":"0.78rem",
        }, children=[
            html.Div(style={"width":"8px","height":"8px","borderRadius":"50%",
                            "background":col,"flexShrink":"0"}),
            html.Span(row["zone_code"], style={"color":MUTED,"fontSize":"0.72rem"}),
            html.Span(f" {p:.0f}", style={"color":TEXT,"fontWeight":"600"}),
        ]))

    return (
        fig,
        f"{mn:.1f} EUR/MWh", f"{mx:.1f} EUR/MWh",
        f"{avg:.1f} EUR/MWh", f"{spd:.1f} EUR/MWh",
        chips, date,
    )

# ── TIMELINE ────────────────────────────────────────────────────────────────
@callback(Output("tl-chart","figure"), Input("tl-date","value"), Input("tl-zones","value"))
def update_timeline(date, zones):
    layout = base_layout(
        xaxis=dict(gridcolor=BORDER,zeroline=False,linecolor=BORDER,
                   tickfont=dict(color=MUTED,size=11),title="Hour (UTC)",
                   tickmode="linear",tick0=0,dtick=2),
        yaxis=dict(gridcolor=BORDER,zeroline=False,linecolor=BORDER,
                   tickfont=dict(color=MUTED,size=11),title="EUR / MWh"),
        legend=dict(bgcolor="rgba(0,0,0,0)",bordercolor=BORDER,font=dict(size=11),
                    orientation="h",y=-0.18,x=0),
        hovermode="x unified",
    )
    fig = go.Figure().update_layout(**layout)
    if not date or not zones:
        return fig

    zones = zones[:8]
    z_in  = ",".join([f"'{z}'" for z in zones])
    df    = q(
        f"SELECT zone_code,zone_name,delivery_hour,price_eur_mwh "
        f"FROM public_marts.mart_hourly_timeline "
        f"WHERE delivery_date=:d AND zone_code IN ({z_in}) ORDER BY zone_code,delivery_hour",
        d=date,
    )
    if df.empty:
        return fig

    for i, zone in enumerate(zones):
        zdf = df[df["zone_code"]==zone]
        if zdf.empty:
            continue
        col   = CAT[i % len(CAT)]
        label_= f"{zone} – {zdf['zone_name'].iloc[0]}"
        fig.add_trace(go.Scatter(
            x=zdf["delivery_hour"], y=zdf["price_eur_mwh"],
            mode="lines+markers", name=label_,
            line=dict(width=2.5,color=col),
            marker=dict(size=7,color=col,line=dict(width=1.5,color=SURFACE)),
            hovertemplate=f"<b>{label_}</b><br>%{{x:02d}}:00  →  %{{y:.1f}} EUR/MWh<extra></extra>",
        ))
    return fig

# ── SPREADS ─────────────────────────────────────────────────────────────────
@callback(Output("spread-heatmap","figure"), Output("spread-badge","children"),
          Input("spread-hour","value"))
def update_spreads(hour):
    fig = go.Figure().update_layout(**base_layout())
    if hour is None:
        return fig, "—"

    df = q("SELECT zone_a,zone_b,spread_eur_mwh FROM public_marts.mart_zone_spreads "
           "WHERE delivery_hour=:h ORDER BY zone_a,zone_b", h=hour)
    if df.empty:
        return fig, f"{hour:02d}:00"

    pivot  = df.pivot(index="zone_a", columns="zone_b", values="spread_eur_mwh")
    zones  = sorted(set(df["zone_a"])|set(df["zone_b"]))
    pivot  = pivot.reindex(index=zones, columns=zones)
    maxabs = float(np.nanmax(np.abs(pivot.values)))

    fig.add_trace(go.Heatmap(
        z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
        colorscale=[[0,ACCENT],[0.5,SURFACE2],[1,PRICEY]],
        zmid=0, zmin=-maxabs, zmax=maxabs,
        colorbar=dict(title=dict(text="EUR/MWh",font=dict(size=11,color=MUTED)),
                      tickfont=dict(size=9,color=MUTED),thickness=12,
                      bgcolor="rgba(0,0,0,0)",bordercolor=BORDER),
        hoverongaps=False,
        hovertemplate="<b>%{y} → %{x}</b><br>Spread: %{z:.1f} EUR/MWh<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family="Inter,sans-serif",color=TEXT),
        margin=dict(l=82,r=16,t=16,b=82),
        xaxis=dict(tickfont=dict(size=9,color=MUTED),gridcolor=BORDER,side="bottom"),
        yaxis=dict(tickfont=dict(size=9,color=MUTED),gridcolor=BORDER,autorange="reversed"),
        hoverlabel=dict(bgcolor=SURFACE2,bordercolor=BORDER,font=dict(family="Inter",size=12,color=TEXT)),
    )
    return fig, f"{hour:02d}:00"

# ── ANOMALIES ───────────────────────────────────────────────────────────────
@callback(
    Output("anom-zone","options"),
    Output("anom-chart","figure"),
    Output("anom-total","children"), Output("anom-spikes","children"),
    Output("anom-dips","children"),  Output("anom-worst","children"),
    Input("anom-zone","value"),
)
def update_anomalies(zone):
    layout = base_layout(
        xaxis=dict(gridcolor=BORDER,zeroline=False,linecolor=BORDER,
                   tickfont=dict(color=MUTED,size=11),title="Date"),
        yaxis=dict(gridcolor=BORDER,zeroline=False,linecolor=BORDER,
                   tickfont=dict(color=MUTED,size=11),title="EUR / MWh"),
        legend=dict(bgcolor="rgba(0,0,0,0)",bordercolor=BORDER,font=dict(size=11),
                    orientation="h",y=-0.18,x=0),
        hovermode="closest",
    )

    # Always reload zone options
    zdf      = q("SELECT DISTINCT zone_code FROM public_marts.mart_price_anomalies ORDER BY zone_code")
    zone_ops = [{"label":z,"value":z} for z in zdf["zone_code"]] if not zdf.empty else []

    sql    = "SELECT * FROM public_marts.mart_price_anomalies"
    params = {}
    if zone:
        sql += " WHERE zone_code=:z"
        params["z"] = zone
    sql += " ORDER BY delivery_date,delivery_hour"
    df = q(sql, **params)

    fig = go.Figure().update_layout(**layout)

    if df.empty:
        fig.update_layout(annotations=[dict(
            text="No anomalies yet — this page fills in after 30 days of daily data",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=14,color=MUTED),
        )])
        return zone_ops, fig, "0", "0", "0", "—"

    spikes = df[df["anomaly_type"]=="spike"]
    dips   = df[df["anomaly_type"]=="dip"]
    worst  = df["z_score"].abs().max()

    for subset, col, name in [(spikes,SPIKE_C,"Spike +2σ"),(dips,DIP_C,"Dip −2σ")]:
        if subset.empty:
            continue
        tsx = subset["delivery_date"].astype(str)+"T"+subset["delivery_hour"].astype(str).str.zfill(2)+":00"
        fig.add_trace(go.Scatter(
            x=tsx, y=subset["price_eur_mwh"],
            mode="markers", name=name,
            marker=dict(color=col,size=10,opacity=0.9,line=dict(width=1.5,color=SURFACE)),
            customdata=subset[["zone_code","z_score","baseline_mean_30d"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Price: %{y:.1f} EUR/MWh<br>"
                "Z-score: %{customdata[1]:.2f}σ<br>"
                "30d avg: %{customdata[2]:.1f} EUR/MWh<extra></extra>"
            ),
        ))

    if zone:
        xs = df["delivery_date"].astype(str)+"T"+df["delivery_hour"].astype(str).str.zfill(2)+":00"
        fig.add_trace(go.Scatter(
            x=xs, y=df["baseline_mean_30d"], mode="lines", name="30d avg",
            line=dict(width=1.5,color=MUTED,dash="dot"),
            hovertemplate="Baseline: %{y:.1f} EUR/MWh<extra></extra>",
        ))

    return zone_ops, fig, str(len(df)), str(len(spikes)), str(len(dips)), f"{worst:.1f}σ"


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8050
    app.run(host="0.0.0.0", port=port, debug=False)
