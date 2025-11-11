# Secure Notification Links - Implementation Summary

## What Was Implemented

Every Slack notification now includes a secure "View Details" link that:
- **Smart redirect** - Takes you to the right page if already logged in
- **NOT an authentication bypass** - Requires normal login if not logged in
- **Reusable** - Works like a bookmark, can click multiple times
- **Expires in 24 hours** - Time-limited for security
- **User-specific** - Checks you're logged in as the correct user
- **Cannot be shared** - Attacker needs victim's password to use it

## Security Model

**IMPORTANT:** The link is NOT a magic auto-login. It's a secure bookmark that:
1. If you're already logged in (as the correct user) → Takes you to the page
2. If you're not logged in → Takes you to login page, then redirects after login
3. If wrong user is logged in → Shows error

**This means shared/intercepted links are useless without the user's password.**

The link is **reusable** (not one-time use) - you can click it multiple times within 24 hours.

## How It Works

### For Users:

**Scenario 1: Already Logged In (as correct user)**
1. User receives Slack notification
2. Clicks "View Details" link
3. ✅ Immediately redirected to relevant page
4. Can click the link again anytime (reusable)

**Scenario 2: Already Logged In (as WRONG user)**
1. Different user clicks the link
2. ❌ Error message: "This link is for [User], but you are logged in as [OtherUser]"
3. Must log out and try again

**Scenario 3: Not Logged In**
1. User receives Slack notification
2. Clicks "View Details" link
3. 🔐 Taken to login page with hint: "Please log in as [User] to view this notification"
4. User enters username & password (normal login)
5. ✅ After successful login, redirected to relevant page
6. Link remains valid - can use again later

### Security Features:
- ✅ **NOT an authentication bypass** - User must login normally if not already logged in
- ✅ **Cryptographically secure tokens** - Generated with `secrets.token_urlsafe(32)`
- ✅ **Reusable** - Works like a bookmark, can click multiple times
- ✅ **Time-limited** - Expires after 24 hours
- ✅ **User-specific** - Only works if you login as the intended user
- ✅ **Cannot be shared** - Attacker would need the victim's password

## Technical Implementation

### 1. OneTimeLoginToken Model (calendarEditor/models.py:591-651)
```python
class OneTimeLoginToken(models.Model):
    user = models.ForeignKey(User)
    token = models.CharField(max_length=64, unique=True)
    notification = models.ForeignKey('Notification')
    redirect_url = models.CharField(max_length=500)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
```

### 2. Token Login View (calendarEditor/views.py:1997-2050)
- Validates token (not expired)
- Checks if user is already logged in as correct user
- If not logged in, routes through login page
- Redirects to notification's action URL after login

### 3. URL Pattern (calendarEditor/urls.py:87)
```python
path('token-login/<str:token>/', views.token_login, name='token_login')
```

### 4. Enhanced Slack Notification (calendarEditor/notifications.py:128-148)
- Generates secure token for each notification
- Builds full URL: `http://127.0.0.1:8000/schedule/token-login/<token>/`
- Appends link to Slack message

### 5. Base URL Configuration (mysite/settings.py:213-216)
```python
BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:8000')
```

## Link Format

**Example Slack message:**
```
*🎯 ON DECK - You're Next!*
Your request "Sample Measurement" is now #1 in line for Hidalgo. Get ready!

<http://127.0.0.1:8000/schedule/token-login/abc123...xyz/|View Details>
```

**URL breakdown:**
- `http://127.0.0.1:8000` - Base URL (changes to production domain)
- `/schedule/token-login/` - Token login endpoint
- `abc123...xyz` - Secure 43-character token
- `|View Details` - Slack link text

## Security Considerations

### Why This Is Secure:

1. **Token Entropy**: 32 bytes → 43 characters → 256 bits of randomness
   - Guessing probability: 1 in 2^256 (effectively impossible)

2. **Reusable**: Can click multiple times within expiration window
   - Link acts like a smart bookmark
   - Convenient for users who want to return to the notification

3. **Time-Limited**: 24-hour expiration
   ```python
   expires_at = timezone.now() + timedelta(hours=24)
   ```

4. **User-Specific**: Token tied to specific user
   - Link checks if you're logged in as the correct user
   - Wrong user must log out and login as the intended user

5. **Cannot Be Shared** (requires password):
   - User A clicks link → If logged in, goes to page
   - User A shares link with User B → User B needs User A's password
   - Without password, link is useless

### What Could Go Wrong (And Why It Doesn't):

**Q: What if someone intercepts the link?**
A: They still need the user's password to login. The link is NOT an authentication bypass - it's just a smart redirect.

**Q: What if user shares the link?**
A: Shared person must login as the original user (needs password). Without the password, link is useless.

**Q: What if attacker clicks the link first?**
A: They're taken to login page asking them to login as the victim. They need the victim's password to proceed.

**Q: What if link expires while user is away?**
A: User sees "expired" message and logs in normally. Notification still visible in app.

**Q: What if attacker gets database access?**
A: Tokens are random strings with no pattern. Can't predict future tokens. Even with a valid token, attacker still needs user's password.

## Production Deployment

### Before Going Live:

1. **Use HTTPS** (required for production):
   ```bash
   export BASE_URL='https://your-domain.com'
   ```

2. **Consider shorter expiration** (optional):
   ```python
   # In OneTimeLoginToken.create_for_notification()
   expires_at = timezone.now() + timedelta(hours=1)  # 1 hour instead of 24
   ```

3. **Add token cleanup** (recommended):
   ```python
   # management/commands/cleanup_tokens.py
   # Delete expired and used tokens older than 7 days
   # Run daily via cron
   ```

4. **Monitor token usage** (optional):
   - Track how many tokens are used vs expired
   - Alert if unusual patterns (could indicate attack)

## Testing

### Manual Test:
```bash
python test_secure_links.py
```

This will:
1. Send a test notification to TimmyRosno
2. Include a secure link in Slack
3. Instructions for testing one-time use

### Test Cases:
- ✅ Valid token → Auto-login + redirect
- ✅ Used token → Error message
- ✅ Expired token → Error message
- ✅ Invalid token → Error message
- ✅ Link works from different devices (as long as not used)

## Files Modified

### New Files:
1. `calendarEditor/models.py` - Added OneTimeLoginToken model (lines 591-651)
2. `calendarEditor/migrations/0024_onetimelogintoken.py` - Database migration
3. `test_secure_links.py` - Testing script
4. `SECURE_LINKS_SUMMARY.md` - This file

### Modified Files:
1. `calendarEditor/views.py` - Added token_login view (lines 1997-2038)
2. `calendarEditor/urls.py` - Added token-login URL pattern (line 87)
3. `calendarEditor/notifications.py` - Enhanced send_slack_dm (lines 128-148)
4. `mysite/settings.py` - Added BASE_URL setting (lines 213-216)

## Future Enhancements

### Optional Improvements:

1. **IP Verification** (paranoid mode):
   - Store user's IP when token is created
   - Verify IP matches when token is used
   - Trade-off: Breaks for users on mobile/changing networks

2. **Device Fingerprinting** (overkill):
   - Store User-Agent when creating token
   - Verify User-Agent matches
   - Trade-off: Complex, breaks across devices

3. **Rate Limiting** (recommended):
   - Limit token creation per user (e.g., max 10 active tokens)
   - Prevent token flooding attacks

4. **Analytics** (nice to have):
   - Track token click-through rates
   - Identify which notification types get most clicks
   - Optimize notification content

## Comparison to Alternatives

### Why not just send regular links?
- ❌ User has to log in manually
- ❌ Breaks user flow
- ❌ Reduces engagement

### Why not use JWT tokens?
- JWT can't be revoked (one-time use requirement)
- Database tokens allow immediate invalidation
- Can track usage analytics

### Why not use Django's password reset tokens?
- Those are for password reset only
- We need custom expiration and one-time use
- Need to tie to notifications

## Summary

The secure link system provides a seamless user experience while maintaining strong security:

- **User Experience**: One click from Slack → Logged in to the right page
- **Security**: One-time use, time-limited, user-specific tokens
- **Scalability**: Database-backed, easy to monitor and manage
- **Flexibility**: Easy to adjust expiration time, add IP checks, etc.

**Current URL Format** (development):
```
http://127.0.0.1:8000/schedule/token-login/<secure-token>/
```

**Production URL Format** (when deployed):
```
https://your-domain.com/schedule/token-login/<secure-token>/
```

Just set `BASE_URL` environment variable and everything updates automatically!
