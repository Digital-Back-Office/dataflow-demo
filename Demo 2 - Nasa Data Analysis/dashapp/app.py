import dash
from dash import dcc, html, Input, Output, State, dash_table, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import time
import traceback
from sqlalchemy import text
import plotly.io as pio

pio.templates.default = "plotly_dark"

class NASASpaceDashboard:
    def __init__(self, db_session=None):
        """
        Initialize the NASA Space Dashboard with optional database session
        
        Args:
            db_session: Optional SQLAlchemy engine/session. If None, Airflow Hook is used.
        """
        self.app = dash.Dash(__name__, 
                            external_stylesheets=[dbc.themes.DARKLY],
                            suppress_callback_exceptions=True)
        self.app.title = "NASA Space Data Dashboard"
        
        self.db_session = db_session
        self.setup_database()
        
        self.setup_layout()
        self.setup_callbacks()
    
    def setup_database(self):
        """Setup database connection using Airflow Hook connection details"""
        try:
            from airflow.hooks.base import BaseHook
            from sqlalchemy import create_engine
            
            # Get connection details from Airflow
            conn = BaseHook.get_connection("demo_db")
            self.db_type = conn.conn_type.lower()
            
            # Create SQLAlchemy engine
            if self.db_type == 'sqlite':
                # For SQLite, try multiple possible paths
                possible_paths = [
                    conn.host,
                    conn.schema,
                    '/home/jovyan/dataflow-demo/demo.db',
                    '/home/jovyan/dataflow-demo/Demo 2 - Nasa Data Analysis/demo.db',
                    './demo.db',
                    'demo.db'
                ]
                
                db_path = None
                for path in possible_paths:
                    if path and path != ':memory:':
                        import os
                        if os.path.exists(path):
                            db_path = path
                            break
                
                if not db_path:
                    # Default to a known location
                    db_path = '/home/jovyan/dataflow-demo/demo.db'
                    print(f"Using default SQLite path: {db_path}")
                
                connection_string = f"sqlite:///{db_path}"
                print(f"SQLite connection string: {connection_string}")
                # Use NullPool to avoid threading issues with SQLite in multi-threaded apps
                from sqlalchemy.pool import NullPool
                self.engine = create_engine(connection_string, poolclass=NullPool)
            else:
                # For PostgreSQL
                connection_string = f"postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}"
                self.engine = create_engine(connection_string)
            self.db_session = self.engine
            
            print(f"Database connection established successfully. Type: {self.db_type}")
            
            # Create tables if they don't exist
            self._create_tables_if_not_exist()
            
            # Test connection
            test_query = "SELECT 1"
            result = self.execute_query_to_dataframe(test_query)
            
            if not result.empty:
                print("Database test query successful")
                
                try:
                    mission_statuses_query = """
                        SELECT DISTINCT status FROM space_missions
                        ORDER BY status
                    """
                    status_df = self.execute_query_to_dataframe(mission_statuses_query)
                    if not status_df.empty and 'status' in status_df.columns:
                        print("Available mission statuses in database:")
                        for status in status_df['status'].tolist():
                            print(f"  - '{status}'")
                except Exception as status_error:
                    print(f"Note: Could not fetch mission statuses: {status_error}")
            else:
                print("Database connection test returned empty result")
                
        except Exception as e:
            print(f"Database connection failed: {e}")
            print("Please check your dataflow configuration and ensure the database is running")
            self.db_session = None
            # Set default db_type if connection fails
            self.db_type = 'sqlite'  # Assume SQLite as default
    
    def _create_tables_if_not_exist(self):
        """Create database tables if they don't exist"""
        try:
            create_table_sqls = [
                """
                CREATE TABLE IF NOT EXISTS apod_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE UNIQUE NOT NULL,
                    title VARCHAR(500),
                    explanation TEXT,
                    url TEXT,
                    media_type VARCHAR(50),
                    hdurl TEXT,
                    copyright VARCHAR(200),
                    service_version VARCHAR(20),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS iss_location (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL UNIQUE,
                    latitude DECIMAL(10,6),
                    longitude DECIMAL(10,6),
                    altitude DECIMAL(10,2),
                    velocity DECIMAL(10,2),
                    is_interpolated INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS asteroids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    neo_id VARCHAR(50),
                    name VARCHAR(200),
                    approach_date DATE,
                    estimated_diameter_min DECIMAL(15,6),
                    estimated_diameter_max DECIMAL(15,6),
                    relative_velocity DECIMAL(15,2),
                    miss_distance DECIMAL(20,2),
                    is_potentially_hazardous INTEGER,
                    absolute_magnitude DECIMAL(8,2),
                    nasa_jpl_url TEXT,
                    orbiting_body VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(neo_id, approach_date)
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS space_missions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_id VARCHAR(50) UNIQUE,
                    name VARCHAR(300),
                    launch_date TIMESTAMP,
                    rocket_name VARCHAR(200),
                    mission_type VARCHAR(100),
                    launch_location VARCHAR(200),
                    status VARCHAR(50),
                    probability INTEGER,
                    launch_service_provider VARCHAR(200),
                    image_url TEXT,
                    webcast_live INTEGER,
                    mission_description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                "CREATE INDEX IF NOT EXISTS idx_apod_date ON apod_images(date);",
                "CREATE INDEX IF NOT EXISTS idx_iss_timestamp ON iss_location(timestamp);",
                "CREATE INDEX IF NOT EXISTS idx_asteroids_approach_date ON asteroids(approach_date);",
                "CREATE INDEX IF NOT EXISTS idx_asteroids_hazardous ON asteroids(is_potentially_hazardous);",
                "CREATE INDEX IF NOT EXISTS idx_missions_launch_date ON space_missions(launch_date);",
                "CREATE INDEX IF NOT EXISTS idx_missions_status ON space_missions(status);"
            ]
            
            with self.engine.begin() as conn:
                for sql in create_table_sqls:
                    if sql.strip():
                        conn.execute(sql)
            
            print("Database tables created/verified successfully")
            
        except Exception as e:
            print(f"Error creating tables: {e}")
            # Don't fail the entire setup if table creation fails
    
    def execute_query_to_dataframe(self, query, params=None) -> pd.DataFrame:
        """
        Execute a SQL query using dataflow session and return results as pandas DataFrame
        with enhanced timeout protection and error handling to prevent 502 Bad Gateway errors
        
        Args:
            query: SQL query to execute (can be string or SQLAlchemy text object)
            params (dict): Query parameters (if supported by dataflow)
            
        Returns:
            pd.DataFrame: Query results or empty DataFrame on error
        """
        import time
        import traceback
        from concurrent.futures import ThreadPoolExecutor, TimeoutError
        
        start_time = time.time()
        
        try:
            if not self.db_session:
                print("No database session available")
                return pd.DataFrame()
            
            max_retries = 2
            retry_count = 0
            
            query_timeout = 10
            
            while retry_count < max_retries:
                try:
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        if hasattr(self.db_session, 'execute'):
                            try:
                                future = executor.submit(self.db_session.execute, query, params or {})
                                
                                result = future.result(timeout=query_timeout)
                                
                                if hasattr(result, 'fetchall') and hasattr(result, 'keys'):
                                    rows = result.fetchmany(100) 
                                    columns = result.keys()
                                    df = pd.DataFrame(rows, columns=columns)
                                elif isinstance(result, list):
                                    if len(result) > 100:
                                        result = result[:100]
                                    df = pd.DataFrame(result)
                                else:
                                    df = pd.DataFrame(result)
                                
                                query_time = time.time() - start_time
                                print(f"Query executed successfully in {query_time:.2f}s, returned {len(df)} rows")
                                return df
                            
                            except TimeoutError:
                                print(f"Query timeout after {query_timeout}s - aborting to prevent 502 error")
                                return pd.DataFrame()
                        else:
                            print(f"Warning: Dataflow session lacks execute method")
                            return pd.DataFrame()
                
                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        print(f"Error executing query after {max_retries} attempts: {e}")
                        print(f"Query: {query}")
                        return pd.DataFrame()
                    else:
                        print(f"Query error (attempt {retry_count}/{max_retries}): {e}. Retrying...")
                        time.sleep(0.5)
                
        except Exception as e:
            print(f"Critical error in execute_query_to_dataframe: {e}")
            traceback.print_exc()
            return pd.DataFrame()
    
    def fetch_apod_data(self, days=30):
        """Fetch APOD data from database using dataflow session with optimizations
        to prevent 502 Bad Gateway errors
        """
        import time
        import traceback
        
        start_time = time.time()
        print(f"Starting APOD data fetch for {days} days")
        
        try:
            max_records = 15

            if self.db_type == 'sqlite':
                date_condition = f"date >= date('now', '-{days} days')"
            else:
                date_condition = f"date >= CURRENT_DATE - INTERVAL '{days} days'"

            query_sql = f"""
            SELECT 
                title, explanation, date, media_type, url
            FROM apod_images 
            WHERE {date_condition}
            ORDER BY date DESC
            LIMIT {max_records}
            """
            print(f"APOD query: {query_sql}")
            
            query = text(query_sql)
            
            fallback_data = [
                {
                    'title': 'Earth and Moon',
                    'explanation': 'A view of Earth and Moon from space',
                    'date': '2025-07-01',
                    'media_type': 'image',
                    'url': 'https://apod.nasa.gov/apod/image/2106/EarthMoon_Artemis1_1080.jpg'
                },
                {
                    'title': 'Spiral Galaxy',
                    'explanation': 'A beautiful spiral galaxy',
                    'date': '2025-07-02',
                    'media_type': 'image',
                    'url': 'https://apod.nasa.gov/apod/image/2106/M66_HubblePohl_2169.jpg'
                },
                {
                    'title': 'Solar Flare',
                    'explanation': 'A massive solar flare erupting from the sun',
                    'date': '2025-07-03',
                    'media_type': 'image',
                    'url': 'https://apod.nasa.gov/apod/image/2105/solarflare_trace_1080.jpg'
                }
            ]
            
            df = self.execute_query_to_dataframe(query)
            
            query_time = time.time() - start_time
            print(f"APOD query completed in {query_time:.2f}s, retrieved {len(df)} records")
            
            if df.empty or 'url' not in df.columns:
                print("WARNING: No APOD data returned, using fallback sample data")
                df = pd.DataFrame(fallback_data)
            else:
                if 'url' in df.columns:
                    print(f"FIRST 3 APOD URLs in database result:")
                    for i, url in enumerate(df['url'].head(3)):
                        print(f"  {i+1}. {url}")
                
                expected_columns = ['title', 'explanation', 'date', 'media_type', 'url']
                missing_columns = [col for col in expected_columns if col not in df.columns]
                
                if missing_columns:
                    print(f"Warning: Missing columns in APOD data: {missing_columns}")
                    for col in missing_columns:
                        df[col] = 'Unknown' if col != 'url' else 'https://apod.nasa.gov/apod/image/2105/solarflare_trace_1080.jpg'
            
            if 'url' in df.columns:
                df['url'] = df['url'].apply(
                    lambda x: 'https://apod.nasa.gov/apod/image/2106/EarthMoon_Artemis1_1080.jpg' 
                    if pd.isna(x) or str(x).strip() == '' 
                    else str(x).strip()
                )
                print(f"URLs after cleaning: {df['url'].head(3).tolist()}")
            
            return df
            
        except Exception as e:
            print(f"Error in fetch_apod_data: {str(e)}")
            traceback.print_exc()

            print("Creating emergency fallback APOD data with known working image URLs")
            return pd.DataFrame([
                {
                    'title': 'Emergency Fallback Image',
                    'explanation': 'This is a fallback image shown when database queries fail',
                    'date': '2025-07-07',
                    'media_type': 'image',
                    'url': 'https://apod.nasa.gov/apod/image/2106/EarthMoon_Artemis1_1080.jpg'
                },
                {
                    'title': 'Emergency Fallback Image 2',
                    'explanation': 'This is another fallback image shown when database queries fail',
                    'date': '2025-07-06',
                    'media_type': 'image',
                    'url': 'https://apod.nasa.gov/apod/image/2106/M66_HubblePohl_2169.jpg'
                }
            ])
    
    def fetch_iss_data(self, hours=24):
        """Fetch ISS location data from database using dataflow session"""
        fetch_hours = max(hours, 1)
        
        try:
            if self.db_type == 'sqlite':
                time_condition = f"timestamp >= datetime('now', '-{fetch_hours} hours')"
                backup_time_condition = "timestamp >= datetime('now', '-24 hours')"
            else:
                time_condition = f"timestamp >= NOW() - INTERVAL '{fetch_hours} hours'"
                backup_time_condition = "timestamp >= NOW() - INTERVAL '24 hours'"
            
            query = text(f"""
            SELECT * FROM iss_location 
            WHERE {time_condition}
            ORDER BY timestamp DESC
            LIMIT 1000  -- Prevent excessive data return
            """)
            df = self.execute_query_to_dataframe(query)

            print(f"ISS data fetch for {fetch_hours} hours: {len(df)} records retrieved")
            
            if df.empty and fetch_hours < 24:
                print(f"No data for {fetch_hours}h window, trying 24h window")
                backup_query = text(f"""
                SELECT * FROM iss_location 
                WHERE {backup_time_condition}
                ORDER BY timestamp DESC
                LIMIT 500
                """)
                df = self.execute_query_to_dataframe(backup_query)
                print(f"Backup ISS data fetch for 24 hours: {len(df)} records retrieved")
                
                if not df.empty and len(df) > 10:
                    if hours <= 1:
                        df = df.head(10)
                    elif hours <= 6:
                        df = df.head(30)
                    print(f"Sampled data to {len(df)} records to match {hours}h window")
            
            if df.empty:
                print("WARNING: ISS data query returned empty result after backup attempt")
                
            return df
        except Exception as e:
            print(f"Error in fetch_iss_data: {e}")
            return pd.DataFrame()
    
    def fetch_asteroid_data(self, days=30):
        """Fetch asteroid data from database using dataflow session"""
        if self.db_type == 'sqlite':
            date_condition = f"approach_date >= date('now') AND approach_date <= date('now', '+{days} days')"
        else:
            date_condition = f"approach_date >= CURRENT_DATE AND approach_date <= CURRENT_DATE + INTERVAL '{days} days'"
        
        query = text(f"""
        SELECT * FROM asteroids 
        WHERE {date_condition}
        ORDER BY approach_date ASC, miss_distance ASC
        """)
        return self.execute_query_to_dataframe(query)
    
    def fetch_missions_data(self, days=90):
        """Fetch space missions data from database using dataflow session"""
        if self.db_type == 'sqlite':
            date_condition = f"launch_date >= date('now') AND launch_date <= date('now', '+{days} days')"
        else:
            date_condition = f"launch_date >= CURRENT_DATE AND launch_date <= CURRENT_DATE + INTERVAL '{days} days'"
        
        query = text(f"""
        SELECT * FROM space_missions 
        WHERE {date_condition}
        ORDER BY launch_date ASC
        """)
        return self.execute_query_to_dataframe(query)
    
    def create_navbar(self):
        """Create navigation bar"""
        return dbc.NavbarSimple(
            children=[
                dbc.NavItem(dbc.NavLink("Overview", href="/", id="nav-overview")),
                dbc.NavItem(dbc.NavLink("APOD Gallery", href="/apod", id="nav-apod")),
                dbc.NavItem(dbc.NavLink("ISS Tracker", href="/iss", id="nav-iss")),
                dbc.NavItem(dbc.NavLink("Asteroids", href="/asteroids", id="nav-asteroids")),
                dbc.NavItem(dbc.NavLink("Missions", href="/missions", id="nav-missions")),
            ],
            brand="NASA Space Data Dashboard",
            brand_href="/",
            color="dark",
            dark=True,
            className="mb-4"
        )
    
    def create_overview_page(self):
        """Create overview page layout"""
        return html.Div([
            dbc.Container([
                html.Div([
                    html.H1("NASA Space Data Dashboard", className="display-3"),
                    html.P("Explore the cosmos with real-time space data from NASA and space agencies", 
                          className="lead"),
                    html.Hr(className="my-2"),
                    html.P("Navigate through different sections to discover space images, track the ISS, "
                          "monitor asteroids, and follow upcoming space missions.")
                ], className="py-4")
            ], fluid=True, className="hero-section text-white mb-4"),

            html.Div(id="overview-stats", className="mb-4"),

            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Latest Space Image"),
                        dbc.CardBody(id="latest-apod-card")
                    ])
                ], width=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("ISS Current Location"),
                        dbc.CardBody(id="current-iss-card")
                    ])
                ], width=6)
            ], className="mb-4"),
            
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Next Asteroid Approach"),
                        dbc.CardBody(id="next-asteroid-card")
                    ])
                ], width=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Next Space Mission"),
                        dbc.CardBody(id="next-mission-card")
                    ])
                ], width=6)
            ])
        ])
    
    def create_apod_page(self):
        """Create APOD gallery page layout"""
        # Get the total count for the header
        total_count = self.fetch_apod_total_count(30)
        
        return html.Div([
            dbc.Row([
                dbc.Col([
                    html.H1("Astronomy Picture of the Day Gallery", className="mb-4"),
                ], width=9),
                dbc.Col([
                    html.Div([
                        html.H5(f"Total Images: {total_count}", 
                               className="text-info text-end")
                    ], style={"paddingTop": "8px"})
                ], width=3)
            ]),

            dbc.Row([
                dbc.Col([
                    html.Br(),
                    dbc.Button("Refresh Data", id="apod-refresh-btn", color="primary")
                ], width=12, className="text-end")
            ], className="mb-4"),

            html.Div(id="apod-gallery")
        ])
    
    def create_iss_page(self):
        """Create ISS tracking page layout"""
        return html.Div([
            html.H1("International Space Station Tracker", className="mb-4"),

            dbc.Row([
                dbc.Col([
                    html.P("Displaying 24-hour ISS orbital path", className="text-muted")
                ], width=9),
                dbc.Col([
                    dbc.Button("Refresh Position", id="iss-refresh-btn", color="primary")
                ], width=3, className="text-end")
            ], className="mb-4"),

            html.Div(id="iss-current-info", className="mb-4"),

            dbc.Card([
                dbc.CardHeader("ISS Orbital Path"),
                dbc.CardBody([
                    dbc.Spinner(
                        dcc.Graph(id="iss-map", style={'height': '600px'}),
                        color="primary", type="border"
                    )
                ])
            ])
        ])
    
    def create_asteroids_page(self):
        """Create asteroids monitoring page layout"""
        return html.Div([
            html.H1("Asteroids Monitor", className="mb-4"),
            
            dbc.Row([
                dbc.Col([
                    dbc.Label("Monitoring Period:"),
                    dcc.Dropdown(
                        id='asteroid-period',
                        options=[
                            {'label': 'Next 7 Days', 'value': 7},
                            {'label': 'Next 30 Days', 'value': 30}
                        ],
                        value=30,
                        clearable=False
                    )
                ], width=4),
                dbc.Col([
                    dbc.Label("Show Only Hazardous:"),
                    dcc.Dropdown(
                        id='asteroid-hazard-filter',
                        options=[
                            {'label': 'All Asteroids', 'value': 'all'},
                            {'label': 'Potentially Hazardous Only', 'value': 'hazardous'}
                        ],
                        value='all',
                        clearable=False
                    )
                ], width=4),
                dbc.Col([
                    dbc.Label(""),
                    html.Div([
                        dbc.Button("Refresh Data", id="asteroid-refresh-btn", color="primary", className="w-100")
                    ], style={"marginTop": "8px"})
                ], width=4)
            ], className="mb-4"),

            html.Div(id="asteroid-stats", className="mb-4"),

            dbc.Card([
                dbc.CardHeader("Asteroid Approach Timeline"),
                dbc.CardBody([
                    dcc.Graph(id="asteroid-timeline")
                ])
            ], className="mb-4"),

            dbc.Card([
                dbc.CardHeader("Asteroid Details"),
                dbc.CardBody([
                    html.Div(id="asteroid-table")
                ])
            ], className="mb-4"),

            dbc.Card([
                dbc.CardHeader("Asteroid Size Comparison"),
                dbc.CardBody([
                    dcc.Graph(id="asteroid-size-chart")
                ])
            ])
        ])
    
    def create_missions_page(self):
        """Create space missions page layout"""
        return html.Div([
            html.H1("Upcoming Space Missions", className="mb-4"),

            dbc.Row([
                dbc.Col([
                    dbc.Label("Mission Timeframe:"),
                    dcc.Dropdown(
                        id='mission-timeframe',
                        options=[
                            {'label': 'Next 30 Days', 'value': 30},
                            {'label': 'Next 90 Days', 'value': 90},
                            {'label': 'Next 180 Days', 'value': 180}
                        ],
                        value=90,
                        clearable=False
                    )
                ], width=4),
                dbc.Col([
                    dbc.Label("Mission Status:"),
                    dcc.Dropdown(
                        id='mission-status-filter',
                        options=[
                            {'label': 'All Missions', 'value': 'all'},
                            {'label': 'Confirmed', 'value': 'Go for Launch'}
                        ],
                        value='all',
                        clearable=False
                    )
                ], width=4),
                dbc.Col([
                    dbc.Label(""),
                    html.Div([
                        dbc.Button("Refresh Data", id="mission-refresh-btn", color="primary", className="w-100")
                    ], style={"marginTop": "8px"})
                ], width=4)
            ], className="mb-4"),

            html.Div(id="mission-stats", className="mb-4"),

            dbc.Card([
                dbc.CardHeader("Launch Calendar"),
                dbc.CardBody([
                    dcc.Graph(id="mission-calendar")
                ])
            ], className="mb-4"),

            dbc.Card([
                dbc.CardHeader("Launch Success Analysis"),
                dbc.CardBody([
                    dcc.Graph(id="mission-success-chart")
                ])
            ], className="mb-4"),

            dbc.Card([
                dbc.CardHeader("Mission Details"),
                dbc.CardBody([
                    html.Div(id="mission-details")
                ])
            ])
        ])
    
    def setup_layout(self):
        """Setup main layout with navigation"""
        self.app.layout = html.Div([
            dcc.Location(id='url', refresh=False),
            self.create_navbar(),
            
            dbc.Container(
                html.Div([
                    html.Div(id='page-content'),
                    
                    html.Div(
                        dbc.Spinner(
                            html.Div("Loading data from database...", 
                                    style={"height": "80px", "padding": "20px"}),
                            color="primary",
                            type="grow",
                            fullscreen=False,
                            spinnerClassName="spinner-large"
                        ),
                        id="loading-overlay",
                        style={"display": "none"}
                    ),
                ]),
                fluid=True
            ),

            html.Div(id='status-container', className="mt-3"),

            dcc.Interval(
                id='interval-component',
                interval=1800*1000,
                n_intervals=0,
                disabled=False 
            ),
            
            dcc.Store(id='loading-states', data={'is_loading': False, 'last_loaded': 0})
        ])
    
    def setup_callbacks(self):
        """Setup all dashboard callbacks"""

        @self.app.callback(
            Output('page-content', 'children'),
            [Input('url', 'pathname')]
        )
        def display_page(pathname):
            if pathname == '/apod':
                return self.create_apod_page()
            elif pathname == '/iss':
                return self.create_iss_page()
            elif pathname == '/asteroids':
                return self.create_asteroids_page()
            elif pathname == '/missions':
                return self.create_missions_page()
            else:
                return self.create_overview_page()
        
        @self.app.callback(
            [Output('overview-stats', 'children'),
             Output('latest-apod-card', 'children'),
             Output('current-iss-card', 'children'),
             Output('next-asteroid-card', 'children'),
             Output('next-mission-card', 'children')],
            [Input('interval-component', 'n_intervals')]
        )
        def update_overview(n_intervals):
            apod_df = self.fetch_apod_data(7)
            iss_df = self.fetch_iss_data(1)
            asteroid_df = self.fetch_asteroid_data(30)
            mission_df = self.fetch_missions_data(30)

            # Get the actual count of all APOD images in the database for the last 30 days
            # This will show the correct total count, not just the limited results in apod_df
            total_apod_images = self.fetch_apod_total_count(30)
            
            stats_cards = dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(total_apod_images, className="card-title"),
                            html.P("Gallery Images", className="card-text")
                        ])
                    ], color="primary", outline=True)
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(len(iss_df), className="card-title"),
                            html.P("ISS Positions", className="card-text")
                        ])
                    ], color="info", outline=True)
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(len(asteroid_df), className="card-title"),
                            html.P("Tracked Asteroids", className="card-text")
                        ])
                    ], color="warning", outline=True)
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(len(mission_df), className="card-title"),
                            html.P("Upcoming Missions", className="card-text")
                        ])
                    ], color="success", outline=True)
                ], width=3)
            ])

            if not apod_df.empty:
                latest_apod = apod_df.iloc[0]
                apod_card = html.Div([
                    html.H5(latest_apod['title']),
                    html.P(latest_apod['explanation'][:200] + "..." if len(latest_apod['explanation']) > 200 else latest_apod['explanation']),
                    html.Small(f"Date: {latest_apod['date']}")
                ])
            else:
                apod_card = html.P("No APOD data available")

            if not iss_df.empty:
                latest_iss = iss_df.iloc[0]
                iss_card = html.Div([
                    html.H5("Current Position"),
                    html.P(f"Latitude: {latest_iss['latitude']:.2f}°"),
                    html.P(f"Longitude: {latest_iss['longitude']:.2f}°"),
                    html.P(f"Altitude: {latest_iss['altitude']:.0f} km"),
                    html.Small(f"Last updated: {latest_iss['timestamp']}")
                ])
            else:
                iss_card = html.P("No ISS data available")

            if not asteroid_df.empty:
                next_asteroid = asteroid_df.iloc[0]
                asteroid_card = html.Div([
                    html.H5(next_asteroid['name']),
                    html.P(f"Approach Date: {next_asteroid['approach_date']}"),
                    html.P(f"Miss Distance: {next_asteroid['miss_distance']:,.0f} km"),
                    html.P(f"Potentially Hazardous: {'Yes' if next_asteroid['is_potentially_hazardous'] else 'No'}")
                ])
            else:
                asteroid_card = html.P("No asteroid data available")

            if not mission_df.empty:
                next_mission = mission_df.iloc[0]
                mission_card = html.Div([
                    html.H5(next_mission['name']),
                    html.P(f"Launch Date: {next_mission['launch_date']}"),
                    html.P(f"Rocket: {next_mission['rocket_name']}"),
                    html.P(f"Status: {next_mission['status']}")
                ])
            else:
                mission_card = html.P("No mission data available")
            
            return stats_cards, apod_card, iss_card, asteroid_card, mission_card

        if not hasattr(self, '_apod_cache'):
            self._apod_cache = {
                'data': None,
                'timestamp': 0,
                'gallery': None
            }
        
        @self.app.callback(
            Output('apod-gallery', 'children'),
            [Input('apod-refresh-btn', 'n_clicks'),
             Input('interval-component', 'n_intervals')]
        )
        def update_apod_page(refresh_clicks, n_intervals):
            import time
            import traceback
            
            time_period = 30
            
            start_time = time.time()
            
            ctx = callback_context
            trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
            print(f"APOD update triggered by: {trigger_id}")
            
            force_refresh = (trigger_id == 'apod-refresh-btn')
            cache_expired = (time.time() - self._apod_cache['timestamp']) > 300
            
            try:
                if (not force_refresh and 
                    not cache_expired and 
                    self._apod_cache['data'] is not None):
                    
                    print(f"Using cached APOD data (cache age: {time.time() - self._apod_cache['timestamp']:.1f}s)")
                    df = self._apod_cache['data']
                else:
                    print(f"Fetching fresh APOD data for {time_period} days")
                    try:
                        df = self.fetch_apod_data(time_period)
                        self._apod_cache['data'] = df
                        self._apod_cache['timestamp'] = time.time()
                    except Exception as e:
                        print(f"Error fetching APOD data: {str(e)}")
                        traceback.print_exc()
                        if self._apod_cache['data'] is not None:
                            df = self._apod_cache['data']
                            print("Using cached data as fallback after fetch error")
                        else:
                            return html.Div([
                                dbc.Alert([
                                    html.H4("Error Loading APOD Data"),
                                    html.P(f"An error occurred: {str(e)}"),
                                    html.P("Please try again later.")
                                ], color="danger")
                            ])
                
                if df.empty and (force_refresh or self._apod_cache['data'] is None):
                    print(f"Empty result with {time_period} days window, trying with 90 days window")
                    df = self.fetch_apod_data(90)

                if df.empty:
                    return html.Div([
                        dbc.Alert([
                            html.H4("No Astronomy Pictures Available"),
                            html.P("Could not retrieve APOD data for the selected time period."),
                            html.P("Try selecting a different time period or check the database connection.")
                        ], color="warning")
                    ])

                print(f"Dataframe shape: {df.shape}, columns: {df.columns.tolist()}")
                
                if 'url' in df.columns:
                    print(f"URL column exists: First few URLs: {df['url'].head(3).tolist()}")
                else:
                    print("WARNING: URL column missing in dataframe")
                    
                gallery = self.create_apod_gallery_items(df)
                
                self._apod_cache['gallery'] = {
                    'content': gallery,
                    'timestamp': time.time()
                }
                
                print(f"APOD gallery update completed in {time.time() - start_time:.2f}s")
                return gallery
                
            except Exception as e:
                print(f"Critical error in APOD update: {str(e)}")
                traceback.print_exc()
                
                return html.Div([
                    dbc.Alert([
                        html.H4("Dashboard Error"),
                        html.P("An error occurred while updating the APOD gallery."),
                        html.P("Please try refreshing the page or selecting a smaller time period."),
                        html.Small(f"Error details: {str(e)}", className="text-muted")
                    ], color="danger")
                ])

        @self.app.callback(
            [Output('iss-current-info', 'children'),
             Output('iss-map', 'figure')],
            [Input('iss-refresh-btn', 'n_clicks'),
             Input('interval-component', 'n_intervals')]
        )
        def update_iss_page(refresh_clicks, n_intervals):
            ctx = callback_context
            trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
            print(f"ISS update triggered by: {trigger_id}")

            duration = 24
            
            df = self.fetch_iss_data(duration)

            if df.empty:
                no_data_alert = dbc.Alert([
                    html.H4("No ISS Data Available"),
                    html.P("Could not retrieve ISS tracking data."),
                    html.P("This could be due to:"),
                    html.Ul([
                        html.Li("Database connection issues"),
                        html.Li("No data available in the system"),
                        html.Li("Data processing delay")
                    ]),
                    html.P("Try refreshing later.")
                ], color="warning")
                
                empty_fig = go.Figure()
                empty_fig.update_layout(
                    title="No ISS Data Available",
                    annotations=[{
                        "text": "No data available",
                        "showarrow": False,
                        "font": {"size": 20, "color": "white"}
                    }]
                )
                empty_fig = self.apply_chart_styling(empty_fig)
                
                return no_data_alert, empty_fig

            latest = df.iloc[0]
            current_info = dbc.Alert([
                html.H4("Current ISS Status"),
                html.P(f"Position: {latest['latitude']:.2f}°N, {latest['longitude']:.2f}°E"),
                html.P(f"Altitude: {latest['altitude']:.0f} km"),
                html.P(f"Velocity: {latest['velocity']:,.0f} km/h"),
                html.P(f"Last Update: {latest['timestamp']}"),
                html.P(f"Displaying complete 24-hour orbital path with {len(df)} data points")
            ], color="info")

            map_fig = go.Figure()

            map_fig.add_trace(go.Scattergeo(
                lon=df['longitude'],
                lat=df['latitude'],
                mode='lines+markers',
                marker=dict(size=4, color='red'),
                line=dict(width=2, color='red'),
                name='ISS Orbital Path'
            ))

            map_fig.add_trace(go.Scattergeo(
                lon=[latest['longitude']],
                lat=[latest['latitude']],
                mode='markers',
                marker=dict(size=15, color='green', symbol='circle'),
                name='Current Position'
            ))
            
            map_fig.update_layout(
                title="ISS Orbital Path",
                geo=dict(
                    projection_type="natural earth",
                    showland=True,
                    landcolor="rgb(43, 53, 77)",
                    coastlinecolor="rgb(144, 164, 174)",
                    showocean=True,
                    oceancolor="rgb(24, 54, 85)"
                ),
                height=600
            )

            map_fig = self.apply_chart_styling(map_fig)
            
            return current_info, map_fig

        @self.app.callback(
            [Output('asteroid-stats', 'children'),
             Output('asteroid-timeline', 'figure'),
             Output('asteroid-table', 'children'),
             Output('asteroid-size-chart', 'figure')],
            [Input('asteroid-period', 'value'),
             Input('asteroid-hazard-filter', 'value'),
             Input('asteroid-refresh-btn', 'n_clicks'),
             Input('interval-component', 'n_intervals')]
        )
        def update_asteroids_page(period, hazard_filter, refresh_clicks, n_intervals):
            ctx = callback_context
            trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
            print(f"Asteroid update triggered by: {trigger_id}, period: {period}")
            
            df = self.fetch_asteroid_data(period)
            
            if df.empty and trigger_id == 'asteroid-refresh-btn' and period != 30:
                print(f"Empty result with {period} days window, trying with 30 days window")
                df = self.fetch_asteroid_data(30)

            if df.empty:
                no_data_alert = html.Div([
                    dbc.Alert([
                        html.H4("No Asteroid Data Available"),
                        html.P("Could not retrieve asteroid data for the selected time period."),
                        html.P("This could be due to database connection issues or no data for this period."),
                        html.P("Try selecting a different time period or refreshing later.")
                    ], color="warning")
                ])
                
                empty_fig = go.Figure()
                empty_fig.update_layout(
                    title="No Asteroid Data Available",
                    annotations=[{
                        "text": "No data available for the selected time period",
                        "showarrow": False,
                        "font": {"size": 20, "color": "white"}
                    }]
                )
                empty_fig = self.apply_chart_styling(empty_fig)
                
                return no_data_alert, empty_fig, html.Div("No asteroid data to display"), empty_fig

            df['estimated_diameter_max'] = pd.to_numeric(df['estimated_diameter_max'], errors='coerce')
            df['miss_distance'] = pd.to_numeric(df['miss_distance'], errors='coerce')
            df['relative_velocity'] = pd.to_numeric(df['relative_velocity'], errors='coerce')

            if hazard_filter == 'hazardous':
                df = df[df['is_potentially_hazardous'] == True]

            total_asteroids = len(df)
            hazardous_count = len(df[df['is_potentially_hazardous'] == True])
            avg_size = df['estimated_diameter_max'].mean()
            closest_approach = df['miss_distance'].min()
            
            stats_cards = dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(total_asteroids, className="card-title"),
                            html.P("Total Asteroids", className="card-text")
                        ])
                    ], color="warning", outline=True)
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(hazardous_count, className="card-title"),
                            html.P("Potentially Hazardous", className="card-text")
                        ])
                    ], color="danger", outline=True)
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(f"{avg_size:.2f} km", className="card-title"),
                            html.P("Average Max Diameter", className="card-text")
                        ])
                    ], color="info", outline=True)
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(f"{closest_approach:,.0f} km", className="card-title"),
                            html.P("Closest Approach", className="card-text")
                        ])
                    ], color="success", outline=True)
                ], width=3)
            ])

            df['approach_date'] = pd.to_datetime(df['approach_date'])

            df['estimated_diameter_max'] = pd.to_numeric(df['estimated_diameter_max'], errors='coerce')

            timeline_fig = px.scatter(
                df,
                x='approach_date',
                y='miss_distance',
                size='estimated_diameter_max',
                color='is_potentially_hazardous',
                hover_data=['name', 'relative_velocity'],
                title='Asteroid Approach Timeline',
                labels={
                    'approach_date': 'Approach Date',
                    'miss_distance': 'Miss Distance (km)',
                    'is_potentially_hazardous': 'Potentially Hazardous'
                }
            )
            timeline_fig.update_layout(
                yaxis_type="log"
            )

            timeline_fig = self.apply_chart_styling(timeline_fig)
            
            table_df = df[['name', 'approach_date', 'estimated_diameter_max', 'miss_distance', 
                          'relative_velocity', 'is_potentially_hazardous']].copy()
            table_df.columns = ['Name', 'Approach Date', 'Max Diameter (km)', 'Miss Distance (km)', 
                               'Velocity (km/h)', 'Potentially Hazardous']
            
            table = dash_table.DataTable(
                data=table_df.to_dict('records'),
                columns=[{"name": i, "id": i} for i in table_df.columns],
                sort_action="native",
                filter_action="native",
                page_size=10,
                style_cell={
                    'textAlign': 'left',
                    'backgroundColor': 'rgba(50, 50, 70, 0.7)',
                    'color': 'white',
                    'border': '1px solid rgba(255, 255, 255, 0.1)'
                },
                style_header={
                    'backgroundColor': 'rgba(70, 70, 90, 0.9)',
                    'color': 'white',
                    'fontWeight': 'bold',
                    'textAlign': 'center',
                    'border': '1px solid rgba(255, 255, 255, 0.2)'
                },
                style_data_conditional=[
                    {
                        'if': {'filter_query': '{Potentially Hazardous} = True'},
                        'backgroundColor': 'rgba(255, 0, 0, 0.3)',
                        'color': '#ff9999',
                        'fontWeight': 'bold'
                    }
                ],
                style_filter={
                    'backgroundColor': 'rgba(70, 70, 90, 0.7)',
                    'color': 'white'
                }
            )
            
            valid_df = df.dropna(subset=['estimated_diameter_max'])
            
            size_fig = px.histogram(
                valid_df,
                x='estimated_diameter_max',
                nbins=20,
                title='Asteroid Size Distribution',
                labels={'estimated_diameter_max': 'Maximum Diameter (km)', 'count': 'Number of Asteroids'},
                color_discrete_sequence=['#ffaa00']
            )
            size_fig = self.apply_chart_styling(size_fig)
            
            return stats_cards, timeline_fig, table, size_fig
        
        @self.app.callback(
            [Output('mission-stats', 'children'),
             Output('mission-calendar', 'figure'),
             Output('mission-details', 'children'),
             Output('mission-success-chart', 'figure')],
            [Input('mission-timeframe', 'value'),
             Input('mission-status-filter', 'value'),
             Input('mission-refresh-btn', 'n_clicks'),
             Input('interval-component', 'n_intervals')]
        )
        def update_missions_page(timeframe, status_filter, refresh_clicks, n_intervals):
            ctx = callback_context
            trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
            print(f"Mission update triggered by: {trigger_id}, timeframe: {timeframe}")
            
            df = self.fetch_missions_data(timeframe)
            
            if df.empty and trigger_id == 'mission-refresh-btn':
                print(f"Empty result with {timeframe} days window, trying with 180 days window")
                df = self.fetch_missions_data(180)
                
            if df.empty:
                no_data_alert = html.Div([
                    dbc.Alert([
                        html.H4("No Mission Data Available"),
                        html.P("Could not retrieve mission data for the selected time period."),
                        html.P("This could be due to database connection issues or no missions scheduled for this period."),
                        html.P("Try selecting a different time period or refreshing later.")
                    ], color="warning")
                ])
                
                empty_fig = go.Figure()
                empty_fig.update_layout(
                    title="No Mission Data Available",
                    annotations=[{
                        "text": "No data available for the selected time period",
                        "showarrow": False,
                        "font": {"size": 20, "color": "white"}
                    }]
                )
                empty_fig = self.apply_chart_styling(empty_fig)
                
                return no_data_alert, empty_fig, html.Div("No mission data to display"), empty_fig
            
            print(f"Available status values in data: {df['status'].unique().tolist()}")
            
            if status_filter != 'all':
                # We only have 'Go for Launch' as a filter option now
                df = df[df['status'] == status_filter]
                print(f"Applied filtering for status: {status_filter}, found {len(df)} records")
                
                if df.empty:
                    print(f"WARNING: No data after filtering by status: {status_filter}")
                    no_data_alert = html.Div([
                        dbc.Alert([
                            html.H4(f"No Confirmed Missions"),
                            html.P(f"No confirmed missions found in the {timeframe}-day timeframe."),
                            html.P("Try selecting 'All Missions' or a different time period.")
                        ], color="warning")
                    ])
                    
                    empty_fig = go.Figure()
                    empty_fig.update_layout(
                        title=f"No Confirmed Missions",
                        annotations=[{
                            "text": f"No confirmed missions available",
                            "showarrow": False,
                            "font": {"size": 20, "color": "white"}
                        }]
                    )
                    empty_fig = self.apply_chart_styling(empty_fig)
                    
                    return no_data_alert, empty_fig, html.Div(f"No confirmed missions"), empty_fig
            
            total_missions = len(df)
            confirmed_missions = len(df[df['status'] == 'Go for Launch'])
            tbc_missions = len(df[df['status'] == 'TBC']) 
            tbd_missions = len(df[df['status'] == 'TBD'])
            next_launch = df['launch_date'].min()
            
            if status_filter == 'Go for Launch':
                status_label = "Confirmed Missions"
                status_color = "success"
                count_display = total_missions
            else:
                status_label = "Total Missions"
                status_color = "primary"
                count_display = total_missions
            
            stats_cards = dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(count_display, className="card-title"),
                            html.P(status_label, className="card-text")
                        ])
                    ], color=status_color, outline=True)
                ], width=4),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(next_launch.strftime('%Y-%m-%d') if not pd.isna(next_launch) else "N/A", className="card-title"),
                            html.P("Next Launch Date", className="card-text")
                        ])
                    ], color="warning", outline=True)
                ], width=4),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(df.shape[0], className="card-title"),
                            html.P("Missions in Timeframe", className="card-text")
                        ])
                    ], color="info", outline=True)
                ], width=4)
            ])
            
            df['launch_date'] = pd.to_datetime(df['launch_date'])
            df['launch_month'] = df['launch_date'].dt.strftime('%Y-%m')
            df['launch_month_name'] = df['launch_date'].dt.strftime('%b %Y')
            
            monthly_launches = df.groupby(['launch_month', 'launch_month_name']).size().reset_index(name='count')
            
            import datetime
            current_month = datetime.datetime.now().strftime('%Y-%m')
            
            def custom_month_sort(month):
                if month == current_month:
                    return '0' + month
                return month
                
            monthly_launches['sort_key'] = monthly_launches['launch_month'].apply(custom_month_sort)
            monthly_launches = monthly_launches.sort_values('sort_key')
            
            calendar_fig = px.bar(
                monthly_launches,
                x='count',
                y='launch_month_name',
                title='Launches by Month',
                labels={'count': 'Number of Launches', 'launch_month_name': 'Month'},
                color_discrete_sequence=['#00ccff'],
                orientation='h'
            )
            
            calendar_fig.update_layout(yaxis={'categoryorder': 'array', 'categoryarray': monthly_launches['launch_month_name'].tolist()})
            calendar_fig = self.apply_chart_styling(calendar_fig)

            status_priority = {
                'Go for Launch': 1,
                'Other': 2
            }
            
            sorted_df = df.copy()
            
            def get_priority(status):
                if status == 'Go for Launch':
                    return 1
                else:
                    return 2
            
            sorted_df['status_priority'] = sorted_df['status'].apply(get_priority)
            
            sorted_df = sorted_df.sort_values(['status_priority', 'launch_date'])
            
            mission_cards = []
            for _, mission in sorted_df.iterrows():
                status = str(mission['status'])
                if status == 'Go for Launch':
                    status_color = "success"
                else:
                    status_color = "secondary" 
                
                badge_style = {}
                status = mission['status']
                if status == 'Go for Launch':
                    badge_style = {"backgroundColor": "#28a745", "color": "white"}  # Green
                else:
                    badge_style = {"backgroundColor": "#6c757d", "color": "white"}  # Gray
                
                card = dbc.Card([
                    dbc.CardBody([
                        html.H5(mission['name'], className="card-title"),
                        html.P(f"Rocket: {mission['rocket_name']}"),
                        html.P(f"Launch: {str(mission['launch_date'])[:10]}"),
                        html.P(f"Location: {mission['launch_location']}"),
                        dbc.Badge(mission['status'], color=status_color, style=badge_style, className="px-2 py-1")
                    ])
                ], className="mb-3")
                mission_cards.append(dbc.Col(card, width=12, lg=6))
            
            # Create a header to explain the sorting and color coding
            mission_header = html.Div([
                html.H5([
                    "Missions sorted by status: ",
                    html.Span("Confirmed (Go for Launch) ", style={"color": "#28a745"}),  # Green
                    "first, followed by other statuses"
                ], className="text-muted mb-3")
            ])
            
            mission_details = html.Div([
                mission_header,
                dbc.Row(mission_cards)
            ])

            df['grouped_status'] = df['status'].apply(lambda x: 
                'Go for Launch' if x == 'Go for Launch' else
                'Other' if pd.notna(x) else
                'Unknown')
            
            status_counts = df['grouped_status'].value_counts()
            success_fig = px.pie(
                values=status_counts.values,
                names=status_counts.index,
                title="Mission Status Distribution",
                color_discrete_map={
                    'Go for Launch': '#28a745',  # Green
                    'Other': '#6c757d',          # Gray
                    'Unknown': '#17a2b8'         # Blue
                }
            )
            success_fig = self.apply_chart_styling(success_fig)
            
            return stats_cards, calendar_fig, mission_details, success_fig

        # Database connection status indicator
        @self.app.callback(
            Output('status-container', 'children'),
            [Input('interval-component', 'n_intervals')]
        )
        def update_connection_status(n_intervals):
            """Display database connection status"""
            try:
                test_query = text("SELECT 1")
                result = self.execute_query_to_dataframe(test_query)
                
                if not result.empty:
                    return dbc.Alert([
                        html.Span("Database Connection: ", className="font-weight-bold"),
                        "Connected ",
                        html.I(className="fas fa-check-circle text-success")
                    ], color="success", dismissable=True, is_open=False)
                else:
                    return dbc.Alert([
                        html.Span("Database Connection: ", className="font-weight-bold"),
                        "Available but no data returned ",
                        html.I(className="fas fa-exclamation-circle text-warning")
                    ], color="warning", dismissable=True)
            except Exception as e:
                return dbc.Alert([
                    html.Span("Database Connection Error: ", className="font-weight-bold"),
                    f"{str(e)}",
                    html.I(className="fas fa-times-circle text-danger")
                ], color="danger", dismissable=True)
    
    def apply_chart_styling(self, fig):
        """Apply consistent dark theme styling to a Plotly figure
        
        Args:
            fig: Plotly figure to style
            
        Returns:
            The styled figure
        """
        fig.update_layout(
            font_color="#ffffff",
            title_font_color="#ffffff",
            legend_font_color="#ffffff",
            paper_bgcolor="rgba(50, 50, 70, 0.3)",
            plot_bgcolor="rgba(50, 50, 70, 0.3)",
            xaxis=dict(
                title_font=dict(color="#ffffff"),
                tickfont=dict(color="#ffffff"),
                gridcolor="rgba(255, 255, 255, 0.1)",
                zerolinecolor="rgba(255, 255, 255, 0.3)"
            ),
            yaxis=dict(
                title_font=dict(color="#ffffff"),
                tickfont=dict(color="#ffffff"),
                gridcolor="rgba(255, 255, 255, 0.1)",
                zerolinecolor="rgba(255, 255, 255, 0.3)"
            )
        )
        return fig
    
    def create_apod_gallery_items(self, df):
        """Create APOD gallery cards from dataframe
        
        Args:
            df: DataFrame with APOD data
            
        Returns:
            html.Div: Gallery layout with cards
        """
        MAX_IMAGES = 15
        
        # Get the total count from the database for the notice
        total_in_db = self.fetch_apod_total_count(30)
        
        if len(df) > MAX_IMAGES:
            print(f"Limiting APOD gallery to {MAX_IMAGES} images to prevent server overload")
            df = df.head(MAX_IMAGES)
        
        print(f"APOD dataframe columns: {df.columns.tolist()}")
        if not df.empty and 'url' in df.columns:
            print(f"Sample URLs: {df['url'].head(3).tolist()}")
            
        gallery_items = []
        
        # Add a notice if we're only showing a subset of available images
        if total_in_db > MAX_IMAGES:
            notice = dbc.Alert(
                f"Showing {MAX_IMAGES} of {total_in_db} total images.",
                color="info",
                className="mb-4"
            )
            gallery_items.append(notice)
        for idx, row in df.iterrows():
            try:
                try:
                    title = str(row['title']) if 'title' in row and pd.notna(row['title']) else "Untitled"
                except:
                    title = "Untitled"
                    
                try:
                    explanation = str(row['explanation']) if 'explanation' in row and pd.notna(row['explanation']) else "No description available"
                except:
                    explanation = "No description available"
                    
                try:
                    date = str(row['date']) if 'date' in row and pd.notna(row['date']) else "Unknown date"
                except:
                    date = "Unknown date"
                    
                try:
                    media_type = str(row['media_type']).lower() if 'media_type' in row and pd.notna(row['media_type']) else "unknown"
                except:
                    media_type = "unknown"
                    
                try:
                    url = str(row['url']) if 'url' in row and pd.notna(row['url']) else ""
                    url = url.strip()
                    print(f"Image {idx} URL: {url}, Type: {media_type}")
                except:
                    url = ""
                    print(f"Error extracting URL for image {idx}")
                
                if not url:
                    image_src = "https://via.placeholder.com/400x300?text=No+Image"
                    print(f"Using placeholder for image {idx} - empty URL")
                elif media_type == 'image':
                    image_src = url
                elif media_type == 'video':
                    image_src = "https://img.icons8.com/color/452/video.png"
                else:
                    image_src = "https://via.placeholder.com/400x300?text=Unknown+Media+Type"
                    print(f"Using placeholder for image {idx} - unknown type: {media_type}")
                
                card_content = [
                    html.Div([
                        html.Img(
                            src=image_src,
                            style={
                                "width": "100%", 
                                "height": "200px",
                                "objectFit": "contain", 
                                "marginBottom": "8px"
                            }
                        )
                    ], style={"textAlign": "center", "backgroundColor": "#121212", "marginBottom": "8px"}),
                    
                    # Card body with text content
                    html.Div([
                        # Title
                        html.H5(
                            title[:40] + "..." if len(title) > 40 else title,
                            style={"fontSize": "16px", "marginBottom": "8px", "fontWeight": "bold"}
                        ),
                        # Description
                        html.P(
                            explanation[:80] + "..." if len(explanation) > 80 else explanation,
                            style={"fontSize": "14px", "color": "#cccccc", "marginBottom": "8px"}
                        ),
                        # Date
                        html.A(
                            f"View (Date: {date})",
                            href=url,
                            target="_blank",
                            style={"fontSize": "12px", "color": "#5bc0de"}
                        )
                    ], style={"padding": "10px"})
                ]
                
                card = html.Div(
                    card_content,
                    style={
                        "border": "1px solid #444",
                        "borderRadius": "4px",
                        "backgroundColor": "#222",
                        "height": "100%", 
                        "boxShadow": "0 2px 4px rgba(0,0,0,0.5)"
                    }
                )
                
                gallery_items.append(
                    dbc.Col(
                        card, 
                        width=12, md=6, lg=4, xl=4,
                        className="mb-3 px-2"
                    )
                )
            except Exception as e:
                print(f"Error creating APOD card {idx}: {str(e)}")
                error_card = html.Div([
                    html.Div([
                        html.H5("Image Error", style={"color": "#ff5555"}),
                        html.P(f"Could not display item {idx}")
                    ], style={"padding": "15px", "textAlign": "center"})
                ], style={"border": "1px solid #ff5555", "borderRadius": "4px", "height": "100%"})
                
                gallery_items.append(
                    dbc.Col(
                        error_card,
                        width=12, md=6, lg=4, xl=4,
                        className="mb-3 px-2"
                    )
                )
        
        if not gallery_items:
            print("WARNING: No gallery items created, adding emergency fallback image")
            emergency_card = html.Div([
                html.Div([
                    html.Img(
                        src="https://apod.nasa.gov/apod/image/2106/EarthMoon_Artemis1_1080.jpg",
                        style={
                            "width": "100%", 
                            "height": "200px",
                            "objectFit": "contain", 
                            "marginBottom": "8px"
                        }
                    )
                ], style={"textAlign": "center", "backgroundColor": "#121212", "marginBottom": "8px"}),
                html.Div([
                    html.H5("NASA Earth and Moon", style={"fontSize": "16px", "marginBottom": "8px", "fontWeight": "bold"}),
                    html.P("Emergency fallback image when database images fail to load", style={"fontSize": "14px"})
                ], style={"padding": "10px"})
            ], style={
                "border": "1px solid #444",
                "borderRadius": "4px",
                "backgroundColor": "#222",
                "height": "100%", 
                "boxShadow": "0 2px 4px rgba(0,0,0,0.5)"
            })
            
            gallery_items = [
                dbc.Col(emergency_card, width=12, md=6, lg=4, xl=4, className="mb-3 px-2")
            ]
            
            warning = html.Div([
                dbc.Alert([
                    html.H5("Image Loading Issue"),
                    html.P("The system is displaying emergency fallback images because the database images could not be loaded."),
                    html.P("Please check your database connection and image URLs.")
                ], color="warning", className="mt-3")
            ])
            
            return html.Div([warning, dbc.Row(gallery_items, className="g-2")])
            
        return html.Div([
            dbc.Alert(
                f"Showing {len(df)} most recent images for optimal performance",
                color="info", 
                dismissable=True,
                is_open=len(df) >= MAX_IMAGES,
                className="mb-2 py-1 small"
            ),
            dbc.Spinner(
                dbc.Row(
                    gallery_items,
                    className="g-2",
                ),
                color="primary",
                type="border",
                spinnerClassName="mb-2"
            )
        ])
    
    def run(self, debug=True, port=8050, host='0.0.0.0'):
        """Run the dashboard with proper cleanup"""
        try:
            self.app.run(debug=debug, port=port, host=host)
        except KeyboardInterrupt:
            print("\nShutting down dashboard...")
            self.cleanup()
    
    def cleanup(self):
        """Cleanup database connections"""
        try:
            if hasattr(self.db_session, 'close'):
                self.db_session.close()
                print("Database session closed")
            elif hasattr(self.db_session, 'disconnect'):
                self.db_session.disconnect()
                print("Database connection closed")
            else:
                print("Dashboard shutdown complete")
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
    def fetch_apod_total_count(self, days=30):
        """Get the total count of APOD images in the database without limit
        
        Args:
            days: Number of days to look back
            
        Returns:
            The total count of APOD images
        """
        try:
            if self.db_type == 'sqlite':
                date_condition = f"date >= date('now', '-{days} days')"
            else:
                date_condition = f"date >= CURRENT_DATE - INTERVAL '{days} days'"
            
            query_sql = f"""
            SELECT COUNT(*) as total_count
            FROM apod_images 
            WHERE {date_condition}
            """
            
            query = text(query_sql)
            result_df = self.execute_query_to_dataframe(query)
            
            if not result_df.empty and 'total_count' in result_df.columns:
                total_count = int(result_df['total_count'].iloc[0])
                print(f"Total APOD images in database for the last {days} days: {total_count}")
                return total_count
            else:
                print("Could not retrieve APOD count, returning 0")
                return 0
                
        except Exception as e:
            print(f"Error in fetch_apod_total_count: {str(e)}")
            return 0

def create_dashboard(db_session=None):
    """
    Factory function to create dashboard with custom dataflow session
    
    Args:
        db_session: Custom dataflow database session
        
    Returns:
        NASASpaceDashboard: Configured dashboard instance
    """
    return NASASpaceDashboard(db_session=db_session)

# Custom CSS for space theme with improved dark theme compatibility
custom_css = """
body {
    background: linear-gradient(135deg, #0c0c1e 0%, #1a1a2e 50%, #16213e 100%);
    color: #ffffff;
    min-height: 100vh;
}

.card {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
    transition: transform 0.2s, box-shadow 0.2s;
    margin-bottom: 20px;
}

.card:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.4);
}

.card-header {
    background-color: rgba(70, 70, 90, 0.5) !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    font-weight: 600;
}

h1, h2, h3, h4, h5, h6, .h1, .h2, .h3, .h4, .h5, .h6 {
    color: #ffffff !important;
    text-shadow: 0px 1px 2px rgba(0,0,0,0.3);
}

p, span, .card-text {
    color: #e0e0e0 !important;
}

label, .form-label {
    color: #ffffff !important;
    font-weight: 500;
}

#page-content h1, 
#page-content .h1 {
    color: #ffffff !important;
    background-color: rgba(0, 0, 0, 0.2);
    padding: 10px;
    border-radius: 5px;
    margin-bottom: 20px;
}

.Select-control, .Select-menu-outer {
    background-color: rgba(255, 255, 255, 0.9) !important;
}

.Select-value-label, .Select-placeholder, .Select-input > input {
    color: #333333 !important;
}

.VirtualizedSelectOption {
    background-color: rgba(255, 255, 255, 0.9) !important;
    color: #333333 !important;
}

.VirtualizedSelectFocusedOption {
    background-color: rgba(100, 100, 255, 0.3) !important;
    color: #ffffff !important;
}

.form-control, .form-select {
    background-color: rgba(255, 255, 255, 0.9) !important;
    color: #333333 !important;
}

.dash-dropdown label {
    color: #ffffff !important;
    font-weight: 500;
}

.dash-dropdown .Select-control {
    border: 1px solid rgba(255, 255, 255, 0.2);
}

.dash-dropdown .Select-value {
    background-color: rgba(255, 255, 255, 0.9) !important;
    border: 1px solid rgba(50, 50, 70, 0.5) !important;
}

.dash-dropdown .Select-menu-outer {
    border: 1px solid rgba(255, 255, 255, 0.2);
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
}

.dash-dropdown .Select-option.is-focused {
    background-color: rgba(100, 100, 255, 0.3);
    color: white;
}

.dash-dropdown .Select-option {
    padding: 8px 12px;
}

.alert {
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner th {
    color: white !important;
    background-color: rgba(70, 70, 90, 0.9) !important;
    text-align: center !important;
    font-weight: bold !important;
}

.dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner td {
    color: white !important;
    background-color: rgba(50, 50, 70, 0.7) !important;
}

.dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner {
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3) !important;
}

.dash-table-container .previous-page, 
.dash-table-container .current-page, 
.dash-table-container .next-page {
    color: white !important;
    background-color: rgba(70, 70, 90, 0.9) !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
}

.dash-table-container input {
    color: #333 !important;
    background-color: rgba(255, 255, 255, 0.9) !important;
}

.plotly .main-title, .plotly .subplot .xtitle, .plotly .subplot .ytitle {
    fill: white !important;
}

.dash-bootstrap .card-header {
    color: #ffffff !important;
    font-weight: 500;
}

#apod-gallery, #asteroid-table, #mission-details {
    color: #ffffff !important;
}
"""

if __name__ == '__main__':
    dashboard = NASASpaceDashboard()
    
    dashboard.app.index_string = f'''
    <!DOCTYPE html>
    <html>
        <head>
            <title>{{%title%}}</title>
            <style>
                {custom_css}
            </style>
            {{%metas%}}
            {{%favicon%}}
            {{%css%}}
        </head>
        <body>
            {{%app_entry%}}
            <footer>
                {{%config%}}
                {{%scripts%}}
                {{%renderer%}}
            </footer>
        </body>
    </html>
    '''
    
    print("Starting NASA Space Data Dashboard...")
    print("Dashboard will be available at: http://localhost:8050")
    print("Navigate between pages using the navigation bar")
    print("Data refreshes every 5 minutes automatically")
    
    dashboard.run(debug=True, port=8050)
    print("Data refreshes every 5 minutes automatically")
