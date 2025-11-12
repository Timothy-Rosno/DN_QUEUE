# Complete Installation Guide: Lab Queue Management System

This guide will walk you through setting up your own instance of the Lab Queue Management System from scratch using free-tier services.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Step 1: Fork GitHub Repository](#step-1-fork-github-repository)
4. [Step 2: Set Up Supabase Database](#step-2-set-up-supabase-database) #Actually changed to 
5. [Step 3: Set Up Render Web Service](#step-3-set-up-render-web-service)
6. [Step 4: Set Up Render Redis](#step-4-set-up-render-redis)
7. [Step 5: Configure Environment Variables](#step-5-configure-environment-variables)
8. [Step 6: Deploy Application](#step-6-deploy-application)
9. [Step 7: Set Up UptimeRobot (Keepalive)](#step-7-set-up-uptimerobot-keepalive)
10. [Step 8: Initial Configuration](#step-8-initial-configuration)
11. [Step 9: Set Up Slack Integration (Optional)](#step-9-set-up-slack-integration-optional)
12. [Step 10: Set Up Temperature Gateway (Optional)](#step-10-set-up-temperature-gateway-optional)
13. [Troubleshooting](#troubleshooting)
14. [Maintenance](#maintenance)

---

## Overview

### What You'll Need

**Required Accounts (All Free Tier):**
- GitHub account (code hosting)
- Render account (web hosting + Redis)
- Supabase account (PostgreSQL database)
- UptimeRobot account (keepalive monitoring)

**Optional Accounts:**
- Slack workspace (for notifications)

**Estimated Setup Time:** 45-60 minutes

### Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   UptimeRobot   │────▶│  Render Web App  │────▶│    Supabase     │
│  (Keepalive)    │     │   (Django/Daphne)│     │  (PostgreSQL)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │   Render Redis   │
                        │ (Channels/Cache) │
                        └──────────────────┘
```

---

## Prerequisites

### 1. Install Git (if not already installed)

**Windows:** Download from https://git-scm.com/download/win

**macOS:**
```bash
# Install via Homebrew
brew install git

# OR use Xcode Command Line Tools
xcode-select --install
```

**Linux:**
```bash
sudo apt-get install git  # Ubuntu/Debian
sudo yum install git      # CentOS/RHEL
```

### 2. Create Required Accounts

Create accounts on these platforms (all free):
- https://github.com (for code hosting)
- https://render.com (for web hosting)
- https://supabase.com (for database)
- https://uptimerobot.com (for monitoring)

---

## Step 1: Fork GitHub Repository

### 1.1 Fork the Repository

1. Navigate to the original repository on GitHub
2. Click the **"Fork"** button in the top-right corner
3. Select your account as the destination
4. Wait for the fork to complete

### 1.2 Clone Your Fork Locally

```bash
# Replace YOUR_USERNAME with your GitHub username
git clone https://github.com/YOUR_USERNAME/schedulerTEST.git
cd schedulerTEST
```

### 1.3 Verify Files

Ensure you have these key files:
```bash
ls -la
# Should see: manage.py, requirements.txt, render.yaml, mysite/, calendarEditor/, etc.
```

---

## Step 2: Set Up Supabase Database

### 2.1 Create Supabase Account

1. Go to https://supabase.com
2. Click **"Start your project"**
3. Sign up with GitHub or email
4. Verify your email if required

### 2.2 Create New Project

1. After login, click **"New Project"** (green button)
2. **Choose organization:** Select your personal organization or create new one
3. **Project Settings:**
   - **Name:** `queue-system` (or your preferred name)
   - **Database Password:** Generate a strong password
     - ⚠️ **IMPORTANT:** Copy this password immediately - you'll need it later
     - Save it in a secure location (password manager recommended)
   - **Region:** Choose **East US (North Virginia)** or closest region to your users
     - For Arkansas users: **East US (Ohio)** is closest
   - **Pricing Plan:** Select **Free** (500MB database)
4. Click **"Create new project"**
5. Wait 2-3 minutes for project provisioning

### 2.3 Get Database Connection String

1. In your Supabase project dashboard, click **"Project Settings"** (gear icon in left sidebar)
2. Click **"Database"** in the left menu
3. Scroll down to **"Connection String"** section
4. **Select "URI" tab** (not "Connection pooling" or "Session pooling")
5. You'll see a connection string like:
   ```
   postgresql://postgres.PROJECT_ID:YOUR_PASSWORD@aws-0-us-east-1.pooler.supabase.com:5432/postgres
   ```
6. **IMPORTANT:** This string has `[YOUR-PASSWORD]` placeholder - you must replace it with the actual password from step 2.2
7. Copy the **modified** connection string (with real password) - you'll need this for Render

**Example of what your final DATABASE_URL should look like:**
```
postgresql://postgres.abcdefghijklmnop:MySecurePassword123!@aws-0-us-east-1.pooler.supabase.com:5432/postgres
```

### 2.4 Verify Database Access (Optional but Recommended)

1. In Supabase dashboard, click **"Table Editor"** in left sidebar
2. You should see an empty database (no tables yet - that's normal)
3. Keep this browser tab open - you'll check it later after deployment

---

## Step 3: Set Up Render Web Service

### 3.1 Create Render Account

1. Go to https://render.com
2. Click **"Get Started"** or **"Sign Up"**
3. Sign up with **GitHub** (recommended for easier repo connection)
4. Authorize Render to access your GitHub account

### 3.2 Create New Web Service

1. After login, click **"New +"** button in top right
2. Select **"Web Service"**

### 3.3 Connect GitHub Repository

**If you signed up with GitHub:**
1. Click **"Configure account"** to grant Render access to your repos
2. In the GitHub permissions page:
   - Select **"Only select repositories"**
   - Choose your forked `schedulerTEST` repository
   - Click **"Install & Authorize"**
3. Back in Render, your repository should now appear in the list
4. Click **"Connect"** next to your `schedulerTEST` repository

**If you didn't sign up with GitHub:**
1. Click **"Connect a repository"**
2. Select **"GitHub"**
3. Follow authorization steps above

### 3.4 Configure Web Service

Fill in the following settings:

**Basic Information:**
- **Name:** `qhog` (or your preferred name)
  - This will become your URL: `qhog.onrender.com`
- **Region:** Select **Ohio (US East)** or closest region
  - Must match your Supabase region for best performance
- **Branch:** `main` (or `master` if that's your default branch)
- **Root Directory:** Leave blank
- **Runtime:** **Python 3**

**Build & Deploy Settings:**
- **Build Command:** (This should auto-populate from `render.yaml`, but verify it matches:)
  ```bash
  pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate && python manage.py load_initial_data && python manage.py create_superuser_if_none
  ```
- **Start Command:** (This should auto-populate from `render.yaml`, but verify it matches:)
  ```bash
  daphne -b 0.0.0.0 -p $PORT mysite.asgi:application
  ```

**Instance Type:**
- Select **"Free"** plan
  - ⚠️ Note: Free plan spins down after 15 minutes of inactivity (we'll fix this with UptimeRobot later)

**Environment Variables:**
- Don't add any yet - we'll do this in Step 5

### 3.5 Save Web Service (Don't Deploy Yet)

1. Scroll to bottom
2. Click **"Create Web Service"**
3. Render will start trying to deploy, but it will fail - that's expected
4. We need to add environment variables first
5. The deployment will show as "Build failed" or "Deploy failed" - ignore this for now

---

## Step 4: Set Up Render Redis

### 4.1 Create Redis Instance

1. In Render dashboard, click **"New +"** button in top right
2. Select **"Redis"**

### 4.2 Configure Redis

Fill in the following settings:

- **Name:** `qhog-redis` (must match name in `render.yaml`)
- **Region:** **Same as your web service** (e.g., Ohio US East)
  - ⚠️ CRITICAL: Redis and web service must be in same region
- **Plan:** Select **"Free"** (25MB)
- **Maxmemory Policy:** `noeviction` (should be default)

### 4.3 Create Redis Instance

1. Click **"Create Redis"**
2. Wait 1-2 minutes for Redis to provision
3. Once created, you'll see the Redis dashboard

### 4.4 Get Redis Connection String

1. In the Redis dashboard, look for **"Internal Redis URL"** or **"Redis URL"**
2. Copy the connection string - it will look like:
   ```
   redis://red-xxxxxxxxxxxxxxxxxxxx:6379
   ```
3. Save this for Step 5 (environment variables)

**Note:** The connection string should NOT have a password if using Render's internal Redis

---

## Step 5: Configure Environment Variables

### 5.1 Navigate to Web Service Environment Variables

1. Go to your Render dashboard
2. Click on your web service (e.g., `qhog`)
3. In the left sidebar, click **"Environment"**

### 5.2 Add Required Environment Variables

Click **"Add Environment Variable"** for each of the following:

#### Database Configuration

**Variable Name:** `DATABASE_URL`
- **Value:** Paste your Supabase connection string from Step 2.3
  ```
  postgresql://postgres.PROJECT_ID:YOUR_REAL_PASSWORD@aws-0-us-east-1.pooler.supabase.com:5432/postgres
  ```
- ⚠️ Make sure the password is the ACTUAL password, not `[YOUR-PASSWORD]`

#### Redis Configuration

**Variable Name:** `REDIS_URL`
- **Value:** Paste your Render Redis connection string from Step 4.4
  ```
  redis://red-xxxxxxxxxxxxxxxxxxxx:6379
  ```

#### Django Secret Key

**Variable Name:** `SECRET_KEY`
- **Value:** Click **"Generate"** button (Render will create a secure random key)
- OR generate your own using:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(50))"
  ```

#### Debug Mode

**Variable Name:** `DEBUG`
- **Value:** `False`
- ⚠️ Always use `False` for production

#### Allowed Hosts

**Variable Name:** `ALLOWED_HOSTS`
- **Value:** `qhog.onrender.com` (replace `qhog` with your actual service name)
- If you have multiple domains, separate with commas: `qhog.onrender.com,yourdomain.com`

#### Base URL

**Variable Name:** `BASE_URL`
- **Value:** `https://qhog.onrender.com` (replace `qhog` with your actual service name)
- ⚠️ Include `https://` prefix

#### Backup API Key

**Variable Name:** `BACKUP_API_KEY`
- **Value:** Click **"Generate"** button
- This is used for automated database backups via GitHub Actions

#### Superuser Credentials

These will create an admin account automatically on first deploy:

**Variable Name:** `DJANGO_SUPERUSER_USERNAME`
- **Value:** Your desired admin username (e.g., `admin`)

**Variable Name:** `DJANGO_SUPERUSER_EMAIL`
- **Value:** Your email address (e.g., `admin@example.com`)

**Variable Name:** `DJANGO_SUPERUSER_PASSWORD`
- **Value:** A strong password for your admin account
- ⚠️ Save this password securely - you'll use it to log in

#### Optional Variables (Set Later)

These can be left empty for initial setup:

**Variable Name:** `SLACK_BOT_TOKEN`
- **Value:** (Leave empty for now - add in Step 9 if needed)

**Variable Name:** `TEMPERATURE_GATEWAY_API_KEY`
- **Value:** (Leave empty for now - add in Step 10 if needed)

### 5.3 Save Environment Variables

1. After adding all variables, click **"Save Changes"** (button at top or bottom)
2. Render will automatically trigger a new deployment

---

## Step 6: Deploy Application

### 6.1 Monitor Deployment

1. In your Render web service dashboard, click **"Logs"** in the left sidebar
2. Watch the deployment process:
   - **Installing dependencies** (pip install)
   - **Collecting static files** (Django collectstatic)
   - **Running migrations** (creating database tables)
   - **Loading initial data** (machines, user profiles)
   - **Creating superuser** (your admin account)
   - **Starting server** (Daphne ASGI server)

### 6.2 Wait for "Live" Status

- Deployment typically takes 5-8 minutes on first deploy
- Status will change from "Building" → "Deploying" → "Live"
- Green "Live" indicator means successful deployment

### 6.3 Verify Deployment

1. At the top of the Render dashboard, you'll see your service URL (e.g., `https://qhog.onrender.com`)
2. Click the URL to open your site
3. You should see the homepage with:
   - "Welcome to QHOG Lab Queue System" header
   - Login/Register buttons
   - Public queue and fridges links

### 6.4 Check Database Tables

1. Go back to Supabase dashboard
2. Click **"Table Editor"** in left sidebar
3. You should now see tables created by Django:
   - `auth_user`
   - `calendarEditor_machine`
   - `calendarEditor_queueentry`
   - `calendarEditor_notification`
   - And many more...

---

## Step 7: Set Up UptimeRobot (Keepalive)

Render's free tier spins down after 15 minutes of inactivity. UptimeRobot will ping your site every 5 minutes to keep it awake.

### 7.1 Create UptimeRobot Account

1. Go to https://uptimerobot.com
2. Click **"Register for FREE"**
3. Sign up with email
4. Verify your email address

### 7.2 Add Monitor

1. After login, click **"Add New Monitor"** (big green button)
2. Fill in the monitor settings:

**Monitor Type:**
- Select **"HTTP(s)"** from dropdown

**Friendly Name:**
- Enter: `QHOG Keepalive` (or your preferred name)

**URL (or IP):**
- Enter: `https://qhog.onrender.com/schedule/health/`
- ⚠️ Replace `qhog` with your actual Render service name
- ⚠️ Don't forget the trailing slash `/`

**Monitoring Interval:**
- Select **"5 minutes"** from dropdown
- This is the most frequent on free tier

**Monitor Timeout:**
- Leave at default **"30 seconds"**

**Alert Contacts:**
- (Optional) Add your email if you want downtime alerts
- Click **"Add Alert Contact"** → Enter email → Verify

### 7.3 Create Monitor

1. Scroll to bottom
2. Click **"Create Monitor"**
3. You'll see your monitor in the dashboard with a green "Up" status

### 7.4 Verify Monitoring

1. Wait 5 minutes
2. Refresh the UptimeRobot dashboard
3. You should see:
   - **Status:** Up (green checkmark)
   - **Response Time:** ~200-500ms
   - **Uptime:** Should start tracking

**What this does:**
- Pings your site every 5 minutes
- Keeps Render web service + Redis from spinning down
- Prevents the 15-minute inactivity timeout
- Site stays responsive 24/7

---

## Step 8: Initial Configuration

### 8.1 Log In as Superuser

1. Go to your site: `https://qhog.onrender.com`
2. Click **"Login"** button
3. Enter the superuser credentials you set in Step 5.2:
   - Username: (e.g., `admin`)
   - Password: (the `DJANGO_SUPERUSER_PASSWORD` you set)
4. Click **"Login"**

### 8.2 Access Admin Dashboard

1. After login, you should be redirected to **"Admin Dashboard"**
2. If not, click your username in top right → **"Admin Dashboard"**

### 8.3 Verify Initial Data

Click through each admin section to verify data was loaded:

**Machine Management:**
1. Click **"Machine Management"**
2. You should see 3 default machines:
   - PPMS AFM/MFM
   - PPMS (VSM, Resistivity, etc.)
   - 14T PPMS
3. Each should show as "Offline" (temperature: None) - this is normal

**User Management:**
1. Click **"User Management"**
2. You should see your superuser account:
   - Status: Approved ✓
   - Staff: Yes ✓

### 8.4 Customize Machines (Optional)

If you want to change the default machines:

1. Go to **"Machine Management"**
2. Click **"Edit"** next to a machine
3. Modify:
   - **Name:** Display name
   - **Slug:** URL-friendly identifier (lowercase, no spaces)
   - **Description:** What the machine does
   - **Status:** Online/Offline/Maintenance
4. Or **"Add New Machine"** for additional equipment
5. Or **"Delete"** machines you don't need

### 8.5 Create Your First Regular User

To test the full workflow:

1. **Option A: Register through site**
   - Open an incognito/private browser window
   - Go to your site
   - Click **"Register"**
   - Fill in the form
   - Submit
   - Back in admin dashboard, approve the user

2. **Option B: Create through admin dashboard**
   - In admin dashboard → **"User Management"**
   - Click **"Add User"** (via Django admin interface)
   - Create user and approve

---

## Step 9: Set Up Slack Integration (Optional)

If you want Slack notifications for queue events, follow these steps.

### 9.1 Create Slack Workspace (If Needed)

1. Go to https://slack.com/create
2. Follow steps to create a workspace
3. Name it (e.g., "Lab Queue System")

### 9.2 Create Slack App

1. Go to https://api.slack.com/apps
2. Click **"Create New App"**
3. Select **"From scratch"**
4. **App Name:** `QHOG Queue Bot` (or your preferred name)
5. **Pick a workspace:** Select your workspace
6. Click **"Create App"**

### 9.3 Configure Bot Token Scopes

1. In the app settings, click **"OAuth & Permissions"** in left sidebar
2. Scroll to **"Scopes"** section
3. Under **"Bot Token Scopes"**, click **"Add an OAuth Scope"**
4. Add these scopes:
   - `chat:write` (Send messages as the bot)
   - `users:read` (View people in workspace)
   - `users:read.email` (View email addresses)
   - `im:write` (Start direct messages with people)

### 9.4 Install App to Workspace

1. Scroll back up to **"OAuth Tokens for Your Workspace"**
2. Click **"Install to Workspace"**
3. Review permissions
4. Click **"Allow"**

### 9.5 Get Bot Token

1. After installation, you'll see **"Bot User OAuth Token"**
2. It will start with `xoxb-` followed by numbers and letters (e.g., `xoxb-[NUMBERS]-[NUMBERS]-[RANDOM-STRING]`)
3. Click **"Copy"** button to copy the full token
4. Save this token securely

### 9.6 Add Token to Render Environment Variables

1. Go to Render dashboard → Your web service → **"Environment"**
2. Find the `SLACK_BOT_TOKEN` variable (or add it if missing)
3. Paste your bot token as the value
4. Click **"Save Changes"**
5. Render will redeploy automatically

### 9.7 Link Slack Users to Django Users

**Important:** For notifications to work, you must link Slack accounts to Django user accounts.

1. Get each user's Slack Member ID:
   - In Slack, right-click user → **"View profile"**
   - Click **"⋮ More"** → **"Copy member ID"**
   - ID looks like: `U01ABC23DEF`

2. Add Slack ID to user profile:
   - In admin dashboard → **"User Management"**
   - Click **"Edit User Profile"** for the user
   - Paste Slack Member ID into **"Slack User ID"** field
   - Save

3. Repeat for all users who want Slack notifications

### 9.8 Test Slack Notifications

1. Create a test queue entry
2. Check Slack - you should receive a DM from the bot
3. If not working, check Render logs for errors

---

## Step 10: Set Up Temperature Gateway (Optional)

If your lab machines have temperature monitoring accessible via local network, you can set up automatic temperature updates.

### 10.1 Generate API Key

On your local machine:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the generated key.

### 10.2 Add API Key to Render

1. Go to Render dashboard → Your web service → **"Environment"**
2. Find the `TEMPERATURE_GATEWAY_API_KEY` variable (or add it)
3. Paste your generated API key
4. Click **"Save Changes"**

### 10.3 Set Up Temperature Gateway Script

The temperature gateway must run on a machine within your lab's local network (to access machine IPs).

1. On your lab network computer, clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/schedulerTEST.git
   cd schedulerTEST/temperature_gateway
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy example config:
   ```bash
   cp gateway_config.json.example gateway_config.json
   ```

4. Edit `gateway_config.json`:
   ```json
   {
     "api_url": "https://qhog.onrender.com/schedule/api/update-machine-temperatures/",
     "api_key": "YOUR_TEMPERATURE_GATEWAY_API_KEY_FROM_STEP_10.1",
     "machines": [
       {
         "id": 1,
         "name": "PPMS AFM/MFM",
         "ip": "192.168.1.100",
         "check_url": "http://192.168.1.100/temperature"
       }
     ],
     "check_interval": 300
   }
   ```

5. Update machine IPs and check URLs for your equipment

6. Test the script:
   ```bash
   python temperature_gateway.py
   ```

7. Set up as a scheduled task (cron on Linux, Task Scheduler on Windows)

For detailed setup, see `temperature_gateway/README.md`

---

## Troubleshooting

### Issue: "Build Failed" on Render

**Symptoms:** Render shows red "Failed" status, build errors in logs

**Common Causes:**
1. Missing environment variables
2. Incorrect `DATABASE_URL` format
3. Database connection refused

**Solutions:**
1. Check all environment variables are set (Step 5.2)
2. Verify `DATABASE_URL` has actual password, not `[YOUR-PASSWORD]`
3. Verify Supabase project is running (check Supabase dashboard)
4. Check Render logs for specific error message

### Issue: "502 Bad Gateway" When Accessing Site

**Symptoms:** Site shows Cloudflare or Render error page

**Common Causes:**
1. Redis connection failure
2. Database connection failure
3. App crashed during startup

**Solutions:**
1. Wait 2-3 minutes - site may be waking up from spin-down
2. Check Render logs for errors
3. Verify Redis is running (Render dashboard → Redis)
4. Verify environment variables are correct
5. Try manual deploy: Render dashboard → **"Manual Deploy"** → **"Deploy latest commit"**

### Issue: Can't Log In with Superuser Credentials

**Symptoms:** Login page shows "Invalid credentials"

**Common Causes:**
1. Superuser wasn't created during deployment
2. Wrong username/password

**Solutions:**
1. Check Render logs - search for "Superuser created"
2. If not found, create manually:
   ```bash
   # In Render dashboard → Shell
   python manage.py createsuperuser
   ```
3. Or delete and recreate environment variables `DJANGO_SUPERUSER_*` and redeploy

### Issue: No Initial Machines in Database

**Symptoms:** Machine Management page is empty

**Solutions:**
1. Check Render logs for "load_initial_data" errors
2. Manually run migration:
   ```bash
   # In Render dashboard → Shell
   python manage.py load_initial_data
   ```

### Issue: UptimeRobot Shows "Down"

**Symptoms:** Red status in UptimeRobot dashboard

**Common Causes:**
1. Site is still deploying
2. Wrong URL in monitor
3. Site crashed

**Solutions:**
1. Wait for deployment to complete (check Render dashboard)
2. Verify monitor URL is correct: `https://YOUR_SERVICE.onrender.com/schedule/health/`
3. Check Render logs for errors
4. Visit the health endpoint directly in browser to see response

### Issue: Site Spins Down Despite UptimeRobot

**Symptoms:** First request after inactivity is slow (502 errors)

**Solutions:**
1. Verify UptimeRobot monitor is active (green status)
2. Verify monitor interval is 5 minutes
3. Check monitor URL includes `/schedule/health/` endpoint
4. Monitor should return HTTP 200 status (check UptimeRobot response codes)

### Issue: Slack Notifications Not Working

**Symptoms:** No Slack DMs received for queue events

**Common Causes:**
1. Missing or invalid `SLACK_BOT_TOKEN`
2. Bot not installed to workspace
3. Missing Slack User IDs in user profiles
4. Notification preferences disabled

**Solutions:**
1. Verify `SLACK_BOT_TOKEN` is set in Render environment
2. Reinstall Slack app to workspace (Step 9.4)
3. Add Slack User IDs to each user profile (Step 9.7)
4. Check notification preferences: Profile → Notification Settings
5. Check Render logs for Slack API errors

### Issue: Redis Connection Errors in Logs

**Symptoms:** Logs show "Redis connection refused" or "Redis timeout"

**Solutions:**
1. Verify Redis instance is running (Render dashboard)
2. Verify `REDIS_URL` environment variable is correct
3. Ensure Redis and web service are in same region
4. Wait 1-2 minutes for Redis to wake up
5. Restart web service if issue persists

---

## Maintenance

### Monitoring Your Application

**Render Dashboard:**
- Check **"Metrics"** tab for resource usage
- Monitor **"Logs"** for errors
- Review **"Events"** for deployment history

**UptimeRobot Dashboard:**
- View uptime percentage (should be 99%+)
- Monitor response times (should be < 1 second)
- Check for downtime alerts

**Supabase Dashboard:**
- Check **"Database"** → **"Usage"** for storage (free tier: 500MB)
- View **"Table Editor"** to browse data
- Use **"SQL Editor"** for custom queries

### Regular Backups

**Automated Backups (Recommended):**
The system includes a GitHub Actions workflow for automated backups (runs every 6 hours). No setup required if you forked the repo.

**Manual Backups:**
1. Log in as admin
2. Go to **"Admin Dashboard"** → **"Database Management"**
3. Click **"Export Entire Database"**
4. Save the JSON file to a secure location

**Restore from Backup:**
1. Go to **"Admin Dashboard"** → **"Database Management"**
2. Click **"Import/Restore Database"**
3. Upload your backup JSON file
4. Choose **"Replace"** or **"Merge"** mode
5. Type `CONFIRM RESTORE` and submit

### Updating the Application

When you want to pull in updates from the original repository:

```bash
# Add original repo as upstream remote (one-time setup)
git remote add upstream https://github.com/ORIGINAL_USERNAME/schedulerTEST.git

# Fetch and merge updates
git fetch upstream
git merge upstream/main

# Push to your fork
git push origin main
```

Render will automatically deploy when you push to your fork.

### Scaling to Paid Tier (Optional)

If you outgrow the free tier:

**Render:**
- Upgrade web service to **Starter ($7/month)** for:
  - No spin-down (always on)
  - Faster deployment
  - More resources
- Upgrade Redis to **Starter ($5/month)** for:
  - More storage
  - Better performance

**Supabase:**
- Upgrade to **Pro ($25/month)** for:
  - 8GB database storage
  - Daily backups
  - Better performance

**Total Cost for Paid Tier:** ~$37/month

---

## Security Best Practices

1. **Rotate Secrets Regularly:**
   - Change `SECRET_KEY` every 6-12 months
   - Update database password periodically
   - Regenerate API keys if compromised

2. **Monitor Access Logs:**
   - Review Render logs weekly for suspicious activity
   - Check failed login attempts in application

3. **Keep Dependencies Updated:**
   - Run `pip list --outdated` to check for updates
   - Update `requirements.txt` with security patches
   - Test updates before deploying to production

4. **Backup Verification:**
   - Test backup restoration quarterly
   - Verify backup files are complete and valid

5. **User Account Security:**
   - Enforce strong passwords
   - Regularly audit user permissions
   - Remove inactive accounts

---

## Support and Community

**Documentation:**
- Django Documentation: https://docs.djangoproject.com/
- Render Documentation: https://render.com/docs
- Supabase Documentation: https://supabase.com/docs

**Troubleshooting:**
- Check Render logs first (most issues appear here)
- Search GitHub issues in the original repository
- Review this guide's Troubleshooting section

**Contributing:**
If you find bugs or have improvements:
1. Create an issue on GitHub
2. Submit a pull request with fixes
3. Update documentation as needed

---

## Success Checklist

Use this checklist to verify your installation is complete:

- [ ] GitHub repository forked and cloned
- [ ] Supabase database created and accessible
- [ ] Render web service created and deployed
- [ ] Render Redis instance created and connected
- [ ] All environment variables configured
- [ ] Application shows "Live" status on Render
- [ ] Can access site at `https://YOUR_SERVICE.onrender.com`
- [ ] Can log in with superuser credentials
- [ ] Admin dashboard accessible
- [ ] 3 default machines visible in Machine Management
- [ ] UptimeRobot monitor created and showing "Up" status
- [ ] Health endpoint returns 200: `https://YOUR_SERVICE.onrender.com/schedule/health/`
- [ ] Can create and approve a test user
- [ ] Can submit a queue entry
- [ ] (Optional) Slack notifications working
- [ ] (Optional) Temperature gateway configured

**Congratulations!** Your Lab Queue Management System is now fully operational.

---

## Appendix: Environment Variable Reference

Complete list of all environment variables with descriptions:

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `DATABASE_URL` | Yes | PostgreSQL connection string from Supabase | `postgresql://postgres.xxx:pass@aws-0-us-east-1.pooler.supabase.com:5432/postgres` |
| `REDIS_URL` | Yes | Redis connection string from Render | `redis://red-xxxxxxxxxxxx:6379` |
| `SECRET_KEY` | Yes | Django secret key for cryptography | `dGh1c2lzYXNlY3JldGtleQ...` |
| `DEBUG` | Yes | Enable debug mode (always False in production) | `False` |
| `ALLOWED_HOSTS` | Yes | Comma-separated list of allowed domain names | `qhog.onrender.com` |
| `BASE_URL` | Yes | Full URL of your site (for links in notifications) | `https://qhog.onrender.com` |
| `BACKUP_API_KEY` | Yes | API key for automated backup endpoint | `random-secure-key-here` |
| `DJANGO_SUPERUSER_USERNAME` | Yes | Admin username created on first deploy | `admin` |
| `DJANGO_SUPERUSER_EMAIL` | Yes | Admin email address | `admin@example.com` |
| `DJANGO_SUPERUSER_PASSWORD` | Yes | Admin password | `SecurePassword123!` |
| `SLACK_BOT_TOKEN` | No | Slack bot OAuth token for notifications | `xoxb-[YOUR-TOKEN-HERE]` |
| `TEMPERATURE_GATEWAY_API_KEY` | No | API key for temperature update endpoint | `random-secure-key-here` |
| `MAX_DATABASE_SIZE_MB` | No | Maximum database size before warnings (default: 500) | `500` |

---

*Last Updated: 2025-11-12*
*Version: 1.0*
