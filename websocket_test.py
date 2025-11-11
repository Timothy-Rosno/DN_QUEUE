import json
import websocket
import time

# --- Connect to WebSocket ---
ws_url = 'ws://10.3.118.25:5002/channel/measurement/listen'
ws = websocket.create_connection(ws_url, timeout=10)

# --- Set duration ---
duration = 30  # seconds
end_time = time.time() + duration

try:
    while time.time() < end_time:
        resp = ws.recv()
        data = json.loads(resp)
        
        # Extract and print Temperature
        temperature = data.get("temperature")
        if temperature is not None:
            print(temperature)
finally:
    ws.close()
    print("WebSocket connection closed.")
