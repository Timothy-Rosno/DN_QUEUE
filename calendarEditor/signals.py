"""
Signal handlers for calendarEditor app.

Ensures queue integrity after deletions and other operations.
"""
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver
from .models import QueueEntry


# Track machines affected by deletions before they happen
_machines_to_reorder = set()


@receiver(pre_delete, sender=QueueEntry)
def track_deleted_queue_entry(sender, instance, **kwargs):
    """
    Track which machines need queue reordering before a QueueEntry is deleted.

    We use pre_delete instead of post_delete because we need to know the machine
    while the entry still exists in the database.
    """
    global _machines_to_reorder

    # Only reorder if the entry was in 'queued' status
    if instance.status == 'queued' and instance.assigned_machine:
        _machines_to_reorder.add(instance.assigned_machine.id)


@receiver(post_delete, sender=QueueEntry)
def reorder_queue_after_deletion(sender, instance, **kwargs):
    """
    Automatically reorder queue positions after a QueueEntry is deleted.

    This ensures:
    - No gaps in queue positions (e.g., 1, 2, 4, 5 becomes 1, 2, 3, 4)
    - Position 1 is always filled if there are queued entries
    - Users are notified of position changes
    """
    global _machines_to_reorder

    # Get machines that need reordering from pre_delete tracking
    machines_to_process = _machines_to_reorder.copy()
    _machines_to_reorder.clear()

    if not machines_to_process:
        return

    from .matching_algorithm import reorder_queue
    from .models import Machine

    for machine_id in machines_to_process:
        try:
            machine = Machine.objects.get(id=machine_id)
            # Reorder the queue and notify users of position changes
            reorder_queue(machine, notify=True)
        except Machine.DoesNotExist:
            # Machine was deleted or doesn't exist
            pass
        except Exception as e:
            # Don't let reordering errors break the deletion
            print(f"Error reordering queue for machine {machine_id}: {e}")
