# Oracle Cloud Migration Checklist

Quick reference checklist for migrating to Oracle Cloud + SQLite.

**Full guide:** See `ORACLE_CLOUD_MIGRATION.md` for detailed instructions.

---

## Pre-Migration (Do First)

- [ ] Read complete migration guide
- [ ] Export current database backup from Render
- [ ] Test SQLite migration locally (Part 3.3)
- [ ] Verify backup restores successfully with SQLite
- [ ] Have domain name ready
- [ ] Have GitHub repository access

---

## Part 1: Oracle Cloud Setup (~45 min)

- [ ] Create Oracle Cloud account
- [ ] Verify email and activate account
- [ ] Create compute instance (VM.Standard.A1.Flex, 2 OCPU, 12GB RAM)
- [ ] Download SSH keys (scheduler-key.pem)
- [ ] Note public IP address: `_________________`
- [ ] Configure cloud firewall (HTTP/HTTPS/SSH ingress rules)
- [ ] Connect to VM via SSH successfully

---

## Part 2: VM Configuration (~30 min)

- [ ] Update system packages (`apt update && apt upgrade`)
- [ ] Install essential tools (curl, git, wget, nano, ufw)
- [ ] Configure UFW firewall (ports 22, 80, 443)
- [ ] Install Docker
- [ ] Install Docker Compose
- [ ] Log out and back in (for Docker group permissions)
- [ ] Verify: `docker --version` and `docker-compose --version` work
- [ ] Create application directories (~/scheduler/app, data, media, etc.)

---

## Part 3: Database Migration (~20 min)

- [ ] Test SQLite migration locally first
- [ ] Verify local SQLite restore works
- [ ] Test local app with SQLite (`python manage.py runserver`)
- [ ] Confirm all features work (login, queue, machines, etc.)
- [ ] Push code to GitHub

---

## Part 4: Deploy to Oracle Cloud (~45 min)

- [ ] Clone repository to VM
- [ ] Create Dockerfile
- [ ] Create docker-compose.yml
- [ ] Create nginx.conf (update YOUR_DOMAIN.com)
- [ ] Create .env file with all secrets
  - [ ] Generate new SECRET_KEY
  - [ ] Generate BACKUP_API_KEY
  - [ ] Add domain name to ALLOWED_HOSTS
  - [ ] Add Slack token (if using)
  - [ ] Add GitHub token and repo
- [ ] Build Docker images (`docker-compose build`)
- [ ] Start services (`docker-compose up -d`)
- [ ] Check logs for errors (`docker-compose logs -f`)
- [ ] Restore database via admin or command line
- [ ] Test: Visit `http://PUBLIC_IP/schedule/`
- [ ] Verify: Can log in and see data

---

## Part 5: DNS and SSL Setup (~30 min)

- [ ] Update DNS A records:
  - [ ] @ → YOUR_PUBLIC_IP
  - [ ] www → YOUR_PUBLIC_IP
- [ ] Wait for DNS propagation (5-10 min)
- [ ] Verify: `nslookup YOUR_DOMAIN.com` returns correct IP
- [ ] Stop nginx temporarily
- [ ] Install certbot (`apt install certbot`)
- [ ] Generate SSL certificate (certbot certonly --standalone)
- [ ] Copy certificates to certbot/conf directory
- [ ] Update nginx.conf to enable HTTPS
- [ ] Restart nginx
- [ ] Test: Visit `https://YOUR_DOMAIN.com/schedule/`
- [ ] Verify: SSL certificate is valid (no warnings)
- [ ] Create SSL renewal script
- [ ] Add renewal to crontab (monthly)

---

## Part 6: Automated Backups (~15 min)

- [ ] Create backup script (~/backup-database.sh)
- [ ] Update script with correct API key and URL
- [ ] Test manual backup (`./backup-database.sh`)
- [ ] Verify backup file exists and is valid JSON
- [ ] Add nightly backup to crontab (2 AM daily)
- [ ] Optional: Configure GitHub push for backups

---

## Part 7: Update GitHub Actions (~5 min)

- [ ] Update backup workflow URL to Oracle Cloud domain
- [ ] Update BACKUP_API_KEY secret in GitHub
- [ ] Test workflow manually
- [ ] Verify backup appears in database-backups branch

---

## Part 8: Testing (~30 min)

### Application

- [ ] Home page loads
- [ ] Can log in
- [ ] Can log out
- [ ] Sessions persist
- [ ] No SSL warnings

### Core Features

- [ ] View machines list
- [ ] Create new queue entry
- [ ] Edit queue entry
- [ ] Delete queue entry
- [ ] Archive measurement
- [ ] View archived measurements
- [ ] View notifications
- [ ] Mark notifications as read

### Real-Time (WebSockets)

- [ ] Queue updates show instantly in another browser
- [ ] Notifications appear without refresh
- [ ] Temperature updates work (if using gateway)

### Admin

- [ ] Admin dashboard loads
- [ ] Database management page works
- [ ] Can export database backup
- [ ] Can import database backup
- [ ] Storage stats display correctly
- [ ] Render usage tracking works

### Performance

- [ ] Pages load in <2 seconds
- [ ] Can create 20+ queue entries rapidly (no rate limits)
- [ ] Can run admin actions repeatedly (no CU limits)
- [ ] Test with 5+ friends accessing simultaneously

### Backups

- [ ] Manual backup via admin downloads valid JSON
- [ ] Backup script runs successfully
- [ ] Can restore from backup without errors
- [ ] Restored data is correct and complete

---

## Part 9: Decommission Render (~10 min)

- [ ] Verify DNS is pointing to Oracle Cloud
- [ ] Monitor traffic (should all be on Oracle Cloud)
- [ ] Wait 24-48 hours to ensure stability
- [ ] Download final backup from Render
- [ ] Delete Render web service
- [ ] Delete Neon/Supabase database (if using)
- [ ] Remove DATABASE_URL from old .env files
- [ ] Update documentation with new URLs

---

## Post-Migration Monitoring (First Week)

### Daily Checks

- [ ] Day 1: Application is up and accessible
- [ ] Day 2: Nightly backup ran successfully
- [ ] Day 3: No errors in logs (`docker-compose logs`)
- [ ] Day 4: SSL certificate is valid
- [ ] Day 5: Disk usage is reasonable (`df -h`)
- [ ] Day 6: All features working normally
- [ ] Day 7: Users report no issues

### Weekly Checks

- [ ] Week 1: Verify automatic backups are running
- [ ] Week 1: Check disk space usage
- [ ] Week 1: Review application logs for errors
- [ ] Week 1: Test backup restore process

---

## Emergency Rollback (If Needed)

If something goes catastrophically wrong:

1. [ ] Keep Render service running until Oracle Cloud is stable
2. [ ] Update DNS back to Render IP temporarily
3. [ ] Debug Oracle Cloud issue without time pressure
4. [ ] Once fixed, switch DNS back to Oracle Cloud

**Don't delete Render until Oracle Cloud is proven stable for 48+ hours!**

---

## Key Information to Keep

**Oracle Cloud:**
- Public IP: `_________________`
- SSH key location: `~/.ssh/scheduler-key.pem`
- VM name: `django-scheduler`
- Region: `_________________`

**Application:**
- Domain: `_________________`
- Admin URL: `https://YOUR_DOMAIN.com/schedule/admin/`
- Backup API endpoint: `https://YOUR_DOMAIN.com/schedule/api/backup/database/`

**Secrets (Store Securely!):**
- SECRET_KEY: `_________________`
- BACKUP_API_KEY: `_________________`
- GITHUB_TOKEN: `_________________`

**SSH Connection:**
```bash
ssh -i ~/.ssh/scheduler-key.pem ubuntu@YOUR_PUBLIC_IP
```

**Common Commands:**
```bash
# View logs
docker-compose logs -f

# Restart services
docker-compose restart

# Update code
cd ~/scheduler/app && git pull && docker-compose restart

# Manual backup
~/backup-database.sh

# Check disk space
df -h
```

---

## Success Criteria

✅ **Migration is complete when:**

1. Application is accessible at https://YOUR_DOMAIN.com
2. SSL certificate is valid with no warnings
3. All data restored correctly
4. All features work (queue, notifications, admin)
5. Real-time updates work (WebSockets)
6. Nightly backups run automatically
7. No rate limits or query restrictions
8. Application responds in <2 seconds
9. Can handle 10+ concurrent users
10. No errors in logs for 24 hours

---

## Timeline

**Minimum:** 3 hours if everything goes smoothly
**Realistic:** 4-5 hours with debugging
**With breaks:** Spread over 1-2 days

**Recommended approach:**
- Day 1 (2-3 hours): Parts 1-4 (Setup + Deploy)
- Day 2 (1-2 hours): Parts 5-8 (DNS + SSL + Testing)
- Day 3: Monitor and decommission Render

---

## Support

**Issues?** Check `ORACLE_CLOUD_MIGRATION.md` Troubleshooting section.

**Common problems:**
- SSH connection fails → Check firewall rules
- Docker build fails → Check disk space
- Database restore errors → Verify backup file format
- SSL fails → Check DNS propagation
- Application won't start → Check .env file and logs

**Still stuck?** Document the error message and check:
1. Docker logs: `docker-compose logs`
2. System logs: `sudo journalctl -u docker`
3. Nginx logs: `docker-compose logs nginx`
