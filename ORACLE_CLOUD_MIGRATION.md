# Oracle Cloud + SQLite Migration Guide

Complete step-by-step guide to migrate your Django scheduler app from Render + PostgreSQL to Oracle Cloud + SQLite.

**Time required:** 2-3 hours
**Cost:** $0/month forever
**Result:** Unlimited queries, 24/7 uptime, no rate limits

---

## Prerequisites

- Oracle Cloud account (we'll create this)
- Domain name (your current domain)
- GitHub repository access
- Current Render backup file

---

## Part 1: Oracle Cloud Setup (45 minutes)

### Step 1.1: Create Oracle Cloud Account

1. Go to https://www.oracle.com/cloud/free/
2. Click "Start for free"
3. Fill in account details:
   - Email address
   - Country/Region
   - Cloud Account Name (use lowercase, letters/numbers only)
4. Complete verification (credit card required but **never charged** for Always Free)
5. Wait for account activation email (5-10 minutes)

### Step 1.2: Create Compute Instance (VM)

1. Sign in to Oracle Cloud Console: https://cloud.oracle.com/
2. Click hamburger menu (☰) → **Compute** → **Instances**
3. Click **"Create Instance"**

**Instance Configuration:**

```
Name: django-scheduler
Image: Ubuntu 22.04
Shape: VM.Standard.A1.Flex (Ampere ARM - Always Free)
  - OCPUs: 2
  - Memory: 12 GB
  (You can use all 4 cores/24GB if you want, but 2/12 is plenty)

Network:
  - Create new VCN: Yes
  - VCN Name: scheduler-vcn
  - Subnet: Public subnet
  - Assign public IPv4: Yes

SSH Keys:
  - Generate SSH key pair (DOWNLOAD BOTH KEYS!)
  - Save private key as: scheduler-key.pem
  - Save public key for reference
```

4. Click **"Create"**
5. Wait for instance state: **RUNNING** (2-3 minutes)
6. **Copy the Public IP address** - you'll need this!

### Step 1.3: Configure Firewall Rules

Oracle Cloud has two firewalls you must configure:

#### A. Cloud Firewall (Security List)

1. Go to **Networking** → **Virtual Cloud Networks**
2. Click your VCN: **scheduler-vcn**
3. Click **Security Lists** → **Default Security List**
4. Click **"Add Ingress Rules"**

Add these rules:

```
Rule 1 - HTTP:
  Source CIDR: 0.0.0.0/0
  IP Protocol: TCP
  Destination Port: 80
  Description: HTTP traffic

Rule 2 - HTTPS:
  Source CIDR: 0.0.0.0/0
  IP Protocol: TCP
  Destination Port: 443
  Description: HTTPS traffic

Rule 3 - SSH (already exists, verify):
  Source CIDR: 0.0.0.0/0
  IP Protocol: TCP
  Destination Port: 22
  Description: SSH access
```

5. Click **"Add Ingress Rules"**

#### B. VM Firewall (iptables)

We'll configure this after SSH access.

### Step 1.4: Connect to Your VM

**On macOS/Linux:**

```bash
# Move SSH key to .ssh directory
mkdir -p ~/.ssh
mv ~/Downloads/scheduler-key.pem ~/.ssh/
chmod 600 ~/.ssh/scheduler-key.pem

# Connect to VM (replace with YOUR public IP)
ssh -i ~/.ssh/scheduler-key.pem ubuntu@YOUR_PUBLIC_IP
```

**On Windows:**

Use PuTTY or Windows Terminal with the downloaded key.

**First time:** You'll see "Are you sure you want to continue connecting?" → Type **yes**

You should see: `ubuntu@django-scheduler:~$`

---

## Part 2: VM Configuration (30 minutes)

### Step 2.1: Update System

```bash
# Update package list
sudo apt update

# Upgrade all packages
sudo apt upgrade -y

# Install essential tools
sudo apt install -y curl git wget nano ufw
```

### Step 2.2: Configure VM Firewall

```bash
# Allow SSH (IMPORTANT - do this first or you'll lock yourself out!)
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw --force enable

# Verify rules
sudo ufw status
```

Expected output:
```
Status: active
To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                     ALLOW       Anywhere
```

### Step 2.3: Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (avoid sudo)
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version

# IMPORTANT: Log out and back in for group changes to take effect
exit
```

**Reconnect to VM:**
```bash
ssh -i ~/.ssh/scheduler-key.pem ubuntu@YOUR_PUBLIC_IP
```

### Step 2.4: Create Application Directory

```bash
# Create app directory
mkdir -p ~/scheduler
cd ~/scheduler

# Create required directories
mkdir -p data media staticfiles backups logs
```

---

## Part 3: Migrate from PostgreSQL to SQLite (20 minutes)

### Step 3.1: Export Current Database from Render

**Option A: Use your existing backup file**

If you have a recent backup from GitHub or manual export, skip to Step 3.3.

**Option B: Export fresh backup from Render**

1. Go to your Render app: https://qhog.onrender.com/schedule/admin/database/
2. Click **"Export Complete Database"**
3. Save file as: `database_backup_YYYY-MM-DD.json`

### Step 3.2: Update Django Settings for SQLite

We'll create new settings that work with both PostgreSQL (local dev) and SQLite (production).

Your current `mysite/settings.py` already supports this! When `DATABASE_URL` is not set, it uses SQLite.

**Verify this in your codebase:**

```python
# In mysite/settings.py (lines 148-172)
database_url = os.environ.get('DATABASE_URL')

if database_url:
    # Production: Use PostgreSQL via DATABASE_URL
    DATABASES = {...}
else:
    # Local development: SQLite
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
```

✅ **This is already correct!** No changes needed.

### Step 3.3: Test SQLite Migration Locally

Before deploying to Oracle Cloud, test the migration locally:

```bash
# Make sure you're in your project directory
cd /Users/timothyrosno/2025-2026/Fall/Stacker_Game/schedulerTEST

# Remove DATABASE_URL to force SQLite mode
unset DATABASE_URL

# Create fresh SQLite database
rm -f db.sqlite3
python manage.py migrate

# Load your backup
python manage.py shell
```

In the Python shell:
```python
import json
from django.core import serializers
from django.contrib.auth.models import User
from userRegistration.models import UserProfile
from calendarEditor.models import Machine, QueuePreset, QueueEntry, ArchivedMeasurement, NotificationPreference, Notification

# Load backup file (adjust path to your backup)
with open('path/to/database_backup_YYYY-MM-DD.json', 'r') as f:
    backup = json.load(f)

# Restore models in order
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
    if model_name in backup['models']:
        print(f"Restoring {model_name}...")
        for obj_data in backup['models'][model_name]:
            try:
                for deserialized_obj in serializers.deserialize('json', json.dumps([obj_data])):
                    deserialized_obj.save()
            except Exception as e:
                print(f"Error: {e}")
        print(f"✓ Restored {model_class.objects.count()} {model_name} records")

print("\n✓ Migration complete!")
exit()
```

**Test the app:**
```bash
python manage.py runserver
```

Visit http://127.0.0.1:8000 and verify:
- ✅ You can log in
- ✅ Machines are listed
- ✅ Queue entries exist
- ✅ Everything works

**Success?** Continue to deployment. **Errors?** Debug before proceeding.

---

## Part 4: Deploy to Oracle Cloud (45 minutes)

### Step 4.1: Push Code to GitHub

Make sure your latest code is in GitHub:

```bash
cd /Users/timothyrosno/2025-2026/Fall/Stacker_Game/schedulerTEST

# Check status
git status

# Add any changes
git add .
git commit -m "Prepare for Oracle Cloud migration - SQLite ready"
git push origin main
```

### Step 4.2: Clone Repository on VM

```bash
# SSH to your VM
ssh -i ~/.ssh/scheduler-key.pem ubuntu@YOUR_PUBLIC_IP

# Clone your repository
cd ~/scheduler
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git app
cd app

# Verify files
ls -la
```

### Step 4.3: Create Docker Configuration

Create `Dockerfile`:

```bash
nano Dockerfile
```

Paste this content:

```dockerfile
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create directories
RUN mkdir -p /app/data /app/media /app/staticfiles

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Run migrations and start server
CMD python manage.py migrate && \
    python manage.py create_superuser_if_none && \
    daphne -b 0.0.0.0 -p 8000 mysite.asgi:application
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

### Step 4.4: Create Docker Compose Configuration

```bash
nano docker-compose.yml
```

Paste this content:

```yaml
version: '3.8'

services:
  # Redis for Django Channels and caching
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis-data:/data
    networks:
      - scheduler-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Django application
  web:
    build: .
    restart: unless-stopped
    volumes:
      - ./data:/app/data              # SQLite database
      - ./media:/app/media            # User uploads
      - ./staticfiles:/app/staticfiles # Static files
      - ./logs:/app/logs              # Application logs
    ports:
      - "8000:8000"
    environment:
      - DEBUG=False
      - SECRET_KEY=${SECRET_KEY}
      - ALLOWED_HOSTS=${ALLOWED_HOSTS}
      - REDIS_URL=redis://redis:6379
      - BASE_URL=${BASE_URL}
      - SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}
      - TEMPERATURE_GATEWAY_API_KEY=${TEMPERATURE_GATEWAY_API_KEY}
      - BACKUP_API_KEY=${BACKUP_API_KEY}
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - GITHUB_REPO=${GITHUB_REPO}
    depends_on:
      - redis
    networks:
      - scheduler-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/schedule/"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Nginx reverse proxy
  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./staticfiles:/usr/share/nginx/html/static:ro
      - ./media:/usr/share/nginx/html/media:ro
      - ./certbot/conf:/etc/letsencrypt:ro
      - ./certbot/www:/var/www/certbot:ro
    depends_on:
      - web
    networks:
      - scheduler-network

volumes:
  redis-data:

networks:
  scheduler-network:
    driver: bridge
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

### Step 4.5: Create Nginx Configuration

```bash
nano nginx.conf
```

Paste this content:

```nginx
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=api:10m rate=5r/s;

    upstream django {
        server web:8000;
    }

    # HTTP server (redirect to HTTPS after SSL is set up)
    server {
        listen 80;
        server_name YOUR_DOMAIN.com www.YOUR_DOMAIN.com;

        # Let's Encrypt verification
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        # Temporary: Allow HTTP for initial setup
        # After SSL is working, uncomment this redirect:
        # location / {
        #     return 301 https://$server_name$request_uri;
        # }

        # Static files
        location /static/ {
            alias /usr/share/nginx/html/static/;
            expires 30d;
            add_header Cache-Control "public, immutable";
        }

        # Media files
        location /media/ {
            alias /usr/share/nginx/html/media/;
            expires 7d;
            add_header Cache-Control "public";
        }

        # Proxy to Django
        location / {
            proxy_pass http://django;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # WebSocket support
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";

            # Timeouts for long-running requests
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }
    }

    # HTTPS server (will enable after SSL setup)
    # server {
    #     listen 443 ssl http2;
    #     server_name YOUR_DOMAIN.com www.YOUR_DOMAIN.com;
    #
    #     ssl_certificate /etc/letsencrypt/live/YOUR_DOMAIN.com/fullchain.pem;
    #     ssl_certificate_key /etc/letsencrypt/live/YOUR_DOMAIN.com/privkey.pem;
    #
    #     # SSL configuration
    #     ssl_protocols TLSv1.2 TLSv1.3;
    #     ssl_prefer_server_ciphers on;
    #     ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    #
    #     # Static and media files
    #     location /static/ {
    #         alias /usr/share/nginx/html/static/;
    #         expires 30d;
    #     }
    #
    #     location /media/ {
    #         alias /usr/share/nginx/html/media/;
    #         expires 7d;
    #     }
    #
    #     # Proxy to Django
    #     location / {
    #         proxy_pass http://django;
    #         proxy_set_header Host $host;
    #         proxy_set_header X-Real-IP $remote_addr;
    #         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    #         proxy_set_header X-Forwarded-Proto $scheme;
    #         proxy_http_version 1.1;
    #         proxy_set_header Upgrade $http_upgrade;
    #         proxy_set_header Connection "upgrade";
    #     }
    # }
}
```

**IMPORTANT:** Replace `YOUR_DOMAIN.com` with your actual domain!

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

### Step 4.6: Create Environment Variables

```bash
nano .env
```

Paste this content (update with your values):

```bash
# Django settings
SECRET_KEY=your-secret-key-here-generate-new-one
DEBUG=False
ALLOWED_HOSTS=YOUR_DOMAIN.com,www.YOUR_DOMAIN.com,YOUR_PUBLIC_IP

# Base URL
BASE_URL=https://YOUR_DOMAIN.com

# Slack (optional - leave empty if not using)
SLACK_BOT_TOKEN=

# Temperature Gateway API (optional)
TEMPERATURE_GATEWAY_API_KEY=

# Backup API key (generate new)
BACKUP_API_KEY=your-backup-key-here

# GitHub (for backups)
GITHUB_TOKEN=your-github-token
GITHUB_REPO=your-username/your-repo
```

**Generate SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

**Generate BACKUP_API_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

### Step 4.7: Build and Start Application

```bash
# Build Docker image
docker-compose build

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f

# Wait for:
# ✓ Redis: Ready to accept connections
# ✓ Web: Performing system checks...
# ✓ Web: Django version X.X.X, using settings 'mysite.settings'
# ✓ Web: Starting ASGI/Daphne version X.X.X
# ✓ Nginx: start worker processes

# Press Ctrl+C to exit logs
```

### Step 4.8: Restore Database

```bash
# Copy your backup file to VM (from your local machine)
# On your LOCAL machine:
scp -i ~/.ssh/scheduler-key.pem database_backup_YYYY-MM-DD.json ubuntu@YOUR_PUBLIC_IP:~/scheduler/app/

# Back on the VM, restore via Django admin:
```

1. Visit: http://YOUR_PUBLIC_IP/schedule/admin/
2. Log in (use the superuser created during setup)
3. Go to **Database Management**
4. Upload your backup file
5. Select **Replace mode**
6. Click **Import Database**

**Or restore via command line:**

```bash
# Copy backup into Docker container
docker cp database_backup_YYYY-MM-DD.json scheduler-web-1:/tmp/backup.json

# Access Django shell
docker-compose exec web python manage.py shell

# In Python shell, paste the restore script from Step 3.3
```

### Step 4.9: Verify Application

```bash
# Check all services are running
docker-compose ps

# Should show:
# NAME                COMMAND              SERVICE   STATUS
# scheduler-web-1     "python manage.py..."  web      Up (healthy)
# scheduler-redis-1   "redis-server..."      redis    Up (healthy)
# scheduler-nginx-1   "nginx -g..."          nginx    Up

# Test HTTP access
curl http://YOUR_PUBLIC_IP/schedule/

# You should see HTML content (not errors)
```

Visit in browser: `http://YOUR_PUBLIC_IP/schedule/`

✅ **Application should be running!**

---

## Part 5: DNS and SSL Setup (30 minutes)

### Step 5.1: Update DNS Records

Go to your domain registrar (where you bought YOUR_DOMAIN.com):

**Add/Update A Records:**

```
Type: A
Name: @
Value: YOUR_PUBLIC_IP
TTL: 3600

Type: A
Name: www
Value: YOUR_PUBLIC_IP
TTL: 3600
```

Wait 5-10 minutes for DNS propagation.

**Test DNS:**
```bash
nslookup YOUR_DOMAIN.com
# Should return YOUR_PUBLIC_IP
```

### Step 5.2: Install SSL Certificate (Let's Encrypt)

```bash
# On your VM
cd ~/scheduler/app

# Create certbot directories
mkdir -p certbot/conf certbot/www

# Install certbot
sudo apt install -y certbot

# Stop nginx temporarily
docker-compose stop nginx

# Generate certificate (replace with your domain and email)
sudo certbot certonly --standalone \
  -d YOUR_DOMAIN.com \
  -d www.YOUR_DOMAIN.com \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email

# Copy certificates to certbot directory
sudo cp -r /etc/letsencrypt/* certbot/conf/

# Fix permissions
sudo chown -R ubuntu:ubuntu certbot/

# Start nginx
docker-compose start nginx
```

### Step 5.3: Enable HTTPS in Nginx

```bash
nano nginx.conf
```

1. Uncomment the HTTPS redirect in the HTTP server block:
```nginx
location / {
    return 301 https://$server_name$request_uri;
}
```

2. Uncomment the entire HTTPS server block

3. Replace `YOUR_DOMAIN.com` with your actual domain

Save and restart:
```bash
docker-compose restart nginx
```

**Test HTTPS:**
Visit: `https://YOUR_DOMAIN.com/schedule/`

✅ **SSL should be working!**

### Step 5.4: Set Up Auto-Renewal

```bash
# Create renewal script
nano ~/renew-ssl.sh
```

Paste:
```bash
#!/bin/bash
cd ~/scheduler/app
docker-compose stop nginx
sudo certbot renew
sudo cp -r /etc/letsencrypt/* certbot/conf/
sudo chown -R ubuntu:ubuntu certbot/
docker-compose start nginx
```

Make executable:
```bash
chmod +x ~/renew-ssl.sh

# Add to crontab (runs monthly)
crontab -e

# Add this line:
0 3 1 * * /home/ubuntu/renew-ssl.sh >> /home/ubuntu/ssl-renew.log 2>&1
```

---

## Part 6: Automated Backups (15 minutes)

### Step 6.1: Create Backup Script

```bash
nano ~/backup-database.sh
```

Paste:
```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/home/ubuntu/scheduler/backups"
BACKUP_API_KEY="your-backup-api-key-from-env"
APP_URL="https://YOUR_DOMAIN.com"
DATE=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_FILE="${BACKUP_DIR}/database_backup_${DATE}.json"

# Create backup directory
mkdir -p ${BACKUP_DIR}

# Export database via API
curl -H "Authorization: Bearer ${BACKUP_API_KEY}" \
  ${APP_URL}/schedule/api/backup/database/ \
  -o ${BACKUP_FILE}

# Check if backup was successful
if [ -s ${BACKUP_FILE} ]; then
    echo "✓ Backup created: ${BACKUP_FILE}"

    # Keep only last 30 backups
    cd ${BACKUP_DIR}
    ls -t database_backup_*.json | tail -n +31 | xargs -r rm

    echo "✓ Old backups cleaned up"
else
    echo "✗ Backup failed"
    exit 1
fi
```

Make executable:
```bash
chmod +x ~/backup-database.sh

# Test backup
./backup-database.sh
```

### Step 6.2: Schedule Nightly Backups

```bash
# Add to crontab
crontab -e

# Add this line (runs daily at 2 AM):
0 2 * * * /home/ubuntu/backup-database.sh >> /home/ubuntu/backup.log 2>&1
```

### Step 6.3: Optional: Push Backups to GitHub

Update `backup-database.sh` to push to GitHub:

```bash
# At the end of backup-database.sh, add:

# Push to GitHub
cd ${BACKUP_DIR}
git init
git add database_backup_${DATE}.json
git commit -m "Automated backup ${DATE}"
git push https://YOUR_GITHUB_TOKEN@github.com/YOUR_USERNAME/YOUR_REPO.git main:database-backups --force
```

---

## Part 7: Update GitHub Actions (5 minutes)

Your existing GitHub Actions backup workflow targets Render. Update it to target Oracle Cloud:

```bash
# On your LOCAL machine
cd /Users/timothyrosno/2025-2026/Fall/Stacker_Game/schedulerTEST
nano .github/workflows/backup-database.yml
```

Update the URL:
```yaml
- name: Backup Database
  run: |
    curl -H "Authorization: Bearer ${{ secrets.BACKUP_API_KEY }}" \
      https://YOUR_DOMAIN.com/schedule/api/backup/database/ \
      -o backups/database_backup_$(date +%Y-%m-%d_%H-%M-%S).json
```

Commit and push:
```bash
git add .github/workflows/backup-database.yml
git commit -m "Update backup workflow for Oracle Cloud"
git push origin main
```

---

## Part 8: Final Testing Checklist

### Test Everything:

```bash
# 1. Application loads
✓ Visit https://YOUR_DOMAIN.com/schedule/
✓ No SSL warnings
✓ Page loads correctly

# 2. User authentication
✓ Log in works
✓ Log out works
✓ Sessions persist

# 3. Core functionality
✓ View machines
✓ Create queue entry
✓ Edit queue entry
✓ Archive measurement
✓ View notifications

# 4. Real-time features (WebSockets)
✓ Queue updates in real-time
✓ Notifications appear instantly
✓ Temperature updates (if using gateway)

# 5. Admin features
✓ Admin dashboard loads
✓ Database management works
✓ Can export backup
✓ Can import backup (test with small backup)

# 6. Performance
✓ Pages load in <2 seconds
✓ No query limits (run admin actions repeatedly)
✓ Handles 10+ concurrent users (test with friends)

# 7. Backups
✓ Manual backup via admin works
✓ Automatic nightly backup runs (check tomorrow)
✓ Backup files are valid JSON
✓ Can restore from backup
```

---

## Part 9: Decommission Render

Once everything is working on Oracle Cloud:

1. Update your domain DNS to point to Oracle Cloud (done in Step 5.1)
2. Wait 24 hours for DNS propagation
3. Verify no traffic is going to Render (check Render logs)
4. Download one final backup from Render
5. Delete Render service:
   - Go to Render dashboard
   - Settings → Delete Service
6. Delete Neon/Supabase database (if applicable)

---

## Troubleshooting

### Application won't start

```bash
# Check logs
docker-compose logs web

# Common issues:
# - Missing environment variables → Check .env file
# - Port already in use → sudo lsof -i :8000
# - Database migration errors → docker-compose exec web python manage.py migrate
```

### SSL certificate fails

```bash
# Make sure DNS is pointing to your VM
nslookup YOUR_DOMAIN.com

# Make sure ports 80/443 are open
sudo ufw status
curl http://YOUR_DOMAIN.com

# Try manual certificate
sudo certbot certonly --standalone -d YOUR_DOMAIN.com
```

### Can't connect to VM

```bash
# Check SSH key permissions
chmod 600 ~/.ssh/scheduler-key.pem

# Verify public IP is correct
# Go to Oracle Cloud Console → Compute → Instances → Copy IP

# Check Oracle Cloud firewall rules
# Networking → VCN → Security Lists → Verify port 22 is open
```

### Redis connection errors

```bash
# Restart Redis
docker-compose restart redis

# Check Redis is running
docker-compose ps redis

# Test Redis connection
docker-compose exec redis redis-cli ping
# Should return: PONG
```

### Database locked errors (SQLite)

SQLite uses file locking. If you see "database is locked" errors:

```bash
# Check for stale connections
docker-compose restart web

# This is rare with Django but can happen with:
# - Long-running queries
# - Multiple processes accessing DB simultaneously

# If persistent, check Django settings:
# DATABASES['default']['OPTIONS'] = {'timeout': 20}
```

---

## Maintenance

### Update Application Code

```bash
# SSH to VM
ssh -i ~/.ssh/scheduler-key.pem ubuntu@YOUR_PUBLIC_IP

# Pull latest code
cd ~/scheduler/app
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d

# Run migrations (if any)
docker-compose exec web python manage.py migrate

# Collect static files (if changed)
docker-compose exec web python manage.py collectstatic --noinput
```

### Monitor Disk Usage

```bash
# Check disk space
df -h

# Check Docker disk usage
docker system df

# Clean up old Docker images
docker system prune -a
```

### View Logs

```bash
# Real-time logs
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f redis
docker-compose logs -f nginx

# View last 100 lines
docker-compose logs --tail=100 web
```

### Restart Services

```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart web
docker-compose restart nginx

# Stop and start (full restart)
docker-compose down
docker-compose up -d
```

---

## Cost Breakdown

**Oracle Cloud Always Free:**
- Compute: $0/month (2 OCPU, 12GB RAM)
- Storage: $0/month (200GB block storage)
- Bandwidth: $0/month (10TB outbound)

**Domain Name:**
- $10-15/year (you already have this)

**Total: $0/month forever!**

---

## Summary

You now have:
- ✅ Unlimited database queries (no CU limits)
- ✅ 24/7 uptime with 12GB RAM, 2 CPU cores
- ✅ 200GB storage (400x your needs)
- ✅ SQLite database (no restore issues)
- ✅ Automated nightly backups
- ✅ SSL certificate with auto-renewal
- ✅ Docker containerization
- ✅ Nginx reverse proxy
- ✅ Redis for real-time features
- ✅ $0/month hosting cost

**Questions?** Check the Troubleshooting section or contact me.

**Ready to start?** Begin with Part 1: Oracle Cloud Setup.
