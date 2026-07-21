"""
EU Electricity Price Pulse — Dash app
Day-ahead electricity prices across 41 ENTSO-E bidding zones sourced from
euenergy.live via a daily Airflow pipeline → dbt marts → this UI.
"""
import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import numpy as np

# ── DB ─────────────────────────────────────────────────────────────────────
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
GOLD     = "#facc15"
SPIKE_C  = "#f87171"
DIP_C    = "#34d399"
CAT      = ["#3b82f6","#f87171","#34d399","#facc15","#a78bfa","#22d3ee","#fb923c","#4ade80"]

COUNTRY_FLAG = {
    "AT":"🇦🇹","BE":"🇧🇪","BG":"🇧🇬","CH":"🇨🇭","CZ":"🇨🇿",
    "DE":"🇩🇪","DK":"🇩🇰","EE":"🇪🇪","ES":"🇪🇸","FI":"🇫🇮",
    "FR":"🇫🇷","GR":"🇬🇷","HR":"🇭🇷","HU":"🇭🇺","IT":"🇮🇹",
    "LT":"🇱🇹","LV":"🇱🇻","NL":"🇳🇱","NO":"🇳🇴","PL":"🇵🇱",
    "PT":"🇵🇹","RO":"🇷🇴","RS":"🇷🇸","SE":"🇸🇪","SI":"🇸🇮",
    "SK":"🇸🇰","UA":"🇺🇦",
}
COUNTRY_NAME = {
    "AT":"Austria","BE":"Belgium","BG":"Bulgaria","CH":"Switzerland","CZ":"Czechia",
    "DE":"Germany","DK":"Denmark","EE":"Estonia","ES":"Spain","FI":"Finland",
    "FR":"France","GR":"Greece","HR":"Croatia","HU":"Hungary","IT":"Italy",
    "LT":"Lithuania","LV":"Latvia","NL":"Netherlands","NO":"Norway","PL":"Poland",
    "PT":"Portugal","RO":"Romania","RS":"Serbia","SE":"Sweden","SI":"Slovenia",
    "SK":"Slovakia","UA":"Ukraine",
}

# ── NAV BUTTON STYLES ──────────────────────────────────────────────────────
_NAV_BASE = {
    "padding":"0 20px","height":"58px","border":"none","outline":"none","cursor":"pointer",
    "background":"none","fontSize":"0.8rem","letterSpacing":"0.04em",
    "fontFamily":"Inter,sans-serif","display":"flex","alignItems":"center",
    "transition":"color 0.15s",
}
NAV_ACTIVE   = {**_NAV_BASE, "color":TEXT, "fontWeight":"600",
                "boxShadow":f"inset 0 -2px 0 {ACCENT}"}
NAV_INACTIVE = {**_NAV_BASE, "color":MUTED, "fontWeight":"400", "boxShadow":"none"}

# ── BASE LAYOUT ─────────────────────────────────────────────────────────────
def base_layout(**overrides):
    layout = dict(
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
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

# ── DATA LOADERS ───────────────────────────────────────────────────────────
def load_dates():
    df = q("SELECT DISTINCT delivery_date FROM public_marts.mart_current_prices ORDER BY delivery_date DESC LIMIT 30")
    return df["delivery_date"].astype(str).tolist() if not df.empty else []

def load_zone_options():
    df = q("SELECT DISTINCT zone_code, zone_name FROM public_marts.mart_hourly_timeline ORDER BY zone_code")
    return [{"label": f"{r['zone_code']} – {r['zone_name']}", "value": r["zone_code"]}
            for _, r in df.iterrows()] if not df.empty else []

def load_country_options():
    df = q("SELECT DISTINCT country FROM public_marts.mart_current_prices ORDER BY country")
    return [
        {"label": f"{COUNTRY_FLAG.get(c,'')}  {COUNTRY_NAME.get(c,c)}", "value": c}
        for c in (df["country"].tolist() if not df.empty else [])
    ]

# ── UI COMPONENTS ──────────────────────────────────────────────────────────
def kpi(kpi_id, lbl):
    return html.Div(style={
        "background":SURFACE2,"border":f"1px solid {BORDER}","borderRadius":"12px",
        "padding":"18px 20px","flex":"1","borderTop":f"2px solid {ACCENT}",
    }, children=[
        html.Div(lbl, style={"fontSize":"0.68rem","fontWeight":"600","letterSpacing":"0.08em",
                              "textTransform":"uppercase","color":MUTED,"marginBottom":"6px"}),
        html.Div(id=kpi_id, style={"fontSize":"1.55rem","fontWeight":"700","color":TEXT}),
    ])

def card(children, style=None):
    s = {"background":SURFACE2,"border":f"1px solid {BORDER}",
         "borderRadius":"14px","padding":"22px 24px","marginBottom":"18px"}
    if style:
        s.update(style)
    return html.Div(style=s, children=children)

def dropdown(id_, options=None, value=None, multi=False, width="160px", placeholder=""):
    return dcc.Dropdown(
        id=id_, options=options or [], value=value, multi=multi,
        clearable=False if not multi else True, placeholder=placeholder,
        style={"width":width,"fontSize":"0.83rem","color":"#000"},
    )

def ctrl_label(text):
    return html.Div(text, style={"fontSize":"0.68rem","fontWeight":"600","letterSpacing":"0.06em",
                                  "textTransform":"uppercase","color":MUTED,"marginBottom":"5px"})

def graph(id_, height=460):
    return dcc.Loading(
        dcc.Graph(id=id_, style={"height":f"{height}px"},
                  config={"displayModeBar":False,"responsive":True}),
        color=ACCENT,
    )

def _dot(color, size=7, mt=7):
    return html.Div(style={
        "width":f"{size}px","height":f"{size}px","borderRadius":"50%",
        "background":color,"flexShrink":"0","marginTop":f"{mt}px",
    })

# ── STARTUP DATA ───────────────────────────────────────────────────────────
dates        = load_dates()
zone_opts    = load_zone_options()
country_opts = load_country_options()
latest_date  = dates[0] if dates else None

# ══════════════════════════════════════════════════════════════════════════
# SMART HOURS HELPERS
# ══════════════════════════════════════════════════════════════════════════

def _div_color(t):
    """Diverging: t∈[-1,1], -1→CHEAP, 0→MUTED neutral, +1→PRICEY"""
    N = (0x6b, 0x7a, 0x99)
    T, s = ((0x22, 0xd3, 0xee), -t) if t <= 0 else ((0xf8, 0x71, 0x71), t)
    return "#{:02x}{:02x}{:02x}".format(
        int(N[0] + s * (T[0] - N[0])),
        int(N[1] + s * (T[1] - N[1])),
        int(N[2] + s * (T[2] - N[2])),
    )

def _hour_period(h):
    if h < 6:   return "Late night"
    if h < 10:  return "Morning"
    if h < 16:  return "Midday"
    if h < 20:  return "Evening"
    return "Night"

def _build_verdict(df, flag, cname):
    if df.empty or pd.isna(df["today_avg"].iloc[0]):
        return html.Div()
    today_avg = float(df["today_avg"].iloc[0])
    raw_bl    = df["baseline_30d"].iloc[0]
    baseline  = float(raw_bl) if raw_bl is not None and not pd.isna(raw_bl) else None

    if baseline and baseline > 0:
        pct = (today_avg - baseline) / baseline * 100
        if pct < -15:
            title, detail = "Good day for electricity", \
                f"Prices are {abs(pct):.0f}% below your 30-day average — good time to run appliances or charge your EV."
            hi_col, bg, bdr = CHEAP,   "rgba(34,211,238,0.05)",  "rgba(34,211,238,0.28)"
        elif pct > 15:
            title, detail = "Expensive day for electricity", \
                f"Prices are {pct:.0f}% above your 30-day average — consider deferring heavy loads if you can."
            hi_col, bg, bdr = PRICEY,  "rgba(248,113,113,0.05)", "rgba(248,113,113,0.28)"
        else:
            title, detail = "Normal day for electricity", \
                f"Prices are {abs(pct):.0f}% {'below' if pct < 0 else 'above'} your 30-day average — nothing unusual."
            hi_col, bg, bdr = GOLD,    "rgba(250,204,21,0.05)",  "rgba(250,204,21,0.28)"
        bl_text = f"€{baseline:.1f}"
    else:
        title, detail = "Building your baseline", "30 days of data needed for comparisons — check back soon."
        hi_col, bg, bdr = ACCENT, "rgba(59,130,246,0.05)", "rgba(59,130,246,0.28)"
        bl_text = "—"

    return html.Div(style={
        "background":bg,"border":f"1px solid {bdr}","borderLeft":f"4px solid {hi_col}",
        "borderRadius":"12px","padding":"20px 24px","display":"flex",
        "justifyContent":"space-between","alignItems":"center","flexWrap":"wrap","gap":"20px",
    }, children=[
        html.Div(style={"minWidth":"0"}, children=[
            html.Div(style={"display":"flex","alignItems":"center","gap":"10px","marginBottom":"5px"}, children=[
                _dot(hi_col, size=9, mt=0),
                html.Span(title, style={"fontSize":"1.05rem","fontWeight":"700","color":TEXT}),
            ]),
            html.Div(detail, style={"fontSize":"0.83rem","color":MUTED,"lineHeight":"1.5","maxWidth":"440px"}),
        ]),
        html.Div(style={"display":"flex","gap":"28px","flexShrink":"0"}, children=[
            html.Div(style={"textAlign":"right"}, children=[
                html.Div("TODAY", style={"fontSize":"0.6rem","fontWeight":"700","letterSpacing":"0.1em","color":MUTED,"marginBottom":"2px"}),
                html.Div(f"€{today_avg:.1f}", style={"fontSize":"1.65rem","fontWeight":"700","color":hi_col}),
                html.Div("per MWh", style={"fontSize":"0.7rem","color":MUTED}),
            ]),
            html.Div(style={"textAlign":"right"}, children=[
                html.Div("30-DAY AVG", style={"fontSize":"0.6rem","fontWeight":"700","letterSpacing":"0.1em","color":MUTED,"marginBottom":"2px"}),
                html.Div(bl_text, style={"fontSize":"1.65rem","fontWeight":"700","color":MUTED}),
                html.Div("per MWh", style={"fontSize":"0.7rem","color":MUTED}),
            ]),
        ]),
    ])


def _build_bar_chart(df):
    layout = base_layout(
        xaxis=dict(
            gridcolor=BORDER, zeroline=False, linecolor=BORDER,
            tickfont=dict(color=MUTED, size=10),
            title=dict(text="Hour (UTC)", font=dict(size=10, color=MUTED), standoff=8),
            tickmode="array",
            tickvals=list(range(0, 24, 3)),
            ticktext=[f"{h:02d}:00" for h in range(0, 24, 3)],
        ),
        yaxis=dict(
            gridcolor=BORDER, zeroline=False, linecolor=BORDER,
            tickfont=dict(color=MUTED, size=10),
            title=dict(text="EUR / MWh", font=dict(size=10, color=MUTED), standoff=8),
        ),
        margin=dict(l=56, r=16, t=12, b=52), showlegend=False,
    )
    fig = go.Figure().update_layout(**layout)
    if df.empty:
        return fig

    avg  = df["price_eur_mwh"].mean()
    mn   = df["price_eur_mwh"].min()
    mx   = df["price_eur_mwh"].max()
    rng  = max(abs(mx - avg), abs(mn - avg), 0.001)
    cols = [_div_color(max(-1.0, min(1.0, (p - avg) / rng))) for p in df["price_eur_mwh"]]
    top3 = set(df.nsmallest(3, "price_eur_mwh")["delivery_hour"].tolist())
    labs = [f"{h:02d}:00–{(h+1)%24:02d}:00" for h in df["delivery_hour"]]

    fig.add_trace(go.Bar(
        x=df["delivery_hour"], y=df["price_eur_mwh"],
        marker_color=cols, marker_line_width=0, width=0.65,
        customdata=labs,
        hovertemplate="<b>%{customdata} UTC</b><br>€%{y:.1f} / MWh<extra></extra>",
    ))
    fig.add_hline(y=avg, line_color=MUTED, line_width=1,
                  annotation_text=f"avg  €{avg:.0f}",
                  annotation_position="top right",
                  annotation_font=dict(color=MUTED, size=10))
    for h in top3:
        row = df[df["delivery_hour"] == h].iloc[0]
        fig.add_annotation(x=h, y=row["price_eur_mwh"], text="★",
                           showarrow=False, font=dict(color=CHEAP, size=12), yshift=11)
    return fig


def _build_windows(df):
    if df.empty:
        return html.Div()
    mx   = df["price_eur_mwh"].max()
    top3 = df.nsmallest(3, "price_eur_mwh").reset_index(drop=True)
    ranks = ["Best hour today", "2nd cheapest", "3rd cheapest"]
    cards = []
    for i, row in top3.iterrows():
        h, p = int(row["delivery_hour"]), float(row["price_eur_mwh"])
        pct  = (mx - p) / mx * 100 if mx > 0 else 0
        cards.append(html.Div(style={
            "background":SURFACE2,"border":f"1px solid {BORDER}",
            "borderTop":f"3px solid {CHEAP}","borderRadius":"12px",
            "padding":"16px 18px","flex":"1","minWidth":"140px",
        }, children=[
            html.Div(ranks[i].upper(), style={"fontSize":"0.6rem","fontWeight":"700",
                                               "letterSpacing":"0.1em","color":CHEAP,"marginBottom":"9px"}),
            html.Div(f"{h:02d}:00 – {(h+1)%24:02d}:00 UTC",
                     style={"fontSize":"0.95rem","fontWeight":"700","color":TEXT,"marginBottom":"2px"}),
            html.Div(_hour_period(h), style={"fontSize":"0.75rem","color":MUTED,"marginBottom":"10px"}),
            html.Div(f"€{p:.1f} / MWh", style={"fontSize":"1.2rem","fontWeight":"700","color":CHEAP}),
            html.Div(f"{pct:.0f}% below today's peak",
                     style={"fontSize":"0.72rem","color":MUTED,"marginTop":"3px"}),
        ]))
    return html.Div(style={"display":"flex","gap":"14px","marginBottom":"18px"}, children=cards)


def _build_leaderboard(df, selected_country):
    if df.empty:
        return [html.Div("No data available.", style={"color":MUTED,"fontSize":"0.85rem"})]
    eu_avg, rows, divider_done = df["price_eur_mwh"].mean(), [], False
    for i, (_, row) in enumerate(df.iterrows()):
        c, p = row["country"], float(row["price_eur_mwh"])
        if not divider_done and p >= eu_avg:
            rows.append(html.Div(style={"display":"flex","alignItems":"center","gap":"10px","margin":"6px 0"}, children=[
                html.Div(style={"flex":"1","height":"1px","background":BORDER}),
                html.Span(f"EU avg  €{eu_avg:.1f}", style={"fontSize":"0.68rem","color":MUTED,"whiteSpace":"nowrap","padding":"0 10px"}),
                html.Div(style={"flex":"1","height":"1px","background":BORDER}),
            ]))
            divider_done = True
        flag, name  = COUNTRY_FLAG.get(c,""), COUNTRY_NAME.get(c,c)
        pct, is_me  = (p - eu_avg) / eu_avg * 100, (c == selected_country)
        if pct < -5:
            bc, bb, bbr, bt = CHEAP,  "rgba(34,211,238,0.1)",  "rgba(34,211,238,0.25)",  f"▼ {abs(pct):.0f}%"
        elif pct > 5:
            bc, bb, bbr, bt = PRICEY, "rgba(248,113,113,0.1)", "rgba(248,113,113,0.25)", f"▲ {pct:.0f}%"
        else:
            bc, bb, bbr, bt = MUTED,  "rgba(107,122,153,0.1)", "rgba(107,122,153,0.25)", "≈ avg"
        rows.append(html.Div(style={
            "display":"flex","alignItems":"center","padding":"9px 12px","borderRadius":"8px",
            "marginBottom":"2px","gap":"10px",
            "background":"rgba(59,130,246,0.07)" if is_me else "transparent",
            "border":f"1px solid {'rgba(59,130,246,0.3)' if is_me else 'transparent'}",
        }, children=[
            html.Span(f"{i+1}", style={"width":"20px","textAlign":"right","color":MUTED,
                                        "fontSize":"0.75rem","fontWeight":"600","flexShrink":"0"}),
            html.Span(flag, style={"fontSize":"1.05rem","flexShrink":"0","lineHeight":"1"}),
            html.Span(name, style={"flex":"1","fontSize":"0.87rem",
                                    "fontWeight":"700" if is_me else "400","color":TEXT}),
            html.Span(f"€{p:.1f}", style={"fontWeight":"700","color":TEXT,"fontSize":"0.87rem",
                                           "fontVariantNumeric":"tabular-nums","flexShrink":"0"}),
            html.Span(bt, style={"fontSize":"0.7rem","fontWeight":"700","color":bc,"background":bb,
                                  "border":f"1px solid {bbr}","borderRadius":"4px","padding":"2px 8px",
                                  "flexShrink":"0","minWidth":"54px","textAlign":"center"}),
        ]))
    return rows


# ══════════════════════════════════════════════════════════════════════════
# HOME PAGE HELPERS
# ══════════════════════════════════════════════════════════════════════════

def _generate_insights(country_now_df, cur_hour):
    """Derive up to 4 plain-English insight bullets from live data."""
    if country_now_df.empty:
        return []

    eu_avg   = float(country_now_df["price"].mean())
    cheapest = country_now_df.iloc[0]
    priciest = country_now_df.iloc[-1]
    c_pct    = (float(cheapest["price"]) - eu_avg) / eu_avg * 100
    p_pct    = (float(priciest["price"]) - eu_avg) / eu_avg * 100

    insights = []

    # ── Solar / wind surplus: near-zero prices ──────────────────────────
    near_zero = country_now_df[country_now_df["price"] < 5]
    if not near_zero.empty:
        nz_count  = len(near_zero)
        nz_names  = ", ".join(COUNTRY_NAME.get(c, c) for c in near_zero["country"].head(3))
        if nz_count == 1:
            nz_c = near_zero.iloc[0]["country"]
            nz_p = float(near_zero.iloc[0]["price"])
            insights.append({"color": GOLD, "text": (
                f"Solar generation is flooding the grid in {COUNTRY_NAME.get(nz_c, nz_c)} — "
                f"prices are near zero (€{nz_p:.1f}/MWh) right now. "
                f"If you're on a dynamic tariff, this is a rare window to use power almost for free."
            )})
        else:
            insights.append({"color": GOLD, "text": (
                f"Solar surplus is pushing prices to near-zero across {nz_count} countries "
                f"({nz_names}) right now. "
                f"If you're on a dynamic tariff, this is a rare window to use power almost for free."
            )})

    # ── Cheapest and most expensive ────────────────────────────────────
    insights.append({"color": CHEAP, "text": (
        f"{COUNTRY_NAME.get(cheapest['country'],'')} is the cheapest in Europe right now "
        f"at €{cheapest['price']:.0f}/MWh — {abs(c_pct):.0f}% below the EU average"
    )})
    insights.append({"color": PRICEY, "text": (
        f"{COUNTRY_NAME.get(priciest['country'],'')} is the most expensive "
        f"at €{priciest['price']:.0f}/MWh — {p_pct:.0f}% above the EU average"
    )})

    # ── Most unusual vs 30-day baseline ────────────────────────────────
    try:
        bl = q("""
            SELECT bz.country,
                   AVG(p.price_eur_mwh)     AS today_avg,
                   AVG(p.baseline_mean_30d) AS baseline
            FROM public_marts.mart_price_baselines p
            JOIN dim.bidding_zones bz ON p.zone_code = bz.zone_code
            WHERE p.delivery_date = (SELECT MAX(delivery_date) FROM public_marts.mart_current_prices)
              AND p.baseline_mean_30d IS NOT NULL AND p.baseline_mean_30d > 0
            GROUP BY bz.country
        """)
        if not bl.empty:
            bl["pct"] = (bl["today_avg"] - bl["baseline"]) / bl["baseline"] * 100
            row       = bl.loc[bl["pct"].abs().idxmax()]
            pct       = float(row["pct"])
            c         = row["country"]
            if abs(pct) > 10:
                mood = "expensive" if pct > 0 else "cheap"
                col  = PRICEY if pct > 0 else CHEAP
                insights.append({"color": col, "text": (
                    f"{COUNTRY_NAME.get(c,'')} is having an unusually {mood} day — "
                    f"prices are {abs(pct):.0f}% {'above' if pct > 0 else 'below'} its 30-day average"
                )})
            eu_today = float(bl["today_avg"].mean())
            eu_base  = float(bl["baseline"].mean())
            if eu_base > 0:
                eu_pct = (eu_today - eu_base) / eu_base * 100
                if abs(eu_pct) > 8:
                    mood2 = "cheap" if eu_pct < 0 else "expensive"
                    col2  = CHEAP if eu_pct < 0 else PRICEY
                    insights.append({"color": col2, "text": (
                        f"Across Europe, today's average is {abs(eu_pct):.0f}% "
                        f"{'below' if eu_pct < 0 else 'above'} the seasonal norm — "
                        f"a relatively {mood2} day continent-wide"
                    )})
    except Exception:
        pass

    # ── Practical tip: cheapest hour for Germany ────────────────────────
    try:
        de = q("""
            SELECT delivery_hour, AVG(price_eur_mwh) AS price
            FROM public_marts.mart_current_prices
            WHERE country = 'DE'
            GROUP BY delivery_hour ORDER BY price LIMIT 1
        """)
        if not de.empty:
            bh  = int(de["delivery_hour"].iloc[0])
            bp  = float(de["price"].iloc[0])
            tod = "late night" if (bh < 6 or bh >= 22) else ("morning" if bh < 12 else "afternoon")
            insights.append({"color": ACCENT, "text": (
                f"Germany's cheapest hour today is {bh:02d}:00 UTC ({tod}) "
                f"at €{bp:.0f}/MWh — ideal for EV charging or running heavy appliances"
            )})
    except Exception:
        pass

    return insights[:4]


def _build_home_heroes(country_now_df, eu_delta, cur_hour):
    if country_now_df.empty:
        return html.Div()
    eu_avg   = float(country_now_df["price"].mean())
    cheapest = country_now_df.iloc[0]
    priciest = country_now_df.iloc[-1]
    c_pct    = (float(cheapest["price"]) - eu_avg) / eu_avg * 100
    p_pct    = (float(priciest["price"]) - eu_avg) / eu_avg * 100

    def _delta_badge(pct):
        if pct is None:
            return html.Span()
        col = CHEAP if pct < 0 else PRICEY
        bg  = "rgba(34,211,238,0.1)" if pct < 0 else "rgba(248,113,113,0.1)"
        return html.Span(
            f"{'▼' if pct < 0 else '▲'} {abs(pct):.0f}% vs 30-day avg",
            style={"fontSize":"0.68rem","fontWeight":"600","color":col,"background":bg,
                   "borderRadius":"4px","padding":"2px 8px","whiteSpace":"nowrap"},
        )

    tile = {"background":SURFACE2,"border":f"1px solid {BORDER}","borderRadius":"14px",
            "padding":"22px 24px","flex":"1","minWidth":"200px"}

    return html.Div(style={"display":"flex","gap":"16px","marginBottom":"20px","flexWrap":"wrap"}, children=[

        # EU Average — widest, hero number
        html.Div(style={**tile,"flex":"1.4","borderTop":f"3px solid {ACCENT}"}, children=[
            html.Div("EU AVERAGE  ·  RIGHT NOW",
                     style={"fontSize":"0.6rem","fontWeight":"700","letterSpacing":"0.1em","color":MUTED,"marginBottom":"8px"}),
            html.Div(style={"display":"flex","alignItems":"baseline","gap":"8px","flexWrap":"wrap","marginBottom":"6px"}, children=[
                html.Span(f"€{eu_avg:.1f}", style={"fontSize":"2.6rem","fontWeight":"800","color":TEXT,"letterSpacing":"-0.02em"}),
                html.Span("/ MWh", style={"fontSize":"0.9rem","color":MUTED}),
            ]),
            html.Div(style={"display":"flex","alignItems":"center","gap":"10px","flexWrap":"wrap"}, children=[
                _delta_badge(eu_delta),
                html.Span(f"{cur_hour:02d}:00 UTC", style={"fontSize":"0.72rem","color":MUTED}),
            ]),
        ]),

        # Cheapest country
        html.Div(style={**tile,"borderTop":f"3px solid {CHEAP}"}, children=[
            html.Div("CHEAPEST RIGHT NOW",
                     style={"fontSize":"0.6rem","fontWeight":"700","letterSpacing":"0.1em","color":CHEAP,"marginBottom":"8px"}),
            html.Div(style={"display":"flex","alignItems":"center","gap":"8px","marginBottom":"6px"}, children=[
                html.Span(COUNTRY_FLAG.get(cheapest["country"],""), style={"fontSize":"1.6rem","lineHeight":"1"}),
                html.Span(COUNTRY_NAME.get(cheapest["country"], cheapest["country"]),
                          style={"fontSize":"1.05rem","fontWeight":"700","color":TEXT}),
            ]),
            html.Div(style={"display":"flex","alignItems":"baseline","gap":"6px","marginBottom":"4px"}, children=[
                html.Span(f"€{cheapest['price']:.1f}", style={"fontSize":"1.7rem","fontWeight":"700","color":CHEAP}),
                html.Span("/ MWh", style={"fontSize":"0.8rem","color":MUTED}),
            ]),
            html.Div(f"{abs(c_pct):.0f}% below EU average", style={"fontSize":"0.72rem","color":MUTED}),
        ]),

        # Most expensive country
        html.Div(style={**tile,"borderTop":f"3px solid {PRICEY}"}, children=[
            html.Div("MOST EXPENSIVE",
                     style={"fontSize":"0.6rem","fontWeight":"700","letterSpacing":"0.1em","color":PRICEY,"marginBottom":"8px"}),
            html.Div(style={"display":"flex","alignItems":"center","gap":"8px","marginBottom":"6px"}, children=[
                html.Span(COUNTRY_FLAG.get(priciest["country"],""), style={"fontSize":"1.6rem","lineHeight":"1"}),
                html.Span(COUNTRY_NAME.get(priciest["country"], priciest["country"]),
                          style={"fontSize":"1.05rem","fontWeight":"700","color":TEXT}),
            ]),
            html.Div(style={"display":"flex","alignItems":"baseline","gap":"6px","marginBottom":"4px"}, children=[
                html.Span(f"€{priciest['price']:.1f}", style={"fontSize":"1.7rem","fontWeight":"700","color":PRICEY}),
                html.Span("/ MWh", style={"fontSize":"0.8rem","color":MUTED}),
            ]),
            html.Div(f"{p_pct:.0f}% above EU average", style={"fontSize":"0.72rem","color":MUTED}),
        ]),
    ])


def _build_insight_cards(insights):
    if not insights:
        return html.Div("Insights load once enough data is available.",
                        style={"color":MUTED,"fontSize":"0.85rem","padding":"8px 0"})
    items = []
    for i, ins in enumerate(insights):
        items.append(html.Div(style={
            "display":"flex","alignItems":"flex-start","gap":"12px","padding":"14px 0",
            "borderBottom":f"1px solid {BORDER}" if i < len(insights)-1 else "none",
        }, children=[
            _dot(ins["color"], size=7, mt=7),
            html.Span(ins["text"], style={"fontSize":"0.875rem","color":TEXT,"lineHeight":"1.6"}),
        ]))
    return html.Div(items)


def _build_split_leaderboard(df):
    if df.empty:
        return html.Div()
    cheapest5 = df.head(5)
    priciest5 = df.tail(5).iloc[::-1]

    def _side(rows_df, accent):
        items = []
        for _, row in rows_df.iterrows():
            c, p = row["country"], float(row["price"])
            flag = COUNTRY_FLAG.get(c, "")
            name = COUNTRY_NAME.get(c, c)
            items.append(html.Div(style={
                "display":"flex","alignItems":"center","gap":"8px",
                "padding":"8px 0","borderBottom":f"1px solid {BORDER}",
            }, children=[
                html.Span(flag, style={"fontSize":"1.05rem","lineHeight":"1","flexShrink":"0"}),
                html.Span(name, style={"flex":"1","fontSize":"0.84rem","color":TEXT}),
                html.Span(f"€{p:.0f}", style={"fontWeight":"700","color":accent,
                                               "fontSize":"0.88rem","fontVariantNumeric":"tabular-nums"}),
            ]))
        return items

    return html.Div(style={"display":"flex"}, children=[
        html.Div(style={"flex":"1","paddingRight":"18px"}, children=[
            html.Div(style={"display":"flex","alignItems":"center","gap":"6px","marginBottom":"10px"}, children=[
                html.Div(style={"width":"3px","height":"13px","background":CHEAP,"borderRadius":"2px"}),
                html.Span("CHEAPEST", style={"fontSize":"0.6rem","fontWeight":"700","letterSpacing":"0.1em","color":CHEAP}),
            ]),
            *_side(cheapest5, CHEAP),
        ]),
        html.Div(style={"width":"1px","background":BORDER,"flexShrink":"0","margin":"0 4px"}),
        html.Div(style={"flex":"1","paddingLeft":"18px"}, children=[
            html.Div(style={"display":"flex","alignItems":"center","gap":"6px","marginBottom":"10px"}, children=[
                html.Div(style={"width":"3px","height":"13px","background":PRICEY,"borderRadius":"2px"}),
                html.Span("MOST EXPENSIVE", style={"fontSize":"0.6rem","fontWeight":"700","letterSpacing":"0.1em","color":PRICEY}),
            ]),
            *_side(priciest5, PRICEY),
        ]),
    ])


def _build_home_quickpick(df):
    if df.empty:
        return []
    mx   = df["price_eur_mwh"].max()
    top3 = df.nsmallest(3, "price_eur_mwh").reset_index(drop=True)
    rows = []
    for i, row in top3.iterrows():
        h, p  = int(row["delivery_hour"]), float(row["price_eur_mwh"])
        pct   = (mx - p) / mx * 100 if mx > 0 else 0
        rows.append(html.Div(style={
            "display":"flex","alignItems":"center","gap":"12px","padding":"10px 14px",
            "borderRadius":"8px","marginBottom":"4px",
            "background":SURFACE if i == 0 else "transparent",
            "border":f"1px solid {BORDER}" if i == 0 else "1px solid transparent",
        }, children=[
            html.Span(f"#{i+1}", style={"fontSize":"0.68rem","fontWeight":"700",
                                         "color":CHEAP,"width":"20px","flexShrink":"0"}),
            html.Div([
                html.Div(f"{h:02d}:00 – {(h+1)%24:02d}:00 UTC",
                         style={"fontWeight":"700","fontSize":"0.88rem","color":TEXT}),
                html.Div(_hour_period(h), style={"fontSize":"0.72rem","color":MUTED}),
            ], style={"flex":"1"}),
            html.Div([
                html.Div(f"€{p:.1f} / MWh",
                         style={"fontWeight":"700","fontSize":"0.88rem","color":CHEAP,"textAlign":"right"}),
                html.Div(f"{pct:.0f}% below peak",
                         style={"fontSize":"0.7rem","color":MUTED,"textAlign":"right"}),
            ]),
        ]))
    return rows


def _nav_card(page_id, title, desc):
    return html.Button(
        id=f"home-nav-{page_id}", n_clicks=0, className="home-nav-card",
        children=[
            html.Div(title, style={"fontWeight":"600","fontSize":"0.85rem","color":TEXT,"marginBottom":"5px"}),
            html.Div(desc,  style={"fontSize":"0.75rem","color":MUTED,"lineHeight":"1.45"}),
        ],
    )


# ══════════════════════════════════════════════════════════════════════════
# PAGE LAYOUTS
# ══════════════════════════════════════════════════════════════════════════

def page_home():
    return html.Div([
        html.Div(style={"marginBottom":"24px"}, children=[
            html.H1("EU Electricity Pulse", style={
                "margin":"0 0 7px","fontSize":"1.75rem","fontWeight":"800","letterSpacing":"-0.02em",
            }),
            html.P(
                "Day-ahead spot prices across 27 European countries, refreshed every morning. "
                "See where power is cheapest right now, whether today is expensive or cheap, "
                "and find the best time to use energy in your country.",
                style={"margin":"0","color":MUTED,"fontSize":"0.88rem","maxWidth":"640px","lineHeight":"1.65"},
            ),
        ]),

        html.Div(id="home-heroes"),

        html.Div(style={"display":"flex","gap":"16px","marginBottom":"18px","flexWrap":"wrap"}, children=[
            html.Div(style={"flex":"1.5","minWidth":"300px"}, children=[
                card([
                    html.Div(style={"marginBottom":"14px"}, children=[
                        html.Div("TODAY'S INSIGHTS", style={"fontSize":"0.6rem","fontWeight":"700",
                                                             "letterSpacing":"0.1em","color":MUTED,"marginBottom":"3px"}),
                        html.Div("What the data is telling us right now",
                                 style={"fontWeight":"700","fontSize":"0.92rem","color":TEXT}),
                    ]),
                    html.Div(id="home-insights"),
                ], style={"marginBottom":"0","height":"100%","boxSizing":"border-box"}),
            ]),
            html.Div(style={"flex":"1","minWidth":"240px"}, children=[
                card([
                    html.Div(style={"marginBottom":"14px"}, children=[
                        html.Div(id="home-lb-time", style={"fontSize":"0.6rem","fontWeight":"700",
                                                            "letterSpacing":"0.1em","color":MUTED,"marginBottom":"3px"}),
                        html.Div("Cheapest vs Most Expensive",
                                 style={"fontWeight":"700","fontSize":"0.92rem","color":TEXT}),
                    ]),
                    html.Div(id="home-leaderboard"),
                ], style={"marginBottom":"0","height":"100%","boxSizing":"border-box"}),
            ]),
        ]),

        html.Div(style={"display":"flex","gap":"16px","flexWrap":"wrap"}, children=[
            html.Div(style={"flex":"2","minWidth":"260px"}, children=[
                card([
                    html.Div(style={"marginBottom":"14px"}, children=[
                        html.Div("YOUR CHEAPEST HOURS TODAY", style={"fontSize":"0.6rem","fontWeight":"700",
                                                                      "letterSpacing":"0.1em","color":MUTED,"marginBottom":"3px"}),
                        html.Div("Best times to run appliances or charge an EV",
                                 style={"fontWeight":"700","fontSize":"0.92rem","color":TEXT}),
                    ]),
                    html.Div(style={"marginBottom":"14px"}, children=[
                        ctrl_label("Your country"),
                        dcc.Dropdown(id="home-country", options=country_opts, value="DE",
                                     clearable=False, style={"width":"220px","fontSize":"0.85rem","color":"#000"}),
                    ]),
                    html.Div(id="home-quickpick"),
                ], style={"marginBottom":"0"}),
            ]),
            html.Div(style={"flex":"3","minWidth":"300px"}, children=[
                card([
                    html.Div(style={"marginBottom":"14px"}, children=[
                        html.Div("EXPLORE DEEPER", style={"fontSize":"0.6rem","fontWeight":"700",
                                                           "letterSpacing":"0.1em","color":MUTED,"marginBottom":"3px"}),
                        html.Div("Specialist views for every use case",
                                 style={"fontWeight":"700","fontSize":"0.92rem","color":TEXT}),
                    ]),
                    html.Div(style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"10px"}, children=[
                        _nav_card("consumer",  "Smart Hours",
                                  "Find the cheapest hours in your country today and see how you rank in Europe"),
                        _nav_card("map",       "Price Map",
                                  "Animated bubble map across 41 ENTSO-E zones — watch prices shift hour by hour"),
                        _nav_card("timeline",  "Timeline",
                                  "Compare price curves for up to 8 zones on a single chart"),
                        _nav_card("spreads",   "Spreads",
                                  "Zone-to-zone arbitrage heatmap — where power is cheapest to import"),
                    ]),
                ], style={"marginBottom":"0"}),
            ]),
        ]),
    ])


def page_map():
    return html.Div([
        html.Div([
            html.H2("Day-Ahead Price Map", style={"margin":"0 0 4px","fontSize":"1.3rem","fontWeight":"700"}),
            html.P("Hourly electricity prices across 41 ENTSO-E bidding zones. "
                   "Bubble size and colour show how expensive each zone is. "
                   "Hit Play to watch prices shift as demand rises and falls through the day.",
                   style={"margin":"0 0 20px","color":MUTED,"fontSize":"0.85rem"}),
        ]),
        html.Div(style={"display":"flex","gap":"14px","marginBottom":"20px"}, children=[
            kpi("kpi-min","Min Price"), kpi("kpi-max","Max Price"),
            kpi("kpi-avg","EU Average"), kpi("kpi-spread","Zone Spread"),
        ]),
        card([
            html.Div(style={"display":"flex","justifyContent":"space-between","alignItems":"flex-end",
                            "marginBottom":"16px","flexWrap":"wrap","gap":"12px"}, children=[
                html.Div([
                    html.Span("Showing all 41 bidding zones · ", style={"color":MUTED,"fontSize":"0.8rem"}),
                    html.Span(id="map-date-label", style={"color":ACCENT,"fontSize":"0.8rem","fontWeight":"600"}),
                ]),
                html.Div([ctrl_label("Date"),
                          dropdown("map-date", options=[{"label":d,"value":d} for d in dates], value=latest_date)]),
            ]),
            graph("price-map", 620),
        ]),
        html.Div([
            html.Div(style={"fontSize":"0.7rem","fontWeight":"600","letterSpacing":"0.06em",
                            "textTransform":"uppercase","color":MUTED,"marginBottom":"10px"},
                     children="All zones · cheapest to most expensive"),
            html.Div(id="zone-ticker", style={"display":"flex","flexWrap":"wrap","gap":"8px"}),
        ]),
    ])


def page_timeline():
    return html.Div([
        html.H2("Hourly Price Timeline", style={"margin":"0 0 4px","fontSize":"1.3rem","fontWeight":"700"}),
        html.P("Select zones to compare how their price curves move through the day. "
               "Renewable zones like Norway (NO1–NO5) and Sweden (SE1–SE2) often look very different "
               "from thermal-heavy zones like Italy or Poland.",
               style={"margin":"0 0 20px","color":MUTED,"fontSize":"0.85rem"}),
        card([
            html.Div(style={"display":"flex","gap":"14px","marginBottom":"20px","flexWrap":"wrap"}, children=[
                html.Div([ctrl_label("Date"),
                          dropdown("tl-date", options=[{"label":d,"value":d} for d in dates],
                                   value=latest_date, width="160px")]),
                html.Div([ctrl_label("Zones (max 8)"),
                          dropdown("tl-zones", options=zone_opts,
                                   value=["DE-LU","FR","ES","NO1"],
                                   multi=True, width="480px", placeholder="Pick zones…")]),
            ]),
            graph("tl-chart", 480),
        ]),
    ])


def page_spreads():
    return html.Div([
        html.H2("Zone Spread Heatmap", style={"margin":"0 0 4px","fontSize":"1.3rem","fontWeight":"700"}),
        html.P("Price of the row zone minus the column zone (EUR/MWh). "
               "A red cell means the row zone is more expensive — the arbitrage signal a power trader "
               "watches across interconnectors. Use the slider to step through the day.",
               style={"margin":"0 0 20px","color":MUTED,"fontSize":"0.85rem"}),
        card([
            html.Div(style={"display":"flex","gap":"24px","alignItems":"flex-end","marginBottom":"20px","flexWrap":"wrap"}, children=[
                html.Div(style={"flex":"1","minWidth":"260px"}, children=[
                    ctrl_label("Delivery Hour"),
                    dcc.Slider(id="spread-hour", min=0, max=23, step=1, value=12,
                               marks={h: {"label":str(h),"style":{"color":MUTED,"fontSize":"0.7rem"}}
                                      for h in range(0,24,3)},
                               tooltip={"placement":"bottom"}),
                ]),
                html.Div(id="spread-badge", style={
                    "background":"rgba(59,130,246,0.12)","color":ACCENT,
                    "border":"1px solid rgba(59,130,246,0.3)","borderRadius":"6px",
                    "padding":"4px 12px","fontSize":"0.85rem","fontWeight":"600","whiteSpace":"nowrap",
                }),
                html.Div("Blue = row cheaper · Red = row pricier",
                         style={"fontSize":"0.75rem","color":MUTED}),
            ]),
            graph("spread-heatmap", 650),
        ]),
    ])


def page_anomalies():
    return html.Div([
        html.H2("Price Anomaly Explorer", style={"margin":"0 0 4px","fontSize":"1.3rem","fontWeight":"700"}),
        html.P("Hours where a zone's price is more than 2 standard deviations from its 30-day same-hour average. "
               "Spikes often signal a supply crunch or interconnector outage; dips appear when wind or solar "
               "floods the grid. This page populates after 30 days of data.",
               style={"margin":"0 0 20px","color":MUTED,"fontSize":"0.85rem"}),
        html.Div(style={"display":"flex","gap":"14px","marginBottom":"20px"}, children=[
            kpi("anom-total","Total Anomalies"), kpi("anom-spikes","Price Spikes (+2σ)"),
            kpi("anom-dips","Price Dips (−2σ)"), kpi("anom-worst","Worst Z-score"),
        ]),
        card([
            html.Div(style={"marginBottom":"16px"}, children=[
                ctrl_label("Filter by Zone"),
                dcc.Dropdown(id="anom-zone", options=[], value=None,
                             clearable=True, placeholder="All zones",
                             style={"width":"200px","fontSize":"0.83rem","color":"#000"}),
            ]),
            graph("anom-chart", 460),
        ]),
    ])


def page_consumer():
    return html.Div([
        html.H2("Smart Hours", style={"margin":"0 0 4px","fontSize":"1.3rem","fontWeight":"700"}),
        html.P("Pick your country to see when electricity is cheapest today, get a plain-English verdict "
               "on whether it's a good or bad day price-wise, and see how your country stacks up "
               "against the rest of Europe.",
               style={"margin":"0 0 20px","color":MUTED,"fontSize":"0.85rem"}),
        card([
            html.Div(style={"display":"flex","alignItems":"center","gap":"24px","flexWrap":"wrap"}, children=[
                html.Div([ctrl_label("Your country"),
                          dcc.Dropdown(id="consumer-country", options=country_opts, value="DE",
                                       clearable=False, style={"width":"230px","fontSize":"0.88rem","color":"#000"})]),
                html.Div("Day-ahead spot prices · hours in UTC · updated daily at 13:00 CEST",
                         style={"fontSize":"0.75rem","color":MUTED,"paddingTop":"16px"}),
            ]),
        ], style={"marginBottom":"14px","padding":"16px 22px"}),
        html.Div(id="consumer-verdict", style={"marginBottom":"16px"}),
        card([
            html.Div(style={"display":"flex","justifyContent":"space-between","alignItems":"baseline","marginBottom":"4px"}, children=[
                html.Div(id="consumer-chart-title", style={"fontWeight":"600","fontSize":"0.9rem","color":TEXT}),
                html.Div("EUR / MWh", style={"fontSize":"0.75rem","color":MUTED}),
            ]),
            html.Div("Bars show deviation from today's average — cyan = below, red = above · star marks 3 cheapest hours",
                     style={"fontSize":"0.72rem","color":MUTED,"marginBottom":"14px"}),
            graph("consumer-bar-chart", 300),
        ]),
        html.Div(id="consumer-windows", style={"marginBottom":"4px"}),
        card([
            html.Div(style={"marginBottom":"12px"}, children=[
                html.Div("Europe right now", style={"fontWeight":"700","fontSize":"0.95rem","color":TEXT,"marginBottom":"2px"}),
                html.Div(id="consumer-lb-subtitle", style={"fontSize":"0.75rem","color":MUTED}),
            ]),
            html.Div(id="consumer-leaderboard", style={"maxHeight":"420px","overflowY":"auto","paddingRight":"2px"}),
        ]),
    ])


# ══════════════════════════════════════════════════════════════════════════
# APP LAYOUT
# ══════════════════════════════════════════════════════════════════════════

app = dash.Dash(__name__, suppress_callback_exceptions=True,
                meta_tags=[{"name":"viewport","content":"width=device-width,initial-scale=1"}])
app.title = "EU Electricity Price Pulse"
server = app.server

NAV = [
    ("home",     "Home"),
    ("consumer", "Smart Hours"),
    ("map",      "Price Map"),
    ("timeline", "Timeline"),
    ("spreads",  "Spreads"),
]
_HOME_NAV = ["consumer","map","timeline","spreads"]

def nav_btn(pid, lbl):
    return html.Button(lbl, id=f"nav-{pid}", n_clicks=0, style=NAV_INACTIVE)

app.layout = html.Div(
    style={"background":BG,"minHeight":"100vh","fontFamily":"Inter,sans-serif","color":TEXT},
    children=[
        dcc.Store(id="active-page", data="home"),

        # ── Navbar ──────────────────────────────────────────────────────
        html.Nav(style={
            "background":SURFACE,"borderBottom":f"1px solid {BORDER}",
            "padding":"0 32px","height":"58px","display":"flex","alignItems":"center",
            "position":"relative",
        }, children=[
            # Left: logo + brand name
            html.Div(style={"display":"flex","alignItems":"center","gap":"10px","flexShrink":"0"}, children=[
                html.Img(
                    src="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjgiIGhlaWdodD0iMzIiIHZpZXdCb3g9IjAgMCAzNiA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMTggMkwzMyAxMC41VjI4LjVMMTggMzhMMyAyOC41VjEwLjVaIiBmaWxsPSJyZ2JhKDU5LDEzMCwyNDYsMC4xMCkiIHN0cm9rZT0iIzNiODJmNiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz48cGF0aCBkPSJNMTkgMTFMMTQgMjFMMTkgMjFMMTUgMzBMMjQgMTlMMTkgMTlaIiBmaWxsPSIjZmFjYzE1Ii8+PC9zdmc+Cg==",
                    style={"width":"24px","height":"28px","flexShrink":"0"},
                ),
                html.Span("EU Electricity Pulse",
                          style={"fontWeight":"700","fontSize":"0.92rem","letterSpacing":"0.01em","color":TEXT}),
                html.Span("LIVE", style={
                    "fontSize":"0.58rem","fontWeight":"700","background":"rgba(34,211,238,0.12)",
                    "color":CHEAP,"border":"1px solid rgba(34,211,238,0.28)","borderRadius":"4px",
                    "padding":"1px 7px","letterSpacing":"0.12em","marginLeft":"4px",
                }),
            ]),
            # Center: nav links (absolutely centered in nav)
            html.Div(
                style={"position":"absolute","left":"50%","transform":"translateX(-50%)",
                       "display":"flex","alignItems":"stretch","height":"100%"},
                children=[nav_btn(pid, lbl) for pid, lbl in NAV],
            ),
        ]),

        # ── Page container ───────────────────────────────────────────────
        html.Div(style={"maxWidth":"1360px","margin":"0 auto","padding":"28px 24px"}, children=[
            html.Div(id="page-home",      children=page_home(),      style={"display":"block"}),
            html.Div(id="page-map",       children=page_map(),       style={"display":"none"}),
            html.Div(id="page-timeline",  children=page_timeline(),  style={"display":"none"}),
            html.Div(id="page-spreads",   children=page_spreads(),   style={"display":"none"}),
            html.Div(id="page-anomalies", children=page_anomalies(), style={"display":"none"}),
            html.Div(id="page-consumer",  children=page_consumer(),  style={"display":"none"}),
        ]),
    ],
)

# ══════════════════════════════════════════════════════════════════════════
# ROUTING  (clientside — zero server round-trip, instant nav switch)
# ══════════════════════════════════════════════════════════════════════════

_NAV_ACTIVE_JS   = {"padding":"0 20px","height":"58px","border":"none","outline":"none",
                    "cursor":"pointer","background":"none","fontSize":"0.8rem",
                    "letterSpacing":"0.04em","fontFamily":"Inter,sans-serif",
                    "display":"flex","alignItems":"center","transition":"color 0.15s",
                    "color":"#e8edf5","fontWeight":"600","boxShadow":"inset 0 -2px 0 #3b82f6"}
_NAV_INACTIVE_JS = {"padding":"0 20px","height":"58px","border":"none","outline":"none",
                    "cursor":"pointer","background":"none","fontSize":"0.8rem",
                    "letterSpacing":"0.04em","fontFamily":"Inter,sans-serif",
                    "display":"flex","alignItems":"center","transition":"color 0.15s",
                    "color":"#6b7a99","fontWeight":"400","boxShadow":"none"}

import json as _json
_NAV_PIDS_JS = _json.dumps([pid for pid, _ in NAV])

app.clientside_callback(
    f"""
    function() {{
        var ctx = window.dash_clientside.callback_context;
        var page = 'home';
        if (ctx && ctx.triggered && ctx.triggered.length > 0) {{
            var btn = ctx.triggered[0].prop_id.split('.')[0];
            if (btn.startsWith('home-nav-')) {{
                page = btn.replace('home-nav-', '');
            }} else if (btn.startsWith('nav-')) {{
                page = btn.replace('nav-', '');
            }}
        }}
        var navPids = {_NAV_PIDS_JS};
        var pageStyles = navPids.map(function(p) {{
            return p === page
                ? {{display: 'block', animation: 'pageIn 0.15s ease-out'}}
                : {{display: 'none'}};
        }});
        var base = {{
            padding:'0 20px', height:'58px', border:'none', outline:'none',
            cursor:'pointer', background:'none', fontSize:'0.8rem',
            letterSpacing:'0.04em', fontFamily:'Inter,sans-serif',
            display:'flex', alignItems:'center', transition:'color 0.15s'
        }};
        var navStyles = navPids.map(function(p) {{
            return p === page
                ? Object.assign({{}}, base, {{color:'#e8edf5', fontWeight:'600',
                    boxShadow:'inset 0 -2px 0 #3b82f6'}})
                : Object.assign({{}}, base, {{color:'#6b7a99', fontWeight:'400',
                    boxShadow:'none'}});
        }});
        return [page].concat(pageStyles).concat(navStyles);
    }}
    """,
    [Output("active-page", "data")] +
    [Output(f"page-{pid}", "style") for pid, _ in NAV] +
    [Output(f"nav-{pid}",  "style") for pid, _ in NAV],
    [Input(f"nav-{pid}", "n_clicks") for pid, _ in NAV] +
    [Input(f"home-nav-{pid}", "n_clicks") for pid in _HOME_NAV],
)

# ══════════════════════════════════════════════════════════════════════════
# HOME CALLBACK
# ══════════════════════════════════════════════════════════════════════════

@callback(
    Output("home-heroes",      "children"),
    Output("home-insights",    "children"),
    Output("home-lb-time",     "children"),
    Output("home-leaderboard", "children"),
    Output("home-quickpick",   "children"),
    Input("home-country",      "value"),
)
def update_home(country):
    from datetime import datetime, timezone
    cur_hour = datetime.now(timezone.utc).hour

    country_now = q("""
        SELECT country, AVG(price_eur_mwh) AS price
        FROM public_marts.mart_current_prices
        WHERE delivery_hour = :h
        GROUP BY country ORDER BY price
    """, h=cur_hour)

    eu_delta = None
    try:
        bl_df = q("""
            SELECT AVG(baseline_mean_30d) AS baseline
            FROM public_marts.mart_price_baselines
            WHERE delivery_date = (SELECT MAX(delivery_date) FROM public_marts.mart_current_prices)
              AND baseline_mean_30d IS NOT NULL
        """)
        if not bl_df.empty and not pd.isna(bl_df["baseline"].iloc[0]):
            bl_val   = float(bl_df["baseline"].iloc[0])
            eu_avg   = float(country_now["price"].mean()) if not country_now.empty else 0
            eu_delta = (eu_avg - bl_val) / bl_val * 100 if bl_val > 0 else None
    except Exception:
        pass

    heroes        = _build_home_heroes(country_now, eu_delta, cur_hour)
    insights      = _generate_insights(country_now, cur_hour)
    insight_cards = _build_insight_cards(insights)
    lb_time       = f"COUNTRIES RANKED  ·  {cur_hour:02d}:00 UTC"
    leaderboard   = _build_split_leaderboard(country_now)

    quickpick = []
    if country:
        hourly = q("""
            SELECT delivery_hour, AVG(price_eur_mwh) AS price_eur_mwh
            FROM public_marts.mart_current_prices
            WHERE country = :c
            GROUP BY delivery_hour ORDER BY delivery_hour
        """, c=country)
        quickpick = _build_home_quickpick(hourly)

    return heroes, insight_cards, lb_time, leaderboard, quickpick

# ══════════════════════════════════════════════════════════════════════════
# PRICE MAP
# ══════════════════════════════════════════════════════════════════════════

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
        return empty,"—","—","—","—",[],""
    df = q("SELECT * FROM public_marts.mart_current_prices WHERE delivery_date=:d ORDER BY delivery_hour", d=date)
    if df.empty:
        return empty,"—","—","—","—",[],date
    mn,mx,avg = df["price_eur_mwh"].min(),df["price_eur_mwh"].max(),df["price_eur_mwh"].mean()
    fig = px.scatter_geo(
        df,lat="latitude",lon="longitude",
        color="price_eur_mwh",size="price_eur_mwh",size_max=34,
        hover_name="zone_name",
        hover_data={"price_eur_mwh":":.1f","zone_code":True,"country":True,"latitude":False,"longitude":False},
        animation_frame="delivery_hour",
        color_continuous_scale=[[0,CHEAP],[0.5,ACCENT],[1,PRICEY]],
        range_color=[df["price_eur_mwh"].quantile(0.05),df["price_eur_mwh"].quantile(0.95)],
        labels={"price_eur_mwh":"EUR/MWh","delivery_hour":"Hour"},
    )
    fig.update_geos(
        lataxis_range=[34,62],lonaxis_range=[-15,42],projection_type="mercator",
        showland=True,landcolor="#161f2e",showocean=True,oceancolor="#0d1420",
        showcoastlines=True,coastlinecolor="#2a3a56",showcountries=True,countrycolor="#2a3a56",
        showframe=False,bgcolor=SURFACE,domain=dict(x=[0,1],y=[0,1]),
    )
    fig.update_layout(
        paper_bgcolor=SURFACE,plot_bgcolor=SURFACE,
        font=dict(family="Inter,sans-serif",color=TEXT),
        margin=dict(l=0,r=80,t=0,b=40),
        coloraxis_colorbar=dict(
            title=dict(text="EUR/MWh",font=dict(size=11,color=MUTED)),
            tickfont=dict(size=10,color=MUTED),len=0.7,thickness=12,
            x=1.0,xanchor="left",bgcolor="rgba(0,0,0,0)",bordercolor=BORDER,
        ),
        hoverlabel=dict(bgcolor=SURFACE2,bordercolor=BORDER,font=dict(family="Inter",size=12,color=TEXT)),
        updatemenus=[dict(
            type="buttons",showactive=False,y=-0.06,x=0.5,xanchor="center",
            bgcolor=SURFACE2,bordercolor=BORDER,font=dict(color=TEXT,size=12),
            buttons=[
                dict(label="Play",  method="animate",
                     args=[None,{"frame":{"duration":700,"redraw":True},"fromcurrent":True}]),
                dict(label="Pause", method="animate",
                     args=[[None],{"frame":{"duration":0},"mode":"immediate"}]),
            ],
        )],
    )
    latest = df["delivery_hour"].max()
    snap   = df[df["delivery_hour"]==latest].sort_values("price_eur_mwh")
    chips  = []
    for _, row in snap.iterrows():
        p   = row["price_eur_mwh"]
        col = CHEAP if p < avg*0.8 else (PRICEY if p > avg*1.2 else ACCENT)
        chips.append(html.Div(style={
            "display":"flex","alignItems":"center","gap":"6px",
            "background":SURFACE,"border":f"1px solid {BORDER}",
            "borderRadius":"20px","padding":"4px 10px 4px 8px","fontSize":"0.78rem",
        }, children=[
            html.Div(style={"width":"8px","height":"8px","borderRadius":"50%","background":col,"flexShrink":"0"}),
            html.Span(row["zone_code"],style={"color":MUTED,"fontSize":"0.72rem"}),
            html.Span(f" {p:.0f}",style={"color":TEXT,"fontWeight":"600"}),
        ]))
    return fig,f"{mn:.1f} EUR/MWh",f"{mx:.1f} EUR/MWh",f"{avg:.1f} EUR/MWh",f"{mx-mn:.1f} EUR/MWh",chips,date

# ══════════════════════════════════════════════════════════════════════════
# TIMELINE
# ══════════════════════════════════════════════════════════════════════════

@callback(Output("tl-chart","figure"),Input("tl-date","value"),Input("tl-zones","value"))
def update_timeline(date,zones):
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
    for i,zone in enumerate(zones):
        zdf = df[df["zone_code"]==zone]
        if zdf.empty:
            continue
        col = CAT[i % len(CAT)]
        lbl = f"{zone} – {zdf['zone_name'].iloc[0]}"
        fig.add_trace(go.Scatter(
            x=zdf["delivery_hour"],y=zdf["price_eur_mwh"],
            mode="lines+markers",name=lbl,
            line=dict(width=2.5,color=col),
            marker=dict(size=7,color=col,line=dict(width=1.5,color=SURFACE)),
            hovertemplate=f"<b>{lbl}</b><br>%{{x:02d}}:00  →  %{{y:.1f}} EUR/MWh<extra></extra>",
        ))
    return fig

# ══════════════════════════════════════════════════════════════════════════
# SPREADS
# ══════════════════════════════════════════════════════════════════════════

@callback(Output("spread-heatmap","figure"),Output("spread-badge","children"),
          Input("spread-hour","value"))
def update_spreads(hour):
    fig = go.Figure().update_layout(**base_layout())
    if hour is None:
        return fig,"—"
    df = q("SELECT zone_a,zone_b,spread_eur_mwh FROM public_marts.mart_zone_spreads "
           "WHERE delivery_hour=:h ORDER BY zone_a,zone_b",h=hour)
    if df.empty:
        return fig,f"{hour:02d}:00"
    pivot  = df.pivot(index="zone_a",columns="zone_b",values="spread_eur_mwh")
    zones  = sorted(set(df["zone_a"])|set(df["zone_b"]))
    pivot  = pivot.reindex(index=zones,columns=zones)
    maxabs = float(np.nanmax(np.abs(pivot.values)))
    fig.add_trace(go.Heatmap(
        z=pivot.values,x=pivot.columns.tolist(),y=pivot.index.tolist(),
        colorscale=[[0,ACCENT],[0.5,SURFACE2],[1,PRICEY]],
        zmid=0,zmin=-maxabs,zmax=maxabs,
        colorbar=dict(title=dict(text="EUR/MWh",font=dict(size=11,color=MUTED)),
                      tickfont=dict(size=9,color=MUTED),thickness=12,
                      bgcolor="rgba(0,0,0,0)",bordercolor=BORDER),
        hoverongaps=False,
        hovertemplate="<b>%{y} → %{x}</b><br>Spread: %{z:.1f} EUR/MWh<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor=SURFACE,plot_bgcolor=SURFACE,
        font=dict(family="Inter,sans-serif",color=TEXT),
        margin=dict(l=82,r=16,t=16,b=82),
        xaxis=dict(tickfont=dict(size=9,color=MUTED),gridcolor=BORDER,side="bottom"),
        yaxis=dict(tickfont=dict(size=9,color=MUTED),gridcolor=BORDER,autorange="reversed"),
        hoverlabel=dict(bgcolor=SURFACE2,bordercolor=BORDER,font=dict(family="Inter",size=12,color=TEXT)),
    )
    return fig,f"{hour:02d}:00"

# ══════════════════════════════════════════════════════════════════════════
# ANOMALIES
# ══════════════════════════════════════════════════════════════════════════

@callback(
    Output("anom-zone","options"),Output("anom-chart","figure"),
    Output("anom-total","children"),Output("anom-spikes","children"),
    Output("anom-dips","children"),Output("anom-worst","children"),
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
    zdf      = q("SELECT DISTINCT zone_code FROM public_marts.mart_price_anomalies ORDER BY zone_code")
    zone_ops = [{"label":z,"value":z} for z in zdf["zone_code"]] if not zdf.empty else []
    sql,params = "SELECT * FROM public_marts.mart_price_anomalies",{}
    if zone:
        sql += " WHERE zone_code=:z"
        params["z"] = zone
    sql += " ORDER BY delivery_date,delivery_hour"
    df  = q(sql,**params)
    fig = go.Figure().update_layout(**layout)
    if df.empty:
        fig.update_layout(annotations=[dict(
            text="No anomalies yet — this page fills in after 30 days of daily data",
            xref="paper",yref="paper",x=0.5,y=0.5,
            showarrow=False,font=dict(size=14,color=MUTED),
        )])
        return zone_ops,fig,"0","0","0","—"
    spikes = df[df["anomaly_type"]=="spike"]
    dips   = df[df["anomaly_type"]=="dip"]
    worst  = df["z_score"].abs().max()
    for subset,col,name in [(spikes,SPIKE_C,"Spike +2σ"),(dips,DIP_C,"Dip −2σ")]:
        if subset.empty:
            continue
        tsx = subset["delivery_date"].astype(str)+"T"+subset["delivery_hour"].astype(str).str.zfill(2)+":00"
        fig.add_trace(go.Scatter(
            x=tsx,y=subset["price_eur_mwh"],mode="markers",name=name,
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
            x=xs,y=df["baseline_mean_30d"],mode="lines",name="30d avg",
            line=dict(width=1.5,color=MUTED,dash="dot"),
            hovertemplate="Baseline: %{y:.1f} EUR/MWh<extra></extra>",
        ))
    return zone_ops,fig,str(len(df)),str(len(spikes)),str(len(dips)),f"{worst:.1f}σ"

# ══════════════════════════════════════════════════════════════════════════
# SMART HOURS
# ══════════════════════════════════════════════════════════════════════════

@callback(
    Output("consumer-verdict",     "children"),
    Output("consumer-chart-title", "children"),
    Output("consumer-bar-chart",   "figure"),
    Output("consumer-windows",     "children"),
    Output("consumer-lb-subtitle", "children"),
    Output("consumer-leaderboard", "children"),
    Input("consumer-country",      "value"),
)
def update_consumer(country):
    from datetime import datetime, timezone
    empty_fig = go.Figure().update_layout(**base_layout())
    if not country:
        return html.Div(),"",empty_fig,html.Div(),"",[]
    flag,cname = COUNTRY_FLAG.get(country,""),COUNTRY_NAME.get(country,country)
    hourly = q("""
        SELECT delivery_hour, AVG(price_eur_mwh) AS price_eur_mwh
        FROM public_marts.mart_current_prices
        WHERE country=:c GROUP BY delivery_hour ORDER BY delivery_hour
    """,c=country)
    verdict_df = q("""
        SELECT AVG(p.price_eur_mwh) AS today_avg, AVG(p.baseline_mean_30d) AS baseline_30d
        FROM public_marts.mart_price_baselines p
        JOIN dim.bidding_zones bz ON p.zone_code=bz.zone_code
        WHERE bz.country=:c
          AND p.delivery_date=(SELECT MAX(delivery_date) FROM public_marts.mart_current_prices)
    """,c=country)
    cur_hour = datetime.now(timezone.utc).hour
    lb_df    = q("""
        SELECT country, AVG(price_eur_mwh) AS price_eur_mwh
        FROM public_marts.mart_current_prices
        WHERE delivery_hour=:h GROUP BY country ORDER BY price_eur_mwh
    """,h=cur_hour)
    latest_df = q("SELECT MAX(delivery_date) AS d FROM public_marts.mart_current_prices")
    date_str  = str(latest_df["d"].iloc[0]) if not latest_df.empty else ""
    return (
        _build_verdict(verdict_df,flag,cname),
        f"{COUNTRY_FLAG.get(country,'')} {cname} · {date_str}",
        _build_bar_chart(hourly),
        _build_windows(hourly),
        f"Average price at {cur_hour:02d}:00 UTC · your country is highlighted",
        _build_leaderboard(lb_df,country),
    )


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8050
    app.run(host="0.0.0.0", port=port, debug=False)
