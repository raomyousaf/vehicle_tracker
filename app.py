import requests  # For API calls
import sqlite3  # Database for storing vehicle data
import urllib3  # To disable SSL warnings
import threading  # Run background tasks
import time  # Time delay in background tasks
import datetime  # Handle timestamps
from dash import Dash, html, dcc, Output, Input  # Dash framework for web UI
import dash_leaflet as dl  # Display maps and vehicle markers

# Disable SSL warnings for API requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API URL for fetching vehicle tracking data
API_URL = "api_Url"

# Local path for vehicle marker icon make 📂 folder name 'assets' and add file car_icon.png
ICON_URL = "/assets/car_icon.png"

# Function to initialize SQLite database
def init_db():
    conn = sqlite3.connect("vehicles.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            RegNo TEXT,
            Lat REAL,
            Lng REAL,
            Speed TEXT,
            StatusText TEXT,
            Location TEXT,
            Timestamp TEXT
        )
    ''')
    cursor.execute("PRAGMA journal_mode=WAL;")  # Enable Write-Ahead Logging for concurrency
    conn.commit()
    conn.close()

# Store API vehicle data in the database
def store_vehicle_data(vehicles):
    conn = sqlite3.connect("vehicles.db", check_same_thread=False)
    cursor = conn.cursor()
    
    for vehicle in vehicles:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")  # Generate current timestamp
        
        cursor.execute('''
            INSERT INTO vehicles (RegNo, Lat, Lng, Speed, StatusText, Location, Timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (vehicle.get('RegNo', 'Unknown'), 
              vehicle.get('Lat', 0.0), 
              vehicle.get('Lng', 0.0), 
              vehicle.get('Speed', '0'), 
              vehicle.get('StatusText', 'Unknown'), 
              vehicle.get('Location', 'Unknown'),
              timestamp))  # Store formatted timestamp
    
    conn.commit()
    conn.close()

# Fetch vehicle tracking data from API
def fetch_vehicle_data():
    try:
        response = requests.get(API_URL, verify=False, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        print("API Response:", data)  # Debugging: Print response to check format
        
        if not isinstance(data, list):
            print("⚠️ Unexpected API response format")
            return []
        
        store_vehicle_data(data)  # Save fetched data in the database
        return data
    except requests.exceptions.RequestException as e:
        print(f"🚨 Error fetching data: {e}")
        return []

# Background thread to fetch data every 5 seconds
def background_fetch():
    while True:
        fetch_vehicle_data()
        time.sleep(5)

threading.Thread(target=background_fetch, daemon=True).start()  # Start background thread

# Initialize the database
init_db()

# Dash Web Application
app = Dash(__name__)

app.layout = html.Div([
    html.H1("🚗 Live Vehicle Tracking in Pakistan"),
    
    dcc.Dropdown(id='vehicle-dropdown', multi=False, placeholder="Select a Vehicle"),
    
    dl.Map(center=[30.3753, 69.3451], zoom=6, children=[
        dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"),
        dl.LayerGroup(id="vehicle-layer")  # Holds vehicle markers
    ], style={'width': '100%', 'height': '600px'}, id="map"),
    
    dcc.Interval(id='interval-component', interval=5000, n_intervals=0)  # Refresh every 5 seconds
])

# Update vehicle markers on the map
@app.callback([
    Output('vehicle-dropdown', 'options'),
    Output('vehicle-layer', 'children')
], [
    Input('vehicle-dropdown', 'value'),
    Input('interval-component', 'n_intervals')
])
def update_markers(selected_regno, _):
    conn = sqlite3.connect("vehicles.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # Fetch latest location of each vehicle
    cursor.execute("""
        SELECT RegNo, Lat, Lng, Speed, StatusText, Location, Timestamp
        FROM vehicles
        WHERE Timestamp IN (
            SELECT MAX(Timestamp) FROM vehicles GROUP BY RegNo
        )
    """)
    
    vehicles = cursor.fetchall()
    conn.close()
    
    if not vehicles:
        return [], []  # No data found, return empty lists
    
    reg_no_list = [v[0] for v in vehicles]
    
    markers = []
    for vehicle in vehicles:
        if selected_regno is None or vehicle[0] == selected_regno:
            popup_text = html.Div([
                html.B("RegNo:"), f" {vehicle[0]}", html.Br(),
                html.B("Status:"), f" {vehicle[4]}", html.Br(),
                html.B("Speed:"), f" {vehicle[3]} km/h", html.Br(),
                html.B("Location:"), f" {vehicle[5]}", html.Br(),
                html.B("Lat:"), f" {vehicle[1]}", html.Br(),
                html.B("Lng:"), f" {vehicle[2]}", html.Br(),
                html.B("Timestamp:"), f" {vehicle[6]}", html.Br()
            ])
            
            markers.append(dl.Marker(
                position=[vehicle[1], vehicle[2]],
                children=dl.Popup(popup_text),
                icon=dict(iconUrl=ICON_URL, iconSize=[30, 30])
            ))

    return [{'label': reg, 'value': reg} for reg in reg_no_list], markers

if __name__ == '__main__':
    app.run_server(debug=True, host="0.0.0.0", port=8051)
