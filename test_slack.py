"""
Test script to verify Slack integration is working.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from django.conf import settings

print("=" * 60)
print("SLACK INTEGRATION TEST")
print("=" * 60)

print(f"\nSLACK_BOT_TOKEN: {settings.SLACK_BOT_TOKEN[:20]}..." if settings.SLACK_BOT_TOKEN else "SLACK_BOT_TOKEN: (empty)")
print(f"SLACK_ENABLED: {settings.SLACK_ENABLED}")

if settings.SLACK_ENABLED:
    print("\n✅ Slack integration is ENABLED")
    
    # Test Slack API connection
    print("\nTesting Slack API connection...")
    try:
        import requests
        response = requests.get(
            'https://slack.com/api/auth.test',
            headers={'Authorization': f'Bearer {settings.SLACK_BOT_TOKEN}'},
            timeout=10
        )
        result = response.json()
        
        if result.get('ok'):
            print(f"✅ Connected to Slack workspace: {result.get('team')}")
            print(f"   Bot user: {result.get('user')}")
        else:
            print(f"❌ Slack API error: {result.get('error')}")
    
    except Exception as e:
        print(f"❌ Failed to connect to Slack: {e}")
else:
    print("\n❌ Slack integration is DISABLED")
    print("   Token is empty or not set!")

print("\n" + "=" * 60 + "\n")
