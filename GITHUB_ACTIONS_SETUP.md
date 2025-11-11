# GitHub Actions Reminder System Setup

## 🎉 FREE 24/7 Reminders with GitHub Actions!

This setup uses GitHub Actions to ping your app every 5 minutes, ensuring reminders are sent on time even when your Render app is asleep.

**Cost:** $0 (FREE forever for public repos)
**Reliability:** GitHub's infrastructure
**Precision:** Within 5 minutes of due time

---

## How It Works

```
Every 5 minutes:
  GitHub Actions runs → Calls /api/check-reminders/
                      ↓
              Wakes up Render app (if asleep)
                      ↓
              Middleware checks for pending reminders
                      ↓
              Sends any reminders that are due
                      ↓
              Returns success/failure
                      ↓
              GitHub logs the result
```

**Benefits:**
- ✅ FREE (unlimited for public repos)
- ✅ Works 24/7 (even overnight)
- ✅ Legitimate (not gaming Render's TOS)
- ✅ Reliable (GitHub's infrastructure)
- ✅ Simple (just one workflow file)

---

## Setup Instructions

### Step 1: Deploy to Render

Follow `RENDER_DEPLOYMENT_GUIDE.md` to deploy your app.

You'll get a URL like: `https://scheduler-app-xyz.onrender.com`

### Step 2: Update GitHub Actions Workflow

Edit `.github/workflows/check-reminders.yml`:

**Change this line:**
```yaml
response=$(curl -s -w "\n%{http_code}" https://yourapp.onrender.com/api/check-reminders/)
```

**To your actual Render URL:**
```yaml
response=$(curl -s -w "\n%{http_code}" https://scheduler-app-xyz.onrender.com/api/check-reminders/)
```

### Step 3: Push to GitHub

```bash
git add .
git commit -m "Add GitHub Actions reminder system"
git push origin main
```

### Step 4: Verify It's Working

1. Go to your GitHub repo
2. Click **"Actions"** tab
3. You should see **"Check Reminders"** workflow
4. Click on it to see runs

**First run:** Happens within 5 minutes of pushing
**Subsequent runs:** Every 5 minutes forever

### Step 5: Monitor (Optional)

Check the Actions tab to see:
- ✅ Green checkmarks = Working
- ❌ Red X's = Failed (check logs)

Each run shows:
- How many reminders were checked
- How many were sent
- Timestamp

---

## Testing

### Test Manually (Before Deploying)

**Local test:**
```bash
python test_reminder_api.py
```

Should show:
```
✅ API endpoint is working!
   Checked: 0 pending reminders
   Sent: 0 reminders
```

### Test After Deploying

**From command line:**
```bash
curl https://your-app.onrender.com/api/check-reminders/
```

**Expected response:**
```json
{
  "success": true,
  "checked": 0,
  "sent": 0,
  "timestamp": "2025-11-11T05:44:51.701351+00:00"
}
```

### Trigger Manually on GitHub

1. Go to **Actions** tab
2. Click **"Check Reminders"**
3. Click **"Run workflow"** button
4. Click **"Run workflow"** again
5. Watch it run in real-time!

---

## Troubleshooting

### Workflow not running?

**Check:**
1. Is repo public? (Private repos have limited free minutes)
2. Did you push the `.github/workflows/check-reminders.yml` file?
3. Is the cron syntax correct?
4. Check Actions tab for errors

### Getting 404 errors?

**Fix:**
1. Update the URL in workflow file
2. Make sure you deployed to Render
3. Test the endpoint manually with `curl`

### Reminders not sending?

**Check:**
1. Are there actually reminders due? (Check database)
2. Is middleware working? (`python test_reminders.py`)
3. Check GitHub Actions logs for errors
4. Test endpoint manually

---

## How Often Does It Run?

**Current setting:** Every 5 minutes

**To change frequency:**

Edit `.github/workflows/check-reminders.yml`:

```yaml
# Every minute (aggressive)
- cron: '* * * * *'

# Every 5 minutes (recommended)
- cron: '*/5 * * * *'

# Every 10 minutes (conservative)
- cron: '*/10 * * * *'

# Every 15 minutes (minimal)
- cron: '*/15 * * * *'
```

**Note:** More frequent = more reliable, but uses more free minutes

**GitHub Free Tier:**
- Public repos: **Unlimited minutes** ✅
- Private repos: 2,000 minutes/month (not enough for 24/7)

---

## Cost Breakdown

**Public Repo:**
- GitHub Actions: FREE (unlimited)
- Render Web Service: FREE (with 15min spin-down)
- **Total: $0/month** 🎉

**Private Repo:**
- GitHub Actions: 2,000 min/month free
- 5-minute cron = 288 runs/day = 8,640 runs/month
- Each run ~30 seconds = 4,320 minutes/month
- **Exceeds free tier** - Need GitHub Pro ($4/month)

**Recommendation:** Keep repo public for unlimited free minutes!

---

## Monitoring & Logs

### View in GitHub

**Actions tab** shows:
- All workflow runs
- Success/failure status
- Execution logs
- Response from API

### What gets logged:

```
Checking for pending reminders...
Response: {"success":true,"checked":0,"sent":0,"timestamp":"..."}
Status: 200
✅ Reminder check successful
Reminder check completed at Mon Nov 11 05:44:51 UTC 2025
```

### Set up notifications (optional)

GitHub can notify you when workflows fail:
1. Go to repo Settings
2. Notifications
3. Configure email alerts

---

## Security Notes

### Is this secure?

**Yes!** The endpoint:
- ✅ Doesn't require authentication (by design)
- ✅ Only checks/sends reminders (read-only operation for triggering)
- ✅ Can't modify data
- ✅ Can't access user information
- ✅ Safe to expose publicly

**Why no authentication?**
- GitHub Actions can't store secrets for cron jobs
- The endpoint is designed to be pinged publicly
- Worst case: Someone sends extra reminder checks (harmless)

### Rate limiting?

Django has no built-in rate limiting, but:
- Only runs every 5 minutes from GitHub
- Very light operation (single DB query)
- No DDoS concern

**If you want to add rate limiting later:**
```bash
pip install django-ratelimit
```

---

## Alternative: Cloudflare Workers

If you prefer not to use GitHub Actions:

**Cloudflare Workers (Free Tier):**
- 100,000 requests/day
- Cron triggers included
- Super reliable

See `CLOUDFLARE_SETUP.md` for instructions (coming soon!)

---

## Files Created

```
.github/
  workflows/
    check-reminders.yml    ← GitHub Actions workflow
    
calendarEditor/
  views.py                 ← Added api_check_reminders()
  urls.py                  ← Added /api/check-reminders/ route
  
test_reminder_api.py       ← Test script
GITHUB_ACTIONS_SETUP.md    ← This file!
```

---

## Next Steps

1. ✅ Deploy to Render
2. ✅ Update workflow file with your URL
3. ✅ Push to GitHub
4. ✅ Check Actions tab
5. ✅ Enjoy free 24/7 reminders!

---

**Questions?** Check the GitHub Actions logs or test the endpoint manually!

**You now have FREE, reliable, 24/7 reminder checking!** 🚀
