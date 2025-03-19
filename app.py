import requests
import sqlite3
import urllib3
import threading
import time
import datetime
from dash import Dash, html, dcc, Output, Input
import dash_leaflet as dl

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API URL
API_URL = "https://103.9.23.45/TrakkerServices/Api/Home/GetSOSLastLocation/SOSUser1/SOSPassword1/03300607077/null"

# Path to the local vehicle icon
ICON_URL = "/assets/car_icon.png"

# Initialize SQLite Database
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

# Store vehicle data (Append new entries)
def store_vehicle_data(vehicles):
    conn = sqlite3.connect("vehicles.db", check_same_thread=False)
    cursor = conn.cursor()
    
    for vehicle in vehicles:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")  # Timestamp with microseconds
        
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

# Fetch data from API and store in database
def fetch_vehicle_data():
    try:
        response = requests.get(API_URL, verify=False, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        # Debugging: Print response to check format
        print("API Response:", data)
        
        if not isinstance(data, list):
            print("⚠️ Unexpected API response format")
            return []
        
        store_vehicle_data(data)  # Save every data point in DB
        return data
    except requests.exceptions.RequestException as e:
        print(f"🚨 Error fetching data: {e}")
        return []

# Start background thread for fetching data
def background_fetch():
    while True:
        fetch_vehicle_data()
        time.sleep(5)  # Fetch data every 5 seconds

threading.Thread(target=background_fetch, daemon=True).start()

# Initialize database
init_db()

# Dash Web App
app = Dash(__name__)

app.layout = html.Div([
    html.H1("🚗 Live Vehicle Tracking in Pakistan"),
    
    dcc.Dropdown(id='vehicle-dropdown', multi=False, placeholder="Select a Vehicle"),
    
    dl.Map(center=[30.3753, 69.3451], zoom=6, children=[
        dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"),
        dl.LayerGroup(id="vehicle-layer")  # Holds vehicle markers
    ], style={'width': '100%', 'height': '600px'}, id="map"),

    dcc.Interval(id='interval-component', interval=5000, n_intervals=0)  # Refresh every 5 sec
])

@app.callback([
    Output('vehicle-dropdown', 'options'),
    Output('vehicle-layer', 'children')
], [
    Input('vehicle-dropdown', 'value'),
    Input('interval-component', 'n_intervals')
])
def update_markers(selected_regno, _):
    """Fetch latest vehicle positions and update markers."""
    conn = sqlite3.connect("vehicles.db", check_same_thread=False)
    cursor = conn.cursor()
    
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
    
    # If no vehicle is selected, show all vehicles
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
                html.B("Timestamp:"), f" {vehicle[6]}", html.Br()  # Displays with microseconds
            ])
            
            markers.append(dl.Marker(
                position=[vehicle[1], vehicle[2]],
                children=dl.Popup(popup_text),
                icon=dict(iconUrl=ICON_URL, iconSize=[30, 30])
            ))

    return [{'label': reg, 'value': reg} for reg in reg_no_list], markers

if __name__ == '__main__':
    app.run_server(debug=True, host="0.0.0.0", port=8051)
