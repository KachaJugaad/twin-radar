import streamlit as st
import folium
from streamlit_folium import st_folium
from fetch import get_aircraft_df
from geopy.distance import geodesic
import math
import pandas as pd

st.set_page_config(layout="wide")
st.title("Radar – Air Cargo Operational Tracker")

# Bounding Box toggle
bbox_choice = st.radio("Bounding Box", ["YVR", "Wide"], index=0)
BBOX = (47.0, -134.0, 55.0, -118.0) if bbox_choice == "YVR" else (30.0, -150.0, 60.0, -100.0)

# YVR coordinates
YVR_COORDS = (49.1947, -123.1792)
APPROACH_HEADING = 135  # Approx approach angle for YVR RWY 08R

# Load data
df = get_aircraft_df(bbox=BBOX)
df = df.dropna(subset=["lat", "lon", "velocity", "track", "callsign", "baro_alt"])

# Classify aircraft
def haversine_bearing(lat1, lon1, lat2, lon2):
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

    expected_alt = dist_nm * 300
    actual_alt = row["baro_alt"]
    alt_diff = actual_alt - expected_alt

    expected_bearing = haversine_bearing(row["lat"], row["lon"], *YVR_COORDS)
    heading_diff = abs(row["track"] - expected_bearing)
    heading_diff = min(heading_diff, 360 - heading_diff)

    prefix = row["callsign"][:3].upper()
    airline = {
        "ACA": "Air Canada",
        "WJA": "WestJet",
        "DAL": "Delta",
        "UAL": "United",
        "FDX": "FedEx",
        "UPS": "UPS",
    }.get(prefix, "Unknown")

    is_cargo = prefix in ["FDX", "UPS"]
    cargo_type = "Freighter" if is_cargo else ("Belly Cargo" if airline != "Unknown" else "Unknown")

    if eta_min > 20:
        eta_risk = "🟢 Normal"
    elif eta_min > 10:
        eta_risk = "🟠 Tight"
    else:
        eta_risk = "🔴 High Risk"

    if alt_diff > 1500:
        alt_status = "🔻 Too High"
    elif alt_diff < -1500:
        alt_status = "⚠️ Low"
    else:
        alt_status = "✅ OK"

    heading_status = "✅ OK" if heading_diff < 30 else "⚠️ Off-Course"

    is_danger = (
        speed_knots > 300 and
        dist_to_yvr_km < 50 and
        abs(row.get("vertical_rate", 0)) > 1500 and
        alt_status != "✅ OK" and
        heading_status != "✅ OK"
    )

    holding = "🌀 Possible Holding" if speed_knots < 120 and abs(row.get("vertical_rate", 0)) < 100 else ""

    return pd.Series({
        "speed_knots": speed_knots,
        "dist_km": dist_to_yvr_km,
        "eta_min": eta_min,
        "eta_risk": eta_risk,
        "altitude_check": alt_status,
        "heading_check": heading_status,
        "airline": airline,
        "cargo_type": cargo_type,
        "is_danger": is_danger,
        "hold_status": holding
    })

# Enrich DataFrame
df = df.join(df.apply(classify_aircraft, axis=1))

# Cargo toggle view
cargo_view = st.sidebar.checkbox("📦 Focus on Cargo Flights Only")
if cargo_view:
    df = df[df["cargo_type"].isin(["Freighter", "Belly Cargo"])]

# Map
m = folium.Map(location=[49.0, -123.0], zoom_start=5, tiles="CartoDB positron")

for _, row in df.iterrows():
    popup = f"""
        ✈️ <b>{row['callsign']}</b><br>
        Airline: {row['airline']}<br>
        Cargo Type: {row['cargo_type']}<br>
        Speed: {row['speed_knots']:.1f} kn<br>
        ETA: {row['eta_min']:.1f} min – {row['eta_risk']}<br>
        Altitude Check: {row['altitude_check']}<br>
        Heading Check: {row['heading_check']}<br>
        {row['hold_status']}<br>
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

# Legend (static placement that stays visible)
#legend_html = """
#<div style="position: absolute; bottom: 30px; left: 30px; z-index: 9999;
#     background-color: white; padding: 10px; border: 2px solid gray; font-size:14px;">
#<b>🗺️ Legend</b><br>
#<i class="fa fa-plane" style="color:green"></i> 🟢 ETA Normal<br>
#<i class="fa fa-plane" style="color:orange"></i> 🟠 ETA Tight<br>
#<i class="fa fa-plane" style="color:blue"></i> 🔴 ETA Risk<br>
#<i class="fa fa-plane" style="color:red"></i> ☢️ Danger Zone<br>
#<b>🌀 Holding</b>: Possible circling or idle<br>
#<b>📦 Cargo Type</b>: Freighter or Belly<br>
#</div>
#"""
#m.get_root().html.add_child(folium.Element(legend_html))

#st_folium(m, width=1300, height=700)
# Display map
st_folium(m, width=1300, height=700)

# Display legend below map
st.markdown("---")
st.subheader("🗺️ Map Legend & Interpretation Guide")

st.markdown("""
- <span style="color:green">🟢 ETA Normal</span>: Aircraft is on schedule with sufficient buffer.  
- <span style="color:orange">🟠 ETA Tight</span>: Approaching time pressure; may affect sequencing.  
- <span style="color:blue">🔴 ETA Risk</span>: Delayed or late; potential cascading delays.  
- <span style="color:red">☢️ Danger Zone</span>: Abnormal descent, off-course, or unsafe altitude.  
- 🌀 **Holding**: Aircraft circling or hovering; possible ground delay or air congestion.  
- 📦 **Cargo Type**:  
    - **Freighter**: Dedicated cargo aircraft (e.g., FedEx, UPS)  
    - **Belly Cargo**: Passenger flight carrying cargo in hold
""", unsafe_allow_html=True)

if st.checkbox("📦 Show Cargo Flight KPIs"):
    st.dataframe(df[[
        "callsign", "airline", "cargo_type", "speed_knots", "eta_min",
        "eta_risk", "altitude_check", "heading_check", "hold_status", "is_danger"
    ]])

st.sidebar.info("⚠️ OpenSky live air-traffic feed. Not for real-world flight ops.")

# === KPI Scorecard ===
if st.checkbox("📊 Show Operational KPI Summary"):
    total_aircraft = len(df)
    cargo_count = len(df[df["cargo_type"].isin(["Freighter", "Belly Cargo"])])
    avg_eta = df["eta_min"].mean()

    eta_15_df = df[df["eta_min"] < 15]
    n_eta_15 = len(eta_15_df)
    avg_dist_eta15 = eta_15_df["dist_km"].mean() if n_eta_15 else 0
    holding_ratio = len(eta_15_df[eta_15_df["hold_status"] != ""]) / n_eta_15 if n_eta_15 else 0
    crs = n_eta_15 * avg_dist_eta15 * holding_ratio

    # Risk category
    if crs > 500:
        crs_status = "🔴 High"
    elif crs > 200:
        crs_status = "🟠 Moderate"
    else:
        crs_status = "🟢 Low"

    st.markdown(f"""
    ### 📊 Operational KPIs

    - ✈️ **Total Aircraft Tracked**: `{total_aircraft}`
    - 📦 **Cargo Aircraft**: `{cargo_count}`
    - 🕓 **Avg ETA**: `{avg_eta:.1f} min`
    - 🚥 **Congestion Risk Score (CRS)**: `{crs:.1f}` → {crs_status}
    """)

# Legend info below
st.markdown("""
---
### ℹ️ Legend & Definitions

- 🟢 ETA Normal (>20 min)
- 🟠 ETA Tight (10–20 min)
- 🔴 ETA Risk (<10 min)
- ☢️ **Danger Zone**: High speed + low altitude + off-course near YVR
- 🌀 **Holding**: Circling or idling suspected
- 📦 **Cargo Type**: Freighter (UPS/FDX) or Belly Cargo
- 🚥 **CRS**: Congestion Risk Score based on aircraft clustering, distance, and idle state
""")

st.sidebar.info("⚠️ OpenSky live air-traffic feed. Not for real-world flight ops.")

