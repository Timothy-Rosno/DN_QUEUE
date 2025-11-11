import time
import math
import requests

INTERVAL_S = 1.0           # polling cadence (seconds)
TIMEOUT_S = 10.0
TEMP_EPS = 0.05            # only notify if |ΔT| >= 0.05 K
DEBOUNCE_S = 5.0           # min seconds between notifications per machine

session = requests.Session()

# Maintain independent state per machine
machines = {
    "10.3.118.25": {
        "name": "Hidalgo",
        "last_temp": None,
        "last_measuring": None,
        "last_notify_ts": 0.0,
    },
    "10.3.118.54": {
        "name": "Griffin",
        "last_temp": None,
        "last_measuring": None,
        "last_notify_ts": 0.0,
    },
      "192.168.10.103": {
      "name": "OptiCool",
      "last_temp": None,
      "last_state": None,
      "last_notify_ts": 0.0,
  }
}


def significant_temp_change(prev, cur, eps=TEMP_EPS):
    if cur is None or (isinstance(cur, float) and math.isnan(cur)):
        return False
    if prev is None:
        return True
    return abs(cur - prev) >= eps


def can_notify(machine_info, now):
    return (now - machine_info["last_notify_ts"]) >= DEBOUNCE_S


while True:
    tick_start = time.time()
    try:
        for ip, info in machines.items():
            base = f"http://{ip}:5001"
            url_meas = f"{base}/channel/measurement/latest"
            url_state = f"{base}/statemachine"

            # measurement
            r = session.get(url_meas, timeout=TIMEOUT_S)
            r.raise_for_status()
            meas = r.json()
            print(meas)
            # state
            s = session.get(url_state, timeout=TIMEOUT_S)
            s.raise_for_status()
            state = s.json()

            # pull only meaningful fields
            t = meas.get("temperature")
            measuring = state.get("measuring")

            # decide if anything meaningful changed
            temp_changed = significant_temp_change(info["last_temp"], t)
            measuring_changed = (
                measuring is not None and measuring != info["last_measuring"]
            )

            now = time.time()
            if (temp_changed or measuring_changed) and can_notify(info, now):
                print(
                    f"{info['name']} ||| "
                    f"T={t:.3f} K | measuring={measuring} | at {meas.get('datetime')}"
                )
                info["last_notify_ts"] = now

            # update baselines *after* decision
            if t is not None:
                info["last_temp"] = t
            if measuring is not None:
                info["last_measuring"] = measuring

    except Exception as e:
        print(f"[poll-error] {e}")

    # sleep the remainder of the interval
    elapsed = time.time() - tick_start
    time.sleep(max(0.0, INTERVAL_S - elapsed))
