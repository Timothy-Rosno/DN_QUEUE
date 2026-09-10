# Slack Integration User Guide

How the Slack DM notification system works in this Django app, and everything you need to replicate it in a new project. No Slack OAuth — uses a single bot token. Users never connect their Slack account; the app finds them automatically by email.

---

## Architecture Overview

- **Bot Token model** — one `xoxb-` token grants the bot permission to read workspace members and send DMs.
- **No OAuth flow** — no client ID, no redirect URI, no user authorization step.
- **Auto-lookup** — the bot calls `users.list` and matches users by email → full name → username. The result is cached in the database so the API is only called once per user.
- **Background threads** — Slack API calls happen in a daemon thread so HTTP responses are never blocked.
- **Secure links** — every Slack DM includes a tokenized URL that handles login automatically before redirecting to the relevant page.
- **Zero Slack SDK** — all API calls are raw HTTP via the `requests` library.

---

## Part 1: Slack App Setup (Do This Once)

### Step 1 — Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and sign in to your Slack workspace.
2. Click **Create New App** → **From scratch**.
3. Give it a name (e.g., "Lab Scheduler Bot") and pick your workspace.
4. Click **Create App**.

### Step 2 — Add Bot Token Scopes

1. In your new app's sidebar, go to **OAuth & Permissions**.
2. Scroll down to **Scopes** → **Bot Token Scopes**.
3. Click **Add an OAuth Scope** and add these two scopes:
   - `users:read` — lets the bot call `users.list` to find members
   - `users:read.email` — lets the bot see email addresses in member profiles (required for email matching)
   - `chat:write` — lets the bot send DMs

### Step 3 — Install the App to Your Workspace

1. Still on the **OAuth & Permissions** page, scroll up to **OAuth Tokens for Your Workspace**.
2. Click **Install to Workspace**.
3. Review the permissions and click **Allow**.
4. Copy the **Bot User OAuth Token** — it starts with `xoxb-`. This is your `SLACK_BOT_TOKEN`.

That's it. You do not need to set up any event subscriptions, webhooks, or redirect URLs.

---

## Part 2: Environment Variables

Add these to your `.env` file (or your hosting platform's environment variable settings):

```env
# Required — the xoxb- token you copied above
SLACK_BOT_TOKEN=xoxb-your-token-here

# Required — the public base URL of your app, used to build clickable links in DMs
# No trailing slash
BASE_URL=https://your-app.example.com
```

In `settings.py`, read these and derive a boolean flag:

```python
import os

SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN', '')
SLACK_ENABLED = bool(SLACK_BOT_TOKEN)   # True only when a token is set

BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:8000')
```

When `SLACK_BOT_TOKEN` is not set, `SLACK_ENABLED` is `False` and all Slack code is skipped — so the app works fine in local development without any Slack credentials.

---

## Part 3: Database — Turso / libsql Notes

### Field: `slack_member_id` on the user profile model

This stores the cached Slack member ID (e.g., `U01234ABCD`) so the bot doesn't call `users.list` every time.

```python
# In your UserProfile model
slack_member_id = models.CharField(
    max_length=50,
    blank=True,
    help_text="Slack member ID (e.g., U01234ABCD) for DM notifications"
)
```

Run `python manage.py makemigrations` and `python manage.py migrate` to add the column. This is a standard `ALTER TABLE ADD COLUMN` and works fine with Turso.

### Field: `slack_notifications` on the notification preference model

A per-user boolean opt-out flag. Default is `True` (opted in).

```python
# In your NotificationPreference model
slack_notifications = models.BooleanField(
    default=True,
    help_text="Send notifications via Slack direct messages"
)
```

**Turso / libsql warning:** Django's normal migration for adding a `BooleanField` to a table with existing rows will try to recreate the table, which Turso does not support. Use a raw SQL migration instead:

```python
# migrations/XXXX_add_slack_notifications_column.py
from django.db import migrations

def add_columns_if_not_exist(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        try:
            cursor.execute("""
                ALTER TABLE yourapp_notificationpreference
                ADD COLUMN slack_notifications INTEGER DEFAULT 1 NOT NULL
            """)
        except Exception as e:
            # Column already exists — safe to ignore
            print(f"slack_notifications column might already exist: {e}")

class Migration(migrations.Migration):
    dependencies = [
        ("yourapp", "XXXX_previous_migration"),
    ]
    operations = [
        migrations.RunPython(add_columns_if_not_exist, migrations.RunPython.noop),
    ]
```

The pattern is: wrap each `ALTER TABLE ADD COLUMN` in its own `try/except` so that re-running migrations (or deploying to a DB that already has the column) doesn't crash. `INTEGER DEFAULT 1 NOT NULL` maps to Django's `BooleanField(default=True)` in SQLite / libsql.

### Model: `OneTimeLoginToken`

Stores the secure tokens embedded in Slack DMs. Create this model once:

```python
import secrets
from datetime import timedelta
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User

class OneTimeLoginToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_tokens')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    notification = models.ForeignKey(
        'Notification', on_delete=models.CASCADE,
        related_name='login_tokens', null=True, blank=True
    )
    redirect_url = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)

    @classmethod
    def create_for_notification(cls, user, notification, redirect_url):
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=24)
        return cls.objects.create(
            user=user,
            token=token,
            notification=notification,
            redirect_url=redirect_url,
            expires_at=expires_at
        )

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at
```

---

## Part 4: The Notification Code

All of this lives in one file, e.g., `yourapp/notifications.py`. Add `requests` to your requirements if it isn't there already.

### 4a — Auto-Lookup: Find a User's Slack Member ID

Called the first time a notification needs to be sent to a user who has no cached ID. Tries email first (most reliable), then full name, then username.

```python
import requests
from django.conf import settings

def lookup_slack_member_id(user):
    if not settings.SLACK_ENABLED:
        return None

    try:
        response = requests.get(
            'https://slack.com/api/users.list',
            headers={'Authorization': f'Bearer {settings.SLACK_BOT_TOKEN}'},
            timeout=10
        )
        result = response.json()
        if not result.get('ok'):
            print(f"Slack API error in users.list: {result.get('error')}")
            return None

        slack_users = result.get('members', [])

        # Strategy 1: match by email
        if user.email:
            for su in slack_users:
                if not su.get('deleted') and not su.get('is_bot'):
                    if su.get('profile', {}).get('email', '').lower() == user.email.lower():
                        return su['id']

        # Strategy 2: match by full name
        full_name = f"{user.first_name} {user.last_name}".strip().lower()
        if full_name:
            for su in slack_users:
                if not su.get('deleted') and not su.get('is_bot'):
                    profile = su.get('profile', {})
                    if full_name in (
                        profile.get('real_name', '').lower(),
                        profile.get('display_name', '').lower()
                    ):
                        return su['id']

        # Strategy 3: match by username
        if user.username:
            for su in slack_users:
                if not su.get('deleted') and not su.get('is_bot'):
                    profile = su.get('profile', {})
                    if user.username.lower() in (
                        su.get('name', '').lower(),
                        profile.get('display_name', '').lower()
                    ):
                        return su['id']

        print(f"Could not find Slack member ID for {user.username}")
        return None

    except Exception as e:
        print(f"Error looking up Slack member ID for {user.username}: {e}")
        return None
```

### 4b — Public Entry Point: `send_slack_dm`

Called from your notification-creation code. Launches a background thread immediately and returns — the HTTP request is never blocked.

```python
import threading

def send_slack_dm(user, title, message, notification=None):
    if not settings.SLACK_ENABLED:
        return
    if user.is_superuser:          # superusers never get Slack DMs
        return
    if not hasattr(user, 'profile'):
        return

    thread = threading.Thread(
        target=_send_slack_dm_worker,
        args=(user.id, title, message, notification.id if notification else None),
        daemon=True
    )
    thread.start()
```

### 4c — Background Worker: `_send_slack_dm_worker`

Does the actual work: checks user preferences, looks up/caches the member ID, creates the secure token link, and POSTs to Slack.

```python
def _send_slack_dm_worker(user_id, title, message, notification_id):
    try:
        from django.contrib.auth.models import User
        from .models import Notification, NotificationPreference, OneTimeLoginToken
        from django.urls import reverse

        user = User.objects.get(id=user_id)
        if user.is_superuser:
            return

        notification = Notification.objects.get(id=notification_id) if notification_id else None

        # Respect per-user opt-out
        prefs = NotificationPreference.get_or_create_for_user(user)
        if not prefs.slack_notifications:
            return

        # Fetch or look up member ID
        slack_member_id = user.profile.slack_member_id
        if not slack_member_id:
            slack_member_id = lookup_slack_member_id(user)
            if slack_member_id:
                user.profile.slack_member_id = slack_member_id
                user.profile.save()
            else:
                return   # user not found in Slack workspace

        # Build message text (Slack mrkdwn)
        slack_text = f"*{title}*\n{message}"

        # Append secure "View Details" link if tied to a notification
        if notification:
            action_url = notification.get_notification_url()   # returns a relative URL like /schedule/queue/
            login_token = OneTimeLoginToken.create_for_notification(
                user=user,
                notification=notification,
                redirect_url=action_url
            )
            token_path = reverse('token_login', kwargs={'token': login_token.token})
            full_url = f"{settings.BASE_URL}{token_path}"
            slack_text += f"\n\n<{full_url}|View Details>"

        # Send the DM
        response = requests.post(
            'https://slack.com/api/chat.postMessage',
            headers={
                'Authorization': f'Bearer {settings.SLACK_BOT_TOKEN}',
                'Content-Type': 'application/json'
            },
            json={
                'channel': slack_member_id,   # member ID used as DM channel
                'text': slack_text,
                'unfurl_links': False,
                'unfurl_media': False,
            },
            timeout=5
        )
        result = response.json()
        if not result.get('ok'):
            print(f"Slack API error: {result.get('error')}")

    except Exception as e:
        print(f"Background Slack send failed for user {user_id}: {e}")
```

### 4d — Central Notification Hub

Every notification in the system goes through one function. It saves the notification to the DB, fires a WebSocket push (if you have Django Channels), and calls `send_slack_dm`. This way every event type gets Slack delivery for free.

```python
def create_notification(recipient, notification_type, title, message, **kwargs):
    # Superusers never receive notifications
    if recipient.is_superuser:
        return None

    notification = Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        # pass through any related objects via kwargs
        **{k: v for k, v in kwargs.items() if k in ('related_preset', 'related_queue_entry', 'related_machine', 'triggering_user')}
    )

    # WebSocket push (optional — requires Django Channels + Redis)
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user_{recipient.id}_notifications',
            {'type': 'notification', 'notification_id': notification.id, 'title': title, 'message': message}
        )
    except Exception:
        pass

    # Slack DM
    if settings.SLACK_ENABLED:
        send_slack_dm(recipient, title, message, notification)

    return notification
```

---

## Part 5: URL Route for Token Login

Add this route to your `urls.py`. It intercepts clicks from Slack DMs and handles authentication before redirecting.

```python
# yourapp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # ...
    path('token-login/<str:token>/', views.token_login, name='token_login'),
]
```

---

## Part 6: The `token_login` View

This view handles three cases when a user clicks a Slack DM link:

```python
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout
from django.utils import timezone

def token_login(request, token):
    from .models import OneTimeLoginToken

    try:
        login_token = OneTimeLoginToken.objects.get(token=token)

        if timezone.now() > login_token.expires_at:
            messages.error(request, 'Expired link — more than 24 hours after send.')
            return redirect('login')

        intended_user = login_token.user
        redirect_url = login_token.redirect_url

        # Case 1: Already logged in as the correct user → go straight there
        if request.user.is_authenticated and request.user.id == intended_user.id:
            return redirect(redirect_url)

        # Case 2: Logged in as a DIFFERENT user → log them out and show warning
        if request.user.is_authenticated and request.user.id != intended_user.id:
            wrong_user = request.user.username
            logout(request)
            request.session['token_auth_hint'] = intended_user.username
            request.session['pending_token'] = token
            messages.warning(
                request,
                f'You were logged in as {wrong_user}. This link is for {intended_user.username}. '
                f'Please log in as {intended_user.username} to continue.'
            )
            return redirect('login')

        # Case 3: Not logged in → store token in session and show login page
        request.session['token_auth_hint'] = intended_user.username
        request.session['pending_token'] = token
        messages.info(request, f'Please log in as {intended_user.username} to view this notification.')
        return redirect('login')

    except OneTimeLoginToken.DoesNotExist:
        messages.error(request, 'Invalid notification link.')
        return redirect('login')
```

---

## Part 7: Post-Login Redirect in `LoginView`

After the user logs in, `get_success_url` checks whether there's a pending Slack token in the session and completes the redirect chain:

```python
# In your LoginView class (extends django.contrib.auth.views.LoginView)
from django.urls import reverse
from django.contrib import messages

def get_success_url(self):
    user = self.request.user
    pending_token = self.request.session.get('pending_token')
    token_auth_hint = self.request.session.get('token_auth_hint')

    if pending_token and token_auth_hint:
        del self.request.session['pending_token']
        self.request.session.pop('token_auth_hint', None)

        if user.username == token_auth_hint:
            # Correct user logged in — hand back to token_login to do the final redirect
            return reverse('token_login', kwargs={'token': pending_token})
        else:
            messages.warning(self.request, 'This notification is not for your account. Returning to home page.')
            return reverse('home')

    # Fall through to your normal post-login redirect logic
    return super().get_success_url()
```

---

## Part 8: User-Facing Controls

### Profile form — let users enter their member ID manually

Auto-lookup works for most users, but let them override it in case the email doesn't match:

```python
# In your profile form
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['slack_member_id', ...]
        widgets = {
            'slack_member_id': forms.TextInput(attrs={
                'placeholder': 'e.g., U01234ABCD (leave blank for auto-lookup)'
            }),
        }
```

To find your Slack member ID: open Slack → click your name → **View profile** → **More** (three-dot menu) → **Copy member ID**.

### Notification preferences form — Slack opt-out

```python
class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = ['slack_notifications', ...]
        labels = {
            'slack_notifications': 'Send notifications via Slack',
        }
```

---

## Part 9: Complete Message Flow (Step by Step)

1. An event occurs in your app (e.g., user reaches position #1 in a queue).
2. Your event code calls `create_notification(recipient, type, title, message, ...)`.
3. `create_notification` skips superusers, saves a `Notification` row to the DB, and pushes via WebSocket.
4. `create_notification` calls `send_slack_dm(user, title, message, notification)`.
5. `send_slack_dm` skips superusers, validates basic state, and starts a **daemon background thread** — returns immediately.
6. In the background thread, `_send_slack_dm_worker`:
   a. Checks `prefs.slack_notifications` — if False, stops.
   b. Reads `user.profile.slack_member_id`. If empty, calls `lookup_slack_member_id` (GET `users.list`), caches the result.
   c. Builds message text: `*Title*\nMessage body`.
   d. Calls `OneTimeLoginToken.create_for_notification(user, notification, redirect_url)` — generates a `secrets.token_urlsafe(32)` token expiring in 24 hours.
   e. Builds: `{BASE_URL}/token-login/{token}/` and appends `<url|View Details>` to the message.
   f. POSTs to `https://slack.com/api/chat.postMessage` with the member ID as `channel`.
7. User receives a Slack DM with a "View Details" link.
8. User clicks link → hits `token_login` view:
   - Already logged in as correct user → direct redirect.
   - Wrong user logged in → logout + warning + redirect to login.
   - Not logged in → store token in session + redirect to login.
9. After login, `get_success_url` sees `pending_token` in session, redirects back through `token_login`, which then does the final redirect to the intended page.

---

## Part 10: Superuser Exclusion (Critical)

Superusers must be excluded at every layer. This is important because:
- Superusers often represent system/admin accounts that don't belong to real humans in the Slack workspace.
- Without this check, the bot will call `users.list` repeatedly trying to find an email that doesn't exist there.

Add these guards everywhere:

| Location | Guard |
|---|---|
| `create_notification()` | `if recipient.is_superuser: return None` — before any DB write |
| `send_slack_dm()` | `if user.is_superuser: return` — before launching thread |
| `_send_slack_dm_worker()` | `if user.is_superuser: return` — defensive check at top of worker |
| `NotificationPreference.save()` | Force all notification fields to `False` for superusers |

---

## Required Python Packages

```
requests        # for Slack API calls (raw HTTP, no Slack SDK needed)
django          # framework
```

Optional (for WebSocket push alongside Slack):
```
channels        # Django Channels
channels-redis  # Redis backend for Channels
```

---

## Checklist for a New Project

- [ ] Create Slack app at api.slack.com/apps
- [ ] Add bot scopes: `users:read`, `users:read.email`, `chat:write`
- [ ] Install app to workspace, copy `xoxb-` Bot Token
- [ ] Set `SLACK_BOT_TOKEN` and `BASE_URL` environment variables
- [ ] Add `SLACK_BOT_TOKEN`, `SLACK_ENABLED`, `BASE_URL` to `settings.py`
- [ ] Add `slack_member_id` field to your user profile model (migration: standard `ADD COLUMN`)
- [ ] Add `slack_notifications` field to notification preferences model (migration: raw SQL for Turso)
- [ ] Create `OneTimeLoginToken` model and migrate
- [ ] Add `lookup_slack_member_id`, `send_slack_dm`, `_send_slack_dm_worker`, `create_notification` to `notifications.py`
- [ ] Add `token-login/<str:token>/` URL route named `token_login`
- [ ] Add `token_login` view
- [ ] Add `pending_token`/`token_auth_hint` handling to `LoginView.get_success_url`
- [ ] Add `slack_member_id` field to user profile form with helpful placeholder
- [ ] Add `slack_notifications` boolean to notification preferences form
- [ ] Add superuser exclusion guards at all four layers
