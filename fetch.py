# --- fetch.py ---
import pandas as pd
import requests
import streamlit as st
import time
from datetime import datetime
from math import radians, cos, sin, asin, sqrt

DEFAULT_BBOX = (47.0, -134.0, 55.0, -118.0)

@st.cache_data(ttl=15)
def get_aircraft_df(bbox=DEFAULT_BBOX, retries=3):
    url = "https://opensky-network.org/api/states/all"
    params = {
        "lamin": bbox[0], "lomin": bbox[1],
        "lamax": bbox[2], "lomax": bbox[3]
    }

    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            states = r.json().get("states", [])

            rows = []
            for s in states:
                if len(s) >= 12:
                    row = {
                        "icao24": s[0],
                        "callsign": s[1],
                        "origin_country": s[2],
                        "time_pos": s[3],
                        "last_contact": s[4],
                        "lon": s[5],
                        "lat": s[6],
                        "baro_alt": s[7],
                        "on_ground": s[8],
                        "velocity": s[9],
                        "track": s[10],
                        "vertical_rate": s[11]
                    }
                    rows.append(row)

            return pd.DataFrame(rows)

        except Exception as e:
            st.warning(f"Attempt {attempt+1} failed: {e}")
            time.sleep(2)

    st.error("❌ All attempts to fetch aircraft data failed.")
    return pd.DataFrame([])

# --- Inactivity Tracking ---
_last_positions = {}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of Earth in km
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * asin(sqrt(a))

def track_aircraft_inactivity(df):
    global _last_positions
    now = datetime.utcnow()
    movement_status = []

    for _, row in df.iterrows():
        icao = row["icao24"]
        lat, lon = row["lat"], row["lon"]

        prev = _last_positions.get(icao)
        if prev:
            time_diff = (now - prev["timestamp"]).total_seconds()
            dist_moved = haversine(lat, lon, prev["lat"], prev["lon"])
            if time_diff > 600 and dist_moved < 0.2:
                status = "🔵 Idle >10 min"
            elif time_diff > 300 and dist_moved < 0.2:
                status = "🟨 Idle 5–10 min"
            else:
                status = "🟩 Active"
        else:
            status = "⚪ Unknown"

        _last_positions[icao] = {"lat": lat, "lon": lon, "timestamp": now}
        movement_status.append(status)

    df["movement_status"] = movement_status
    return df

# --- VesselFinder Vessels List API ---
def get_ship_positions(api_key, lat_min=47.0, lat_max=50.0, lon_min=-125.0, lon_max=-122.0):
    try:
        url = "https://api.vesselfinder.com/vesselslist"
        params = {
            "key": api_key,
            "latmin": lat_min,
            "latmax": lat_max,
            "lonmin": lon_min,
            "lonmax": lon_max,
            "format": "json"
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        print("RAW RESPONSE:")
        print(response.text)
        if not isinstance(data, list):
            st.warning("Unexpected response format from VesselFinder API")
            return pd.DataFrame([])

        ships = []
        for s in data:
            ships.append({
                "mmsi": s.get("MMSI"),
                "name": s.get("NAME"),
                "lat": float(s.get("LAT", 0)),
                "lon": float(s.get("LON", 0)),
                "speed": float(s.get("SPEED", 0)),
                "type": s.get("TYPE")
            })

        return pd.DataFrame(ships)

    except Exception as e:
        st.warning(f"Failed to fetch ship data: {e}")
        return pd.DataFrame([])

