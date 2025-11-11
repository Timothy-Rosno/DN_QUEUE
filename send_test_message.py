#!/usr/bin/env python
"""
Send a test Slack message to verify integration works.
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from django.contrib.auth.models import User
from calendarEditor.notifications import send_slack_dm

# Get user with Slack ID
user = User.objects.get(username='TimmyRosno')

print(f"Sending test message to: {user.username}")
print(f"Slack Member ID: {user.profile.slack_member_id}")

success = send_slack_dm(
    user=user,
    title="Slack Integration Test",
    message="Success! Your Django app can now send Slack notifications.\n\nThis is a test message from send_test_message.py  \n\n-Timmy"
)

if success:
    print("\n✅ MESSAGE SENT SUCCESSFULLY!")
    print("Check your Slack DMs from 'dn_notifications_test' bot")
else:
    print("\n❌ Failed to send message")
    print("Check the output above for error details")
