#!/usr/bin/env python
"""
Diagnostic script to check Slack integration setup.
"""

import os
import sys
import django
import requests

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from django.conf import settings
from django.contrib.auth.models import User

print("=" * 70)
print("SLACK INTEGRATION DIAGNOSTICS")
print("=" * 70)

# Check 1: Token in environment
print("\n1. Environment Variable Check:")
env_token = os.environ.get('SLACK_BOT_TOKEN', '')
if env_token:
    print(f"   ✓ SLACK_BOT_TOKEN is set in environment")
    print(f"   Token preview: {env_token[:15]}...")
else:
    print("   ❌ SLACK_BOT_TOKEN NOT set in environment")
    print("   Run: export SLACK_BOT_TOKEN='xoxb-your-token-here'")

# Check 2: Django settings
print("\n2. Django Settings Check:")
if settings.SLACK_BOT_TOKEN:
    print(f"   ✓ Django sees token: {settings.SLACK_BOT_TOKEN[:15]}...")
    print(f"   ✓ SLACK_ENABLED: {settings.SLACK_ENABLED}")
else:
    print("   ❌ Django settings.SLACK_BOT_TOKEN is empty")
    print("   Make sure to set the environment variable BEFORE starting Django")

# Check 3: Test Slack API
print("\n3. Slack API Test:")
if settings.SLACK_BOT_TOKEN:
    try:
        response = requests.get(
            'https://slack.com/api/auth.test',
            headers={'Authorization': f'Bearer {settings.SLACK_BOT_TOKEN}'},
            timeout=10
        )
        result = response.json()

        if result.get('ok'):
            print(f"   ✓ API connection successful!")
            print(f"   Bot user: {result.get('user')}")
            print(f"   Team: {result.get('team')}")
        else:
            print(f"   ❌ API error: {result.get('error')}")
            if result.get('error') == 'invalid_auth':
                print("   → Token is invalid or expired")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
else:
    print("   ⊘ Skipped (no token)")

# Check 4: User with Slack ID
print("\n4. Users with Slack Member IDs:")
users_with_slack = User.objects.filter(
    profile__slack_member_id__isnull=False
).exclude(profile__slack_member_id='')

if users_with_slack.exists():
    for user in users_with_slack[:5]:
        print(f"   • {user.username}: {user.profile.slack_member_id}")
else:
    print("   ⚠ No users have Slack Member IDs set")

# Check 5: Test sending a message
print("\n5. Message Send Test:")
if settings.SLACK_BOT_TOKEN and users_with_slack.exists():
    test_user = users_with_slack.first()
    print(f"   Testing with user: {test_user.username}")
    print(f"   Slack ID: {test_user.profile.slack_member_id}")

    send_test = input("\n   Send test message to this user? (y/n): ").strip().lower()

    if send_test == 'y':
        try:
            response = requests.post(
                'https://slack.com/api/chat.postMessage',
                headers={
                    'Authorization': f'Bearer {settings.SLACK_BOT_TOKEN}',
                    'Content-Type': 'application/json'
                },
                json={
                    'channel': test_user.profile.slack_member_id,
                    'text': '*🔧 Diagnostic Test*\nThis is a test message from diagnose_slack.py',
                    'unfurl_links': False,
                    'unfurl_media': False
                },
                timeout=10
            )

            result = response.json()

            if result.get('ok'):
                print(f"   ✓ MESSAGE SENT!")
                print(f"   Check Slack for the message")
            else:
                print(f"   ❌ Send failed: {result.get('error')}")

                if result.get('error') == 'channel_not_found':
                    print("   → Slack Member ID is incorrect or user left workspace")
                elif result.get('error') == 'not_in_channel':
                    print("   → Bot needs to be added to channel/user DM")
                elif result.get('error') == 'invalid_auth':
                    print("   → Token is invalid")

        except Exception as e:
            print(f"   ❌ Error: {e}")
else:
    print("   ⊘ Skipped (no token or no users with Slack IDs)")

print("\n" + "=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)

if not settings.SLACK_BOT_TOKEN:
    print("\n⚠️  ACTION REQUIRED:")
    print("   1. Get your token from: https://api.slack.com/apps")
    print("   2. export SLACK_BOT_TOKEN='xoxb-your-token-here'")
    print("   3. Restart Django server")
    print("   4. Run this script again")
