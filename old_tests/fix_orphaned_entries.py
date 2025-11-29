"""
Clean up orphaned running entries and fix machine statuses.

This script fixes database inconsistencies caused by the Celery bug.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from django.utils import timezone
from calendarEditor.models import QueueEntry, Machine

print("=" * 60)
print("FIXING ORPHANED ENTRIES AND MACHINE STATUSES")
print("=" * 60)

# Fix 1: Update orphaned running entries
print("\n1️⃣  Fixing orphaned running entries...")
orphaned = QueueEntry.objects.filter(status='running', completed_at__isnull=True)
count = orphaned.count()

if count > 0:
    print(f"   Found {count} orphaned running entry(ies)")
    for entry in orphaned:
        print(f"   - Setting entry {entry.id} ({entry.title}) to 'cancelled'")

    orphaned.update(status='cancelled')
    print(f"   ✅ Fixed {count} orphaned entry(ies)")
else:
    print("   ✅ No orphaned entries found")

# Fix 2: Fix machine statuses
print("\n2️⃣  Fixing machine statuses...")
machines = Machine.objects.all()

for machine in machines:
    running_count = QueueEntry.objects.filter(
        assigned_machine=machine,
        status='running'
    ).count()

    # If machine shows 'running' but has no running jobs, fix it
    if machine.current_status == 'running' and running_count == 0:
        print(f"   - {machine.name}: Fixing status (running → idle)")
        machine.current_status = 'idle'
        machine.current_user = None
        machine.estimated_available_time = None
        machine.save()

    # If machine shows not 'running' but has running jobs, fix it
    elif machine.current_status != 'running' and running_count > 0:
        running_entry = QueueEntry.objects.filter(
            assigned_machine=machine,
            status='running'
        ).first()

        print(f"   - {machine.name}: Fixing status (idle → running)")
        machine.current_status = 'running'
        machine.current_user = running_entry.user
        machine.save()

print("\n✅ Database cleanup complete!")

# Verify fix
print("\n" + "=" * 60)
print("VERIFICATION")
print("=" * 60)

orphaned_after = QueueEntry.objects.filter(status='running', completed_at__isnull=True).count()
print(f"\nOrphaned running entries: {orphaned_after}")

if orphaned_after == 0:
    print("✅ All orphaned entries cleaned up!")
else:
    print(f"⚠️  Still have {orphaned_after} orphaned entries")

# Check machines
inconsistent = 0
for machine in Machine.objects.all():
    running_count = QueueEntry.objects.filter(
        assigned_machine=machine,
        status='running'
    ).count()

    if (machine.current_status == 'running' and running_count == 0) or \
       (machine.current_status != 'running' and running_count > 0):
        inconsistent += 1

print(f"Machines with inconsistent status: {inconsistent}")

if inconsistent == 0:
    print("✅ All machine statuses are consistent!")
else:
    print(f"⚠️  {inconsistent} machines still have inconsistent status")

print("\n" + "=" * 60)
print("✅ You can now check in successfully!")
print("=" * 60 + "\n")
