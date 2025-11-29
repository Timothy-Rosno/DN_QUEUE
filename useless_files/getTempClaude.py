import time
import requests
import json

INTERVAL_S = 1.0           # polling cadence (seconds)
TIMEOUT_S = 10.0

session = requests.Session()

# Machine configuration with different API types
machines = {
    "10.3.118.25": {
        "name": "Hidalgo",
        "api_type": "port5001",
        "last_temp": None,
        "last_status": None,
        "online": None,  # None = unknown, True = online, False = offline
    },
    "10.3.118.54": {
        "name": "Griffin",
        "api_type": "port5001",
        "last_temp": None,
        "last_status": None,
        "online": None,
    },
    "192.168.10.103": {
        "name": "OptiCool",
        "api_type": "quantum_design",
        "port": 47101,
        "last_temp": None,
        "last_status": None,
        "online": None,
    },
    "192.168.10.105": {
        "name": "CryoCore",
        "api_type": "quantum_design",
        "port": 47101,
        "last_temp": None,
        "last_status": None,
        "online": None,
    },
}


def fetch_port5001_data(ip):
    """Fetch data from Hidalgo/Griffin-style machines (port 5001)"""
    base = f"http://{ip}:5001"
    url_meas = f"{base}/channel/measurement/latest"
    url_state = f"{base}/statemachine"

    # measurement
    r = session.get(url_meas, timeout=TIMEOUT_S)
    r.raise_for_status()
    meas = r.json()

    # state
    s = session.get(url_state, timeout=TIMEOUT_S)
    s.raise_for_status()
    state = s.json()

    temperature = meas.get("temperature")
    status = state.get("measuring")
    timestamp = meas.get("datetime")

    return temperature, status, timestamp


def fetch_quantum_design_data(ip, port):
    """Fetch data from OptiCool/CryoCore-style machines (Quantum Design API)"""
    base = f"http://{ip}:{port}"

    # Get temperature
    url_temp = f"{base}/v1/sampleChamber/temperatureControllers/user1/thermometer/properties/sample"
    r = session.get(url_temp, timeout=TIMEOUT_S)
    r.raise_for_status()
    temp_data = json.loads(r.content.decode('utf-8'))
    temperature = temp_data['sample']['temperature']

    # Get system status
    url_status = f"{base}/v1/controller/properties/systemGoal"
    s = session.get(url_status, timeout=TIMEOUT_S)
    s.raise_for_status()
    status_data = json.loads(s.content.decode('utf-8'))
    status = status_data['systemGoal']

    timestamp = None  # Quantum Design API doesn't provide timestamp in the same way

    return temperature, status, timestamp


while True:
    tick_start = time.time()
    try:
        for ip, info in machines.items():
            try:
                # Fetch data based on API type
                if info["api_type"] == "port5001":
                    temperature, status, timestamp = fetch_port5001_data(ip)
                elif info["api_type"] == "quantum_design":
                    temperature, status, timestamp = fetch_quantum_design_data(ip, info["port"])
                else:
                    print(f"[{info['name']}] Unknown API type: {info['api_type']}")
                    continue

                # Machine is reachable - check if it just came online
                if info["online"] == False:
                    print(f"{info['name']} ||| BACK ONLINE")
                info["online"] = True

                # Print current status every iteration
                timestamp_str = f" | at {timestamp}" if timestamp else ""
                temp_str = f"{temperature:.3f}" if temperature is not None else "N/A"
                print(
                    f"{info['name']} ||| "
                    f"T={temp_str} K | status={status}{timestamp_str}"
                )

                # Update baselines
                if temperature is not None:
                    info["last_temp"] = temperature
                if status is not None:
                    info["last_status"] = status

            except Exception as e:
                # Machine is unreachable - print offline status every iteration
                if info["online"] != False:
                    print(f"{info['name']} ||| WENT OFFLINE")
                info["online"] = False
                info["last_temp"] = None
                info["last_status"] = None

                # Print offline status every iteration
                print(f"{info['name']} ||| T=N/A K | status=OFFLINE")

    except Exception as e:
        print(f"[poll-error] {e}")

    # Sleep the remainder of the interval
    elapsed = time.time() - tick_start
    time.sleep(max(0.0, INTERVAL_S - elapsed))
