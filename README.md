# Lab Equipment Queue Scheduler

A Django web application for managing shared access to laboratory cryogenic equipment (PPMS fridges). Users submit job requests with specific experimental requirements, and the system automatically assigns them to compatible machines and manages the execution queue.

**Live Instance:** https://qhog.onrender.com

---

## What This Project Does

This application solves the problem of scheduling access to expensive, shared lab equipment. Research labs often have multiple users competing for limited equipment time. This system:

1. **Accepts job requests** - Users submit their experimental requirements (temperature, magnetic field, duration, etc.)
2. **Automatically assigns machines** - Matching algorithm finds compatible equipment based on capabilities
3. **Manages the queue** - Each machine has its own queue with position tracking and wait time estimates
4. **Sends real-time notifications** - WebSocket-based updates when your job moves up, reaches "ON DECK", starts running, etc.
5. **Provides admin oversight** - Lab managers can reorder queues, approve rush jobs, and manage users

### Key Features

- **Smart Machine Matching** - Algorithm filters by temperature range, magnetic field specs, connections, and optical capabilities
- **Real-time Updates** - WebSocket connections push live queue changes to all users
- **Preset System** - Save and share common experiment configurations
- **User Approval Workflow** - Admins approve new user registrations before they can submit jobs
- **Slack Integration** - Optional notifications via Slack DMs with automatic user matching
- **Temperature Monitoring** - Live temperature readings from lab equipment (requires local network gateway)
- **Automatic Reminders** - Checkout and check-in reminders to ensure equipment availability
- **Measurement Archival** - Preserve experimental data with file uploads and preset snapshots
- **Granular Notification Control** - Customize which notifications you receive (38+ types)
- **Secure Slack Links** - One-time login tokens for notification links (24-hour expiration)

---

## Architecture

### Technology Stack

- **Backend:** Django 4.2.25 (Python web framework)
- **Real-time:** Django Channels + Redis (WebSocket support)
- **Database:** PostgreSQL via Supabase (production), SQLite (local dev)
- **Server:** Daphne ASGI server (handles HTTP + WebSockets)
- **Hosting:** Render.com (web service + Redis)
- **Deployment:** Automatic from GitHub via `render.yaml` blueprint

### How It Works

```
User submits job request
    ↓
Matching algorithm evaluates requirements:
- Temperature range (min/max in Kelvin)
- Magnetic field strength (B_x, B_y, B_z in Tesla)
- Magnetic field direction (parallel/perpendicular/both/none)
- DC/RF connections needed
- Daughterboard compatibility
- Optical capabilities
    ↓
System selects machine with shortest wait time
    ↓
Entry added to machine's queue
    ↓
WebSocket broadcasts update to all connected users
    ↓
Notifications sent (in-app, Slack if configured)
    ↓
When job reaches position #1: "ON DECK" notification
    ↓
Admin starts job → status changes to "running"
    ↓
Admin completes job → entry archived
```

### Data Model

**Machine** - Lab equipment with capabilities:
- Temperature range (min_temp, max_temp in Kelvin)
- Magnetic field specs (b_field_x, b_field_y, b_field_z in Tesla)
- Connection counts (dc_lines, rf_lines)
- Daughterboard compatibility
- Optical capabilities
- Current status (idle/running/cooldown/maintenance)

**QueueEntry** - User's job request:
- Experimental requirements (matches Machine fields)
- Assigned machine (auto-selected by algorithm)
- Queue position (1 = "ON DECK")
- Status (queued/running/completed/cancelled)
- Duration estimate
- Timestamps (submitted, started, completed)

**QueuePreset** - Saved experiment configuration:
- All requirement fields from QueueEntry
- Public/private visibility
- Creator and edit history

**Notification** - In-app notification:
- Type (queue_added, on_deck, job_started, etc.)
- Recipient user
- Related objects (queue entry, preset, machine)
- Read status

**Additional Models:**
- **NotificationPreference** - User notification settings (38+ toggleable types, delivery methods)
- **OneTimeLoginToken** - Secure tokens for Slack notification links (24-hour expiration)
- **ArchivedMeasurement** - Historical experimental data with file uploads and preset snapshots
- **UserProfile** - Extended user data (Slack ID, department, approval status)

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for complete technical documentation.

### Additional Features

**Measurement Archival System:**
- Archive completed experiments with file uploads (PDF, images, data files)
- Preserves full experimental history including preset snapshots (JSON)
- Maintains machine references even after equipment is decommissioned
- Access via Admin Dashboard → Machine Management → Archived Measurements
- Searchable by machine, user, date range, and measurement type

**Secure Authentication for Slack Links:**
- One-time login tokens (`OneTimeLoginToken` model) for notification links
- 24-hour expiration with automatic cleanup
- Single-use tokens prevent unauthorized access
- Enables secure login from Slack without storing passwords
- Tokens automatically bind to user and notification for audit trail

**Granular Notification Preferences:**
- User-configurable notification settings (`NotificationPreference` model)
- Control 38+ specific notification types individually:
  - Preset notifications (created, edited, deleted)
  - Queue notifications (position changes, on deck, started, completed)
  - Machine notifications (status changes, maintenance alerts)
  - Admin notifications (user approvals, rush job updates)
  - Account notifications (profile changes, security alerts)
- Choose delivery methods: in-app notifications, email (when configured)
- Access via Profile → Notification Settings

**Automatic Reminder System:**
- Checkout reminders: Automatically sent 2 hours after job starts
- Check-in reminders: Prompt users to verify they're still using equipment
- Middleware-based system (no Celery required)
- Reminders sent on next page load after due time
- Snooze functionality: Extend checkout time if still working
- Automatic cancellation if user checks out early

**Machine Deletion Safety:**
- `machine_name_text` fallback preserves equipment names in historical records
- Queue entries and archived measurements maintain references
- Prevents data loss when decommissioning equipment
- Admin warning before deleting machines with active queue entries

**Slack Member ID Auto-Lookup:**
- Three-tier automatic matching strategy:
  1. Email address (most reliable)
  2. Full name (first + last)
  3. Username (fallback)
- One-time lookup with caching in user profile
- Manual override available if automatic match fails
- Lookup runs automatically on first notification

---

## Setting Up This Project

### Prerequisites

**Required Accounts (all free tier):**
- GitHub account
- Render.com account (sign up with GitHub)
- Supabase.com account (PostgreSQL database)

**Optional:**
- UptimeRobot account (prevents free tier spin-down)
- Slack workspace (for notifications)

**Local Development (optional):**
- Python 3.9 or higher
- Redis (for WebSocket testing)
- Git

### Installation Steps

#### 1. Clone Repository

```bash
git clone https://github.com/Timothy-Rosno/DN_QUEUE.git
cd schedulerTEST
```

#### 2. Create Supabase Database

1. Go to https://supabase.com and create account
2. Create new project:
   - Name: `queue-system`
   - Database Password: Generate strong password (save it!)
   - Region: East US or closest to you
   - Plan: Free (500MB)
3. Wait 2-3 minutes for provisioning
4. Get connection string:
   - Go to Settings → Database
   - Find "Connection String" section
   - Select "URI" tab (NOT "Connection pooling")
   - Copy the string (looks like `postgresql://postgres.xxx:[YOUR-PASSWORD]@...`)
   - **IMPORTANT:** Replace `[YOUR-PASSWORD]` with your actual database password
5. Save complete connection string for next step

**Example final DATABASE_URL:**
```
postgresql://postgres.abcd123:MyPassword456!@aws-0-us-east-1.pooler.supabase.com:5432/postgres
```

#### 3. Deploy to Render

1. Go to https://render.com and sign up with GitHub
2. Authorize Render to access your repositories
3. In Render dashboard, click **"New +"** → **"Blueprint"**
4. Connect your GitHub repository
5. Select the repository from the list
6. Click **"Connect"**
7. Render detects `render.yaml` and shows deployment plan:
   - Web service: `qhog` (Python/Django)
   - Redis: `qhog-redis` (for WebSockets)
8. Click **"Apply"**

This will start deployment but it will fail initially - that's expected. We need to add environment variables first.

#### 4. Configure Environment Variables

1. In Render dashboard, click on your web service (e.g., `qhog`)
2. Go to **"Environment"** tab
3. Add these required variables:

| Variable | Value | Notes |
|----------|-------|-------|
| `DATABASE_URL` | Your Supabase connection string | From step 2 - must include actual password |
| `ALLOWED_HOSTS` | `your-app.onrender.com` | Replace with your actual Render service name |
| `BASE_URL` | `https://your-app.onrender.com` | Include `https://` prefix |
| `DJANGO_SUPERUSER_USERNAME` | `admin` | Your admin username |
| `DJANGO_SUPERUSER_EMAIL` | `admin@example.com` | Your email |
| `DJANGO_SUPERUSER_PASSWORD` | Strong password | Save this - you'll need it to log in |

**Note:** `SECRET_KEY`, `BACKUP_API_KEY`, `DEBUG`, and `REDIS_URL` are already configured by `render.yaml`

4. Click **"Save Changes"** at top

This triggers automatic deployment.

#### 5. Monitor Deployment

1. Go to **"Logs"** tab in your Render service
2. Watch for these stages:
   - Installing dependencies
   - Collecting static files
   - Running database migrations
   - Loading initial data (3 default machines)
   - Creating superuser
   - Starting Daphne server
3. Wait for status to change to **"Live"** (green)
4. Typical deployment time: 5-8 minutes

#### 6. Verify Deployment

1. Click your service URL (e.g., `https://qhog.onrender.com`)
2. You should see homepage with Login/Register buttons
3. Click **"Login"**
4. Enter superuser credentials from step 4
5. You should see Admin Dashboard

**Check default data loaded:**
- Admin Dashboard → Machine Management
- Should show default machines loaded from `initial_data.json`
  - Example machines: Hidalgo, Griffin, or similar PPMS-style equipment
  - Machine names are configurable and may vary by lab

---

## Environment Variables Reference

### Required for Production

| Variable | Purpose | Example | Where to Set |
|----------|---------|---------|--------------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql://postgres.xxx:pass@...` | Render Environment |
| `REDIS_URL` | Redis for WebSockets | `redis://red-xxx:6379` | Auto-linked by render.yaml |
| `SECRET_KEY` | Django cryptography | Auto-generated | Auto-generated by render.yaml |
| `DEBUG` | Debug mode (False in prod) | `False` | Pre-set in render.yaml |
| `ALLOWED_HOSTS` | Allowed domains | `qhog.onrender.com` | Render Environment |
| `BASE_URL` | Full site URL | `https://qhog.onrender.com` | Render Environment |
| `DJANGO_SUPERUSER_USERNAME` | Admin username | `admin` | Render Environment |
| `DJANGO_SUPERUSER_EMAIL` | Admin email | `admin@example.com` | Render Environment |
| `DJANGO_SUPERUSER_PASSWORD` | Admin password | Strong password | Render Environment |

### Optional Features

| Variable | Purpose | When Needed |
|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | Slack notifications | See [Slack Setup](#slack-integration) |
| `TEMPERATURE_GATEWAY_API_KEY` | Temperature monitoring | See [Temperature Gateway](#temperature-monitoring) |
| `BACKUP_API_KEY` | Database backups | Auto-generated by render.yaml |

### Local Development (.env file)

For local development, copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env`:
```bash
SECRET_KEY=your-local-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
REDIS_URL=redis://127.0.0.1:6379
SLACK_BOT_TOKEN=xoxb-your-token  # Optional
BASE_URL=http://127.0.0.1:8000
```

**Database:** If `DATABASE_URL` is not set, SQLite is used automatically (perfect for local dev).

---

## Optional Features

### UptimeRobot (Prevent Free Tier Spin-Down)

Render's free tier spins down after 15 minutes of inactivity, causing 30-60 second cold starts. Use UptimeRobot to keep the app responsive:

1. Create free account at https://uptimerobot.com
2. Add new monitor:
   - **Type:** HTTP(s)
   - **URL:** `https://your-app.onrender.com/schedule/health/`
   - **Interval:** 5 minutes
3. Save

The health endpoint gets pinged every 5 minutes, preventing spin-down.

### Slack Integration

Send queue notifications via Slack DMs. Users are automatically matched using a three-tier strategy:
1. **Email address** (most reliable) - Matches Django user email with Slack email
2. **Full name** (first + last) - Matches with Slack display name or real name
3. **Username** (fallback) - Matches Django username with Slack username

The system performs lookup automatically on the first notification, caches the Slack Member ID in the user's profile, and reuses it for future notifications. Manual Slack Member ID entry is available in user profiles if automatic matching fails.

**Setup:**

1. Create Slack app at https://api.slack.com/apps
   - Click "Create New App" → "From scratch"
   - Name it (e.g., "Lab Queue Bot")
   - Select your workspace
2. Add bot token scopes:
   - Go to OAuth & Permissions
   - Add scopes: `chat:write`, `users:read`, `users:read.email`
3. Install to workspace:
   - Click "Install to Workspace"
   - Authorize
   - Copy "Bot User OAuth Token" (starts with `xoxb-`)
4. Add to Render:
   - Render Dashboard → Environment
   - Add variable: `SLACK_BOT_TOKEN` = `xoxb-your-token`
   - Save (triggers redeploy)

**See [`SLACK_SETUP.md`](./SLACK_SETUP.md) for detailed instructions.**

### Temperature Monitoring

Display live temperature readings from lab equipment. **This requires a separate Python script (`temperature_gateway.py`) running continuously on a computer within your lab's local network.**

**Why:** Lab equipment has local IP addresses (192.168.x.x) that Render cannot reach from the cloud. The temperature gateway acts as a bridge - it runs locally to fetch temperatures from equipment, then pushes updates to your Render deployment via authenticated API calls.

**Setup:**

1. Generate API key:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. Add to Render environment: `TEMPERATURE_GATEWAY_API_KEY=<generated-key>`
3. On lab network computer:
   ```bash
   cd temperature_gateway
   pip install -r requirements.txt
   cp gateway_config.json.example gateway_config.json
   # Edit gateway_config.json with machine IPs and API key
   python temperature_gateway.py
   ```
4. Set up as scheduled task (cron/Task Scheduler)

**See [`temperature_gateway/README.md`](./temperature_gateway/README.md) and [`NETWORK_LIMITATIONS.md`](./NETWORK_LIMITATIONS.md) for details.**

---

## Local Development

### Setup

```bash
# Clone repository
git clone https://github.com/Timothy-Rosno/DN_QUEUE.git
cd schedulerTEST

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env as needed (SQLite used by default)

# Run migrations
python manage.py migrate

# Load default machines
python manage.py load_initial_data

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

Visit http://127.0.0.1:8000

### Redis (for WebSocket testing)

**macOS:**
```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian:**
```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

Add to `.env`:
```
REDIS_URL=redis://127.0.0.1:6379
```

### Running Tests

```bash
python manage.py test
```

---

## Project Structure

```
schedulerTEST/
├── calendarEditor/          # Main app - queue, machines, notifications
│   ├── models.py           # Machine, QueueEntry, QueuePreset, Notification,
│   │                       # NotificationPreference, ArchivedMeasurement, OneTimeLoginToken
│   ├── views.py            # Queue submission, presets
│   ├── admin_views.py      # Admin dashboard
│   ├── consumers.py        # WebSocket consumers
│   ├── matching_algorithm.py  # Machine assignment logic
│   ├── notifications.py    # Notification delivery, Slack integration
│   └── middleware.py       # Reminder checking
│
├── userRegistration/        # Authentication, user profiles
│   ├── models.py           # UserProfile
│   ├── views.py            # Registration, login
│   └── middleware.py       # User approval checking
│
├── mysite/                  # Django project config
│   ├── settings.py         # Environment variables loaded here
│   ├── urls.py             # URL routing
│   └── asgi.py             # ASGI config (WebSockets)
│
├── templates/               # HTML templates
├── static/                  # CSS, JavaScript
├── temperature_gateway/     # Optional temp monitoring script
│
├── manage.py               # Django management
├── requirements.txt        # Python dependencies
├── render.yaml             # Render deployment config
├── initial_data.json       # Default machines
│
├── README.md               # This file
├── ARCHITECTURE.md         # Technical documentation
├── PROJECT_STRUCTURE.md    # Directory breakdown
├── QUEUE_SYSTEM_INSTALLATION_GUIDE.md  # Detailed setup
├── SLACK_SETUP.md          # Slack integration
├── DATABASE_BACKUP.md      # Backup procedures
└── NETWORK_LIMITATIONS.md  # Cloud deployment constraints
```

---

## Documentation

### Setup & Deployment
- **[QUEUE_SYSTEM_INSTALLATION_GUIDE.md](./QUEUE_SYSTEM_INSTALLATION_GUIDE.md)** - Extremely detailed step-by-step guide
- **[RENDER_DEPLOYMENT_GUIDE.md](./RENDER_DEPLOYMENT_GUIDE.md)** - Render-specific deployment
- **[SLACK_SETUP.md](./SLACK_SETUP.md)** - Slack integration

### Architecture & Maintenance
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Complete technical documentation
- **[PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md)** - Directory organization
- **[NETWORK_LIMITATIONS.md](./NETWORK_LIMITATIONS.md)** - Cloud deployment constraints
- **[DATABASE_BACKUP.md](./DATABASE_BACKUP.md)** - Backup/restore procedures
- **[GITHUB_ACTIONS_SETUP.md](./GITHUB_ACTIONS_SETUP.md)** - Automated backups

---

## How to Use (End Users)

### Submitting a Job Request

1. Log in to the system
2. Click **"Submit Queue Entry"**
3. Fill in experimental requirements:
   - Temperature range needed
   - Magnetic field specs
   - Connection requirements (DC/RF lines)
   - Daughterboard type
   - Optical access needed
   - Estimated duration
4. Submit - system automatically assigns best machine
5. Track your position in **"My Queue"**

### Using Presets

Save common configurations:

1. Go to **"Submit Queue Entry"**
2. Click **"Save as Preset"** after filling form
3. Name your preset
4. Choose public (everyone can see) or private (only you)

Load preset:
1. Click **"Load Preset"** on submission form
2. Select from dropdown
3. Form auto-fills with preset values

### Notifications

Real-time notifications appear in bell icon (top-right):
- Your job added to queue
- Your position changed
- **"ON DECK"** - You're next! (position #1)
- Your job started
- Your job completed

Configure which notifications you receive in Profile → Notification Settings.

### Checkout Reminders

When your job is running, you'll receive automatic reminders:
- **2-hour checkout reminder** - Sent 2 hours after your job starts
- **Check-in reminder** - Periodic prompts to verify you're still using equipment

**Responding to reminders:**
1. If you're done: Click **"Check Out"** to complete your job
2. If still working: Click **"Snooze"** to extend your time
3. Ignore reminder: Will be sent again on next page load after due time

Reminders help ensure equipment availability for other users.

---

## How to Use (Admins)

### Admin Dashboard

Access via top-right menu after logging in as staff user.

**User Management:**
- Approve/reject new user registrations
- View all users
- Manage user permissions

**Machine Management:**
- Edit machine specifications
- Update machine status (idle/running/maintenance)
- View queue for each machine

**Queue Management:**
- View all queue entries
- Reorder queue (move up/down)
- Reassign entries to different machines
- Set specific queue position

**Rush Jobs:**
- Review rush job requests
- Approve (moves to position #1)
- Reject with reason

### Starting/Completing Jobs

When a user's job is ready to run:

1. Admin Dashboard → Queue Management
2. Find entry at position #1
3. Click **"Start Job"**
4. Entry status changes to "running"
5. User receives notification

When job completes:
1. Click **"Complete Job"**
2. Entry status changes to "completed"
3. Next entry moves to position #1
4. User receives "ON DECK" notification

### Archiving Measurements

Preserve experimental data for completed jobs:

**Creating Archives:**
1. Admin Dashboard → Machine Management → Select Machine
2. Click **"Archived Measurements"**
3. Click **"Add New Archive"**
4. Fill in details:
   - Select user and date
   - Upload files (PDFs, images, data files)
   - System automatically saves preset snapshot (JSON)
   - Add notes about the experiment
5. Save

**Viewing Archives:**
- Search by machine, user, date range, or measurement type
- Download archived files
- View preset configurations used
- Historical data preserved even if machines are decommissioned

Archives maintain data integrity with automatic machine name fallback when equipment is removed from service.

---

## Troubleshooting

### Deployment Failed on Render

**Check:**
1. All environment variables set correctly
2. `DATABASE_URL` has actual password (not `[YOUR-PASSWORD]`)
3. Supabase database is running
4. Review Render logs for specific error

### Can't Log In

**Check:**
1. Using correct credentials from `DJANGO_SUPERUSER_*` env vars
2. User is approved (if not superuser)
3. Check Render logs for "Superuser created successfully"

### 502 Bad Gateway

**Solution:**
1. Wait 2-3 minutes (app may be waking from spin-down)
2. Verify Redis is running (Render dashboard)
3. Check Render logs for crashes

### No Machines Showing

**Solution:**
1. Check Render logs for "load_initial_data" output
2. Verify `initial_data.json` exists in repo
3. May need manual deploy

### Slack Not Working

**Check:**
1. `SLACK_BOT_TOKEN` set in Render
2. Token starts with `xoxb-`
3. Bot has scopes: `chat:write`, `users:read`, `users:read.email`
4. Bot installed to workspace
5. Render logs for Slack errors

---

## Free Tier Limitations

**Render:**
- Spins down after 15 min inactivity (use UptimeRobot)
- First request after spin-down: 30-60 sec cold start
- Limited CPU/memory (sufficient for lab use)

**Supabase:**
- 500MB database storage
- Database pauses after 7 days inactivity (auto-resumes)

**Upgrading:**
- Render $7/month: No spin-down, faster
- Supabase $25/month: 8GB storage, better performance

---

## Contributing

This is a specific lab instance, but contributions are welcome:

1. Fork repository
2. Create feature branch
3. Test locally
4. Submit pull request

---

## License

MIT License

---

## Contact

**Repository:** https://github.com/Timothy-Rosno/DN_QUEUE
**Live Instance:** https://qhog.onrender.com

For bugs or feature requests, open an issue on GitHub.

---

**Last Updated:** November 2025
# Test deployment verification
