"""
Dynamic GRIT Safety Map - Dash Implementation
Pure Python callbacks with Dash Leaflet for displaying color-coded safety ratings
"""

import dash
from dash import html, dcc, callback, Output, Input, State, no_update
import dash_leaflet as dl
import dash_leaflet.express as dlx
from dash_extensions.javascript import assign
import pandas as pd
import json
import os
import hashlib
from functools import lru_cache
from typing import Optional, Tuple
from datetime import datetime, timedelta
import uuid
from airflow.providers.postgres.hooks.postgres import PostgresHook

# Map configuration
DEFAULT_CENTER = [51.5074, -0.1278]  # London, UK
DEFAULT_ZOOM = 10
MAX_FEATURES = 10000

# Add 10% buffer to ensure full coverage
INITIAL_BBOX_OFFSET_LAT = 0.9  # degrees latitude (covers ~1080px + buffer)
INITIAL_BBOX_OFFSET_LNG = 1.5  # degrees longitude (covers ~1920px + buffer)

# Color configuration
COLORS = {
    'green': '#22c55e',   # grit < 1.0 (safest)
    'yellow': '#eab308',  # grit 1.0-2.0
    'orange': '#f97316',  # grit 2.0-3.0
    'red': '#ef4444'      # grit >= 3.0 (risk)
}

# =============================================================================
# CACHING SYSTEM (similar to Streamlit's @st.cache_data)
# =============================================================================
class QueryCache:
    """Simple in-memory cache for database queries with TTL support"""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        self.cache = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.access_times = {}
    
    def _make_key(self, table: str, bbox: Tuple[float, float, float, float]) -> str:
        """Create a cache key from query parameters"""
        # Round bbox to reduce cache misses for similar queries
        rounded_bbox = tuple(round(x, 3) for x in bbox)
        key_str = f"{table}:{rounded_bbox}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, table: str, bbox: Tuple[float, float, float, float]):
        """Get cached result if exists and not expired"""
        key = self._make_key(table, bbox)
        if key in self.cache:
            timestamp, data = self.cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.ttl_seconds):
                self.access_times[key] = datetime.now()
                return data
            else:
                # Expired, remove it
                del self.cache[key]
                if key in self.access_times:
                    del self.access_times[key]
        return None
    
    def set(self, table: str, bbox: Tuple[float, float, float, float], data):
        """Store result in cache"""
        key = self._make_key(table, bbox)
        
        # Evict oldest entries if cache is full
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.access_times, key=self.access_times.get)
            del self.cache[oldest_key]
            del self.access_times[oldest_key]
        
        self.cache[key] = (datetime.now(), data)
        self.access_times[key] = datetime.now()
    
    def clear(self):
        """Clear all cached data"""
        self.cache.clear()
        self.access_times.clear()
    
    def stats(self):
        """Get cache statistics"""
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'ttl_seconds': self.ttl_seconds
        }


# =============================================================================
# INCREMENTAL LOADING SYSTEM - Feature-level caching for delta updates
# =============================================================================
class FeatureStore:
    """
    Stores rendered features by their ID to enable incremental loading.
    Tracks which features are currently rendered and their bounding boxes.
    """
    
    def __init__(self):
        self.features = {}  # {area_code: feature_dict}
        self.last_bbox = None  # (min_lng, min_lat, max_lng, max_lat)
        self.last_zoom = None
        self.last_table = None
    
    def get_rendered_ids(self) -> set:
        """Get set of all currently rendered feature IDs"""
        return set(self.features.keys())
    
    def add_features(self, features_list: list):
        """Add new features to the store"""
        for feature in features_list:
            area_code = feature.get('properties', {}).get('area_code')
            if area_code:
                self.features[area_code] = feature
    
    def get_all_features(self) -> list:
        """Get all stored features as a list"""
        return list(self.features.values())
    
    def clear(self):
        """Clear all stored features"""
        self.features.clear()
        self.last_bbox = None
        self.last_zoom = None
        self.last_table = None
    
    def update_viewport(self, bbox: tuple, zoom: int, table: str):
        """Update the last known viewport"""
        self.last_bbox = bbox
        self.last_zoom = zoom
        self.last_table = table
    
    def needs_full_refresh(self, new_zoom: int, new_table: str) -> bool:
        """Check if we need a full refresh (zoom/table changed)"""
        if self.last_table is None:
            return True
        if new_table != self.last_table:
            return True
        if new_zoom != self.last_zoom and abs(new_zoom - self.last_zoom) > 0:
            # Zoom changed significantly, might need different resolution
            return True
        return False
    
    def prune_outside_viewport(self, bbox: tuple, buffer: float = 0.5):
        """Remove features that are far outside the current viewport"""
        min_lng, min_lat, max_lng, max_lat = bbox
        # Expand bbox by buffer for pruning (keep nearby features)
        prune_bbox = (
            min_lng - buffer,
            min_lat - buffer,
            max_lng + buffer,
            max_lat + buffer
        )
        
        to_remove = []
        for area_code, feature in self.features.items():
            # Check if feature centroid is within pruning bbox
            geom = feature.get('geometry', {})
            if geom.get('type') == 'Polygon':
                coords = geom.get('coordinates', [[]])[0]
                if coords:
                    # Approximate centroid from first coordinate
                    lng, lat = coords[0][0], coords[0][1]
                    if not (prune_bbox[0] <= lng <= prune_bbox[2] and 
                            prune_bbox[1] <= lat <= prune_bbox[3]):
                        to_remove.append(area_code)
        
        for area_code in to_remove:
            del self.features[area_code]
        
        return len(to_remove)


def compute_delta_regions(old_bbox: tuple, new_bbox: tuple) -> list:
    """
    Compute the rectangular regions that are in new_bbox but not in old_bbox.
    Returns a list of (min_lng, min_lat, max_lng, max_lat) tuples.
    
    For a pan operation, this typically creates 1-3 rectangular strips.
    """
    if old_bbox is None:
        return [new_bbox]
    
    old_min_lng, old_min_lat, old_max_lng, old_max_lat = old_bbox
    new_min_lng, new_min_lat, new_max_lng, new_max_lat = new_bbox
    
    # Check if there's any overlap
    if (new_max_lng <= old_min_lng or new_min_lng >= old_max_lng or
        new_max_lat <= old_min_lat or new_min_lat >= old_max_lat):
        # No overlap - need to fetch entire new region
        return [new_bbox]
    
    delta_regions = []
    
    # Left strip (new area to the left of old bbox)
    if new_min_lng < old_min_lng:
        delta_regions.append((
            new_min_lng, 
            max(new_min_lat, old_min_lat),  # Overlap vertically
            old_min_lng, 
            min(new_max_lat, old_max_lat)
        ))
    
    # Right strip (new area to the right of old bbox)
    if new_max_lng > old_max_lng:
        delta_regions.append((
            old_max_lng, 
            max(new_min_lat, old_min_lat),
            new_max_lng, 
            min(new_max_lat, old_max_lat)
        ))
    
    # Top strip (new area above old bbox, full width of new bbox)
    if new_max_lat > old_max_lat:
        delta_regions.append((
            new_min_lng, 
            old_max_lat, 
            new_max_lng, 
            new_max_lat
        ))
    
    # Bottom strip (new area below old bbox, full width of new bbox)
    if new_min_lat < old_min_lat:
        delta_regions.append((
            new_min_lng, 
            new_min_lat, 
            new_max_lng, 
            old_min_lat
        ))
    
    # Filter out invalid regions (where min >= max)
    valid_regions = [
        r for r in delta_regions 
        if r[0] < r[2] and r[1] < r[3]
    ]
    
    return valid_regions if valid_regions else []


# Initialize stores
feature_store = FeatureStore()

# Initialize cache (5 minute TTL, max 100 entries)
query_cache = QueryCache(max_size=100, ttl_seconds=300)

# Token to track latest in-flight query so stale results can be dropped
LATEST_QUERY_TOKEN = None

# Connection pool
db_pool = None
pg_hook = None

def init_db_pool():
    """Initialize database connection pool"""
    global db_pool
    global pg_hook
    try:
        # Use Airflow PostgresHook to manage connections
        pg_hook = PostgresHook(postgres_conn_id='test_db_1')
        print("PostgresHook initialized successfully")
    except Exception as e:
        print(f"Warning: Could not initialize PostgresHook: {e}")
        pg_hook = None

def get_db_connection():
    """Get database connection from pool"""
    # If running without Airflow, keep backward compatibility by returning None
    if pg_hook is None:
        return None
    try:
        return pg_hook.get_conn()
    except Exception as e:
        print(f"Warning: could not get connection from PostgresHook: {e}")
        return None

def release_db_connection(conn):
    """Release connection back to pool"""
    if conn:
        try:
            conn.close()
        except Exception:
            pass

def get_table_for_zoom(zoom: int) -> str:
    """Select appropriate table based on zoom level"""
    # New mapping: LAD (coarse) -> MSOA (mid) -> LSOA (fine)
    # - zoom <= 7 : LAD (country/region view)
    # - 8 <= zoom <= 11 : MSOA (regional view)
    # - zoom >= 12 : LSOA (neighborhood/fine view)
    if zoom <= 8:
        return 'neighbourhood_grit_lad'
    elif zoom <= 11:
        return 'neighbourhood_grit_msoa'
    else:
        return 'neighbourhood_grit_lsoa'

def get_color_for_grit(grit_score: float) -> str:
    """Get color based on grit score"""
    if grit_score is None:
        return COLORS['green']
    if grit_score < 1.0:
        return COLORS['green']
    elif grit_score < 1.5:
        return COLORS['yellow']
    elif grit_score < 2.0:
        return COLORS['orange']
    else:
        return COLORS['red']

def fetch_grid_data(min_lng: float, min_lat: float, max_lng: float, max_lat: float, zoom: int):
    """Fetch grid data from database for visible map area (with caching)"""
    conn = None
    cache_hit = False
    query_time = 0
    
    try:
        table = get_table_for_zoom(zoom)

        # mark this request as the latest
        local_token = uuid.uuid4().hex
        global LATEST_QUERY_TOKEN
        LATEST_QUERY_TOKEN = local_token

        # map table -> code/name columns
        code_map = {
            'neighbourhood_grit_lsoa': ('lsoa_code', 'lsoa_name'),
            'neighbourhood_grit_msoa': ('msoa_code', 'msoa_name'),
            'neighbourhood_grit_lad': ('lad_code', 'lad_name'),
        }
        code_col, name_col = code_map.get(table, (None, None))
        bbox = (min_lng, min_lat, max_lng, max_lat)
        
        # Check cache first
        cached_result = query_cache.get(table, bbox)
        if cached_result is not None:
            # Return cached result with cache_hit flag and 0 query time (from cache)
            geojson, tbl, count, truncated, cached_query_time = cached_result
            return geojson, tbl, count, truncated, True, cached_query_time
        
        # Query database with timing
        conn = get_db_connection()
        if conn is None:
            return None, table, 0, False, False, 0
        
        cursor = conn.cursor()
        
        # Query with spatial intersection and limit
        # choose precomputed simplified geojson for MSOA/LAD to reduce payload
        if table in ('neighbourhood_grit_msoa', 'neighbourhood_grit_lad'):
            geom_col = 'geom_geojson_simpl as geom_geojson'
        else:
            geom_col = 'geom_geojson'

        # include the area code/name if available so popups can show them
        select_cols = [geom_col, "crime_count", "avg_rating", "grit_score"]
        if code_col:
            select_cols.insert(0, f"{code_col} as area_code")
        if name_col:
            select_cols.insert(1, f"{name_col} as area_name")

        query = f"""
            SELECT {', '.join(select_cols)}
            FROM {table}
            WHERE ST_Intersects(geom, ST_MakeEnvelope(%s, %s, %s, %s, 4326))
            LIMIT %s
        """
        
        # Time the database query
        query_start = datetime.now()
        cursor.execute(query, (*bbox, MAX_FEATURES))
        rows = cursor.fetchall()
        query_time = (datetime.now() - query_start).total_seconds() * 1000  # milliseconds
        
        # If another newer request has started, drop this stale result
        if LATEST_QUERY_TOKEN != local_token:
            cursor.close()
            return 'STALE', table, 0, False, False, 0
        columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(rows, columns=columns)
        cursor.close()
        truncated = len(df) >= MAX_FEATURES
        
        if df.empty:
            result = ({"type": "FeatureCollection", "features": []}, table, 0, False, query_time)
            query_cache.set(table, bbox, result)
            return {"type": "FeatureCollection", "features": []}, table, 0, False, False, query_time
        
        # Build GeoJSON feature collection
        features = []
        for _, row in df.iterrows():
            grit_score = row['grit_score'] if pd.notna(row['grit_score']) else 0
            
            feature = {
                "type": "Feature",
                "geometry": json.loads(row['geom_geojson']),
                "properties": {
                    "area_code": row['area_code'] if 'area_code' in row else None,
                    "area_name": row['area_name'] if 'area_name' in row else None,
                    "crime_count": int(row['crime_count']) if pd.notna(row['crime_count']) else 0,
                    "avg_rating": round(float(row['avg_rating']), 2) if pd.notna(row['avg_rating']) else 0,
                    # "hygiene_count": int(row['hygiene_count']) if pd.notna(row['hygiene_count']) else 0,
                    "grit_score": round(float(grit_score), 2),
                    "color": get_color_for_grit(grit_score)
                }
            }
            features.append(feature)
        
        geojson_data = {
            "type": "FeatureCollection",
            "features": features
        }
        
        result = (geojson_data, table, len(features), truncated, query_time)
        
        # Store in cache
        query_cache.set(table, bbox, result)
        return geojson_data, table, len(features), truncated, False, query_time  # False = cache miss
        
    except Exception as e:
        print(f"Error fetching grid data: {e}")
        return None, get_table_for_zoom(zoom), 0, False, False, 0
    finally:
        if conn:
            release_db_connection(conn)


def fetch_incremental_data(new_bbox: tuple, zoom: int, existing_ids: set) -> tuple:
    """
    Fetch only new features that aren't already rendered.
    Uses delta regions to minimize database queries.
    
    Returns: (new_features_list, table, new_count, query_time, delta_regions_count)
    """
    conn = None
    query_time = 0
    
    try:
        table = get_table_for_zoom(zoom)
        
        # Check if we need full refresh (zoom/table changed)
        if feature_store.needs_full_refresh(zoom, table):
            feature_store.clear()
            # Fall back to full fetch
            geojson, tbl, count, truncated, cached, q_time = fetch_grid_data(
                new_bbox[0], new_bbox[1], new_bbox[2], new_bbox[3], zoom
            )
            if geojson and geojson != 'STALE':
                return geojson.get('features', []), tbl, count, q_time, 0, True
            return [], table, 0, 0, 0, True
        
        # Compute delta regions
        old_bbox = feature_store.last_bbox
        delta_regions = compute_delta_regions(old_bbox, new_bbox)
        
        if not delta_regions:
            # No new area to fetch - return empty (existing features are sufficient)
            return [], table, 0, 0, 0, False
        
        # map table -> code/name columns
        code_map = {
            'neighbourhood_grit_lsoa': ('lsoa_code', 'lsoa_name'),
            'neighbourhood_grit_msoa': ('msoa_code', 'msoa_name'),
            'neighbourhood_grit_lad': ('lad_code', 'lad_name'),
        }
        code_col, name_col = code_map.get(table, (None, None))
        
        conn = get_db_connection()
        if conn is None:
            return [], table, 0, 0, len(delta_regions), False
        
        cursor = conn.cursor()
        
        # Build query for delta regions using UNION
        if table in ('neighbourhood_grit_msoa', 'neighbourhood_grit_lad'):
            geom_col = 'geom_geojson_simpl as geom_geojson'
        else:
            geom_col = 'geom_geojson'
        
        select_cols = [geom_col, "crime_count", "avg_rating", "grit_score"]
        if code_col:
            select_cols.insert(0, f"{code_col} as area_code")
        if name_col:
            select_cols.insert(1, f"{name_col} as area_name")
        
        # Build WHERE clause for multiple regions using OR
        region_conditions = []
        params = []
        for region in delta_regions:
            region_conditions.append(
                "ST_Intersects(geom, ST_MakeEnvelope(%s, %s, %s, %s, 4326))"
            )
            params.extend(region)
        
        # Exclude already rendered features
        exclude_clause = ""
        if existing_ids and code_col:
            # Limit exclusion list to avoid huge queries
            limited_ids = list(existing_ids)[:5000]
            if limited_ids:
                placeholders = ','.join(['%s'] * len(limited_ids))
                exclude_clause = f" AND {code_col} NOT IN ({placeholders})"
                params.extend(limited_ids)
        
        query = f"""
            SELECT DISTINCT {', '.join(select_cols)}
            FROM {table}
            WHERE ({' OR '.join(region_conditions)}){exclude_clause}
            LIMIT %s
        """
        params.append(MAX_FEATURES)
        
        # Time the query
        query_start = datetime.now()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        query_time = (datetime.now() - query_start).total_seconds() * 1000
        
        columns = [desc[0] for desc in cursor.description]
        cursor.close()
        
        # Build features list
        new_features = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            grit_score = row_dict['grit_score'] if row_dict['grit_score'] is not None else 0
            
            feature = {
                "type": "Feature",
                "geometry": json.loads(row_dict['geom_geojson']),
                "properties": {
                    "area_code": row_dict.get('area_code'),
                    "area_name": row_dict.get('area_name'),
                    "crime_count": int(row_dict['crime_count']) if row_dict['crime_count'] else 0,
                    "avg_rating": round(float(row_dict['avg_rating']), 2) if row_dict['avg_rating'] else 0,
                    "grit_score": round(float(grit_score), 2),
                    "color": get_color_for_grit(grit_score)
                }
            }
            new_features.append(feature)
        
        return new_features, table, len(new_features), query_time, len(delta_regions), False
        
    except Exception as e:
        print(f"Error in incremental fetch: {e}")
        return [], get_table_for_zoom(zoom), 0, 0, 0, False
    finally:
        if conn:
            release_db_connection(conn)

# JavaScript function for styling features
style_handle = assign("""
function(feature) {
    return {
        fillColor: feature.properties.color,
        weight: 1,
        opacity: 0.8,
        color: '#ffffff',
        fillOpacity: 0.6
    };
}
""")

# JavaScript function for hover effects and tooltip binding
on_each_feature = assign("""
function(feature, layer) {
    // Build tooltip content
    var props = feature.properties;
    var areaName = props.area_name || props.area_code || 'Unknown';
    var gritScore = (props.grit_score !== null && props.grit_score !== undefined) ? props.grit_score.toFixed(2) : 'N/A';
    var crimeCount = (props.crime_count !== null && props.crime_count !== undefined) ? props.crime_count.toLocaleString() : 'N/A';
    var avgRating = (props.avg_rating !== null && props.avg_rating !== undefined) ? props.avg_rating.toFixed(2) : 'N/A';
    var color = props.color || '#333';
    
    var html = '<div style="min-width:160px;padding:2px;">' +
        '<b style="font-size:13px;color:#333;">' + areaName + '</b>' +
        '<hr style="margin:5px 0;border:0;border-top:1px solid #ddd;">' +
        '<table style="font-size:12px;width:100%;border-collapse:collapse;">' +
        '<tr><td style="color:#666;padding:2px 8px 2px 0;">GRIT Score</td><td style="font-weight:600;color:' + color + ';text-align:right;">' + gritScore + '</td></tr>' +
        '<tr><td style="color:#666;padding:2px 8px 2px 0;">Crime Count</td><td style="font-weight:600;text-align:right;">' + crimeCount + '</td></tr>' +
        '<tr><td style="color:#666;padding:2px 8px 2px 0;">Avg Rating</td><td style="font-weight:600;text-align:right;">' + avgRating + '</td></tr>' +
        '</table></div>';
    
    layer.bindTooltip(html, {sticky: true, direction: 'auto', opacity: 0.95});
    
    // Hover style effects
    layer.on('mouseover', function(e) {
        e.target.setStyle({weight: 2, color: '#333', fillOpacity: 0.8});
        e.target.bringToFront();
    });
    layer.on('mouseout', function(e) {
        e.target.setStyle({weight: 1, color: '#ffffff', fillOpacity: 0.6});
    });

    // Subtle shimmer for newly-rendered features
    try {
        if (feature && feature.properties && feature.properties.new_since) {
            var age = Date.now() - feature.properties.new_since;
            if (age >= 0 && age < 2000) {
                // Add CSS class to SVG path for animation
                if (layer && layer._path) {
                    layer._path.classList.add('feature-shimmer');
                    setTimeout(function() {
                        try { layer._path.classList.remove('feature-shimmer'); } catch(e) {}
                    }, 1200);
                }
            }
        }
    } catch(e) {
        // swallow errors - non-critical
    }
}
""")

# Initialize the Dash app
app = dash.Dash(
    __name__,
    title="GRIT Safety Map",
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}]
)

# Custom CSS
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            }
            
            .map-container {
                width: 100%;
                height: 100vh;
                position: relative;
            }
            
            .legend {
                position: fixed;
                bottom: 30px;
                right: 10px;
                background: white;
                padding: 15px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                z-index: 1000;
                min-width: 160px;
            }
            
            .legend h4 {
                margin-bottom: 10px;
                font-size: 14px;
                color: #333;
                border-bottom: 1px solid #eee;
                padding-bottom: 8px;
            }
            
            .legend-item {
                display: flex;
                align-items: center;
                margin: 8px 0;
                font-size: 13px;
            }
            
            .legend-color {
                width: 24px;
                height: 18px;
                margin-right: 10px;
                border-radius: 3px;
                border: 1px solid rgba(0,0,0,0.2);
            }
            
            .info-panel {
                position: fixed;
                top: 10px;
                left: 60px;
                background: white;
                padding: 12px 16px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                z-index: 1000;
                font-size: 13px;
            }
            
            .zoom-level {
                font-weight: bold;
                color: #3498db;
            }
            
            .table-name {
                color: #666;
                margin-left: 10px;
            }
            
            .feature-count {
                margin-left: 10px;
                color: #27ae60;
            }
            
            /* Minimal loading indicator - small pill in corner */
            .loading-indicator {
                position: fixed;
                bottom: 30px;
                left: 10px;
                background: rgba(52, 152, 219, 0.9);
                color: white;
                padding: 6px 12px;
                border-radius: 16px;
                z-index: 10000;
                font-size: 11px;
                font-weight: 500;
                box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                display: flex;
                align-items: center;
                gap: 6px;
                backdrop-filter: blur(4px);
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            
            .loading-spinner {
                width: 12px;
                height: 12px;
                border: 2px solid rgba(255,255,255,0.3);
                border-top: 2px solid white;
                border-radius: 50%;
                animation: spin 0.6s linear infinite;
            }
            
            /* No map overlay dimming - keep map fully visible */
            .map-overlay {
                display: none !important;
            }

            /* Shimmer effect for newly-rendered features */
            .feature-shimmer {
                animation: featureGlow 0.8s ease-out;
            }

            @keyframes featureGlow {
                0% { 
                    stroke: #fff;
                    stroke-width: 3px;
                    stroke-opacity: 1;
                    filter: drop-shadow(0 0 6px rgba(255,255,255,0.8));
                }
                100% { 
                    stroke: #fff;
                    stroke-width: 1px;
                    stroke-opacity: 0.8;
                    filter: none;
                }
            }
            
            /* Alternative: border highlight shimmer */
            .feature-highlight {
                animation: borderPulse 0.6s ease-out;
            }
            
            @keyframes borderPulse {
                0% { 
                    stroke: #3498db;
                    stroke-width: 2px;
                }
                100% { 
                    stroke: #ffffff;
                    stroke-width: 1px;
                }
            }
            
            .popup-content h3 {
                margin-bottom: 8px;
                color: #333;
                font-size: 15px;
                border-bottom: 2px solid #3498db;
                padding-bottom: 5px;
            }
            
            .popup-content .metric {
                display: flex;
                justify-content: space-between;
                margin: 4px 0;
                font-size: 13px;
            }
            
            .popup-content .metric-label {
                color: #666;
            }
            
            .popup-content .metric-value {
                font-weight: bold;
                color: #333;
            }
            
            .grit-badge {
                display: inline-block;
                padding: 2px 8px;
                border-radius: 12px;
                color: white;
                font-weight: bold;
            }
            
            .error-message {
                position: fixed;
                top: 20px;
                left: 50%;
                transform: translateX(-50%);
                background: #e74c3c;
                color: white;
                padding: 12px 24px;
                border-radius: 8px;
                z-index: 10000;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            }
            
            .cache-indicator {
                margin-left: 10px;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 11px;
                background: #9b59b6;
                color: white;
            }
            
            .cache-hit {
                background: #27ae60;
            }
            
            .cache-miss {
                background: #e67e22;
            }
            
            /* Custom tooltip styling */
            .custom-tooltip {
                background: white;
                border: none;
                border-radius: 8px;
                box-shadow: 0 3px 14px rgba(0,0,0,0.25);
                padding: 8px 12px;
            }
            
            .custom-tooltip::before {
                border-top-color: white;
            }
            
            .leaflet-tooltip-left.custom-tooltip::before {
                border-left-color: white;
            }
            
            .leaflet-tooltip-right.custom-tooltip::before {
                border-right-color: white;
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

# App layout
app.layout = html.Div([
    # Store components for state management
    dcc.Store(id='map-bounds-store', data=None),
    dcc.Store(id='pending-bounds', data=None),
    dcc.Store(id='debounced-bounds', data={
        'bounds': [
            [DEFAULT_CENTER[0] - INITIAL_BBOX_OFFSET_LAT, DEFAULT_CENTER[1] - INITIAL_BBOX_OFFSET_LNG],
            [DEFAULT_CENTER[0] + INITIAL_BBOX_OFFSET_LAT, DEFAULT_CENTER[1] + INITIAL_BBOX_OFFSET_LNG]
        ],
        'zoom': DEFAULT_ZOOM
    }),
    dcc.Store(id='debounce-timestamp', data=None),
    dcc.Interval(id='debounce-interval', interval=300, n_intervals=0, disabled=True),
    dcc.Store(id='geojson-store', data=None),
    dcc.Store(id='map-meta-store', data={'table': 'neighbourhood_grit_msoa', 'count': 0, 'truncated': False}),
    
    # Loading indicator with spinner (small, non-intrusive)
    html.Div(
        id='loading-indicator',
        className='loading-indicator',
        children=[
            html.Div(className='loading-spinner'),
            html.Span('Loading...')
        ],
        style={'display': 'none'}
    ),
    
    # Error message
    html.Div(
        id='error-message',
        className='error-message',
        style={'display': 'none'}
    ),
    
    # Info panel
    html.Div(
        id='info-panel',
        className='info-panel',
        children=[
            html.Span('Zoom: '),
            html.Span(id='zoom-display', className='zoom-level', children=str(DEFAULT_ZOOM)),
            html.Span(id='table-display', className='table-name', children='neighbourhood_grit_msoa'),
            html.Span(id='count-display', className='feature-count', children='0 features'),
            html.Span(id='cache-display', className='cache-indicator', children='', style={'display': 'none'}),
        ]
    ),
    
    # Map container
    html.Div(
        className='map-container',
        children=[
            dl.Map(
                id='map',
                center=DEFAULT_CENTER,
                zoom=DEFAULT_ZOOM,
                style={'width': '100%', 'height': '100vh'},
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
        ]
    ),
    
    # Legend
    html.Div(
        className='legend',
        children=[
            html.H4('🛡️ Safety Rating'),
            html.Div(className='legend-item', children=[
                html.Div(className='legend-color', style={'background': '#22c55e'}),
                html.Span('Safe (< 1.0)')
            ]),
            html.Div(className='legend-item', children=[
                html.Div(className='legend-color', style={'background': '#eab308'}),
                html.Span('Moderate (1.0 - 2.0)')
            ]),
            html.Div(className='legend-item', children=[
                html.Div(className='legend-color', style={'background': '#f97316'}),
                html.Span('Caution (2.0 - 3.0)')
            ]),
            html.Div(className='legend-item', children=[
                html.Div(className='legend-color', style={'background': '#ef4444'}),
                html.Span('Risk (≥ 3.0)')
            ]),
        ]
    ),
    
    # Popup for clicked feature
    html.Div(id='feature-popup', style={'display': 'none'}),
    
], style={'width': '100%', 'height': '100vh', 'overflow': 'hidden'})


# Callback to fetch data when map bounds or zoom change
@callback(
    Output('pending-bounds', 'data'),
    Output('debounce-timestamp', 'data'),
    Output('debounce-interval', 'disabled', allow_duplicate=True),
    Output('debounced-bounds', 'data', allow_duplicate=True),
    Input('map', 'bounds'),
    Input('map', 'zoom'),
    State('debounced-bounds', 'data'),
    prevent_initial_call='initial_duplicate'
)
def on_map_move(bounds, zoom, current_debounced):
    """Capture map movements and start debounce timer.
    On initial load, immediately update with actual bounds."""
    if not bounds:
        return None, None, True, no_update
    
    new_bounds = {'bounds': bounds, 'zoom': int(zoom) if zoom else DEFAULT_ZOOM}
    
    # Check if this is the first real bounds update from the map
    # (current_debounced will have our calculated approximation initially)
    if current_debounced and current_debounced.get('bounds'):
        approx_lat = current_debounced['bounds'][0][0]
        actual_lat = bounds[0][0]
        # If bounds differ by more than 0.001 degrees, this is the first real update
        if abs(approx_lat - (DEFAULT_CENTER[0] - INITIAL_BBOX_OFFSET_LAT)) < 0.001:
            # This is the first real bounds from the map - update immediately
            return None, None, True, new_bounds
    
    # Normal pan/zoom - use debouncing
    return new_bounds, datetime.now().timestamp(), False, no_update


@callback(
    Output('debounced-bounds', 'data'),
    Output('debounce-interval', 'disabled', allow_duplicate=True),
    Input('debounce-interval', 'n_intervals'),
    State('debounce-timestamp', 'data'),
    State('pending-bounds', 'data'),
    prevent_initial_call=True
)
def check_debounce(n_intervals, ts, pending):
    """When interval ticks, check if enough time has passed since last move and emit debounced bounds."""
    if not ts or not pending:
        return None, True
    if datetime.now().timestamp() - ts > 0.4:
        return pending, True
    return None, False

@callback(
    Output('grid-layer', 'data'),
    Output('map-meta-store', 'data'),
    Output('error-message', 'style'),
    Output('error-message', 'children'),
    Input('debounced-bounds', 'data'),
    running=[
        (Output('loading-indicator', 'style'), {'display': 'flex'}, {'display': 'none'}),
    ],
    prevent_initial_call=False
)
def fetch_data_on_map_change(bounds_zoom):
    """Fetch grid data incrementally - only fetch new regions that aren't already rendered"""
    if not bounds_zoom:
        return (
            {"type": "FeatureCollection", "features": []},
            {'table': get_table_for_zoom(DEFAULT_ZOOM), 'count': 0, 'truncated': False, 'cached': False,
             'query_time': 0, 'render_time': 0, 'mode': 'empty', 'delta_regions': 0, 'new_features': 0},
            {'display': 'none'},
            ''
        )

    bounds = bounds_zoom.get('bounds')
    zoom = int(bounds_zoom.get('zoom', DEFAULT_ZOOM))

    # bounds is [[south, west], [north, east]]
    min_lat = bounds[0][0]
    min_lng = bounds[0][1]
    max_lat = bounds[1][0]
    max_lng = bounds[1][1]
    new_bbox = (min_lng, min_lat, max_lng, max_lat)
    
    # Track render start time
    render_start = datetime.now()
    server_ts_ms = int(datetime.now().timestamp() * 1000)
    
    table = get_table_for_zoom(zoom)
    
    # Check if we need full refresh or can do incremental
    existing_ids = feature_store.get_rendered_ids()
    
    # Try incremental fetch
    new_features, table, new_count, query_time, delta_regions, was_full_refresh = fetch_incremental_data(
        new_bbox, zoom, existing_ids
    )
    
    if was_full_refresh:
        # Full refresh - replace all features
        feature_store.clear()
        # Optionally mark full-refresh features as new for subtle shimmer, but only if not huge
        if new_features and len(new_features) <= 2000:
            for f in new_features:
                try:
                    props = f.setdefault('properties', {})
                    props['new_since'] = server_ts_ms
                except Exception:
                    pass
        feature_store.add_features(new_features)
        feature_store.update_viewport(new_bbox, zoom, table)
        
        all_features = new_features
        mode = 'full'
    else:
        # Incremental update - merge new features with existing
        if new_features:
            # mark newly fetched features with server timestamp so client can animate them
            for f in new_features:
                try:
                    props = f.setdefault('properties', {})
                    props['new_since'] = server_ts_ms
                except Exception:
                    pass
            feature_store.add_features(new_features)
        
        # Prune features that are far outside the viewport to limit memory
        pruned = feature_store.prune_outside_viewport(new_bbox, buffer=0.3)
        
        # Update viewport tracking
        feature_store.update_viewport(new_bbox, zoom, table)
        
        # Get all current features for rendering
        all_features = feature_store.get_all_features()
        mode = 'incremental'
    
    # Build final GeoJSON
    geojson_data = {
        "type": "FeatureCollection",
        "features": all_features
    }
    
    # Calculate render time
    render_time = (datetime.now() - render_start).total_seconds() * 1000
    
    meta = {
        'table': table,
        'count': len(all_features),
        'truncated': len(all_features) >= MAX_FEATURES,
        'cached': mode == 'incremental' and new_count == 0,
        'query_time': query_time,
        'render_time': render_time,
        'mode': mode,
        'delta_regions': delta_regions,
        'new_features': new_count
    }
    
    return geojson_data, meta, {'display': 'none'}, ''


# Callback to update info panel
@callback(
    Output('zoom-display', 'children'),
    Output('table-display', 'children'),
    Output('count-display', 'children'),
    Output('cache-display', 'children'),
    Output('cache-display', 'className'),
    Output('cache-display', 'style'),
    Input('map', 'zoom'),
    Input('map-meta-store', 'data')
)
def update_info_panel(zoom, meta):
    """Update the info panel with current state"""
    zoom = int(zoom) if zoom else DEFAULT_ZOOM
    table = meta.get('table', get_table_for_zoom(zoom)) if meta else get_table_for_zoom(zoom)
    # Friendly labels
    table_labels = {
        'neighbourhood_grit_lad': 'LAD (Coarse)',
        'neighbourhood_grit_msoa': 'MSOA (Regional)',
        'neighbourhood_grit_lsoa': 'LSOA (Neighborhood)'
    }
    table = table_labels.get(table, table)
    count = meta.get('count', 0) if meta else 0
    truncated = meta.get('truncated', False) if meta else False
    cached = meta.get('cached', False) if meta else False
    query_time = meta.get('query_time', 0) if meta else 0
    render_time = meta.get('render_time', 0) if meta else 0
    
    count_text = f"{count:,} features"
    if truncated:
        count_text += " (limited)"
    
    # Get incremental loading stats
    mode = meta.get('mode', 'full') if meta else 'full'
    new_features = meta.get('new_features', 0) if meta else 0
    delta_regions = meta.get('delta_regions', 0) if meta else 0
    
    # Timing indicator - show query and render times with mode
    if count > 0:
        if mode == 'incremental':
            if new_features > 0:
                mode_text = f"⚡ +{new_features} new"
                cache_class = "cache-indicator cache-miss"
            else:
                mode_text = "📦 cached"
                cache_class = "cache-indicator cache-hit"
        else:
            mode_text = "🔄 full"
            cache_class = "cache-indicator cache-miss"
        
        timing_text = f"{mode_text} | DB: {query_time:.0f}ms | Render: {render_time:.0f}ms"
        cache_style = {'display': 'inline-block'}
    else:
        timing_text = ""
        cache_class = "cache-indicator"
        cache_style = {'display': 'none'}
    
    return str(zoom), table, count_text, timing_text, cache_class, cache_style


# Callback for feature click popup
@callback(
    Output('feature-popup', 'children'),
    Output('feature-popup', 'style'),
    Input('grid-layer', 'click_feature'),
    prevent_initial_call=True
)
def show_feature_popup(feature):
    """Show popup when a feature is clicked"""
    if feature is None:
        return '', {'display': 'none'}
    
    props = feature.get('properties', {})
    grit_score = props.get('grit_score', 0)
    color = props.get('color', '#22c55e')
    
    popup_content = html.Div(
        className='popup-content',
        style={
            'position': 'fixed',
            'top': '50%',
            'left': '50%',
            'transform': 'translate(-50%, -50%)',
            'background': 'white',
            'padding': '20px',
            'borderRadius': '8px',
            'boxShadow': '0 4px 20px rgba(0,0,0,0.3)',
            'zIndex': 10001,
            'minWidth': '250px'
        },
        children=[
            html.H3(f"📍 {props.get('area_name', props.get('area_code', 'Unknown'))}"),
            html.Div(className='metric', children=[
                html.Span('Area Code:', className='metric-label'),
                html.Span(str(props.get('area_code', '')), className='metric-value')
            ]),
            html.Div(className='metric', children=[
                html.Span('GRIT Score:', className='metric-label'),
                html.Span(
                    str(grit_score),
                    className='grit-badge',
                    style={'background': color}
                )
            ]),
            html.Div(className='metric', children=[
                html.Span('Crime Count:', className='metric-label'),
                html.Span(str(props.get('crime_count', 0)), className='metric-value')
            ]),
            html.Div(className='metric', children=[
                html.Span('Avg Rating:', className='metric-label'),
                html.Span(str(props.get('avg_rating', 0)), className='metric-value')
            ]),
            # hygiene_count not available on these aggregate tables
            html.Button(
                '✕ Close',
                id='close-popup-btn',
                style={
                    'marginTop': '15px',
                    'width': '100%',
                    'padding': '8px',
                    'border': 'none',
                    'borderRadius': '4px',
                    'background': '#e74c3c',
                    'color': 'white',
                    'cursor': 'pointer'
                }
            )
        ]
    )
    
    return popup_content, {'display': 'block'}


# Initialize database pool on startup
init_db_pool()

# Server for production deployment
server = app.server

if __name__ == '__main__':
    print("Starting GRIT Safety Map (Dash version)...")
    app.run(debug=True, host='0.0.0.0')
