"""
GRIT Safety Map — Dash app
Displays neighbourhood safety ratings derived from crime density and food hygiene data.
"""

import dash
from dash import html, dcc, callback, Output, Input, no_update
import dash_leaflet as dl
from dash_extensions.javascript import assign
import json
import hashlib
import threading
from datetime import datetime, timedelta

DEFAULT_CENTER = [51.5074, -0.1278]
DEFAULT_ZOOM = 10
MAX_FEATURES = 10000
INITIAL_BBOX_OFFSET_LAT = 0.9
INITIAL_BBOX_OFFSET_LNG = 1.5

# Single source of truth for bucket colours and labels
BUCKETS = [
    ('safest',   '#22c55e', 'Safest 40%'),
    ('safer',    '#eab308', 'Safer'),
    ('riskier',  '#f97316', 'Riskier'),
    ('riskiest', '#ef4444', 'Highest-risk 10%'),
    ('no_data',  '#9ca3af', 'No data'),
]
BUCKET_COLORS  = {b[0]: b[1] for b in BUCKETS}
BUCKET_LABELS  = {b[0]: b[2] for b in BUCKETS}


# =============================================================================
# CACHE
# =============================================================================
class QueryCache:
    """LRU cache with TTL for viewport→FeatureCollection results."""

    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        self.cache = {}
        self.access_times = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

    def _key(self, table, bbox):
        rounded = tuple(round(x, 3) for x in bbox)
        return hashlib.md5(f"{table}:{rounded}".encode()).hexdigest()

    def get(self, table, bbox):
        key = self._key(table, bbox)
        if key in self.cache:
            ts, data = self.cache[key]
            if datetime.now() - ts < timedelta(seconds=self.ttl_seconds):
                self.access_times[key] = datetime.now()
                return data
            del self.cache[key]
            self.access_times.pop(key, None)
        return None

    def set(self, table, bbox, data):
        key = self._key(table, bbox)
        if len(self.cache) >= self.max_size:
            oldest = min(self.access_times, key=self.access_times.get)
            self.cache.pop(oldest, None)
            self.access_times.pop(oldest, None)
        self.cache[key] = (datetime.now(), data)
        self.access_times[key] = datetime.now()


query_cache = QueryCache(max_size=100, ttl_seconds=300)

# Stale-request guard: only the last-started request updates the UI
_req_lock  = threading.Lock()
_latest_id = [0]


# =============================================================================
# DATABASE
# =============================================================================
def get_db_connection():
    try:
        from dataflow import Dataflow
        import psycopg2
        c = Dataflow().connection('ukns_db', mode='dict')
        return psycopg2.connect(
            host=c['host'], port=c['port'], dbname=c['schema'],
            user=c['login'], password=c['password']
        )
    except Exception:
        try:
            from airflow.providers.postgres.hooks.postgres import PostgresHook
            return PostgresHook(postgres_conn_id='ukns_db').get_conn()
        except Exception as e:
            print(f"DB connection failed: {e}")
            return None


# =============================================================================
# DATA FETCHING
# =============================================================================
TABLE_META = {
    'neighbourhood_grit_lsoa': ('lsoa_code', 'lsoa_name', 'Neighbourhood', 'geom_geojson'),
    'neighbourhood_grit_msoa': ('msoa_code', 'msoa_name', 'Area',          'geom_geojson_simpl as geom_geojson'),
    'neighbourhood_grit_lad':  ('lad_code',  'lad_name',  'District',      'geom_geojson_simpl as geom_geojson'),
}


def get_table_for_zoom(zoom: int) -> str:
    if zoom <= 8:
        return 'neighbourhood_grit_lad'
    elif zoom <= 11:
        return 'neighbourhood_grit_msoa'
    else:
        return 'neighbourhood_grit_lsoa'


def fetch_grid_data(min_lng, min_lat, max_lng, max_lat, zoom):
    """
    Returns (geojson, table, count, truncated, cached, query_time_ms).
    Stateless: every call returns exactly the features in the viewport.
    """
    table = get_table_for_zoom(zoom)
    code_col, name_col, level_label, geom_expr = TABLE_META[table]
    bbox = (min_lng, min_lat, max_lng, max_lat)

    cached = query_cache.get(table, bbox)
    if cached is not None:
        geojson, count, truncated, q_time = cached
        return geojson, table, count, truncated, True, q_time

    conn = get_db_connection()
    if conn is None:
        return None, table, 0, False, False, 0

    try:
        cur = conn.cursor()
        query = f"""
            SELECT {code_col} AS area_code,
                   {name_col} AS area_name,
                   {geom_expr},
                   crime_count, crime_per_km2, avg_rating,
                   grit_score, grit_bucket, data_quality
            FROM {table}
            WHERE ST_Intersects(geom, ST_MakeEnvelope(%s, %s, %s, %s, 4326))
            LIMIT %s
        """
        t0 = datetime.now()
        cur.execute(query, (*bbox, MAX_FEATURES))
        rows = cur.fetchall()
        q_time = (datetime.now() - t0).total_seconds() * 1000
        cols = [d[0] for d in cur.description]
        cur.close()

        features = []
        for row in rows:
            r = dict(zip(cols, row))
            features.append({
                "type": "Feature",
                "geometry": json.loads(r['geom_geojson']),
                "properties": {
                    "area_code":    r['area_code'],
                    "area_name":    r['area_name'],
                    "level":        level_label,
                    "crime_count":  int(r['crime_count']) if r['crime_count'] is not None else 0,
                    "crime_per_km2": round(float(r['crime_per_km2']), 2) if r['crime_per_km2'] is not None else None,
                    "avg_rating":   round(float(r['avg_rating']), 2) if r['avg_rating'] is not None else None,
                    "grit_score":   round(float(r['grit_score']), 4) if r['grit_score'] is not None else None,
                    "grit_bucket":  r['grit_bucket'] or 'no_data',
                    "data_quality": r['data_quality'],
                }
            })

        geojson = {"type": "FeatureCollection", "features": features}
        truncated = len(features) >= MAX_FEATURES
        query_cache.set(table, bbox, (geojson, len(features), truncated, q_time))
        return geojson, table, len(features), truncated, False, q_time

    except Exception as e:
        print(f"fetch_grid_data error: {e}")
        return None, table, 0, False, False, 0
    finally:
        conn.close()


# =============================================================================
# CLIENT-SIDE JS
# =============================================================================
_colors_js  = json.dumps(BUCKET_COLORS)
_labels_js  = json.dumps(BUCKET_LABELS)

# Native Leaflet event handler — fires BEFORE any animation or Dash prop sync.
# This is the only reliable way to show the pill the instant the user acts.
_show_pill_js = assign("""
function(e) {
    var pill = document.getElementById('loading-indicator');
    if (pill) pill.style.display = 'flex';
    var card = document.getElementById('hover-card');
    if (card) card.style.display = 'none';
}
""")

style_handle = assign(f"""
function(feature) {{
    var colors = {_colors_js};
    var bucket = (feature.properties && feature.properties.grit_bucket) || 'no_data';
    return {{
        fillColor: colors[bucket] || '#9ca3af',
        weight: 1,
        opacity: 0.8,
        color: '#ffffff',
        fillOpacity: 0.6
    }};
}}
""")

on_each_feature = assign(f"""
function(feature, layer) {{
    var colors = {_colors_js};
    var labels = {_labels_js};

    layer.on('mouseover mousemove', function(e) {{
        var p = feature.properties || {{}};
        var name  = p.area_name || p.area_code || 'Unknown';
        var level = p.level || '';
        var bucket = p.grit_bucket || 'no_data';
        var label  = labels[bucket] || 'No data';
        var color  = colors[bucket] || '#9ca3af';
        var cpkm2  = p.crime_per_km2 != null ? parseFloat(p.crime_per_km2).toFixed(1) : 'N/A';
        var crimes = p.crime_count != null ? p.crime_count.toLocaleString() : '0';
        var ratingHtml = p.avg_rating != null
            ? parseFloat(p.avg_rating).toFixed(1) + ' / 5'
            : '<span style="color:#9ca3af">No data</span>';
        var scoreHtml = p.grit_score != null
            ? 'Percentile ' + (parseFloat(p.grit_score) * 100).toFixed(0)
              + '% &mdash; <b style="color:' + color + '">' + label + '</b>'
            : '<span style="color:#9ca3af">No data</span>';

        var html = '<div style="font-family:system-ui,sans-serif;font-size:13px;min-width:210px;">'
            + '<b style="font-size:14px">' + name + '</b>'
            + (level ? '<div style="color:#888;font-size:11px;margin-bottom:6px">' + level + '</div>' : '<br>')
            + '<table style="width:100%;border-collapse:collapse">'
            + '<tr><td style="color:#666;padding:2px 12px 2px 0">Crime density</td>'
            +     '<td style="font-weight:600">' + cpkm2 + '/km\xb2 (' + crimes + ')</td></tr>'
            + '<tr><td style="color:#666;padding:2px 12px 2px 0">Food hygiene</td>'
            +     '<td style="font-weight:600">' + ratingHtml + '</td></tr>'
            + '<tr><td style="color:#666;padding:2px 12px 2px 0">GRIT</td>'
            +     '<td>' + scoreHtml + '</td></tr>'
            + '</table></div>';

        var card = document.getElementById('hover-card');
        if (card) {{ card.innerHTML = html; card.style.display = 'block'; }}

        e.target.setStyle({{weight: 2, color: '#333', fillOpacity: 0.8}});
    }});

    layer.on('mouseout', function(e) {{
        var card = document.getElementById('hover-card');
        if (card) card.style.display = 'none';
        e.target.setStyle({{weight: 1, color: '#ffffff', fillOpacity: 0.6}});
    }});
}}
""")


# =============================================================================
# APP
# =============================================================================
app = dash.Dash(
    __name__,
    title="GRIT Safety Map",
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}]
)

app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            * { margin:0; padding:0; box-sizing:border-box; }
            body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; }

            .map-container { width:100%; height:100vh; position:relative; }

            .legend {
                position:fixed; bottom:30px; right:10px;
                background:white; padding:14px; border-radius:8px;
                box-shadow:0 2px 10px rgba(0,0,0,0.2); z-index:1000; min-width:170px;
            }
            .legend h4 { margin-bottom:6px; font-size:14px; color:#333;
                         border-bottom:1px solid #eee; padding-bottom:6px; }
            .legend-note { font-size:10px; color:#888; margin-bottom:8px; }
            .legend-item { display:flex; align-items:center; margin:6px 0; font-size:13px; }
            .legend-color { width:22px; height:16px; margin-right:9px; border-radius:3px;
                            border:1px solid rgba(0,0,0,0.15); flex-shrink:0; }

            .info-panel {
                position:fixed; top:10px; left:60px;
                background:white; padding:10px 14px; border-radius:8px;
                box-shadow:0 2px 10px rgba(0,0,0,0.2); z-index:1000; font-size:13px;
            }

            .loading-indicator {
                position:fixed; bottom:30px; left:10px;
                background:rgba(52,152,219,0.9); color:white;
                padding:6px 12px; border-radius:16px; z-index:10000;
                font-size:11px; font-weight:500;
                box-shadow:0 2px 8px rgba(0,0,0,0.15);
                display:flex; align-items:center; gap:6px;
                backdrop-filter:blur(4px);
            }
            @keyframes spin { to { transform:rotate(360deg); } }
            .loading-spinner {
                width:12px; height:12px;
                border:2px solid rgba(255,255,255,0.3);
                border-top:2px solid white;
                border-radius:50%; animation:spin 0.6s linear infinite;
            }

            #hover-card {
                position:fixed; bottom:80px; left:10px;
                background:white; padding:10px 14px; border-radius:8px;
                box-shadow:0 3px 14px rgba(0,0,0,0.2); z-index:1000;
                pointer-events:none; max-width:300px;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

app.layout = html.Div([
    # Stores
    dcc.Store(id='debounced-bounds', data={
        'bounds': [
            [DEFAULT_CENTER[0] - INITIAL_BBOX_OFFSET_LAT, DEFAULT_CENTER[1] - INITIAL_BBOX_OFFSET_LNG],
            [DEFAULT_CENTER[0] + INITIAL_BBOX_OFFSET_LAT, DEFAULT_CENTER[1] + INITIAL_BBOX_OFFSET_LNG],
        ],
        'zoom': DEFAULT_ZOOM,
    }),
    dcc.Store(id='map-meta-store', data={'table': 'neighbourhood_grit_msoa', 'count': 0}),

    # Loading pill
    html.Div(
        id='loading-indicator',
        className='loading-indicator',
        children=[html.Div(className='loading-spinner'), html.Span('Loading…')],
        style={'display': 'none'}
    ),

    # Info panel
    html.Div(id='info-panel', className='info-panel'),

    # Hover card (updated by JS)
    html.Div(id='hover-card', style={'display': 'none'}),

    # Map
    html.Div(className='map-container', children=[
        dl.Map(
            id='map',
            center=DEFAULT_CENTER,
            zoom=DEFAULT_ZOOM,
            preferCanvas=True,
            style={'width': '100%', 'height': '100vh'},
            # movestart/zoomstart fire before any animation — before Leaflet even
            # updates its own bounds, so far before Dash props sync. This is the
            # only path that shows the pill with zero perceptible delay.
            eventHandlers=dict(movestart=_show_pill_js, zoomstart=_show_pill_js),
            children=[
                dl.TileLayer(
                    url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                    attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                ),
                dl.GeoJSON(
                    id='grid-layer',
                    data={"type": "FeatureCollection", "features": []},
                    options=dict(style=style_handle, onEachFeature=on_each_feature),
                    zoomToBoundsOnClick=False,
                ),
            ]
        ),
    ]),

    # Legend (derived from BUCKETS — single source of truth)
    html.Div(
        className='legend',
        children=[
            html.H4('GRIT Safety Rating'),
            html.P('Relative to areas at the same zoom level', className='legend-note'),
            *[
                html.Div(className='legend-item', children=[
                    html.Div(className='legend-color', style={'background': color}),
                    html.Span(label),
                ])
                for _, color, label in BUCKETS
            ],
        ]
    ),

], style={'width': '100%', 'height': '100vh', 'overflow': 'hidden'})


# =============================================================================
# CLIENTSIDE CALLBACKS
# =============================================================================

# Debounce map moves in the browser.
# Also does immediate DOM work (no Dash round-trip needed):
#   • shows the loading pill the moment the map moves
#   • hides the hover card so a stale card can't outlive a layer swap
# Never writes null into debounced-bounds — returns no_update while the timer
# is pending so the server callback is not retriggered with a null payload.
app.clientside_callback(
    """
    function(bounds, zoom) {
        if (!bounds) return window.dash_clientside.no_update;

        // Immediate DOM feedback — no Dash round-trip
        var pill = document.getElementById('loading-indicator');
        if (pill) pill.style.display = 'flex';
        var card = document.getElementById('hover-card');
        if (card) card.style.display = 'none';

        // Debounce: reset the timer; fire the server request only after motion stops
        if (window._boundsTimer) clearTimeout(window._boundsTimer);
        window._boundsTimer = setTimeout(function() {
            window.dash_clientside.set_props('debounced-bounds', {
                data: {bounds: bounds, zoom: zoom}
            });
        }, 350);

        return window.dash_clientside.no_update;
    }
    """,
    Output('debounced-bounds', 'data', allow_duplicate=True),
    Input('map', 'bounds'),
    Input('map', 'zoom'),
    prevent_initial_call=True,
)

# When new data arrives: hide the loading pill and close any open hover card.
# This handles the layer-swap case — Leaflet destroys old layers without firing
# mouseout, so the card must be forcibly dismissed here.
app.clientside_callback(
    """
    function(d) {
        var card = document.getElementById('hover-card');
        if (card) card.style.display = 'none';
        return {display: 'none'};
    }
    """,
    Output('loading-indicator', 'style', allow_duplicate=True),
    Input('grid-layer', 'data'),
    prevent_initial_call=True,
)


# =============================================================================
# SERVER CALLBACKS
# =============================================================================

@callback(
    Output('grid-layer', 'data'),
    Output('map-meta-store', 'data'),
    Input('debounced-bounds', 'data'),
    running=[
        (Output('loading-indicator', 'style'), {'display': 'flex'}, {'display': 'none'}),
    ],
    prevent_initial_call=False,
)
def fetch_data_on_map_change(bounds_zoom):
    """Stateless viewport fetch — returns exactly the features in the current viewport.

    Stale-request guard: if a newer request arrived while this one was running
    (e.g. the user panned again before the DB responded), discard this result
    so the UI always ends up with the most-recently-requested viewport.
    """
    empty = {"type": "FeatureCollection", "features": []}

    # Claim a slot; remember our own ID
    with _req_lock:
        _latest_id[0] += 1
        my_id = _latest_id[0]

    if not bounds_zoom:
        return empty, {'table': get_table_for_zoom(DEFAULT_ZOOM), 'count': 0}

    bounds = bounds_zoom['bounds']
    zoom   = int(bounds_zoom.get('zoom', DEFAULT_ZOOM))
    min_lat, min_lng = bounds[0]
    max_lat, max_lng = bounds[1]

    geojson, table, count, truncated, cached, _ = fetch_grid_data(
        min_lng, min_lat, max_lng, max_lat, zoom
    )

    # Drop result if a newer request has already arrived
    with _req_lock:
        if _latest_id[0] != my_id:
            return no_update, no_update

    if not geojson:
        geojson = empty

    return geojson, {'table': table, 'count': count}


@callback(
    Output('info-panel', 'children'),
    Input('map', 'zoom'),
    Input('map-meta-store', 'data'),
)
def update_info_panel(zoom, meta):
    zoom  = int(zoom) if zoom else DEFAULT_ZOOM
    meta  = meta or {}
    table = meta.get('table', get_table_for_zoom(zoom))
    count = meta.get('count', 0)

    level_labels = {
        'neighbourhood_grit_lad':  'District',
        'neighbourhood_grit_msoa': 'Area',
        'neighbourhood_grit_lsoa': 'Neighbourhood',
    }
    level = level_labels.get(table, '')

    return [
        html.B('GRIT Safety Map'),
        html.Span(f' — {level}' if level else '', style={'color': '#555'}),
        html.Br(),
        html.Span(
            'Crime density + food hygiene, ranked relative to all areas at this zoom level',
            style={'font-size': '11px', 'color': '#888'},
        ),
        html.Br(),
        html.Span(
            f'{count:,} area{"s" if count != 1 else ""} shown'
            '  ·  Source: police.uk, FHRS, ONS',
            style={'font-size': '11px', 'color': '#aaa'},
        ),
    ]


server = app.server

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', threaded=True)
