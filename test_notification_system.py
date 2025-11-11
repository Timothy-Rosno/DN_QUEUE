#!/usr/bin/env python
"""
Test the full notification system (in-app + Slack).
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

# Get user with Slack ID
user = User.objects.get(username='TimmyRosno')

print(f"Creating test notification for: {user.username}")
print(f"This will send to BOTH:")
print(f"  - In-app (WebSocket)")
print(f"  - Slack DM (to {user.profile.slack_member_id})")
print()

# Create a test notification using the real notification system
notification = create_notification(
    recipient=user,
    notification_type='queue_moved',
    title='🧪 Integration Test',
    message='This is a test notification sent through the full notification system. You should receive this in both the web app AND Slack!'
)

print(f"✅ Notification created (ID: {notification.id})")
print(f"✅ Should appear in:")
print(f"   - Web app notifications")
print(f"   - Slack DM from 'dn_notifications_test' bot")
print()
print("Check both places to confirm!")
