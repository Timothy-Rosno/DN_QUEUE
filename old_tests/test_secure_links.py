#!/usr/bin/env python
"""
Test secure one-time login links in Slack notifications.
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from django.contrib.auth.models import User
from calendarEditor.notifications import create_notification
from django.conf import settings

print("=" * 70)
print("SECURE LINK TEST")
print("=" * 70)

# Get test user
user = User.objects.get(username='TimmyRosno')

print(f"\nSending test notification to: {user.username}")
print(f"Slack Member ID: {user.profile.slack_member_id}")
print(f"Base URL: {settings.BASE_URL}")
print()

# Create a test notification (this will automatically send to Slack with secure link)
notification = create_notification(
    recipient=user,
    notification_type='queue_moved',
    title='Secure Link Test',
    message='This notification includes a secure one-time login link. Click "View Details" to test it!'
)

print(f"Notification created (ID: {notification.id})")
print(f"Action URL: {notification.get_notification_url()}")
print()
print("Check your Slack DM for:")
print("  1. The notification message")
print("  2. A 'View Details' link at the bottom")
print()
print("How the link works:")
print("  ✓ NOT an authentication bypass (requires password if not logged in)")
print("  ✓ REUSABLE - Can click multiple times (like a bookmark)")
print("  ✓ Expires in 24 hours for security")
print("  ✓ User-specific (checks you're logged in as correct user)")
print("  ✓ Cannot be shared (attacker needs your password)")
print()
print("Try these scenarios:")
print()
print("  Scenario 1: Already logged in as TimmyRosno")
print("    1. Click the link → Immediately redirected to page ✅")
print("    2. Click again → Works again! ✅")
print()
print("  Scenario 2: Not logged in")
print("    1. Click the link → Taken to login page")
print("    2. Enter TimmyRosno credentials")
print("    3. After login → Redirected to page ✅")
print()
print("  Scenario 3: Share link with someone")
print("    1. They click the link → Taken to login page")
print("    2. They need YOUR password to proceed")
print("    3. Without password, link is useless ✅")
print()
print("  Scenario 4: Normal login (not from link)")
print("    1. Go to login page directly")
print("    2. Login normally → Goes to default page ✅")
print()
print("=" * 70)
