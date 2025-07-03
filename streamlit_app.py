import streamlit as st
import folium
from streamlit_folium import st_folium
from fetch import get_aircraft_df
from geopy.distance import geodesic
import math
import pandas as pd

st.set_page_config(layout="wide")
st.title("Radar – Risk-Aware Live Tracker")

# Bounding Box toggle
bbox_choice = st.radio("Bounding Box", ["YVR", "Wide"], index=0)
BBOX = (47.0, -134.0, 55.0, -118.0) if bbox_choice == "YVR" else (30.0, -150.0, 60.0, -100.0)

# YVR coordinates
YVR_COORDS = (49.1947, -123.1792)
APPROACH_HEADING = 135  # Approx approach angle for YVR RWY 08R

# Load data
df = get_aircraft_df(bbox=BBOX)
df = df.dropna(subset=["lat", "lon", "velocity", "track", "callsign", "baro_alt"])

def haversine_bearing(lat1, lon1, lat2, lon2):
    """Calculate initial bearing from point 1 to point 2"""
    dLon = math.radians(lon2 - lon1)
    lat1, lat2 = map(math.radians, [lat1, lat2])
    x = math.sin(dLon) * math.cos(lat2)
    y = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dLon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360

def classify_aircraft(row):
    speed_knots = row["velocity"] * 1.943
    coords = (row["lat"], row["lon"])
    dist_to_yvr_km = geodesic(coords, YVR_COORDS).km
    dist_nm = dist_to_yvr_km * 0.539957
    eta_min = (dist_nm / speed_knots) * 60 if speed_knots > 50 else 999

    # Altitude profile check: expected 300 ft per NM
    expected_alt = dist_nm * 300
    actual_alt = row["baro_alt"]
    alt_diff = actual_alt - expected_alt

    # Approach vector deviation
    expected_bearing = haversine_bearing(row["lat"], row["lon"], *YVR_COORDS)
    heading_diff = abs(row["track"] - expected_bearing)
    heading_diff = min(heading_diff, 360 - heading_diff)

    # Airline detection
    prefix = row["callsign"][:3].upper()
    airline = {
        "ACA": "Air Canada",
        "WJA": "WestJet",
        "DAL": "Delta",
        "UAL": "United",
        "FDX": "FedEx",
        "UPS": "UPS",
    }.get(prefix, "Unknown")

    # ETA risk levels
    if eta_min > 20:
        eta_risk = "🟢 Normal"
    elif eta_min > 10:
        eta_risk = "🟠 Tight"
    else:
        eta_risk = "🔴 High Risk"

    # Altitude check
    if alt_diff > 1500:
        alt_status = "🔻 Too High"
    elif alt_diff < -1500:
        alt_status = "⚠️ Low"
    else:
        alt_status = "✅ OK"

    # Heading check
    heading_status = "✅ OK" if heading_diff < 30 else "⚠️ Off-Course"

    # Danger zone trigger
    is_danger = (
        speed_knots > 300 and
        dist_to_yvr_km < 50 and
        abs(row.get("vertical_rate", 0)) > 1500 and
        alt_status != "✅ OK" and
        heading_status != "✅ OK"
    )

    return pd.Series({
        "speed_knots": speed_knots,
        "dist_km": dist_to_yvr_km,
        "eta_min": eta_min,
        "eta_risk": eta_risk,
        "altitude_check": alt_status,
        "heading_check": heading_status,
        "airline": airline,
        "is_danger": is_danger
    })

# Add analysis columns
df = df.join(df.apply(classify_aircraft, axis=1))

# Create map
m = folium.Map(location=[49.0, -123.0], zoom_start=5, tiles="CartoDB positron")

# Add markers
for _, row in df.iterrows():
    popup = f"""
        ✈️ <b>{row['callsign']}</b><br>
        Airline: {row['airline']}<br>
        Speed: {row['speed_knots']:.1f} kn<br>
        ETA: {row['eta_min']:.1f} min – {row['eta_risk']}<br>
        Altitude Check: {row['altitude_check']}<br>
        Heading Check: {row['heading_check']}<br>
        Distance: {row['dist_km']:.1f} km
    """
    if row["is_danger"]:
        popup += "<br><b>☢️ DANGER ZONE</b>"

    icon_color = "red" if row["is_danger"] else (
        "orange" if row["eta_risk"].startswith("🟠") else (
            "blue" if row["eta_risk"].startswith("🔴") else "green"
        )
    )

    folium.Marker(
        location=[row["lat"], row["lon"]],
        popup=popup,
        icon=folium.Icon(color=icon_color, icon="plane", prefix="fa")
    ).add_to(m)

# Add legend
legend_html = """
<div style="position: fixed;
     top: 20px; right: 20px; z-index: 9999;
     background-color: white; padding: 10px; border: 2px solid gray; font-size:14px;">
<b>🗺️ Legend</b><br>
<i class="fa fa-plane" style="color:green"></i> 🟢 ETA Normal<br>
<i class="fa fa-plane" style="color:orange"></i> 🟠 ETA Tight<br>
<i class="fa fa-plane" style="color:blue"></i> 🔴 ETA Risk<br>
<i class="fa fa-plane" style="color:red"></i> ☢️ Danger Zone<br><br>
<b>🚨 Danger Zone</b>: Red + near YVR + vertical + alt anomaly + heading off
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# Display map
st_folium(m, width=1300, height=700)

# Optional debug table
if st.checkbox("📊 Show risk analysis table"):
    st.dataframe(df[[
        "callsign", "airline", "speed_knots", "eta_min",
        "eta_risk", "altitude_check", "heading_check", "is_danger"
    ]])

# Sidebar
st.sidebar.info("⚠️ OpenSky live air-traffic feed. Not for real-world flight operations.")

