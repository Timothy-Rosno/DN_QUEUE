"""
Best-fit algorithm for matching user requests to lab equipment.
"""
from django.utils import timezone
from datetime import timedelta
from .models import Machine, QueueEntry
from . import notifications


def find_best_machine(queue_entry, return_details=False):
    """
    Find the best matching machine for a queue entry based on requirements.

    Algorithm:
    1. Filter machines that meet temperature requirements
    2. Filter machines that meet B-field strength requirements
    3. Filter machines that meet B-field direction requirements
    4. Filter machines that meet DC/RF line requirements
    5. Filter machines that meet daughterboard requirements
    6. Filter machines that meet optical capabilities requirements
    7. Among valid machines, select the one that will be available SOONEST
       (calculated as current time + wait time for existing queue)
    8. If no machines match, return None

    This ensures requests go to the machine that will be open first,
    optimizing overall throughput and minimizing user wait times.

    Args:
        queue_entry: QueueEntry instance with user requirements
        return_details: If True, return detailed matching information

    Returns:
        Machine instance or None if no suitable machine found
        If return_details=True, returns (Machine, details_dict)
    """
    # Get all available machines (not in maintenance and marked as available)
    available_machines = Machine.objects.filter(is_available=True).exclude(current_status='maintenance')

    matching_details = {
        'total_machines': available_machines.count(),
        'temp_compatible': [],
        'field_compatible': [],
        'availability_times': {},
        'rejected_reasons': []
    }

    # Filter by temperature requirements
    temp_compatible = []
    for machine in available_machines:
        # Machine must be able to reach the required minimum temperature
        if machine.min_temp <= queue_entry.required_min_temp:
            # If max temp specified, check that machine can handle it
            if queue_entry.required_max_temp:
                if machine.max_temp >= queue_entry.required_max_temp:
                    temp_compatible.append(machine)
                    matching_details['temp_compatible'].append(machine.name)
                else:
                    matching_details['rejected_reasons'].append(
                        f"{machine.name}: Max temp {machine.max_temp}K < required {queue_entry.required_max_temp}K"
                    )
            else:
                # If no max temp specified, just check min temp
                temp_compatible.append(machine)
                matching_details['temp_compatible'].append(machine.name)
        else:
            matching_details['rejected_reasons'].append(
                f"{machine.name}: Min temp {machine.min_temp}K > required {queue_entry.required_min_temp}K"
            )

    if not temp_compatible:
        if return_details:
            return None, matching_details
        return None

    # Filter by B-field requirements
    field_compatible = []
    for machine in temp_compatible:
        if (machine.b_field_x >= queue_entry.required_b_field_x and
            machine.b_field_y >= queue_entry.required_b_field_y and
            machine.b_field_z >= queue_entry.required_b_field_z):
            field_compatible.append(machine)
            matching_details['field_compatible'].append(machine.name)
        else:
            matching_details['rejected_reasons'].append(
                f"{machine.name}: B-field insufficient (has {machine.b_field_x}/{machine.b_field_y}/{machine.b_field_z}T, "
                f"need {queue_entry.required_b_field_x}/{queue_entry.required_b_field_y}/{queue_entry.required_b_field_z}T)"
            )

    if not field_compatible:
        if return_details:
            return None, matching_details
        return None

    # Filter by B-field direction requirements
    direction_compatible = []
    for machine in field_compatible:
        # If user requires a specific direction
        if queue_entry.required_b_field_direction and queue_entry.required_b_field_direction != '':
            if queue_entry.required_b_field_direction == 'none':
                # User explicitly doesn't need B-field - all machines work
                direction_compatible.append(machine)
            elif queue_entry.required_b_field_direction == 'parallel_perpendicular':
                # User needs both - machine must support both
                if machine.b_field_direction == 'parallel_perpendicular':
                    direction_compatible.append(machine)
                else:
                    matching_details['rejected_reasons'].append(
                        f"{machine.name}: Needs parallel AND perpendicular, has {machine.get_b_field_direction_display()}"
                    )
            else:
                # User needs perpendicular or parallel
                # Machine with both directions satisfies any single direction need
                if (machine.b_field_direction == 'parallel_perpendicular' or
                    machine.b_field_direction == queue_entry.required_b_field_direction):
                    direction_compatible.append(machine)
                else:
                    matching_details['rejected_reasons'].append(
                        f"{machine.name}: B-field direction mismatch (has {machine.get_b_field_direction_display()}, "
                        f"need {dict(queue_entry.B_FIELD_DIRECTION_CHOICES).get(queue_entry.required_b_field_direction)})"
                    )
        else:
            # No specific direction required - all machines pass
            direction_compatible.append(machine)

    if not direction_compatible:
        if return_details:
            return None, matching_details
        return None

    # Filter by DC/RF line requirements
    connection_compatible = []
    for machine in direction_compatible:
        if (machine.dc_lines >= queue_entry.required_dc_lines and
            machine.rf_lines >= queue_entry.required_rf_lines):
            connection_compatible.append(machine)
        else:
            matching_details['rejected_reasons'].append(
                f"{machine.name}: Insufficient connections (has {machine.dc_lines} DC/{machine.rf_lines} RF, "
                f"need {queue_entry.required_dc_lines} DC/{queue_entry.required_rf_lines} RF)"
            )

    if not connection_compatible:
        if return_details:
            return None, matching_details
        return None

    # Filter by daughterboard requirements
    daughterboard_compatible = []
    for machine in connection_compatible:
        # If user requires a specific daughterboard
        if queue_entry.required_daughterboard:
            # Check if machine's daughterboard matches or is compatible
            # For "QBoard I or QBoard II", split and check both
            machine_boards = [b.strip() for b in machine.daughterboard_type.split('or')]
            if any(queue_entry.required_daughterboard.lower() in board.lower() for board in machine_boards):
                daughterboard_compatible.append(machine)
            else:
                matching_details['rejected_reasons'].append(
                    f"{machine.name}: Daughterboard incompatible (has {machine.daughterboard_type}, need {queue_entry.required_daughterboard})"
                )
        else:
            # No specific daughterboard required - all machines pass
            daughterboard_compatible.append(machine)

    if not daughterboard_compatible:
        if return_details:
            return None, matching_details
        return None

    # Filter by optical requirements (CURRENTLY DISABLED - NOT YET IMPLEMENTED)
    # For now, optical capability is captured in the form but not used for machine matching
    optical_compatible = daughterboard_compatible  # All daughterboard-compatible machines pass

    # Future implementation will filter based on optical requirements:
    # if queue_entry.requires_optical:
    #     if machine.optical_capabilities in ['available', 'with_work', 'under_construction']:
    #         optical_compatible.append(machine)

    if not optical_compatible:
        if return_details:
            return None, matching_details
        return None

    # Among compatible machines, find the one that will be available SOONEST
    # This is the machine with the earliest predicted open time
    best_machine = None
    earliest_available_time = None

    for machine in optical_compatible:
        wait_time = machine.get_estimated_wait_time()
        available_at = timezone.now() + wait_time

        matching_details['availability_times'][machine.name] = {
            'wait_time': wait_time,
            'available_at': available_at,
            'queue_count': machine.get_queue_count()
        }

        if earliest_available_time is None or available_at < earliest_available_time:
            earliest_available_time = available_at
            best_machine = machine

    matching_details['selected_machine'] = best_machine.name if best_machine else None
    matching_details['selected_available_at'] = earliest_available_time

    if return_details:
        return best_machine, matching_details
    return best_machine


def assign_to_queue(queue_entry):
    """
    Assign a queue entry to the best matching machine and set queue position.

    Args:
        queue_entry: QueueEntry instance to assign

    Returns:
        True if successfully assigned, False otherwise
    """
    best_machine = find_best_machine(queue_entry)

    if not best_machine:
        return False

    # Assign to machine
    queue_entry.assigned_machine = best_machine

    # Get current max queue position for this machine
    max_position = QueueEntry.objects.filter(
        assigned_machine=best_machine,
        status='queued'
    ).aggregate(models.Max('queue_position'))['queue_position__max']

    # Set queue position
    if max_position is None:
        queue_entry.queue_position = 1
    else:
        queue_entry.queue_position = max_position + 1

    # Calculate estimated start time
    queue_entry.estimated_start_time = queue_entry.calculate_estimated_start_time()

    queue_entry.save()

    # If this entry is at position #1, notify the user
    # (On Deck if machine is busy, Ready for Check-In if machine is idle)
    if queue_entry.queue_position == 1:
        try:
            notifications.check_and_notify_on_deck_status(best_machine)
        except Exception as e:
            print(f"Notification failed for position #1: {e}")

    return True


def get_matching_machines(required_min_temp, required_max_temp=None,
                         required_b_field_x=0, required_b_field_y=0, required_b_field_z=0):
    """
    Get list of machines that match the given requirements.
    Useful for showing users which machines are compatible before submission.

    Args:
        required_min_temp: Minimum temperature required (Kelvin)
        required_max_temp: Maximum temperature required (Kelvin, optional)
        required_b_field_x: Required B-field X (Tesla)
        required_b_field_y: Required B-field Y (Tesla)
        required_b_field_z: Required B-field Z (Tesla)

    Returns:
        QuerySet of compatible Machine instances
    """
    from django.db.models import Q

    # Start with all available, non-maintenance machines
    machines = Machine.objects.filter(is_available=True).exclude(current_status='maintenance')

    # Filter by temperature
    machines = machines.filter(min_temp__lte=required_min_temp)
    if required_max_temp:
        machines = machines.filter(max_temp__gte=required_max_temp)

    # Filter by B-field
    machines = machines.filter(
        b_field_x__gte=required_b_field_x,
        b_field_y__gte=required_b_field_y,
        b_field_z__gte=required_b_field_z
    )

    return machines


def reorder_queue(machine, notify=True):
    """
    Reorder queue positions for a machine after an entry is removed or queue changes.

    This ensures:
    - All queued entries have sequential positions starting from 1
    - Entries with NULL positions are fixed
    - Estimated start times are recalculated

    Args:
        machine: Machine instance whose queue needs reordering
        notify: If True (default), notify the person at position #1 they're on deck/ready.
                If False, skip notifications (used for deletions to avoid notifying during cleanup).
    """
    from django.db.models import F

    # Get all queued entries, handling NULLs by ordering them last
    # This ensures we process valid positions first, then fix any corrupted NULL positions
    queued_entries = QueueEntry.objects.filter(
        assigned_machine=machine,
        status='queued'
    ).order_by(F('queue_position').asc(nulls_last=True), 'submitted_at')

    # Reassign sequential positions to all queued entries
    for index, entry in enumerate(queued_entries, start=1):
        if entry.queue_position != index:
            entry.queue_position = index
        entry.estimated_start_time = entry.calculate_estimated_start_time()
        entry.save()

    # Check if there's a new entry at position #1 and notify them they're ON DECK
    # (unless notify=False, which is used for deletions)
    if notify:
        try:
            notifications.check_and_notify_on_deck_status(machine)
        except Exception as e:
            print(f"ON DECK notification failed: {e}")


def move_queue_entry_up(entry_id):
    """
    Move a queue entry up in the queue (decrease position number).

    Args:
        entry_id: ID of the QueueEntry to move up

    Returns:
        True if successfully moved, False if already at position 1 or not found
    """
    try:
        entry = QueueEntry.objects.get(id=entry_id, status='queued')
    except QueueEntry.DoesNotExist:
        return False

    if entry.queue_position <= 1:
        return False  # Already at the top

    machine = entry.assigned_machine

    # Find the entry currently at the position above
    entry_above = QueueEntry.objects.filter(
        assigned_machine=machine,
        status='queued',
        queue_position=entry.queue_position - 1
    ).first()

    if entry_above:
        # Swap positions
        old_position = entry.queue_position
        entry_above.queue_position += 1
        entry.queue_position -= 1
        new_position = entry.queue_position

        entry_above.estimated_start_time = entry_above.calculate_estimated_start_time()
        entry.estimated_start_time = entry.calculate_estimated_start_time()

        entry_above.save()
        entry.save()

        # Notify user of position change
        try:
            notifications.notify_queue_position_change(entry, old_position, new_position)
            # Check if someone is now ON DECK after the move
            notifications.check_and_notify_on_deck_status(machine)
        except Exception as e:
            print(f"Notification failed: {e}")

        return True

    return False


def move_queue_entry_down(entry_id):
    """
    Move a queue entry down in the queue (increase position number).

    Args:
        entry_id: ID of the QueueEntry to move down

    Returns:
        True if successfully moved, False if already at last position or not found
    """
    try:
        entry = QueueEntry.objects.get(id=entry_id, status='queued')
    except QueueEntry.DoesNotExist:
        return False

    machine = entry.assigned_machine

    # Find the entry currently at the position below
    entry_below = QueueEntry.objects.filter(
        assigned_machine=machine,
        status='queued',
        queue_position=entry.queue_position + 1
    ).first()

    if entry_below:
        # Swap positions
        old_position = entry.queue_position
        entry_below.queue_position -= 1
        entry.queue_position += 1
        new_position = entry.queue_position

        entry_below.estimated_start_time = entry_below.calculate_estimated_start_time()
        entry.estimated_start_time = entry.calculate_estimated_start_time()

        entry_below.save()
        entry.save()

        # Notify user of position change
        try:
            notifications.notify_queue_position_change(entry, old_position, new_position)
            # Check if someone is now ON DECK after the move
            notifications.check_and_notify_on_deck_status(machine)
        except Exception as e:
            print(f"Notification failed: {e}")

        return True

    return False


def set_queue_position(entry_id, new_position):
    """
    Set a queue entry to a specific position in the queue.

    Args:
        entry_id: ID of the QueueEntry to reposition
        new_position: Desired queue position (1-based)

    Returns:
        True if successfully repositioned, False if invalid position or not found
    """
    try:
        entry = QueueEntry.objects.get(id=entry_id, status='queued')
    except QueueEntry.DoesNotExist:
        return False

    if new_position < 1:
        return False

    machine = entry.assigned_machine
    old_position = entry.queue_position

    # Get max position for this machine's queue
    max_position = QueueEntry.objects.filter(
        assigned_machine=machine,
        status='queued'
    ).count()

    if new_position > max_position:
        new_position = max_position

    if old_position == new_position:
        return True  # No change needed

    # Get all queued entries for this machine
    entries = QueueEntry.objects.filter(
        assigned_machine=machine,
        status='queued'
    ).order_by('queue_position')

    # Remove the entry being moved from its current position
    entries_list = list(entries)
    entries_list.remove(entry)

    # Insert it at the new position (0-indexed)
    entries_list.insert(new_position - 1, entry)

    # Update all positions
    for index, e in enumerate(entries_list, start=1):
        e.queue_position = index
        e.estimated_start_time = e.calculate_estimated_start_time()
        e.save()

    # Notify user of position change
    try:
        notifications.notify_queue_position_change(entry, old_position, new_position)
        # Check if someone is now ON DECK after the reposition
        notifications.check_and_notify_on_deck_status(machine)
    except Exception as e:
        print(f"Notification failed: {e}")

    return True


# Import models for aggregate function
from django.db import models
