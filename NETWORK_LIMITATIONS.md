# Network Limitations for Cloud Deployment

## Temperature Monitoring in Production

⚠️ **IMPORTANT**: Live temperature monitoring will **NOT work** when deployed to Render.com (or any cloud hosting).

### Why?

The lab equipment machines have **local network IP addresses** (e.g., `192.168.x.x`, `10.x.x.x`) that are only accessible from within your lab's network. Render's servers are hosted in the cloud and cannot reach these private IPs.

### What This Means

**✅ Still Works:**
- Viewing machine specifications
- Booking/queueing experiments
- Check-in/checkout system
- Slack notifications
- Queue management
- All scheduling features

**❌ Won't Work:**
- Real-time temperature updates
- Live machine status (Connected/Disconnected)
- Temperature polling from frontend

### What You'll See in Production

- Machines will show as **"Status: Unknown"** or last cached temperature
- Temperature readings won't update
- Machine availability status still works (based on queue, not live connection)

### Solutions (If You Need Live Monitoring)

#### Option 1: Accept the Limitation ✅ Recommended
- Use the app primarily for scheduling
- Check temperatures manually on lab network when needed
- Most users only need scheduling functionality

#### Option 2: Tunnel/Proxy Setup (Advanced)
Set up a tunnel from your lab network to expose machine APIs:

**Using ngrok:**
```bash
# On a computer in the lab network that stays on 24/7
ngrok http 192.168.x.x:5001  # For each machine
```

Then update machine IPs in Django admin to use ngrok URLs like:
`https://abc123.ngrok-free.app` instead of `192.168.x.x`

**Downsides:**
- Requires computer running 24/7 in lab
- ngrok free tier has connection limits
- URLs change on restart (unless paid plan)
- Security concerns exposing lab equipment to internet

#### Option 3: Hybrid Deployment (Complex)
- Keep scheduler on Render (public access)
- Run separate local service just for temperature updates
- Requires VPN or secure tunnel between local service and Render database

### Current Configuration

The temperature monitoring code is still in the codebase but will fail gracefully:
- `machine.update_temperature_cache()` - Will mark machines as offline
- Frontend polling continues but gets stale/empty data
- No errors shown to users, just "Status: Unknown"

### Recommendation for Lab Use

**Best approach:** Deploy to Render for scheduling, but keep a local dev server running on lab network for anyone who needs real-time temperature monitoring while physically in the lab.

**To run local server:**
```bash
python manage.py runserver 0.0.0.0:8000
```

Then lab members can access:
- `https://qhog.onrender.com` - From anywhere, for scheduling
- `http://LAB-COMPUTER-IP:8000` - From lab network only, for temps

Both access the same PostgreSQL database on Render!
