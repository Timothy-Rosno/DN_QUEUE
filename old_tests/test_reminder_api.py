"""
Test the reminder check API endpoint.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from django.test import RequestFactory
from calendarEditor.views import api_check_reminders
import json

print("=" * 60)
print("TESTING REMINDER CHECK API")
print("=" * 60)

# Create a fake request
factory = RequestFactory()
request = factory.get('/api/check-reminders/')

# Call the view
response = api_check_reminders(request)

# Parse response
data = json.loads(response.content)

print(f"\nResponse Status: {response.status_code}")
print(f"Response Data:")
print(json.dumps(data, indent=2))

if response.status_code == 200 and data.get('success'):
    print("\n✅ API endpoint is working!")
    print(f"   Checked: {data.get('checked')} pending reminders")
    print(f"   Sent: {data.get('sent')} reminders")
else:
    print("\n❌ API endpoint failed!")
    if 'error' in data:
        print(f"   Error: {data['error']}")

print("\n" + "=" * 60)
print("GitHub Actions will call this endpoint every 5 minutes")
print("URL: https://yourapp.onrender.com/api/check-reminders/")
print("=" * 60 + "\n")
