import streamlit as st
from fetch import get_aircraft_df
import pydeck as pdk

st.set_page_config(layout="wide")
st.title("✈️ YVR Twin Radar")

df = get_aircraft_df()

st.pydeck_chart(pdk.Deck(
    map_style="mapbox://styles/mapbox/light-v9",
    initial_view_state=pdk.ViewState(
        latitude=49.0,
        longitude=-123.0,
        zoom=5,
        pitch=40,
    ),
    layers=[
        pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position='[lon, lat]',
            get_color='[0, 128, 255, 160]',
            get_radius=6000,
        ),
    ],
))

st.sidebar.warning("Not for navigation. Data may be delayed or inaccurate.")

