# Temperature Gateway Service

**Secure temperature monitoring bridge for lab equipment on private university network**

## What is This?

This is a lightweight Python service that runs on a computer within your university network. It:

1. **Reads** temperature data from lab machines (192.168.x.x IPs)
2. **Sends** data to your public Render.com site via secure HTTPS API
3. **Enables** live temperature monitoring without exposing machines to internet

## Architecture

```
┌──────────────────────────────────┐
│   Internet (Anywhere)            │
│   https://qhog.onrender.com      │
│   - Public scheduler access      │
│   - Live temp display            │
└────────────┬─────────────────────┘
             │ HTTPS POST
             │ (Outbound only)
             ↓
┌──────────────────────────────────┐
│   University Network (Private)   │
│                                   │
│   Lab Computer                    │
│   ├─ temperature_gateway.py      │
│   └─ gateway_config.json          │
│                │                  │
│                ↓                  │
│   Machine A    Machine B   ...    │
│   192.168.1.10 192.168.1.11      │
└──────────────────────────────────┘
```

## Requirements

- **Python 3.6+**
- **requests library** (`pip install requests`)
- **Computer on university network** (can be student laptop, lab workstation, or server)
- **API key** (generated during setup)

## Setup Instructions

### Step 1: Get Machine Information

You need to know the machine IDs from your Django database. Run this command on your local dev environment:

```bash
python manage.py shell
```

Then run:
```python
from calendarEditor.models import Machine
for m in Machine.objects.all():
    print(f"ID: {m.id}, Name: {m.name}, IP: {m.ip_address}, API Type: {m.api_type}")
```

### Step 2: Get API Key from Render

1. Go to your Render dashboard
2. Click on **qhog** service
3. Go to **Environment** section
4. Find `TEMPERATURE_GATEWAY_API_KEY`
5. Copy the value (should look like: `VFcENEWY2NfQNbiGZabGa7JovxnRtlbYmp63EAdKSyQ`)

### Step 3: Create Configuration File

1. Copy the example config:
   ```bash
   cp gateway_config.json.example gateway_config.json
   ```

2. Edit `gateway_config.json`:
   ```json
   {
     "api_url": "https://qhog.onrender.com/schedule/api/update-machine-temperatures/",
     "api_key": "YOUR-API-KEY-FROM-RENDER",
     "update_interval": 15,
     "machines": [
       {
         "id": 1,
         "name": "Hidalgo",
         "ip": "192.168.1.10",
         "api_type": "port5001"
       }
     ]
   }
   ```

3. Update:
   - `api_key`: Paste the key from Render
   - `machines`: Add your machines with correct IDs and IPs from Step 1

### Step 4: Install Dependencies

```bash
pip install requests
```

Or if you have a requirements file:
```bash
pip install -r requirements.txt
```

### Step 5: Run the Gateway

```bash
python temperature_gateway.py
```

You should see:
```
==============================================================
Temperature Gateway Service
==============================================================
Monitoring 4 machines
Update interval: 15 seconds
API endpoint: https://qhog.onrender.com/schedule/api/update-machine-temperatures/

Press Ctrl+C to stop

==============================================================

[2025-11-11 01:30:00] Reading temperatures...
  ✅ Hidalgo: 4.20K
  ✅ Griffin: 3.50K
  ❌ OptiCool: N/A
  ✅ CryoCore: 10.15K
  Sending 4 readings to API...
  ✅ Successfully updated 4 machines

Waiting 15 seconds until next update...
```

## Running in Background

### Option 1: Screen Session (Easiest)

```bash
# Start screen session
screen -S temp-gateway

# Run the script
python temperature_gateway.py

# Detach: Press Ctrl+A, then D

# Reattach later
screen -r temp-gateway
```

### Option 2: tmux

```bash
# Start tmux session
tmux new -s temp-gateway

# Run the script
python temperature_gateway.py

# Detach: Press Ctrl+B, then D

# Reattach later
tmux attach -t temp-gateway
```

### Option 3: systemd Service (Linux)

Create `/etc/systemd/system/temp-gateway.service`:

```ini
[Unit]
Description=Lab Equipment Temperature Gateway
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/temperature_gateway
ExecStart=/usr/bin/python3 temperature_gateway.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable temp-gateway
sudo systemctl start temp-gateway
sudo systemctl status temp-gateway
```

## Configuration Options

### `api_url`
- The Render API endpoint
- Should always be: `https://qhog.onrender.com/schedule/api/update-machine-temperatures/`

### `api_key`
- Secret key for authentication
- Get from Render environment variables
- Keep this secure! Don't commit to git

### `update_interval`
- How often to update temperatures (in seconds)
- Default: 15 seconds
- Recommended range: 10-60 seconds
- Too frequent = unnecessary network traffic
- Too slow = stale temperature data

### Machine Configuration

**For Port 5001 API (Hidalgo/Griffin style):**
```json
{
  "id": 1,
  "name": "Hidalgo",
  "ip": "192.168.1.10",
  "api_type": "port5001"
}
```

**For Quantum Design API (OptiCool/CryoCore):**
```json
{
  "id": 3,
  "name": "OptiCool",
  "ip": "192.168.1.20",
  "api_type": "quantum_design",
  "api_port": 47101
}
```

**For machines without API:**
```json
{
  "id": 5,
  "name": "Legacy Machine",
  "ip": "",
  "api_type": "none"
}
```

## Troubleshooting

### Gateway can't reach machines
- **Check**: Are you on the university network?
- **Check**: Can you ping the machine IPs?
- **Check**: Are the IPs correct in gateway_config.json?

### API key invalid
- **Check**: Did you copy the full key from Render?
- **Check**: Are there extra spaces in the config file?
- **Fix**: Regenerate key in Render and update config

### Render app sleeping (free tier)
- Expected on free tier (spins down after 15 min inactivity)
- Gateway will retry automatically
- First request wakes it up (30-60 sec delay)
- Subsequent requests work normally
- GitHub Actions pings every 5 min to keep alive

### Machine shows offline but is running
- **Check**: Is the machine API responding? Try: `curl http://192.168.1.10:5001/channel/measurement/latest`
- **Check**: Firewall blocking? Some machines may block requests
- **Check**: API type correct? (port5001 vs quantum_design)

### Logs say "connection refused"
- Machine may be powered off
- API service may not be running on machine
- IP address may be wrong

## Security Notes

✅ **Secure:**
- Only outbound HTTPS connections (port 443)
- API key authentication
- No inbound connections to university network
- No VPN or port forwarding needed

❌ **Keep Secret:**
- `gateway_config.json` (contains API key)
- Never commit to public repository
- Don't share API key

## FAQ

**Q: Does this work if I'm off-campus?**
A: No. The gateway must run on a computer that can reach the machines' local IPs (192.168.x.x). That means it must be on the university network.

**Q: Can I run this on my laptop?**
A: Yes! As long as your laptop is on the university network when running. If you close your laptop or leave campus, temperatures stop updating (but scheduler still works).

**Q: What if the gateway goes down?**
A: The main scheduler on Render continues working normally. Temperatures just show as stale/unknown. No other features are affected.

**Q: How much network bandwidth does this use?**
A: Very little. Each update is ~1KB. At 15-second intervals with 5 machines, that's ~288KB per hour or ~7MB per day.

**Q: Can I run multiple gateways?**
A: Yes, but not recommended. Multiple gateways would make redundant updates. One gateway can handle all machines.

## Support

If you need help:
1. Check this README
2. Check `NETWORK_LIMITATIONS.md` in main project
3. Check Render logs for API errors
4. Verify gateway_config.json is valid JSON

---

**Generated API Key:** `VFcENEWY2NfQNbiGZabGa7JovxnRtlbYmp63EAdKSyQ`

**Remember to add this to Render environment variables!**
