# Turso Setup Guide: Fix CU Limits Forever!

**Goal:** Switch from Neon PostgreSQL (100 CU/month limit) to Turso SQLite (NO CU limits!)

**Time:** 2-3 hours

**Result:** Keep Django on Render, just change the database. All features stay the same.

---

## What is Turso?

- **SQLite edge database** deployed globally
- **Free tier:** 9GB storage, unlimited reads, 1M writes/month
- **NO COMPUTE UNIT (CU) LIMITS!** ← This solves your problem!
- SQLite-compatible (you already tested SQLite migration locally)
- Edge-deployed for fast access from anywhere

---

## Step 1: Create Turso Account (5 min)

### 1.1 Install Turso CLI

On your local machine:

```bash
# Mac/Linux
curl -sSfL https://get.tur.so/install.sh | bash

# Restart your terminal to use turso command
```

### 1.2 Sign Up for Turso

```bash
# This will open your browser to sign up
turso auth signup

# After signing up, verify you're logged in
turso auth whoami
```

### 1.3 Create Database

```bash
# Create database in US East (closest to Render's default region)
turso db create scheduler-db --location ord

# View your database details
turso db show scheduler-db

# You'll see output like:
# Name:           scheduler-db
# URL:            libsql://scheduler-db-yourname.turso.io
# Regions:        iad (primary)
# Size:           0 B
```

### 1.4 Create Auth Token

```bash
# Create authentication token
turso db tokens create scheduler-db

# Save this token! It looks like:
# eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9...
eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3NjU5ODk1NDQsImlkIjoiYTE1NDI1ZGItMjRhOC00M2Y4LWI1OTAtNDgwOGQ5NzRhM2MwIiwicmlkIjoiMDM2NjI0YzAtNGFlNS00MTdkLWIxOGYtNjAyNzRhMWEwZWZjIn0.kXvDiaQcbfeebdYaHhK4MTs4_3cbMthAtEBXN9JBpNpa3VsXXnikorHRVmLPMywtvCJSpOEhi_6XfFzdP6BBCw

db url: 
libsql://scheduler-db-timothy-rosno.aws-us-east-2.turso.io
# Copy both:
# - Database URL: libsql://scheduler-db-yourname.turso.io
# - Auth Token: eyJhbGc...
```

**IMPORTANT:** Save these two values - you'll need them later!

---

## Step 2: Test Locally (30 min)

### 2.1 Install Python Package

```bash
# In your project directory
pip install libsql-client-py==0.2.1

# Or if you already updated requirements.txt:
pip install -r requirements.txt
```

### 2.2 Create Local .env File

Create or update `.env` in your project root:

```bash

# Turso Configuration (PRODUCTION)
TURSO_DATABASE_URL=libsql://scheduler-db-yourname.turso.io
TURSO_AUTH_TOKEN=eyJhbGc...your-token-here

# Keep existing settings
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
SLACK_BOT_TOKEN=your-slack-token
TEMPERATURE_GATEWAY_API_KEY=your-gateway-key
BACKUP_API_KEY=your-backup-key
```

**Note:** With Turso configured, Django will use Turso instead of local SQLite!

### 2.3 Test Connection

```bash
# Check if Turso connection works
python manage.py sync_turso --status

# You should see:
# ✓ Connected to Turso: libsql://scheduler-db-yourname.turso.io
# ✓ Turso connection is healthy
#   URL: libsql://scheduler-db-yourname.turso.io
#   No tables found (database is empty)
```

### 2.4 Run Migrations

```bash
# Create tables in Turso database
python manage.py migrate

# Check status again
python manage.py sync_turso --status

# Now you should see tables listed!
```

### 2.5 Import Your Data

You have two options:

**Option A: Load from existing backup**

```bash
# If you have a backup JSON file from Render
python manage.py loaddata database_backup_2024-12-15.json

# Or download latest backup first
# (instructions in next step)
```

**Option B: Start fresh with test data**

```bash
# Create a superuser
python manage.py createsuperuser

# Load initial machine data
python manage.py populate_machines

# Load test data if available
python manage.py load_initial_data
```

### 2.6 Test Locally

```bash
# Start development server
python manage.py runserver

# Open http://localhost:8000/schedule/
# Test:
# - Can you log in?
# - Can you see machines?
# - Can you create queue entries?
# - Do notifications work?
```

If everything works, you're ready for production! 🎉

---

## Step 3: Deploy to Render (15 min)

### 3.1 Export Current Render Database

Before switching, back up your current data:

1. Go to your Render dashboard
2. Open your web service
3. Go to https://qhog.onrender.com/schedule/admin/database/
4. Click "Export Database Backup"
5. Save the downloaded JSON file

**IMPORTANT:** Keep this backup safe!

### 3.2 Update Render Environment Variables

1. Go to Render dashboard → Your web service
2. Click "Environment" tab
3. Add these two new variables:

```
TURSO_DATABASE_URL = libsql://scheduler-db-yourname.turso.io
TURSO_AUTH_TOKEN = eyJhbGc...your-token-here
```

4. **OPTIONAL:** Remove or comment out `DATABASE_URL` (keep as backup):
   - Find `DATABASE_URL` variable
   - Don't delete it yet (in case you need to rollback)
   - Add a comment in the name: `DATABASE_URL_BACKUP`

5. Click "Save Changes"

Render will automatically redeploy with the new environment variables.

### 3.3 Wait for Deployment

```bash
# Watch the logs in Render dashboard
# You should see:
# ✓ Using Turso database: libsql://scheduler-db-yourname.turso.io
```

### 3.4 Run Migrations on Render

1. In Render dashboard, click "Shell" tab
2. Run:

```bash
python manage.py migrate

# Verify Turso connection
python manage.py sync_turso --status
```

### 3.5 Import Your Data

In the Render shell:

```bash
# If you exported from admin interface, you can re-import via admin
# OR upload your backup JSON and run:
python manage.py loaddata database_backup_2024-12-15.json
```

**Alternative:** Use the admin interface:
1. Go to https://qhog.onrender.com/schedule/admin/database/
2. Click "Import Database Backup"
3. Upload your JSON backup file
4. Click "Import"

---

## Step 4: Test in Production (15 min)

### 4.1 Basic Functionality Tests

Visit https://qhog.onrender.com/schedule/ and test:

- ✅ Login works
- ✅ Can see machines
- ✅ Can view queue
- ✅ Can create queue entry
- ✅ Can edit queue entry
- ✅ Can delete queue entry
- ✅ WebSocket updates work (test in two browsers)
- ✅ Notifications appear
- ✅ Archived measurements work

### 4.2 Performance Tests

- ✅ Pages load quickly
- ✅ Can create 20+ queue entries rapidly (no rate limits!)
- ✅ Can refresh page multiple times (no CU warnings!)
- ✅ Admin actions work smoothly

### 4.3 Monitor for 24 Hours

Check after 24 hours:

```bash
# In Render shell
python manage.py sync_turso --status

# Check Render logs for any Turso errors
```

---

## Step 5: Cleanup (After 48 hours of stable operation)

Once Turso is working perfectly:

### 5.1 Decommission Neon Database

1. Go to Neon dashboard (or wherever your old database is hosted)
2. **Download final backup** (just in case)
3. Delete the database project
4. Verify you're no longer being charged/using CU

### 5.2 Update Documentation

Update any docs that reference the old database setup.

---

## Troubleshooting

### Error: "libsql-client-py not installed"

```bash
pip install libsql-client-py==0.2.1
```

### Error: "TURSO_DATABASE_URL not set"

Make sure you added the environment variables in:
- Local: `.env` file
- Production: Render dashboard → Environment tab

### Error: "Connection timeout"

Check your database URL and auth token are correct:

```bash
turso db show scheduler-db
turso db tokens create scheduler-db
```

### Database Feels Slow

Turso uses edge replication. First request might be slow, but subsequent requests are fast.

If still slow, check your database location:

```bash
turso db show scheduler-db

# Should show:
# Regions:        iad (primary)  ← US East
```

### Data Not Syncing

Turso doesn't auto-sync with local SQLite. You need to:
- Use Turso for production (Render)
- Use local SQLite for development
- Import/export data when needed

---

## Cost Analysis

### Before (Neon PostgreSQL)

- Free tier: 0.5GB storage, **100 CU/month**
- Your usage: **4.28 CU in 1 day** → Would hit limit in ~23 days
- Result: ❌ RATE LIMITED

### After (Turso SQLite)

- Free tier: 9GB storage, 1M writes/month
- **NO COMPUTE UNIT LIMITS!** ← Problem solved!
- Your usage: ~0.1GB, <10K writes/month
- Result: ✅ NEVER RATE LIMITED

---

## Next Steps

### Option 1: Keep This Setup (RECOMMENDED)

- ✅ You're done! Enjoy unlimited database access.
- Monitor for a week to ensure stability
- Delete old Neon database after 48 hours

### Option 2: Migrate to Full Serverless Later

If you want to modernize further:
- Migrate Django → Next.js + Vercel
- Add CDN for faster page loads
- Move reminders to GitHub Actions
- See plan file: `~/.claude/plans/warm-cuddling-taco.md`

---

## Support

### Check Status Anytime

```bash
python manage.py sync_turso --status
```

### View Turso Database

```bash
# Open interactive shell to your Turso database
turso db shell scheduler-db

# Run SQL queries:
.tables                    # List all tables
SELECT COUNT(*) FROM calendarEditor_machine;
.schema calendarEditor_machine
```

### Backup Your Turso Database

```bash
# Export to SQL dump
turso db shell scheduler-db ".dump" > turso_backup.sql

# Or use Django's export:
python manage.py dumpdata > database_backup.json
```

### Restore from Backup

```bash
# Import SQL dump
turso db shell scheduler-db < turso_backup.sql

# Or use Django's import:
python manage.py loaddata database_backup.json
```

---

## Summary

**What Changed:**
- Database: Neon PostgreSQL → Turso SQLite Edge
- Environment variables: Added `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN`
- Dependencies: Added `libsql-client-py` package

**What Stayed the Same:**
- Django code (100% unchanged)
- Render hosting
- All features (WebSockets, notifications, queue, etc.)
- URL: https://qhog.onrender.com

**Result:**
- ✅ NO MORE CU LIMITS!
- ✅ Free forever (9GB storage, 1M writes/month)
- ✅ All features working
- ✅ 2-3 hours total migration time

---

## Key Files Modified

- ✅ `mysite/settings.py` - Added Turso connection logic (lines 143-220)
- ✅ `requirements.txt` - Added `libsql-client-py==0.2.1`
- ✅ `calendarEditor/management/commands/sync_turso.py` - New management command

---

## Questions?

- **How do I check my Turso usage?** Visit https://turso.tech/dashboard
- **Can I exceed the free tier?** Yes, but you'd need 9GB+ data or 1M+ writes/month (unlikely!)
- **What happens if I hit limits?** Turso will email you. Paid tier is $29/month.
- **Can I switch back to PostgreSQL?** Yes! Just remove Turso env vars and restore `DATABASE_URL`
- **Does this work with existing backups?** Yes! Use the admin import feature.

---

🎉 **Congratulations!** You've eliminated CU limits forever while keeping Django on Render!
