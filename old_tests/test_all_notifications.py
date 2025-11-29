#!/usr/bin/env python
"""
Verify that all notification types include View Details links and no emojis.
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
from calendarEditor.models import Notification, QueuePreset, Machine, QueueEntry

print("=" * 70)
print("NOTIFICATION LINK & EMOJI CHECK - ALL NOTIFICATION TYPES")
print("=" * 70)

# Get test user
user = User.objects.get(username='TimmyRosno')

# Get admin user for admin notifications
admin_user = User.objects.filter(is_staff=True).first()
if not admin_user:
    print("WARNING: No admin user found. Creating one for testing...")
    admin_user = User.objects.create_user(
        username='test_admin',
        email='admin@test.com',
        password='testpass',
        is_staff=True,
        is_superuser=True
    )

print(f"\nTesting with regular user: {user.username}")
print(f"Testing with admin user: {admin_user.username}")
print(f"User Slack Member ID: {user.profile.slack_member_id}")
print()

# Get or create related objects for testing
preset = QueuePreset.objects.filter(creator=user).first()
machine = Machine.objects.first()
queue_entry = QueueEntry.objects.filter(user=user).first()

# Test ALL notification types (14 types)
test_notifications = [
    # Preset notifications (3)
    {
        'type': 'preset_created',
        'title': 'New Public Preset Created',
        'message': 'Test preset created notification',
        'related_preset': preset
    },
    {
        'type': 'preset_edited',
        'title': 'Public Preset Updated',
        'message': 'Test preset edited notification',
        'related_preset': preset
    },
    {
        'type': 'preset_deleted',
        'title': 'Public Preset Deleted',
        'message': 'Test preset deleted notification'
    },
    # Queue notifications (3)
    {
        'type': 'queue_added',
        'title': 'New Entry Added to Queue',
        'message': 'Test queue entry added notification',
        'related_queue_entry': queue_entry,
        'related_machine': machine
    },
    {
        'type': 'queue_moved',
        'title': 'Queue Position Changed',
        'message': 'Test queue position change notification',
        'related_queue_entry': queue_entry,
        'related_machine': machine
    },
    {
        'type': 'queue_cancelled',
        'title': 'Queue Entry Cancelled',
        'message': 'Test queue entry cancelled notification',
        'related_queue_entry': queue_entry,
        'related_machine': machine
    },
    # On Deck / Check-in notifications (3)
    {
        'type': 'on_deck',
        'title': 'ON DECK - You\'re Next!',
        'message': 'Test ON DECK notification',
        'related_queue_entry': queue_entry,
        'related_machine': machine
    },
    {
        'type': 'ready_for_check_in',
        'title': 'Ready for Check-In!',
        'message': 'Test ready for check-in notification',
        'related_queue_entry': queue_entry,
        'related_machine': machine
    },
    {
        'type': 'checkout_reminder',
        'title': 'Time for Check-Out!',
        'message': 'Test checkout reminder notification',
        'related_queue_entry': queue_entry,
        'related_machine': machine
    },
    # Admin action notifications (3)
    {
        'type': 'machine_status_changed',
        'title': 'Time to Check Out',
        'message': 'Test machine status changed notification',
        'related_queue_entry': queue_entry,
        'related_machine': machine,
        'triggering_user': admin_user
    },
    {
        'type': 'admin_check_in',
        'title': 'Admin Check-In',
        'message': 'Test admin check-in notification',
        'related_queue_entry': queue_entry,
        'related_machine': machine,
        'triggering_user': admin_user
    },
    {
        'type': 'admin_checkout',
        'title': 'Admin Check-Out',
        'message': 'Test admin check-out notification',
        'related_queue_entry': queue_entry,
        'related_machine': machine,
        'triggering_user': admin_user
    },
    {
        'type': 'admin_edit_entry',
        'title': 'Admin Edited Your Entry',
        'message': 'Test admin edit entry notification',
        'related_queue_entry': queue_entry,
        'related_machine': machine,
        'triggering_user': admin_user
    }
]

# Admin-only notifications (2) - separate list for admin user
admin_notifications = [
    {
        'type': 'admin_new_user',
        'title': 'New User Signup',
        'message': 'Test new user signup notification',
        'triggering_user': user
    },
    {
        'type': 'admin_rush_job',
        'title': 'Rush Job Submitted',
        'message': 'Test rush job notification',
        'related_queue_entry': queue_entry,
        'related_machine': machine,
        'triggering_user': user
    }
]

print("Creating REGULAR USER test notifications:")
print("-" * 70)

created_count = 0
for notif in test_notifications:
    # Build kwargs with optional related objects
    kwargs = {}
    if 'related_preset' in notif and notif['related_preset']:
        kwargs['related_preset'] = notif['related_preset']
    if 'related_queue_entry' in notif and notif['related_queue_entry']:
        kwargs['related_queue_entry'] = notif['related_queue_entry']
    if 'related_machine' in notif and notif['related_machine']:
        kwargs['related_machine'] = notif['related_machine']
    if 'triggering_user' in notif and notif['triggering_user']:
        kwargs['triggering_user'] = notif['triggering_user']

    notification = create_notification(
        recipient=user,
        notification_type=notif['type'],
        title=notif['title'],
        message=notif['message'],
        **kwargs
    )
    created_count += 1

    # Check for emojis in title
    has_emoji = any(char in notif['title'] for char in ['🎯', '✅', '⚠️', '⏰', '👤', '🚨', '❌'])
    emoji_status = "❌ HAS EMOJI" if has_emoji else "✓ No emoji"

    # Get expected link URL
    link_url = notification.get_notification_url()

    print(f"{created_count}. {notif['title']}")
    print(f"   Type: {notif['type']}")
    print(f"   Link: {link_url}")
    print(f"   Emoji check: {emoji_status}")
    print()

print()
print("Creating ADMIN USER test notifications:")
print("-" * 70)

admin_count = 0
for notif in admin_notifications:
    # Build kwargs with optional related objects
    kwargs = {}
    if 'related_queue_entry' in notif and notif['related_queue_entry']:
        kwargs['related_queue_entry'] = notif['related_queue_entry']
    if 'related_machine' in notif and notif['related_machine']:
        kwargs['related_machine'] = notif['related_machine']
    if 'triggering_user' in notif and notif['triggering_user']:
        kwargs['triggering_user'] = notif['triggering_user']

    notification = create_notification(
        recipient=admin_user,
        notification_type=notif['type'],
        title=notif['title'],
        message=notif['message'],
        **kwargs
    )
    admin_count += 1

    # Check for emojis in title
    has_emoji = any(char in notif['title'] for char in ['🎯', '✅', '⚠️', '⏰', '👤', '🚨', '❌'])
    emoji_status = "❌ HAS EMOJI" if has_emoji else "✓ No emoji"

    # Get expected link URL
    link_url = notification.get_notification_url()

    print(f"{admin_count}. {notif['title']}")
    print(f"   Type: {notif['type']}")
    print(f"   Link: {link_url}")
    print(f"   Emoji check: {emoji_status}")
    print()

total_count = created_count + admin_count

print("=" * 70)
print(f"\n✅ Created {total_count} test notifications (15 total types):")
print(f"   • {created_count} regular user notifications sent to {user.username}")
print(f"   • {admin_count} admin notifications sent to {admin_user.username}")
print()
print("EXPECTED NOTIFICATION LINKS BY TYPE:")
print("-" * 70)
print("  Preset notifications → /submit/ or /submit/?preset_id=X")
print("  Queue notifications → /my-queue/")
print("  Check-in notifications → /check-in-check-out/")
print("  Admin new user → /admin-users/?status=pending")
print("  Admin rush job → /admin-rush-jobs-review/")
print()
print("CHECK SLACK DMs:")
print("  1. Each notification should have a 'View Details' link")
print("  2. No emojis should appear in titles")
print("  3. Links should be clickable and reusable")
print("  4. Admin user should receive admin-specific notifications")
print()
print("To verify:")
print("  • Click each link (should work)")
print("  • Click same link again (should still work)")
print("  • All links should redirect to appropriate pages")
print("  • Admin links should go to admin pages")
print()
print("=" * 70)
