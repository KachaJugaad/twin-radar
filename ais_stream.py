# --- ais_stream.py ---
import asyncio
import websockets
import json
import threading
from queue import Queue
import streamlit as st

# Shared queue to pass messages to Streamlit
ais_queue = Queue()

# Use Streamlit secrets if available
API_KEY = st.secrets.get("AIS_API_KEY", "public")

# Start background thread to fetch AIS data
def start_ais_stream():
    async def connect_and_stream():
        uri = "wss://stream.aisstream.io/v0/stream"
        payload = {
            "Apikey": API_KEY,
            "BoundingBoxes": [[[-125.0, 47.0], [-122.0, 50.0]]],
            "FilterMessageTypes": ["PositionReport"]
        }

        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps(payload))
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                print("RECEIVED:", data)  # Add this
                ais_queue.put(data)

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(connect_and_stream())

    t = threading.Thread(target=run, daemon=True)
    t.start()

