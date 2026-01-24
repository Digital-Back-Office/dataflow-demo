import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from airflow.providers.postgres.hooks.postgres import PostgresHook
import json

st.title("Safe & Clean Neighborhood Scout - Prototype")

# Initialize session state
if 'map_zoom' not in st.session_state:
    st.session_state.map_zoom = 6
if 'map_center' not in st.session_state:
    st.session_state.map_center = [54, -2]  # UK center [lat, lng]
if 'map_bounds' not in st.session_state:
    st.session_state.map_bounds = {'_southWest': {'lat': 49, 'lng': -8}, '_northEast': {'lat': 61, 'lng': 2}}

# Helper to ensure center is always a list
def get_center_as_list(center):
    if isinstance(center, dict):
        return [center.get('lat', 54), center.get('lng', -2)]
    elif isinstance(center, (list, tuple)):
        return list(center)
    return [54, -2]

# Function to determine grid table based on zoom
def get_grid_table_for_zoom(zoom):
    if zoom <= 7:
        return 'grid_grit_level1', 'Level 1 (Coarse)'
    elif zoom <= 9:
        return 'grid_grit_level2', 'Level 2'
    elif zoom <= 11:
        return 'grid_grit_level3', 'Level 3'
    elif zoom <= 13:
        return 'grid_grit_level4', 'Level 4'
    else:
        return 'grid_grit_level5', 'Level 5 (Fine)'

# Load data filtered by table and bbox
@st.cache_data
def load_grid_data(table, bbox):
    hook = PostgresHook(postgres_conn_id='new_conn')
    conn = hook.get_conn()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT grid_code, geom_geojson, crime_count, avg_rating, hygiene_count, grit_score 
        FROM {table} 
        WHERE ST_Intersects(geom, ST_MakeEnvelope(%s, %s, %s, %s, 4326))
    """, bbox)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    df = pd.DataFrame(rows, columns=columns)
    cursor.close()
    conn.close()
    return df

# Get current bounds for query
bounds = st.session_state.map_bounds
minx = bounds['_southWest']['lng']
miny = bounds['_southWest']['lat']
maxx = bounds['_northEast']['lng']
maxy = bounds['_northEast']['lat']
bbox = (minx, miny, maxx, maxy)

# Determine table based on current zoom
current_zoom = st.session_state.map_zoom
table, level_label = get_grid_table_for_zoom(current_zoom)

# Load data for current view
df = load_grid_data(table, bbox)

# Controls above the map
col1, col2 = st.columns([1, 3])
with col1:
    if st.button("🔄 Refresh Map", type="primary"):
        pass  # Will capture state after map renders
with col2:
    st.caption("🟢 Safe (< 1) | 🟡 Moderate (1-2) | 🟠 Caution (2-3) | 🔴 Rough (> 3)")

st.write(f"**{level_label}** | {len(df)} grid cells | Zoom: {current_zoom}")

# Create base map at current position
center_list = get_center_as_list(st.session_state.map_center)
m = folium.Map(
    location=center_list, 
    zoom_start=current_zoom, 
    tiles='cartodbpositron'
)

# Create FeatureGroup for choropleth
fg = folium.FeatureGroup(name="Grit Score Choropleth")

# Add grid cells to FeatureGroup
for _, row in df.iterrows():
    grit = float(row['grit_score'])
    color = 'green' if grit < 1 else 'yellow' if grit < 2 else 'orange' if grit < 3 else 'red'
    
    geojson_geom = json.loads(row['geom_geojson'])
    
    fg.add_child(
        folium.GeoJson(
            geojson_geom,
            style_function=lambda x, c=color: {
                'fillColor': c, 
                'color': 'black', 
                'weight': 0.5, 
                'fillOpacity': 0.6
            },
            tooltip=f"Grid: {row['grid_code']}<br>Crimes: {row['crime_count']}<br>Avg Rating: {row['avg_rating']:.2f}<br>Grit Score: {grit:.2f}"
        )
    )

# Display map - capture returned state
map_output = st_folium(
    m,
    feature_group_to_add=fg,
    width=800,
    height=600,
    key="main_map",
    returned_objects=["center", "zoom", "bounds"]
)

# Update session state when Refresh button was clicked
if map_output:
    if map_output.get('center'):
        st.session_state.map_center = get_center_as_list(map_output['center'])
    if map_output.get('zoom'):
        st.session_state.map_zoom = map_output['zoom']
    if map_output.get('bounds'):
        st.session_state.map_bounds = map_output['bounds']

st.caption("Pan/zoom the map to automatically load data for the visible area.")