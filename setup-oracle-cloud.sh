#!/bin/bash
# Oracle Cloud Quick Setup Script
# Run this on your Oracle Cloud VM after cloning the repository
#
# Usage: ./setup-oracle-cloud.sh YOUR_DOMAIN.com YOUR_PUBLIC_IP

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check arguments
if [ "$#" -ne 2 ]; then
    echo -e "${RED}Error: Missing arguments${NC}"
    echo "Usage: ./setup-oracle-cloud.sh YOUR_DOMAIN.com YOUR_PUBLIC_IP"
    echo "Example: ./setup-oracle-cloud.sh scheduler.example.com 123.45.67.89"
    exit 1
fi

DOMAIN=$1
PUBLIC_IP=$2

echo -e "${GREEN}Oracle Cloud Setup Script${NC}"
echo "Domain: $DOMAIN"
echo "Public IP: $PUBLIC_IP"
echo ""

# Confirm
read -p "Continue with setup? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled"
    exit 1
fi

echo -e "\n${YELLOW}Step 1: Generating secrets...${NC}"

# Generate secrets
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
BACKUP_API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

echo "✓ Secrets generated"

echo -e "\n${YELLOW}Step 2: Creating .env file...${NC}"

# Create .env file
cat > .env << EOF
# Django settings
SECRET_KEY=$SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=$DOMAIN,www.$DOMAIN,$PUBLIC_IP

# Base URL
BASE_URL=https://$DOMAIN

# Slack (optional - leave empty if not using)
SLACK_BOT_TOKEN=

# Temperature Gateway API (optional)
TEMPERATURE_GATEWAY_API_KEY=

# Backup API key
BACKUP_API_KEY=$BACKUP_API_KEY

# GitHub (for backups - update with your values)
GITHUB_TOKEN=your-github-token-here
GITHUB_REPO=your-username/your-repo
EOF

echo "✓ .env file created"

echo -e "\n${YELLOW}Step 3: Creating nginx.conf...${NC}"

# Create nginx.conf
cat > nginx.conf << 'NGINX_EOF'
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss;

    limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=api:10m rate=5r/s;

    upstream django {
        server web:8000;
    }

    server {
        listen 80;
        server_name DOMAIN_PLACEHOLDER www.DOMAIN_PLACEHOLDER;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location /static/ {
            alias /usr/share/nginx/html/static/;
            expires 30d;
            add_header Cache-Control "public, immutable";
        }

        location /media/ {
            alias /usr/share/nginx/html/media/;
            expires 7d;
            add_header Cache-Control "public";
        }

        location / {
            proxy_pass http://django;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }
    }
}
NGINX_EOF

# Replace domain placeholder
sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" nginx.conf

echo "✓ nginx.conf created"

echo -e "\n${YELLOW}Step 4: Creating backup script...${NC}"

# Create backup script
cat > ~/backup-database.sh << EOF
#!/bin/bash

BACKUP_DIR="/home/ubuntu/scheduler/backups"
BACKUP_API_KEY="$BACKUP_API_KEY"
APP_URL="https://$DOMAIN"
DATE=\$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_FILE="\${BACKUP_DIR}/database_backup_\${DATE}.json"

mkdir -p \${BACKUP_DIR}

curl -H "Authorization: Bearer \${BACKUP_API_KEY}" \
  \${APP_URL}/schedule/api/backup/database/ \
  -o \${BACKUP_FILE}

if [ -s \${BACKUP_FILE} ]; then
    echo "✓ Backup created: \${BACKUP_FILE}"
    cd \${BACKUP_DIR}
    ls -t database_backup_*.json | tail -n +31 | xargs -r rm
    echo "✓ Old backups cleaned up"
else
    echo "✗ Backup failed"
    exit 1
fi
EOF

chmod +x ~/backup-database.sh

echo "✓ Backup script created"

echo -e "\n${YELLOW}Step 5: Creating SSL renewal script...${NC}"

# Create SSL renewal script
cat > ~/renew-ssl.sh << 'EOF'
#!/bin/bash
cd ~/scheduler/app
docker-compose stop nginx
sudo certbot renew
sudo cp -r /etc/letsencrypt/* certbot/conf/
sudo chown -R ubuntu:ubuntu certbot/
docker-compose start nginx
EOF

chmod +x ~/renew-ssl.sh

echo "✓ SSL renewal script created"

echo -e "\n${YELLOW}Step 6: Creating required directories...${NC}"

mkdir -p data media staticfiles backups logs certbot/conf certbot/www

echo "✓ Directories created"

echo -e "\n${GREEN}Setup complete!${NC}"
echo ""
echo -e "${YELLOW}Important Information:${NC}"
echo "===================="
echo ""
echo "Backup API Key: $BACKUP_API_KEY"
echo "Secret Key: $SECRET_KEY"
echo ""
echo -e "${RED}SAVE THESE KEYS SECURELY!${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Update .env file with your GitHub token and repo"
echo "   nano .env"
echo ""
echo "2. Build and start the application:"
echo "   docker-compose build"
echo "   docker-compose up -d"
echo ""
echo "3. Check logs for any errors:"
echo "   docker-compose logs -f"
echo ""
echo "4. After DNS is configured, set up SSL:"
echo "   See ORACLE_CLOUD_MIGRATION.md Part 5.2"
echo ""
echo "5. Set up automated backups:"
echo "   crontab -e"
echo "   Add: 0 2 * * * /home/ubuntu/backup-database.sh >> /home/ubuntu/backup.log 2>&1"
echo "   Add: 0 3 1 * * /home/ubuntu/renew-ssl.sh >> /home/ubuntu/ssl-renew.log 2>&1"
echo ""
echo "For detailed instructions, see: ORACLE_CLOUD_MIGRATION.md"
