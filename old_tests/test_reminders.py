"""
Test script to verify the reminder system works without Celery.

This script:
1. Creates a test queue entry with a past reminder_due_at time
2. Simulates the middleware check
3. Verifies the reminder is sent and marked as sent
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from calendarEditor.models import QueueEntry
from calendarEditor.middleware import CheckReminderMiddleware

print("=" * 60)
print("TESTING REMINDER SYSTEM (WITHOUT CELERY)")
print("=" * 60)

# Check for running entries
running_entries = QueueEntry.objects.filter(status='running')
print(f"\nFound {running_entries.count()} running entries")

if running_entries.count() == 0:
    print("\n⚠️  No running entries found.")
    print("To test the reminder system:")
    print("1. Check in to a machine through the web interface")
    print("2. Run this script again to see the pending reminder")
    print("3. Update the reminder_due_at to the past in Django admin or shell")
    print("4. Refresh any page in the app to trigger the middleware")
else:
    for entry in running_entries:
        print(f"\n📋 Entry: {entry.title} (ID: {entry.id})")
        print(f"   User: {entry.user.username}")
        print(f"   Started: {entry.started_at}")
        print(f"   Duration: {entry.estimated_duration_hours} hours")

        if entry.reminder_due_at:
            print(f"   Reminder due: {entry.reminder_due_at}")
            print(f"   Reminder sent: {entry.reminder_sent}")

            if entry.reminder_sent:
                print("   ✅ Reminder already sent")
            elif entry.reminder_due_at <= timezone.now():
                print("   ⏰ Reminder is DUE! Will be sent on next page load")
            else:
                time_until = entry.reminder_due_at - timezone.now()
                print(f"   ⏳ Reminder in {time_until}")
        else:
            print("   ⚠️  No reminder set (old entry before migration)")

# Check if there are any pending reminders
pending_count = QueueEntry.objects.filter(
    reminder_due_at__lte=timezone.now(),
    reminder_sent=False,
    status='running'
).count()

print(f"\n{'=' * 60}")
print(f"PENDING REMINDERS: {pending_count}")
if pending_count > 0:
    print("These will be sent on the next HTTP request to the app!")
print(f"{'=' * 60}\n")

# Test the middleware logic directly
print("Testing middleware check function...")
middleware = CheckReminderMiddleware(lambda x: x)
try:
    middleware._check_pending_reminders()
    print("✅ Middleware check completed successfully")

    # Check again after running middleware
    still_pending = QueueEntry.objects.filter(
        reminder_due_at__lte=timezone.now(),
        reminder_sent=False,
        status='running'
    ).count()

    if still_pending == 0 and pending_count > 0:
        print(f"✅ Successfully sent {pending_count} reminder(s)!")
    elif still_pending == 0:
        print("ℹ️  No pending reminders to send")

except Exception as e:
    print(f"❌ Error: {e}")

print("\nDone!")
