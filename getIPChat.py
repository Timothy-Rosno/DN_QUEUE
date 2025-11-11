# -*- coding: utf-8 -*-
"""
Scan subnet to find dilution fridge by querying http://10.3.118.X:5001/statemachine
"""

import requests

BASE_IP = "10.3.118."
PORT = 5001
ENDPOINT = "statemachine"
TIMEOUT = 1.5  # seconds

for i in range(0, 256):
    ip = f"{BASE_IP}{i}"
    url = f"http://{ip}:{PORT}/{ENDPOINT}"
    try:
        r = requests.get(url, timeout=TIMEOUT)
        if r.status_code == 200:
            print(f"[+] Response from {ip}: {r.text[:100]}...")  # show first 100 chars
        else:
            print(f"[-] {ip}: Status {r.status_code}")
    except requests.exceptions.RequestException:
        pass  # no response, skip

print("Scan complete.")