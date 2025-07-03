import pandas as pd
import requests
import streamlit as st

BBOX = (47.0, -134.0, 55.0, -118.0)

@st.cache_data(ttl=15)
def get_aircraft_df():
    url = "https://opensky-network.org/api/states/all"
    params = {
        "lamin": BBOX[0], "lomin": BBOX[1],
        "lamax": BBOX[2], "lomax": BBOX[3]
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        states = r.json().get("states", [])

        # Extract just the fields we need (match OpenSky's docs: 17 or fewer)
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
        st.error(f"Failed to fetch aircraft data: {e}")
        return pd.DataFrame([])

