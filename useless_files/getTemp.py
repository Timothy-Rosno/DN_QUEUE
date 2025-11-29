import requests
from time import sleep

DEVICE_IP = '10.3.118.25'
LOOP_TIMEOUT = 20

# Gonna have to handle the machines diffferently. Get one as proof of concept.

TIMEOUT = 10
url = f'http://{DEVICE_IP}:5001/channel/measurement/latest'

try:
    print(f"Gonna get the temperature now:")
    response = requests.get(url, timeout=TIMEOUT)
    data = response.json()  # this is a dict
    
    # Just get the temperature value
    temperature = data.get("temperature")
    if temperature is not None:
        print(temperature)
        
except requests.exceptions.RequestException as e:
    print(f"Error requesting data: {e}")

sleep(1)

print(f"Gonna get the statuses now:")

url = f'http://{DEVICE_IP}:5001/statemachine'
try:
    response = requests.get(url, timeout=TIMEOUT)
    data = response.json()

    #Just get the measuring status
    measuring = data.get("measuring")
    if measuring is not None:
        print(f"Measuring: {measuring}")
except Exception as e:
    print(f"Filure to retreiveee meaeurbeu status: {e}")