# Slack Integration Setup Guide

This guide will help you set up Slack notifications for your Django app.

## Step 1: Create a Slack Bot

1. Go to https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. Give it a name (e.g., "Lab Scheduler Bot") and select your workspace
4. Click **"Create App"**

## Step 2: Configure Bot Permissions

1. In the left sidebar, click **"OAuth & Permissions"**
2. Scroll down to **"Scopes"** → **"Bot Token Scopes"**
3. Add these scopes:
   - `chat:write` - Send messages as the bot
   - `users:read` - Look up users by Member ID
   - `users:read.email` - **REQUIRED** for automatic user lookup by email

## Step 3: Install Bot to Workspace

1. Scroll up to **"OAuth Tokens for Your Workspace"**
2. Click **"Install to Workspace"** (or **"Reinstall to Workspace"** if you already created the bot)
3. Review permissions and click **"Allow"**
4. Copy the **"Bot User OAuth Token"** (starts with `xoxb-`)

**IMPORTANT**: If you already created the bot but didn't add `users:read.email` scope:
- Add the scope in Step 2
- You MUST click **"Reinstall to Workspace"** for the new scope to take effect
- Copy the new token (the old one won't have email access)

## Step 4: Set Environment Variable

### Option A: Environment Variable (Recommended for production)
```bash
export SLACK_BOT_TOKEN='xoxb-your-token-here'
```

### Option B: Add to settings.py (Quick testing only)
In `mysite/settings.py`, replace:
```python
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN', '')
```
with:
```python
SLACK_BOT_TOKEN = 'xoxb-your-token-here'  # NEVER commit this to git!
```

## Step 5: Run Database Migration

```bash
python manage.py migrate
```

## Step 6: How Slack Member ID Works

### Automatic Lookup (Recommended)
**You don't need to do anything!** The system automatically finds and caches Slack Member IDs on the first notification.

The system tries to match users in this order:
1. **Email** - Matches Django user email with Slack email (most reliable)
2. **Full Name** - Matches first name + last name with Slack display name or real name
3. **Username** - Matches Django username with Slack username or display name

Once found, the Member ID is cached in the user's profile for future notifications.

### Manual Entry (Optional)
Users can manually enter their Slack Member ID in their profile if automatic lookup fails:

#### How to Find Your Slack Member ID:

**Method 1: From Slack Desktop/Web**
1. Click on your profile picture in Slack
2. Click **"Profile"**
3. Click the **⋯ (More)** button
4. Click **"Copy member ID"**
5. Member ID looks like: `U01234ABCD`

**Method 2: From a Message**
1. Right-click on any of your messages
2. Select **"Copy link"**
3. The Member ID is in the URL after `/team/`:
   - Example URL: `https://yourworkspace.slack.com/team/U01234ABCD`
   - Member ID: `U01234ABCD`

**Method 3: Check Your Profile Page**
1. Log into the Django app
2. Go to your profile page
3. Check if the "Slack Member ID" field is already filled (from auto-lookup)
4. If not, enter it manually using Method 1 or 2 above

## Step 7: Test Notifications

Once set up:
- Any in-app notification will **automatically** be sent to Slack
- Users will receive DMs from your bot
- On first notification, the system automatically looks up and caches the Slack Member ID
- Check Django logs to see if Member IDs are being found successfully

## Troubleshooting

### "channel_not_found" error
- The Slack Member ID is incorrect
- User needs to find and re-enter their correct Member ID

### "not_authed" error
- SLACK_BOT_TOKEN is not set or invalid
- Check that the token starts with `xoxb-`

### No messages received
- Check that the bot is installed in the workspace
- Verify the user's Slack Member ID is correct
- Check Django logs for error messages

## Security Note

**NEVER commit your SLACK_BOT_TOKEN to version control!**
- Add it to `.gitignore` if you put it in a config file
- Use environment variables in production
- Consider using Django's secrets management or AWS Secrets Manager
