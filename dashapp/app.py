import dash
from dash import html, dcc
import dash_deck
import pydeck as pdk
import pandas as pd
import json
from airflow.providers.postgres.hooks.postgres import PostgresHook

# Database connection using Airflow hook
def get_connection():
    hook = PostgresHook(postgres_conn_id='new_conn')
    return hook.get_conn()

# Load all LSOAs
print("Loading all LSOAs from database...")
conn = get_connection()
cursor = conn.cursor()
cursor.execute("""
    SELECT lsoa_code, lsoa_name, geom_geojson, crime_count, avg_rating, grit_score 
    FROM neighbourhood_grit_lsoa
""")
rows = cursor.fetchall()
columns = [desc[0] for desc in cursor.description]
df = pd.DataFrame(rows, columns=columns)
cursor.close()
conn.close()
print(f"Loaded {len(df)} LSOAs")

# Prepare GeoJSON features
features = []
for _, row in df.iterrows():
    feature = {
        'type': 'Feature',
        'geometry': json.loads(row['geom_geojson']),
        'properties': {
            'grit_score': float(row['grit_score']),
            'lsoa_name': row['lsoa_name'],
            'avg_rating': float(row['avg_rating']),
            'crime_count': int(row['crime_count'])
        }
    }
    features.append(feature)

geojson_data = {'type': 'FeatureCollection', 'features': features}
print(f"Created GeoJSON with {len(features)} features")

# Create PyDeck layer
layer = pdk.Layer(
    "GeoJsonLayer",
    data=geojson_data,
    filled=True,
    get_fill_color=[
        "properties.grit_score < 1 ? 0 : properties.grit_score < 2 ? 255 : properties.grit_score < 3 ? 255 : 255",
        "properties.grit_score < 1 ? 128 : properties.grit_score < 2 ? 255 : properties.grit_score < 3 ? 165 : 0",
        "properties.grit_score < 1 ? 0 : properties.grit_score < 2 ? 0 : properties.grit_score < 3 ? 0 : 0",
        180
    ],
    get_line_color=[0, 0, 0, 100],
    line_width_min_pixels=0.5,
    pickable=True,
)

# Initial view state centered on UK
view_state = pdk.ViewState(
    latitude=54,
    longitude=-2,
    zoom=6,
    pitch=0
)

# Create deck
deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    tooltip={"text": "LSOA: {lsoa_name}\nCrimes: {crime_count}\nAvg Rating: {avg_rating}\nGrit Score: {grit_score}"}
)

# Convert to JSON for dash-deck
deck_json = deck.to_json()

# Create Dash app
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("Safe & Clean Neighborhood Scout - All LSOAs (35k+)"),
    html.P(f"Displaying {len(df)} LSOAs. Green = safe/clean, Red = rough."),
    dash_deck.DeckGL(
        id='deck-gl',
        data=deck_json,
        style={'width': '100%', 'height': '80vh'},
        tooltip=True,
        mapboxKey=None,  # Uses default map style without Mapbox token
    )
])

if __name__ == '__main__':
    print("Starting Dash app on http://localhost:8501")
    app.run(debug=True, host='0.0.0.0', port=8501)
