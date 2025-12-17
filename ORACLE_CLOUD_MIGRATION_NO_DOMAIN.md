# Oracle Cloud + SQLite Migration Guide (Free Domain with HTTPS)

Complete migration guide for moving your Django scheduler from Render + PostgreSQL to Oracle Cloud + SQLite with a **free DuckDNS domain** and SSL certificate.

---

## Architecture Overview

**What you're building:**

```
┌─────────────────────────────────────────────────────┐
│  Oracle Cloud VM (runs 24/7)                        │
│  ├── Your Django app (always running)               │
│  ├── Redis (always running)                         │
│  ├── Nginx (always running)                         │
│  ├── SQLite database (stored on VM disk)            │
│  └── Automated backups (cron jobs)                  │
└─────────────────────────────────────────────────────┘
         ↓ accessible via
   https://qhog.duckdns.org
         ↓ points to
   Oracle Cloud Static IP: 123.45.67.89
```

**Your local computer:**
- Used ONLY for initial setup and occasional SSH access for maintenance
- NOT involved in running the application
- Can be turned off after deployment

**Oracle Cloud VM:**
- Runs 24/7 on Oracle's servers (not your computer)
- Static public IP address (doesn't change)
- This is the production backend server

---

## Overview

**Time required:** 3-4 hours
**Cost:** $0/month forever (truly free)
**Result:**
- Production backend running 24/7 on Oracle Cloud
- Free domain: `yourname.duckdns.org`
- Free HTTPS/SSL certificate
- Unlimited database queries (no CU limits)
- 200GB storage, 12GB RAM, 2 CPU cores

---

## Prerequisites

**What you need:**
- [ ] Oracle Cloud account (we'll create this)
- [ ] Current database backup from Render
- [ ] GitHub account (for DuckDNS login)
- [ ] Your local computer with SSH client
- [ ] 3-4 hours of focused time

**What you DON'T need:**
- ❌ Custom domain ($10-15/year)
- ❌ Credit card charges (card required for verification but never charged)
- ❌ DevOps expertise (this guide covers everything)

---

## Part 0: Get Your Free Domain (10 minutes)

DuckDNS provides **free subdomains** with full DNS control. You'll get a permanent domain like `qhog.duckdns.org`.

### Step 0.1: Create DuckDNS Account

**On your local computer:**

1. Go to https://www.duckdns.org/
2. Click sign in with:
   - **GitHub** (recommended - you already have this)
   - Or: Google, Reddit, Twitter, Persona
3. Authorize DuckDNS (read-only access, totally safe)
4. You'll see: "You currently have no domains"

### Step 0.2: Choose Your Subdomain

1. In the "sub domain" field, type your desired name:
   - Example: `qhog`
   - Example: `quantumlab`
   - Example: `cryolab`

2. Your full domain will be: `yourname.duckdns.org`

3. **Leave "current ip" BLANK for now** (we'll add this after creating Oracle VM)

4. Click **"add domain"**

5. **IMPORTANT: Save your token!**
   - You'll see a token at the top of the page (long random string)
   - Copy it to a text file: `duckdns_token.txt`
   - You'll need this later

**Example result:**
- Domain: `qhog.duckdns.org`
- Token: `a1b2c3d4-5678-90ab-cdef-1234567890ab`

### Step 0.3: Note Your Domain

Write down your domain (you'll use it throughout this guide):

```
My DuckDNS domain: qhog.duckdns.org
My DuckDNS token: 87ca7166-09f6-4eba-b4ec-90b301030c39

```

---

## Part 1: Oracle Cloud VM Setup (45 minutes)

This creates your production backend server that runs 24/7 on Oracle's infrastructure.

### Step 1.1: Create Oracle Cloud Account

**On your local computer:**

1. Go to https://www.oracle.com/cloud/free/
2. Click **"Start for free"**
3. Fill in account information:
   - Email address (use your real email)
   - Country/Region
   - **Cloud Account Name:** Choose carefully (lowercase, letters/numbers only)
     - Example: `qhog`
     - This becomes your Oracle Cloud tenant name
4. Click **"Verify my email"**
5. Check your email and click verification link
    trosno@uark.edu
6. Complete account setup:
   - **Password** (save this!) 
        2Dsemiconductor!
   - **Home Region** (choose closest: US East for East Coast, US West for West Coast)
   - Credit card (required for verification but **NEVER CHARGED** for Always Free resources)
7. Wait for "Your account is ready" email (5-10 minutes)

**Why credit card?** Oracle requires it to prevent abuse, but Always Free resources are truly free forever. Your card will NOT be charged.

### Step 1.2: Sign In to Oracle Cloud Console

1. Go to https://cloud.oracle.com/
2. Enter your **Cloud Account Name** (from step 1.1)
3. Click **"Next"**
4. Enter your email and password
5. You'll see the Oracle Cloud Console dashboard

**Bookmark this page** - this is your Oracle Cloud control panel.

### Step 1.3: Create Your VM (Compute Instance)

This creates the server that runs your app 24/7.

1. In the Oracle Cloud Console, click the **hamburger menu** (≡ top left)
2. Navigate to: **Compute** → **Instances**
3. Make sure you're in the **root compartment** (check dropdown at top)
4. Click **"Create Instance"**

**Instance Configuration:**

```
Name: django-scheduler
(or any name you like - this is just for your reference)

Placement:
  - Availability domain: (leave default) (A1 for free)

Image and shape:
  Click "Edit" next to "Image and shape"

  Image:
    - Click "Change Image"
    - Select: "Canonical Ubuntu"
    - Version: 22.04 (LTS)
    - Click "Select Image"

  Shape:
    - Click "Change Shape"
    - Shape series: Select "Ampere" (ARM-based)
    - Shape name: VM.Standard.A1.Flex
    - Number of OCPUs: 1
    - Amount of memory (GB): 6
    - Click "Select Shape"

  ⚠️ IMPORTANT: Must use Ampere (A1) shape for Always Free!

Networking:
  Click "Edit" next to "Networking"

  - Virtual cloud network: "Create new virtual cloud network"
  - New VCN name: scheduler-vcn
  - Subnet: "Create new public subnet"
  - New subnet name: scheduler-subnet
  - ✅ "Assign a public IPv4 address" (MUST be checked!)

Add SSH keys:
  - Click "Generate a key pair for me"
  - Click "Save Private Key" → Save as: scheduler-key.pem
  - Click "Save Public Key" → Save as: scheduler-key.pub

  ⚠️ CRITICAL: You CANNOT download these keys again!
  Save them somewhere safe (like ~/Documents/oracle-keys/)

Boot volume:
  - Leave default (50GB)
```

5. Click **"Create"** at the bottom
6. Wait for instance state to change from "PROVISIONING" to **"RUNNING"** (2-3 minutes)

### Step 1.4: Get Your Public IP Address

Once the instance is RUNNING:

1. On the instance details page, find **"Public IP address"**
2. Copy this IP address - example: `123.45.67.89`
3. **Save this IP:**

```
My Oracle Cloud public IP: ___________________
```

**This IP is STATIC** - it won't change unless you delete and recreate the VM.

### Step 1.5: Update DuckDNS with Your IP

Now connect your free domain to your Oracle VM:

**On your local computer:**

1. Go back to https://www.duckdns.org/ (should still be logged in)
2. Find your domain in the list
3. In the **"current ip"** field, paste your Oracle Cloud public IP
4. Click **"update ip"**
5. You should see "**OK**" confirmation

**Test that it works:**

```bash
# On your local computer
ping qhog.duckdns.org

# Should return your Oracle Cloud IP
# Press Ctrl+C to stop
```

If ping works, your domain is correctly pointing to your VM! ✅

### Step 1.6: Configure Network Security (Firewall)

Oracle Cloud has TWO firewalls - you must configure both.

#### A. Cloud-Level Firewall (Security List)

1. In Oracle Cloud Console, click hamburger menu (≡)
2. Navigate to: **Networking** → **Virtual Cloud Networks**
3. Click on **"scheduler-vcn"** (your VCN name)
4. In the left sidebar, click **"Security Lists"**
5. Click **"Default Security List for scheduler-vcn"**
6. Scroll down to **"Ingress Rules"** section
7. You should see one existing rule for SSH (port 22)
8. Click **"Add Ingress Rules"**

**Add Rule 1 - HTTP:**
```
Stateless: [ ] (unchecked)
Source Type: CIDR
Source CIDR: 0.0.0.0/0
IP Protocol: TCP
Source Port Range: (leave blank)
Destination Port Range: 80
Description: HTTP traffic
```
Click **"Add Ingress Rules"**

**Add Rule 2 - HTTPS:**

Click **"Add Ingress Rules"** again:
```
Stateless: [ ] (unchecked)
Source Type: CIDR
Source CIDR: 0.0.0.0/0
IP Protocol: TCP
Source Port Range: (leave blank)
Destination Port Range: 443
Description: HTTPS traffic
```
Click **"Add Ingress Rules"**

You should now have 3 ingress rules total:
- Port 22 (SSH)
- Port 80 (HTTP)
- Port 443 (HTTPS)

#### B. VM-Level Firewall (Ubuntu UFW)

We'll configure this after connecting to the VM.

### Step 1.7: Connect to Your VM via SSH

**On your local computer:**

First, move your SSH key to the correct location:

```bash
# Open Terminal (on macOS) or Command Prompt (on Windows with SSH)

# Move SSH key to .ssh directory
mkdir -p ~/.ssh
mv ~/Downloads/scheduler-key.pem ~/.ssh/
# (adjust path if you saved it somewhere else)

# Set correct permissions (REQUIRED on Linux/macOS)
chmod 600 ~/.ssh/scheduler-key.pem

# Connect to your VM (replace YOUR_PUBLIC_IP with your actual IP)
ssh -i ~/.ssh/scheduler-key.pem ubuntu@YOUR_PUBLIC_IP
```

**First time connecting:**
- You'll see: "The authenticity of host... are you sure you want to continue?"
- Type: **yes** and press Enter

**Success looks like:**
```
ubuntu@django-scheduler:~$
```

You're now connected to your Oracle Cloud VM! 🎉

**Keep this terminal window open** - we'll use it for the rest of the setup.

---

## Part 2: Configure Your VM (30 minutes)

All commands in this section run **on your Oracle VM** (the terminal you just opened).

### Step 2.1: Update System Packages

```bash
# Update package lists
sudo apt update

# Upgrade all installed packages
sudo apt upgrade -y

# This takes 5-10 minutes - be patient
# Press Enter if prompted for any questions
```

### Step 2.2: Install Essential Tools

```bash
# Install required utilities
sudo apt install -y curl git wget nano ufw

# Verify installations
git --version
curl --version
```

### Step 2.3: Configure VM Firewall (UFW)

Ubuntu's built-in firewall needs to allow web traffic:

```bash
# IMPORTANT: Allow SSH first (or you'll lock yourself out!)
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw --force enable

# Check status
sudo ufw status
```

**Expected output:**
```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                     ALLOW       Anywhere
```

✅ Firewall configured!

### Step 2.4: Install Docker

Docker packages your app and runs it in isolated containers.

```bash
# Download Docker installation script
curl -fsSL https://get.docker.com -o get-docker.sh

# Install Docker
sudo sh get-docker.sh

# Add your user to docker group (avoids needing sudo)
sudo usermod -aG docker ubuntu

# Clean up
rm get-docker.sh

# Verify Docker installed
docker --version
# Should show: Docker version 24.x.x
```

### Step 2.5: Install Docker Compose

Docker Compose manages multiple containers (Django, Redis, Nginx) together.

```bash
# Download Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Make it executable
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker-compose --version
# Should show: Docker Compose version 2.x.x
```

### Step 2.6: Log Out and Back In

**IMPORTANT:** You must log out for Docker group permissions to take effect.

```bash
# Log out
exit
```

**Reconnect to your VM:**

```bash
# On your local computer terminal
ssh -i ~/.ssh/scheduler-key.pem ubuntu@YOUR_PUBLIC_IP
```

**Test Docker works without sudo:**

```bash
docker ps
# Should show empty list (no containers yet) without errors
```

✅ Docker configured correctly!

### Step 2.7: Create Application Directories

```bash
# Create main directory structure
mkdir -p ~/scheduler
cd ~/scheduler

# Create subdirectories
mkdir -p data media staticfiles backups logs
mkdir -p certbot/conf certbot/www

# Verify structure
ls -la
# Should show: data, media, staticfiles, backups, logs, certbot
```

**What each directory is for:**
- `data/` - SQLite database file lives here
- `media/` - User-uploaded files (measurements, etc.)
- `staticfiles/` - CSS, JavaScript, images
- `backups/` - Nightly database backups
- `logs/` - Application logs
- `certbot/` - SSL certificates

### Step 2.8: Set Up DuckDNS Auto-Update (Optional but Recommended)

Even though Oracle Cloud IPs are static, this ensures DNS stays correct if anything changes.

**This runs ON YOUR VM** (not your local computer):

```bash
# Create update script
nano ~/update-duckdns.sh
```

Paste this content (replace YOUR_DOMAIN and YOUR_TOKEN):

```bash
#!/bin/bash
# Updates DuckDNS with current IP
# Runs every 5 minutes via cron
echo url="https://www.duckdns.org/update?domains=YOUR_DOMAIN&token=YOUR_TOKEN&ip=" | curl -k -o ~/duckdns.log -K -
```

**Example:**
```bash
#!/bin/bash
echo url="https://www.duckdns.org/update?domains=qhog&token=a1b2c3d4-5678-90ab-cdef-1234567890ab&ip=" | curl -k -o ~/duckdns.log -K -
```

**Note:** Don't include `.duckdns.org` in the domain name, just the subdomain part.

Save the file:
- Press `Ctrl+O` then `Enter` (save)
- Press `Ctrl+X` (exit)

**Make it executable and test:**

```bash
# Make executable
chmod +x ~/update-duckdns.sh

# Test it
~/update-duckdns.sh

# Check result
cat ~/duckdns.log
# Should show: OK
```

If you see "OK", it's working! ✅

**Schedule auto-updates:**

```bash
# Open crontab
crontab -e

# If prompted, select editor: choose 1 (nano)

# Add this line at the bottom:
*/5 * * * * ~/update-duckdns.sh >/dev/null 2>&1

# Save: Ctrl+O, Enter, Ctrl+X
```

**This updates DNS every 5 minutes** - runs in the background on your VM forever.

---

## Part 3: Test SQLite Migration Locally (20 minutes)

**CRITICAL:** Test SQLite works with your data BEFORE deploying to Oracle Cloud.

**Switch to your LOCAL COMPUTER for this part** (not the VM).

### Step 3.1: Download Current Database Backup

1. Open browser on your local computer
2. Go to: https://qhog.onrender.com/schedule/admin/
3. Log in as admin
4. Click "Manage Storage" or go to: https://qhog.onrender.com/schedule/admin/database/
5. Click **"Export Complete Database"**
6. Save file as: `database_backup.json` in your project directory

### Step 3.2: Test SQLite Locally

```bash
# On your LOCAL computer
cd /Users/timothyrosno/2025-2026/Fall/Stacker_Game/schedulerTEST

# Make sure DATABASE_URL is not set (forces SQLite mode)
unset DATABASE_URL

# Remove old SQLite database
rm -f db.sqlite3

# Create fresh SQLite database
python manage.py migrate

# You should see:
# Operations to perform:
#   Apply all migrations: admin, auth, calendarEditor, ...
# Running migrations:
#   Applying contenttypes.0001_initial... OK
#   ...
```

### Step 3.3: Restore Data to SQLite

```bash
# Start Python shell
python manage.py shell
```

**In the Python shell, paste this entire script:**

```python
import json
from django.core import serializers
from django.contrib.auth.models import User
from userRegistration.models import UserProfile
from calendarEditor.models import (
    Machine, QueuePreset, QueueEntry, ArchivedMeasurement,
    NotificationPreference, Notification
)

# Load backup file
with open('database_backup.json', 'r') as f:
    backup = json.load(f)

print(f"Backup date: {backup.get('export_date', 'Unknown')}")
print(f"Backup type: {backup.get('export_type', 'Unknown')}")
print()

# Models to restore (in dependency order - IMPORTANT!)
models_order = [
    ('auth.User', User),
    ('userRegistration.UserProfile', UserProfile),
    ('calendarEditor.Machine', Machine),
    ('calendarEditor.QueuePreset', QueuePreset),
    ('calendarEditor.QueueEntry', QueueEntry),
    ('calendarEditor.ArchivedMeasurement', ArchivedMeasurement),
    ('calendarEditor.NotificationPreference', NotificationPreference),
    ('calendarEditor.Notification', Notification),
]

# Restore each model
for model_name, model_class in models_order:
    if model_name not in backup['models']:
        print(f"⚠️  {model_name} not in backup, skipping")
        continue

    model_data = backup['models'][model_name]

    # Skip if error in backup
    if isinstance(model_data, dict) and 'error' in model_data:
        print(f"⚠️  {model_name} has error: {model_data['error']}")
        continue

    print(f"Restoring {model_name}...", end=' ')
    count = 0
    errors = 0

    for obj_data in model_data:
        try:
            # Deserialize and save
            for deserialized_obj in serializers.deserialize('json', json.dumps([obj_data])):
                deserialized_obj.save()
                count += 1
        except Exception as e:
            errors += 1
            if errors <= 3:  # Only print first 3 errors
                print(f"\n  Error: {e}")

    print(f"✓ Restored {count} records" + (f" ({errors} errors)" if errors > 0 else ""))

print("\n✅ Migration complete!")
print(f"Total users: {User.objects.count()}")
print(f"Total machines: {Machine.objects.count()}")
print(f"Total queue entries: {QueueEntry.objects.count()}")

# Exit Python shell
exit()
```

**Expected output:**
```
Backup date: 2024-XX-XX
Backup type: full_database_backup

Restoring auth.User... ✓ Restored 5 records
Restoring userRegistration.UserProfile... ✓ Restored 5 records
Restoring calendarEditor.Machine... ✓ Restored 3 records
...

✅ Migration complete!
Total users: 5
Total machines: 3
Total queue entries: 12
```

### Step 3.4: Test the Application

```bash
# Start development server
python manage.py runserver
```

**Open browser:** http://127.0.0.1:8000/schedule/

**Test these features:**
- ✅ Can you log in?
- ✅ Are machines listed?
- ✅ Are queue entries visible?
- ✅ Can you create a new queue entry?
- ✅ Do notifications work?

**If everything works:** SQLite migration is successful! Continue to deployment.

**If there are errors:** Debug locally before deploying. Check:
- Migration errors in terminal
- Database backup file is valid JSON
- All models restored correctly

Press `Ctrl+C` to stop the development server.

### Step 3.5: Commit and Push to GitHub

```bash
# Make sure latest code is in GitHub
git status
git add -A
git commit -m "Prepare for Oracle Cloud migration - SQLite tested"
git push origin main
```

---

## Part 4: Deploy to Oracle Cloud (45 minutes)

**Switch back to your Oracle VM terminal** for this entire part.

### Step 4.1: Clone Your Repository

```bash
# On your Oracle VM
cd ~/scheduler

# Clone your repository
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git app

# Example:
# git clone https://github.com/timrosno/schedulerTEST.git app

cd app

# Verify files
ls -la
# Should show: manage.py, mysite/, calendarEditor/, etc.
```

### Step 4.2: Run Setup Script

The setup script automatically creates all configuration files.

```bash
# Make script executable
chmod +x setup-oracle-cloud.sh

# Run setup (replace with YOUR domain and IP)
./setup-oracle-cloud.sh qhog.duckdns.org 123.45.67.89

# Example:
# ./setup-oracle-cloud.sh qhog.duckdns.org 129.146.123.45
```

**The script will:**
1. Generate SECRET_KEY
2. Generate BACKUP_API_KEY
3. Create .env file
4. Create nginx.conf
5. Create backup scripts
6. Create SSL renewal script
7. Create required directories

**IMPORTANT:** At the end, it displays your secrets:

```
Backup API Key: abc123xyz...
Secret Key: def456uvw...

SAVE THESE KEYS SECURELY!
```

**Copy these to a safe place!** You'll need them later.

### Step 4.3: Update Environment Variables

```bash
# Edit .env file
nano .env
```

**Update these values:**

```bash
# Find and update:
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_REPO=your-username/your-repo

# If using Slack, update:
SLACK_BOT_TOKEN=xoxb-your-slack-token

# Verify these are correct:
ALLOWED_HOSTS=qhog.duckdns.org,www.qhog.duckdns.org,YOUR_PUBLIC_IP
BASE_URL=https://qhog.duckdns.org
```

**How to get GitHub token:**
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Give it a name: "Oracle Cloud Backup"
4. Select scopes: `repo` (full control of private repositories)
5. Click "Generate token"
6. Copy the token (you won't see it again!)

Save the file: `Ctrl+O`, `Enter`, `Ctrl+X`

### Step 4.4: Build Docker Images

```bash
# Build all containers
docker-compose build

# This takes 5-10 minutes
# You'll see:
# - Downloading base images
# - Installing Python packages
# - Collecting static files
```

**If build fails,** check:
- `requirements.txt` exists and is valid
- Dockerfile exists
- You have internet connection on the VM

### Step 4.5: Start All Services

```bash
# Start in detached mode (runs in background)
docker-compose up -d

# View logs
docker-compose logs -f
```

**Watch for these success messages:**

```
redis-1  | Ready to accept connections
web-1    | Performing system checks...
web-1    | System check identified no issues
web-1    | Starting ASGI/Daphne version X.X.X
web-1    | Listening on TCP address 0.0.0.0:8000
nginx-1  | start worker processes
```

Press `Ctrl+C` to exit logs (containers keep running).

**Check all containers are up:**

```bash
docker-compose ps
```

**Expected output:**
```
NAME                COMMAND                  SERVICE   STATUS
scheduler-web-1     "python manage.py..."    web       Up (healthy)
scheduler-redis-1   "redis-server..."        redis     Up (healthy)
scheduler-nginx-1   "nginx -g..."            nginx     Up
```

All should show "Up"! ✅

### Step 4.6: Restore Database on VM

**Copy your backup file to the VM:**

```bash
# On your LOCAL computer (new terminal):
scp -i ~/.ssh/scheduler-key.pem database_backup.json ubuntu@YOUR_PUBLIC_IP:~/scheduler/app/

# Example:
# scp -i ~/.ssh/scheduler-key.pem database_backup.json ubuntu@129.146.123.45:~/scheduler/app/
```

**Back on your VM terminal:**

```bash
# Copy backup into web container
docker cp database_backup.json $(docker ps -qf "name=scheduler.*web"):/tmp/backup.json

# Access Django shell inside container
docker-compose exec web python manage.py shell
```

**In the Django shell, paste the same restore script from Step 3.3:**

(Paste the entire Python script again, but change the file path to `/tmp/backup.json`)

```python
import json
from django.core import serializers
from django.contrib.auth.models import User
from userRegistration.models import UserProfile
from calendarEditor.models import (
    Machine, QueuePreset, QueueEntry, ArchivedMeasurement,
    NotificationPreference, Notification
)

# Load backup file (NOTE: different path!)
with open('/tmp/backup.json', 'r') as f:
    backup = json.load(f)

print(f"Backup date: {backup.get('export_date', 'Unknown')}")
print(f"Backup type: {backup.get('export_type', 'Unknown')}")
print()

models_order = [
    ('auth.User', User),
    ('userRegistration.UserProfile', UserProfile),
    ('calendarEditor.Machine', Machine),
    ('calendarEditor.QueuePreset', QueuePreset),
    ('calendarEditor.QueueEntry', QueueEntry),
    ('calendarEditor.ArchivedMeasurement', ArchivedMeasurement),
    ('calendarEditor.NotificationPreference', NotificationPreference),
    ('calendarEditor.Notification', Notification),
]

for model_name, model_class in models_order:
    if model_name not in backup['models']:
        print(f"⚠️  {model_name} not in backup, skipping")
        continue

    model_data = backup['models'][model_name]

    if isinstance(model_data, dict) and 'error' in model_data:
        print(f"⚠️  {model_name} has error: {model_data['error']}")
        continue

    print(f"Restoring {model_name}...", end=' ')
    count = 0
    errors = 0

    for obj_data in model_data:
        try:
            for deserialized_obj in serializers.deserialize('json', json.dumps([obj_data])):
                deserialized_obj.save()
                count += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"\n  Error: {e}")

    print(f"✓ Restored {count} records" + (f" ({errors} errors)" if errors > 0 else ""))

print("\n✅ Migration complete!")
print(f"Total users: {User.objects.count()}")
print(f"Total machines: {Machine.objects.count()}")
print(f"Total queue entries: {QueueEntry.objects.count()}")

exit()
```

You should see the same success messages as local testing.

### Step 4.7: Test HTTP Access

```bash
# Test via public IP
curl http://YOUR_PUBLIC_IP/schedule/

# Test via domain
curl http://qhog.duckdns.org/schedule/

# Both should return HTML (not errors)
```

**Open browser on your local computer:**

Go to: `http://qhog.duckdns.org/schedule/`

(Replace with your actual domain)

**You should see:**
- ✅ Your scheduler login page
- ✅ Can log in
- ✅ Can see machines and queue

**🎉 Your app is running on Oracle Cloud!**

(Still HTTP only - we'll add HTTPS next)

---

## Part 5: Add HTTPS/SSL (20 minutes)

Now we'll get a free SSL certificate from Let's Encrypt.

**All commands in your Oracle VM terminal.**

### Step 5.1: Install Certbot

```bash
sudo apt install -y certbot
```

### Step 5.2: Stop Nginx Temporarily

```bash
cd ~/scheduler/app
docker-compose stop nginx
```

### Step 5.3: Generate SSL Certificate

```bash
# Replace with YOUR domain and email
sudo certbot certonly --standalone \
  -d qhog.duckdns.org \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email

# Example:
# sudo certbot certonly --standalone \
#   -d qhog.duckdns.org \
#   --email tim@university.edu \
#   --agree-tos \
#   --no-eff-email
```

**You should see:**
```
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/qhog.duckdns.org/fullchain.pem
Key is saved at: /etc/letsencrypt/live/qhog.duckdns.org/privkey.pem
```

✅ SSL certificate obtained!

### Step 5.4: Copy Certificates to App Directory

```bash
# Copy certificates
sudo cp -r /etc/letsencrypt/* ~/scheduler/app/certbot/conf/

# Fix ownership
sudo chown -R ubuntu:ubuntu ~/scheduler/app/certbot/
```

### Step 5.5: Enable HTTPS in Nginx Config

```bash
cd ~/scheduler/app
nano nginx.conf
```

**Find this section (around line 60):**
```nginx
# Temporary: Allow HTTP for initial setup
# After SSL is working, uncomment this redirect:
# location / {
#     return 301 https://$server_name$request_uri;
# }
```

**Uncomment the redirect (remove the #):**
```nginx
location / {
    return 301 https://$server_name$request_uri;
}
```

**Scroll down to line ~70 and find:**
```nginx
# HTTPS server (will enable after SSL setup)
# server {
#     listen 443 ssl http2;
#     ...
# }
```

**Uncomment the entire HTTPS server block** (remove all # symbols from the server block).

**Verify your domain is correct in the HTTPS block:**
```nginx
server {
    listen 443 ssl http2;
    server_name qhog.duckdns.org www.qhog.duckdns.org;

    ssl_certificate /etc/letsencrypt/live/qhog.duckdns.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/qhog.duckdns.org/privkey.pem;

    # ... rest of config
}
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

### Step 5.6: Start Nginx with HTTPS

```bash
# Restart nginx with new config
docker-compose start nginx

# Check for errors
docker-compose logs nginx

# Should see: "start worker processes" with no errors
```

### Step 5.7: Test HTTPS

**Open browser:** `https://qhog.duckdns.org/schedule/`

You should see:
- ✅ Green padlock in address bar
- ✅ "Connection is secure"
- ✅ No SSL warnings
- ✅ Application loads correctly

**Test redirect:**

Visit: `http://qhog.duckdns.org/schedule/` (without 's')

Should automatically redirect to `https://` ✅

### Step 5.8: Set Up Auto-Renewal

SSL certificates expire every 90 days. Auto-renew them:

```bash
# Edit crontab
crontab -e

# Add this line (renews on 1st of every month at 3 AM):
0 3 1 * * /home/ubuntu/renew-ssl.sh >> /home/ubuntu/ssl-renew.log 2>&1
```

**The renewal script** (`~/renew-ssl.sh`) was already created by the setup script.

**Test renewal manually:**
```bash
# Test renewal (won't actually renew yet - cert is brand new)
sudo certbot renew --dry-run

# Should see: "Cert not yet due for renewal"
```

---

## Part 6: Automated Backups (10 minutes)

Set up nightly database backups that run on your VM.

**All commands on your Oracle VM.**

### Step 6.1: Verify Backup Script Exists

The setup script already created `~/backup-database.sh`.

**Test it:**

```bash
# Run backup manually
~/backup-database.sh

# Check result
ls ~/scheduler/backups/
# Should show: database_backup_YYYY-MM-DD_HH-MM-SS.json
```

If you see a backup file, it works! ✅

### Step 6.2: Schedule Nightly Backups

```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 2 AM):
0 2 * * * /home/ubuntu/backup-database.sh >> /home/ubuntu/backup.log 2>&1

# Save: Ctrl+O, Enter, Ctrl+X
```

**View your crontab:**
```bash
crontab -l
```

Should show:
```
*/5 * * * * ~/update-duckdns.sh >/dev/null 2>&1
0 3 1 * * /home/ubuntu/renew-ssl.sh >> /home/ubuntu/ssl-renew.log 2>&1
0 2 * * * /home/ubuntu/backup-database.sh >> /home/ubuntu/backup.log 2>&1
```

✅ Automated backups configured!

**Your VM now automatically:**
- Updates DNS every 5 minutes
- Backs up database daily at 2 AM
- Renews SSL monthly

---

## Part 7: Update GitHub Actions (5 minutes)

**Switch to your LOCAL computer** for this part.

Your existing GitHub Actions workflow still targets Render. Update it for Oracle Cloud:

```bash
cd /Users/timothyrosno/2025-2026/Fall/Stacker_Game/schedulerTEST

# Edit backup workflow
nano .github/workflows/backup-database.yml
```

**Find this line:**
```yaml
https://qhog.onrender.com/schedule/api/backup/database/ \
```

**Replace with your Oracle Cloud domain:**
```yaml
https://qhog.duckdns.org/schedule/api/backup/database/ \
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

**Update GitHub secret:**

1. Go to: https://github.com/YOUR_USERNAME/YOUR_REPO/settings/secrets/actions
2. Find `BACKUP_API_KEY`
3. Click "Update"
4. Paste the new BACKUP_API_KEY (from setup script output)
5. Click "Update secret"

**Commit and push:**

```bash
git add .github/workflows/backup-database.yml
git commit -m "Update backup workflow for Oracle Cloud"
git push origin main
```

**Test the workflow:**

1. Go to: https://github.com/YOUR_USERNAME/YOUR_REPO/actions
2. Click "Backup Database" workflow
3. Click "Run workflow"
4. Check it completes successfully
5. Verify backup appears in `database-backups` branch

---

## Part 8: Final Testing (15 minutes)

**Comprehensive testing checklist:**

### Application Basics

- [ ] Visit `https://qhog.duckdns.org/schedule/`
- [ ] Green padlock shows (SSL valid)
- [ ] No SSL warnings
- [ ] Page loads in <2 seconds
- [ ] Can log in with existing account
- [ ] Can log out
- [ ] Sessions persist (don't get logged out)

### Core Features

- [ ] View machines list
- [ ] Create new queue entry
- [ ] Edit existing queue entry
- [ ] Delete queue entry
- [ ] Archive measurement
- [ ] View archived measurements
- [ ] Upload file to archived measurement
- [ ] Download uploaded file
- [ ] View notifications
- [ ] Mark notification as read
- [ ] Clear all notifications

### Real-Time Features (WebSockets)

- [ ] Open app in two browsers
- [ ] Create queue entry in Browser 1
- [ ] See it appear instantly in Browser 2 (no refresh)
- [ ] Edit entry in Browser 1
- [ ] See changes in Browser 2 instantly

### Admin Features

- [ ] Access admin dashboard
- [ ] View storage statistics
- [ ] Export database backup manually
- [ ] Import database backup (test with small backup)
- [ ] View Render usage page (will be zeroed out)
- [ ] Database management page loads

### Performance Tests

- [ ] Create 20 queue entries rapidly (no rate limits!)
- [ ] Delete them all
- [ ] Run admin actions repeatedly
- [ ] No "CU limit" errors
- [ ] No "rate limit" errors

### Backup Tests

- [ ] Manual backup via admin downloads valid JSON
- [ ] Check `~/scheduler/backups/` has backup files
- [ ] Backup files are valid JSON (not error pages)
- [ ] Can restore from backup without errors

**If all tests pass:** Migration successful! 🎉

---

## Part 9: Decommission Render (Wait 48 Hours)

**DO NOT rush this step.** Keep Render running until you're 100% sure Oracle Cloud is stable.

### Day 1-2: Monitor Oracle Cloud

Watch for:
- Application stays up 24/7
- No errors in logs: `docker-compose logs`
- Nightly backups run successfully
- SSL certificate valid
- Users can access without issues

**Check logs:**
```bash
# On your Oracle VM
cd ~/scheduler/app

# Application logs
docker-compose logs --tail=100 web

# Nginx logs
docker-compose logs --tail=100 nginx

# Backup log
tail -50 ~/backup.log

# SSL renewal log
tail -50 ~/ssl-renew.log
```

### Day 3: Final Backup from Render

**Before deleting Render:**

1. Go to: https://qhog.onrender.com/schedule/admin/database/
2. Export one final backup
3. Save it safely: `render_final_backup.json`
4. Store it somewhere safe (external drive, cloud storage)

### Day 3: Delete Render Service

1. Go to: https://dashboard.render.com/
2. Click on `qhog` service
3. Settings → Delete Service
4. Type service name to confirm
5. Click "Delete"

### Day 3: Delete Neon/Supabase Database

If you were using external PostgreSQL:

1. Go to Neon/Supabase dashboard
2. Delete the database project
3. Confirm deletion

**You're now 100% on Oracle Cloud! 🎉**

---

## Your New Production Setup

### Access Information

**Application URL:** `https://qhog.duckdns.org/schedule/`
**Admin Dashboard:** `https://qhog.duckdns.org/schedule/admin/`

**SSH to VM:**
```bash
ssh -i ~/.ssh/scheduler-key.pem ubuntu@YOUR_PUBLIC_IP
```

**Application directory on VM:** `~/scheduler/app/`

### What Runs 24/7 on Your VM

```
Oracle Cloud VM (12GB RAM, 2 CPU, 200GB storage)
├── Django App (Daphne/ASGI)
│   └── SQLite database in ~/scheduler/app/data/
├── Redis (caching + WebSockets)
├── Nginx (reverse proxy + SSL termination)
└── Cron jobs:
    ├── DuckDNS update (every 5 min)
    ├── Database backup (daily 2 AM)
    └── SSL renewal (monthly)
```

### Resources

**Total cost:** $0/month forever

**Limits:**
- Database queries: Unlimited ✅
- Storage: 200GB (using ~0.5GB)
- RAM: 12GB (using ~2GB)
- CPU: 2 cores
- Bandwidth: 10TB/month

**Perfect for:**
- <50 concurrent users ✅
- Hourly reminders ✅
- Nightly backups ✅
- Real-time WebSocket updates ✅

---

## Common Maintenance Tasks

### View Application Logs

```bash
ssh -i ~/.ssh/scheduler-key.pem ubuntu@YOUR_PUBLIC_IP
cd ~/scheduler/app

# Real-time logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100 web

# Specific service
docker-compose logs redis
docker-compose logs nginx
```

### Restart Application

```bash
ssh -i ~/.ssh/scheduler-key.pem ubuntu@YOUR_PUBLIC_IP
cd ~/scheduler/app

# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart web
```

### Update Application Code

```bash
ssh -i ~/.ssh/scheduler-key.pem ubuntu@YOUR_PUBLIC_IP
cd ~/scheduler/app

# Pull latest code
git pull origin main

# Rebuild containers
docker-compose build

# Restart
docker-compose restart

# Run new migrations (if any)
docker-compose exec web python manage.py migrate
```

### Check Disk Space

```bash
# Check VM disk usage
df -h

# Check Docker disk usage
docker system df

# Clean up old Docker images (saves space)
docker system prune -a
```

### Manual Database Backup

```bash
# Run backup script
~/backup-database.sh

# Check backups
ls -lh ~/scheduler/backups/

# Download backup to your computer
# On your LOCAL computer:
scp -i ~/.ssh/scheduler-key.pem ubuntu@YOUR_PUBLIC_IP:~/scheduler/backups/database_backup_*.json ./
```

### Check Scheduled Jobs

```bash
# View crontab
crontab -l

# View backup log
tail -50 ~/backup.log

# View SSL renewal log
tail -50 ~/ssl-renew.log

# View DuckDNS log
cat ~/duckdns.log
```

---

## Troubleshooting

### Application won't start

```bash
# Check logs
docker-compose logs web

# Common issues:
# 1. Missing .env file
ls -la .env

# 2. Redis not running
docker-compose ps redis

# 3. Database migration errors
docker-compose exec web python manage.py migrate
```

### SSL certificate errors

```bash
# Check certificate files exist
ls -la ~/scheduler/app/certbot/conf/live/

# Renew certificate manually
docker-compose stop nginx
sudo certbot renew
sudo cp -r /etc/letsencrypt/* ~/scheduler/app/certbot/conf/
sudo chown -R ubuntu:ubuntu ~/scheduler/app/certbot/
docker-compose start nginx
```

### Domain not resolving

```bash
# Test DNS
ping qhog.duckdns.org
nslookup qhog.duckdns.org

# Update DuckDNS manually
~/update-duckdns.sh
cat ~/duckdns.log
# Should show: OK

# Wait 2-3 minutes and try again
```

### Out of disk space

```bash
# Check disk usage
df -h

# Clean up Docker
docker system prune -a

# Clean up old backups (keeps last 30)
cd ~/scheduler/backups
ls -t database_backup_*.json | tail -n +31 | xargs rm
```

### Can't SSH to VM

```bash
# Check SSH key permissions
chmod 600 ~/.ssh/scheduler-key.pem

# Verify IP is correct (might have changed if VM recreated)
# Go to Oracle Cloud Console → Compute → Instances

# Check Oracle Cloud firewall allows port 22
# Networking → VCN → Security Lists
```

---

## Security Best Practices

Your setup is already secure, but here are important notes:

**What's secure:**
- ✅ HTTPS with valid SSL certificate
- ✅ Firewall restricts access to only necessary ports
- ✅ Django SECRET_KEY is random and secret
- ✅ Passwords never transmitted over HTTP
- ✅ SQLite file not web-accessible
- ✅ Admin requires login

**Additional security tips:**
- Keep Django updated: `pip install --upgrade django`
- Keep Ubuntu updated: `sudo apt update && sudo apt upgrade`
- Monitor logs for suspicious activity
- Use strong passwords for admin accounts
- Don't share your SSH key or API keys

---

## Success Summary

### What You Built

A production-grade Django application running on Oracle Cloud with:

**Infrastructure:**
- Oracle Cloud VM (2 CPU, 12GB RAM, 200GB storage)
- Docker containerization
- Nginx reverse proxy
- Redis for caching and WebSockets

**Features:**
- Free domain (DuckDNS)
- Free SSL certificate (Let's Encrypt)
- SQLite database (no limits!)
- Automated backups (daily)
- Automated SSL renewal (monthly)
- 24/7 uptime

**Cost:** $0/month forever

**Limits:** None! Unlimited queries, unlimited users (within VM capacity)

### Before vs After

**Before (Render + Neon):**
- ❌ 4.28 CU/day (too high!)
- ❌ Database restore broken (unique constraints)
- ❌ Hitting rate limits
- ❌ Worried about costs

**After (Oracle Cloud):**
- ✅ Unlimited queries
- ✅ SQLite (no sequence issues)
- ✅ No rate limits
- ✅ $0/month forever
- ✅ More resources (12GB RAM vs shared)

---

## Questions?

**Check these resources:**
- **This guide** - Complete reference
- **MIGRATION_CHECKLIST.md** - Quick task list
- **Oracle Cloud docs:** https://docs.oracle.com/en-us/iaas/
- **DuckDNS help:** https://www.duckdns.org/
- **Docker docs:** https://docs.docker.com/

**Common questions answered in this guide:**
- "Where does the application run?" → Oracle Cloud VM, 24/7
- "Do I need to keep my computer on?" → No! VM runs on Oracle's servers
- "What if my IP changes?" → Auto-update script handles it
- "How do I update the app?" → SSH to VM, git pull, docker-compose restart

---

## Congratulations! 🎉

You've successfully migrated your Django scheduler to Oracle Cloud with SQLite!

**Your application is now:**
- Running 24/7 on production infrastructure
- Accessible via HTTPS with your free domain
- Backed up automatically every night
- Completely free to run forever
- Scalable to handle your lab's needs

**Next steps:**
- Use it! Your users can access it at your DuckDNS domain
- Monitor logs for the first few days
- Set calendar reminder to check it monthly
- Share the URL with your lab members

**You did it! 🚀**
