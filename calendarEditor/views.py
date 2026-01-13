from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .decorators import require_queue_status, require_machine_available, atomic_operation, require_own_entry
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db.models import F, Q
from datetime import timedelta
from .models import ScheduleEntry, QueueEntry, Machine, QueuePreset, NotificationPreference, ArchivedMeasurement
from .forms import ScheduleEntryForm, QueueEntryForm, QueuePresetForm, ArchivedMeasurementForm
from .matching_algorithm import (assign_to_queue, get_matching_machines, reorder_queue,
                                find_best_machine, move_queue_entry_up, move_queue_entry_down,
                                set_queue_position)
from . import notifications
from .notifications import auto_clear_notifications


# ====================
# PUBLIC DISPLAY VIEWS (formerly calendarDisplay app)
# ====================

def home(request):
    """Home page showing live machine status and queue. Simplified view for quick overview."""
    from django.db.models import Q, Prefetch

    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    machine_filter = request.GET.get('machine', 'all')

    # Fetch all machines with prefetched data (fresh from database - no caching)
    all_machines = Machine.objects.prefetch_related(
        Prefetch('queue_entries',
                 queryset=QueueEntry.objects.select_related('user').filter(
                     Q(status='running') | Q(status='queued')
                 ).order_by('queue_position'),
                 to_attr='prefetched_entries')
    ).order_by('name')

    # Apply filters
    machines = all_machines
    if status_filter != 'all':
        machines = machines.filter(current_status=status_filter)
    if machine_filter != 'all':
        machines = machines.filter(id=machine_filter)

    # Build machine status overview data (using prefetched data)
    machine_status_data = []
    for machine in all_machines:
        # Use prefetched data instead of separate queries
        running_job = next((e for e in machine.prefetched_entries if e.status == 'running'), None)
        on_deck_job = next((e for e in machine.prefetched_entries if e.status == 'queued' and e.queue_position == 1), None)
        queue_count = sum(1 for e in machine.prefetched_entries if e.status == 'queued')
        running_entries = [e for e in machine.prefetched_entries if e.status == 'running']

        machine_status_data.append({
            'machine': machine,
            'running_job': running_job,
            'on_deck_job': on_deck_job,
            'queue_count': queue_count,
            'live_temp': machine.get_live_temperature(),
            'display_status': machine.get_display_status(prefetch_running=running_entries),
        })

    # Build filtered machine data (data is already prefetched on cached objects)
    machine_data = []
    for machine in machines:
        wait_time = machine.get_estimated_wait_time()

        # Calculate estimated available time
        estimated_available_time = None
        if wait_time.total_seconds() > 0:
            estimated_available_time = timezone.now() + wait_time

        running_entries = [e for e in machine.prefetched_entries if e.status == 'running']
        data = {
            'machine': machine,
            'wait_time': wait_time,
            'estimated_available_time': estimated_available_time,
            'live_temp': machine.get_live_temperature(),
            'display_status': machine.get_display_status(prefetch_running=running_entries),
        }

        # Only fetch queue details if user is logged in
        if request.user.is_authenticated:
            # Use prefetched data (already on cached objects)
            queued_entries = [e for e in machine.prefetched_entries if e.status == 'queued']

            # Get top 3 queue entries
            queue_entries = queued_entries[:3]

            # If user has an entry beyond position 3, add it
            user_entries_beyond_3 = [e for e in queued_entries if e.user_id == request.user.id and e.queue_position and e.queue_position > 3]
            if user_entries_beyond_3:
                queue_entries.append(user_entries_beyond_3[0])

            data['queue_entries'] = queue_entries
            data['running_entry'] = next((e for e in machine.prefetched_entries if e.status == 'running'), None)
            data['queue_count'] = len(queued_entries)

        machine_data.append(data)

    context = {
        'machine_data': machine_data,
        'machine_status_data': machine_status_data,
        'all_machines': all_machines,
        'status_filter': status_filter,
        'machine_filter': machine_filter,
    }

    return render(request, 'calendarEditor/public/home.html', context)


def fridge_list(request):
    """Fridge specifications page showing detailed specs for all machines."""
    from django.db.models import Count, Q, Prefetch

    # Fetch from database with optimized query (no caching)
    machines_qs = Machine.objects.prefetch_related(
        Prefetch('queue_entries',
                 queryset=QueueEntry.objects.select_related('user').filter(
                     Q(status='running') | Q(status='queued')
                 ),
                 to_attr='prefetched_queue')
    ).order_by('name')

    # Add running_job and queue_count to each machine
    machines = []
    for machine in machines_qs:
        running_job = next((e for e in machine.prefetched_queue if e.status == 'running'), None)
        machine.running_job = running_job
        machine.queue_count = sum(1 for e in machine.prefetched_queue if e.status == 'queued')
        machines.append(machine)

    context = {
        'machines': machines,
    }

    return render(request, 'calendarEditor/public/fridge_list.html', context)


@login_required
def public_queue(request):
    """Public queue page showing full queue for all machines with filters."""
    from django.db.models import Q, Count, Prefetch

    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    machine_filter = request.GET.get('machine', 'all')

    # Fetch all machines with prefetched data (fresh from database - no caching)
    all_machines = Machine.objects.prefetch_related(
        Prefetch('queue_entries',
                 queryset=QueueEntry.objects.select_related('user').filter(
                     Q(status='running') | Q(status='queued')
                 ).order_by('queue_position'),
                 to_attr='prefetched_entries')
    ).order_by('name')

    # Apply filters
    machines = all_machines
    if status_filter != 'all':
        machines = machines.filter(current_status=status_filter)
    if machine_filter != 'all':
        machines = machines.filter(id=machine_filter)

    # Build machine status overview (shows all machines regardless of filters)
    machine_status_data = []
    for machine in all_machines:
        # Use prefetched data instead of separate queries
        running_job = next((e for e in machine.prefetched_entries if e.status == 'running'), None)
        on_deck_job = next((e for e in machine.prefetched_entries if e.status == 'queued' and e.queue_position == 1), None)
        queue_count = sum(1 for e in machine.prefetched_entries if e.status == 'queued')
        running_entries = [e for e in machine.prefetched_entries if e.status == 'running']

        machine_status_data.append({
            'machine': machine,
            'running_job': running_job,
            'on_deck_job': on_deck_job,
            'queue_count': queue_count,
            'live_temp': machine.get_live_temperature(),
            'display_status': machine.get_display_status(prefetch_running=running_entries),
        })

    # Build queue data for filtered machines (show ALL queue entries, not just top 3)
    machine_queue_data = []
    for machine in machines:
        # Use prefetched data (already on cached objects)
        queued_entries = [e for e in machine.prefetched_entries if e.status == 'queued']
        running_entry = next((e for e in machine.prefetched_entries if e.status == 'running'), None)
        running_entries = [e for e in machine.prefetched_entries if e.status == 'running']

        # Calculate wait time
        wait_time = machine.get_estimated_wait_time()
        estimated_available_time = None
        if wait_time.total_seconds() > 0:
            estimated_available_time = timezone.now() + wait_time

        machine_queue_data.append({
            'machine': machine,
            'queue_entries': queued_entries,
            'running_entry': running_entry,
            'queue_count': len(queued_entries),
            'wait_time': wait_time,
            'estimated_available_time': estimated_available_time,
            'live_temp': machine.get_live_temperature(),
            'display_status': machine.get_display_status(prefetch_running=running_entries),
        })

    context = {
        'machine_queue_data': machine_queue_data,
        'machine_status_data': machine_status_data,
        'all_machines': all_machines,
        'status_filter': status_filter,
        'machine_filter': machine_filter,
    }

    return render(request, 'calendarEditor/public/queue.html', context)


# ====================
# QUEUE MANAGEMENT VIEWS
# ====================

@login_required
def submit_queue_entry(request):
    """Submit a new queue entry."""
    if request.method == 'POST':
        form = QueueEntryForm(request.POST)
        if form.is_valid():
            queue_entry = form.save(commit=False)
            queue_entry.user = request.user

            # Handle rush job submission
            if queue_entry.is_rush_job:
                queue_entry.rush_job_submitted_at = timezone.now()

            # Find best matching machine with details
            best_machine, details = find_best_machine(queue_entry, return_details=True)

            if best_machine:
                # Auto-calculate estimated duration as cooldown + warmup + requested measurement time
                queue_entry.estimated_duration_hours = best_machine.cooldown_hours + best_machine.warmup_hours + (queue_entry.requested_measurement_days * 24)
                # Assign to queue
                if assign_to_queue(queue_entry):
                    # Broadcast queue update to all connected users (gracefully fails if Redis unavailable)
                    try:
                        channel_layer = get_channel_layer()
                        async_to_sync(channel_layer.group_send)(
                            'queue_updates',
                            {
                                'type': 'queue_update',
                                'update_type': 'submitted',
                                'entry_id': queue_entry.id,
                                'user_id': queue_entry.user.id,
                                'machine_id': queue_entry.assigned_machine.id if queue_entry.assigned_machine else None,
                                'machine_name': queue_entry.assigned_machine.name if queue_entry.assigned_machine else None,
                                'triggering_user_id': request.user.id,
                            }
                        )
                    except Exception as e:
                        # WebSocket broadcast failed (Redis likely not running) - continue anyway
                        print(f"WebSocket broadcast failed: {e}")

                    # Notify other users in the queue about the new entry
                    try:
                        notifications.notify_machine_queue_addition(queue_entry, request.user)
                    except Exception as e:
                        print(f"Machine queue notification failed: {e}")

                    # Notify the user that their entry was successfully added
                    try:
                        notifications.notify_queue_added(queue_entry)
                    except Exception as e:
                        print(f"Queue added notification failed: {e}")

                    # Build detailed success message
                    wait_time = details['availability_times'][best_machine.name]['wait_time']
                    hours = int(wait_time.total_seconds() // 3600)

                    success_msg = (
                        f'Queue entry submitted successfully! '
                        f'You have been assigned to <strong>{queue_entry.assigned_machine.name}</strong> '
                        f'at position <strong>#{queue_entry.queue_position}</strong>.<br>'
                        f'<strong>Estimated Duration:</strong> {queue_entry.estimated_duration_hours} hours (includes machine cooldown and warmup sequences). '
                    )

                    if hours == 0:
                        success_msg += 'Machine is available now!'
                    else:
                        success_msg += f'<strong>Estimated wait:</strong> {hours} hours.'

                    # Add info about why this machine was selected
                    if len(details['field_compatible']) > 1:
                        other_machines = [m for m in details['field_compatible'] if m != best_machine.name]
                        success_msg += f' (Selected as next available machine)'

                    # Add queue appeal notification
                    if queue_entry.is_rush_job:
                        success_msg += '<br><strong>Queue Appeal:</strong> Admins have been notified and will review your request.'
                        # Send email notification to admins
                        send_rush_job_notification(queue_entry, request)

                    messages.success(request, success_msg, extra_tags='safe')
                else:
                    messages.error(request,
                        'Error assigning to queue. Please try again.')
                    machines = Machine.objects.all()
                    presets = _get_presets_for_user(request.user)
                    next_url = request.POST.get('next', request.GET.get('next', ''))
                    return render(request, 'calendarEditor/submit_queue.html', {
                        'form': form,
                        'machines': machines,
                        'presets': presets,
                        'next_url': next_url,
                    })
            else:
                # Build detailed error message
                error_msg = 'Could not find a suitable machine for your requirements. '
                if details['rejected_reasons']:
                    error_msg += '<br><br><strong>Reasons:</strong><ul>'
                    for reason in details['rejected_reasons']:
                        error_msg += f'<li>{reason}</li>'
                    error_msg += '</ul>'
                messages.error(request, error_msg, extra_tags='safe')
                machines = Machine.objects.all()
                presets = _get_presets_for_user(request.user)
                next_url = request.POST.get('next', request.GET.get('next', ''))
                return render(request, 'calendarEditor/submit_queue.html', {
                    'form': form,
                    'machines': machines,
                    'presets': presets,
                    'next_url': next_url,
                })

            # Check for next parameter to redirect back to referring page
            next_url = request.POST.get('next', '')
            if next_url == 'public_queue':
                return redirect('public_queue')
            elif next_url == 'home':
                return redirect('home')
            elif next_url:
                # If there's some other next value, go to my_queue
                return redirect('my_queue')
            else:
                # No next parameter means they came directly to submit page, stay here
                return redirect('submit_queue')
        else:
            # Form validation failed
            machines = Machine.objects.all()
            presets = _get_presets_for_user(request.user)
            next_url = request.POST.get('next', request.GET.get('next', ''))
            return render(request, 'calendarEditor/submit_queue.html', {
                'form': form,
                'machines': machines,
                'presets': presets,
                'next_url': next_url,
            })
    else:
        form = QueueEntryForm()

    # Get all machines to show capabilities
    machines = Machine.objects.all()

    # Get presets for dropdown
    presets = _get_presets_for_user(request.user)

    # Get next parameter for redirect
    next_url = request.GET.get('next', '')

    return render(request, 'calendarEditor/submit_queue.html', {
        'form': form,
        'machines': machines,
        'presets': presets,
        'next_url': next_url,
    })


def _get_presets_for_user(user):
    """Helper function to get presets for dropdown (private + public, alphabetically ordered)."""
    # Get user's private presets
    private_presets = QueuePreset.objects.filter(creator=user, is_public=False).order_by('name')

    # Get all public presets
    public_presets = QueuePreset.objects.filter(is_public=True).order_by('name')

    return {
        'private': private_presets,
        'public': public_presets,
    }

@login_required
def my_queue(request):
    """Show user's queue entries."""
    # OPTIMIZED: Added select_related to prevent N+1 queries when accessing assigned_machine
    queued = QueueEntry.objects.filter(user=request.user, status='queued').select_related('assigned_machine').order_by('assigned_machine', 'queue_position')
    running = QueueEntry.objects.filter(user=request.user, status='running').select_related('assigned_machine')
    completed = QueueEntry.objects.filter(user=request.user, status='completed').select_related('assigned_machine').order_by('-completed_at')[:10]

    # Check which machines have running jobs and annotate entries
    machines_with_running_jobs = {}
    for entry in queued:
        if entry.assigned_machine and entry.assigned_machine.id not in machines_with_running_jobs:
            has_running = QueueEntry.objects.filter(
                assigned_machine=entry.assigned_machine,
                status='running'
            ).exists()
            machines_with_running_jobs[entry.assigned_machine.id] = has_running

        # Annotate each entry with whether its machine is busy
        if entry.assigned_machine:
            entry.machine_is_busy = machines_with_running_jobs.get(entry.assigned_machine.id, False)
        else:
            entry.machine_is_busy = False

    # Count ready-to-check-in entries (position 1 AND machine is idle) and running entries for badge
    ready_to_check_in_count = queued.filter(queue_position=1, assigned_machine__current_status='idle').count()
    ready_to_check_out_count = running.count()
    # Count on-deck entries that are NOT ready to check in (machine is not idle)
    on_deck_not_ready_count = queued.filter(queue_position=1).exclude(assigned_machine__current_status='idle').count()
    check_in_out_count = ready_to_check_in_count + ready_to_check_out_count

    # Organize queued entries by machine
    queued_by_machine = {}
    for entry in queued:
        machine_name = entry.assigned_machine.name if entry.assigned_machine else "Unassigned"
        if machine_name not in queued_by_machine:
            queued_by_machine[machine_name] = []
        queued_by_machine[machine_name].append(entry)

    return render(request, 'calendarEditor/my_queue.html', {
        'queued_entries': queued,
        'queued_by_machine': queued_by_machine,
        'running_entries': running,
        'completed_entries': completed,
        'ready_to_check_in_count': ready_to_check_in_count,
        'ready_to_check_out_count': ready_to_check_out_count,
        'on_deck_not_ready_count': on_deck_not_ready_count,
        'check_in_out_count': check_in_out_count,
    })

@login_required
def cancel_queue_entry(request, pk):
    """Cancel a queued or running entry."""
    # Check if entry exists and belongs to current user
    queue_entry = get_object_or_404(QueueEntry, pk=pk)
    if queue_entry.user != request.user:
        messages.warning(request, 'This queue entry is not for your account. Returning to home page.')
        return redirect('home')

    if queue_entry.status not in ['queued', 'running']:
        messages.error(request, 'Can only cancel queued or running entries.')
        return redirect('my_queue')

    if request.method == 'POST':
        machine = queue_entry.assigned_machine
        is_rush = queue_entry.is_rush_job
        was_running = (queue_entry.status == 'running')
        entry_title = queue_entry.title
        machine_name = machine.name if machine else "Unknown Machine"

        queue_entry.status = 'cancelled'
        queue_entry.save()

        # Auto-clear all notifications related to this cancelled queue entry
        auto_clear_notifications(related_queue_entry=queue_entry)

        # Notify the user that their entry was cancelled
        try:
            notifications.notify_queue_cancelled(queue_entry)
        except Exception as e:
            print(f"Queue cancelled notification failed: {e}")

        # Always archive canceled measurements
        try:
            ArchivedMeasurement.objects.create(
                user=queue_entry.user,
                machine=machine,
                machine_name=machine.name if machine else "Unknown Machine",
                related_queue_entry=queue_entry,
                title=entry_title,
                notes=queue_entry.description,
                measurement_date=queue_entry.started_at if was_running else queue_entry.submitted_at,
                archived_at=timezone.now(),
                status='cancelled'
            )
        except Exception as e:
            # Don't fail the cancellation if archiving fails
            print(f'Archive creation failed: {str(e)}')

        # If canceling a running measurement, clean up machine status
        if was_running and machine:
            # No need to cancel reminder - middleware checks status automatically
            machine.current_status = 'idle'
            machine.current_user = None
            machine.estimated_available_time = None
            machine.save()

            # Notify admins about canceled running measurement
            try:
                from .models import Notification
                admin_users = User.objects.filter(is_staff=True)
                for admin in admin_users:
                    notifications.create_notification(
                        recipient=admin,
                        notification_type='queue_cancelled',
                        title='🚫 Running Measurement Canceled',
                        message=f'{request.user.username} canceled their running measurement "{entry_title}" on {machine_name}.',
                        related_queue_entry=queue_entry,
                        related_machine=machine,
                    )
            except Exception as e:
                print(f"Admin notification for canceled running measurement failed: {e}")

        # Notify admins if this was a rush job
        if is_rush:
            try:
                notifications.notify_admins_rush_job_deleted(entry_title, machine_name, request.user)
            except Exception as e:
                print(f"Rush job deletion notification failed: {e}")

        # Reorder the queue for the machine
        if machine:
            reorder_queue(machine)

        # If the canceled job was running, notify the next user that the machine is now available
        if machine and was_running and machine.current_status == 'idle':
                next_entry = QueueEntry.objects.filter(
                    assigned_machine=machine,
                    status='queued',
                    queue_position=1
                ).first()
                if next_entry:
                    notifications.notify_ready_for_check_in(next_entry)

        # Broadcast queue update to all connected users (gracefully fails if Redis unavailable)
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'queue_updates',
                {
                    'type': 'queue_update',
                    'update_type': 'cancelled',
                    'entry_id': queue_entry.id,
                    'user_id': queue_entry.user.id,
                    'machine_id': machine.id if machine else None,
                    'triggering_user_id': request.user.id,
                }
            )
        except Exception as e:
            # WebSocket broadcast failed (Redis likely not running) - continue anyway
            print(f"WebSocket broadcast failed: {e}")

        messages.success(request, 'Queue entry cancelled successfully!')
        # Redirect based on 'next' parameter
        next_page = request.GET.get('next', 'my_queue')
        if next_page == 'public_queue':
            return redirect('public_queue')
        return redirect('my_queue')

    return render(request, 'calendarEditor/cancel_queue.html', {
        'queue_entry': queue_entry,
        'next': request.GET.get('next', 'my_queue')
    })


@login_required
def appeal_queue_entry(request, pk):
    """Submit an appeal for a queued entry (marks as rush job)."""
    # Check if entry exists and belongs to current user
    queue_entry = get_object_or_404(QueueEntry, pk=pk)
    if queue_entry.user != request.user:
        messages.warning(request, 'This queue entry is not for your account.')
        return redirect('home')

    # Only allow appeals for queued entries
    if queue_entry.status != 'queued':
        messages.error(request, 'Can only appeal queued entries.')
        return redirect('queue')

    if request.method == 'POST':
        appeal_explanation = request.POST.get('appeal_explanation', '').strip()

        # Validate explanation (minimum 15 characters)
        if len(appeal_explanation) < 15:
            messages.error(request, 'Appeal explanation must be at least 15 characters.')
            return redirect('queue')

        # Mark entry as rush job and save explanation
        queue_entry.is_rush_job = True
        queue_entry.special_requirements = appeal_explanation
        queue_entry.save()

        # Notify admins about the appeal
        try:
            notifications.notify_admins_rush_job(queue_entry)
        except Exception as e:
            print(f"Rush job appeal notification failed: {e}")

        messages.success(request, f'Appeal submitted successfully for "{queue_entry.title}". Admins have been notified.')
        return redirect('queue')

    # If not POST, redirect to queue
    return redirect('queue')


@require_queue_status('queued', redirect_to='check_in_check_out')
@require_machine_available(redirect_to='check_in_check_out')
@atomic_operation
def check_in_job(request, queue_entry):
    """
    User checks in to start their measurement (ON DECK → RUNNING).

    Requirements (enforced by decorators):
    - User must own the entry (@require_queue_status)
    - Entry status must be 'queued' (@require_queue_status)
    - Entry must have an assigned machine (@require_machine_available)
    - Machine must be available and not in maintenance (@require_machine_available)
    - Machine must not have another running job (@require_machine_available)

    Additional business rule (checked here):
    - Entry must be at position #1 (ON DECK)
    """
    # Additional validation: Must be at position #1
    if queue_entry.queue_position != 1:
        messages.error(request, f'Cannot check in - you are position #{queue_entry.queue_position}. Only ON DECK (position #1) users can check in.')
        return redirect('check_in_check_out')

    # Get machine (already validated by decorator)
    machine = queue_entry.assigned_machine

    # Start the job
    queue_entry.status = 'running'
    queue_entry.started_at = timezone.now()
    queue_entry.queue_position = None  # Remove from queue
    queue_entry.save()

    # Auto-clear queue status notifications (on_deck, ready_for_check_in, admin_check_in)
    auto_clear_notifications(related_queue_entry=queue_entry)

    # Update machine status
    machine.current_status = 'running'
    machine.current_user = request.user
    # Estimated available time = now + job duration + cooldown
    machine.estimated_available_time = timezone.now() + timedelta(
        hours=queue_entry.estimated_duration_hours + machine.cooldown_hours
    )
    machine.save()

    # Reorder queue (shift everyone up)
    # NOTE: reorder_queue() internally calls check_and_notify_on_deck_status()
    from .matching_algorithm import reorder_queue
    reorder_queue(machine)

    # Set checkout reminder due time (replaces Celery scheduled task)
    # Reminder will be sent every 2 hours (except 12 AM - 6 AM) until checkout
    queue_entry.reminder_due_at = queue_entry.started_at + timedelta(hours=queue_entry.estimated_duration_hours)
    queue_entry.last_reminder_sent_at = None
    queue_entry.reminder_snoozed_until = None

    # Clear check-in reminder fields (user has now checked in)
    queue_entry.checkin_reminder_due_at = None
    queue_entry.last_checkin_reminder_sent_at = None
    queue_entry.checkin_reminder_snoozed_until = None

    queue_entry.save(update_fields=['reminder_due_at', 'last_reminder_sent_at', 'reminder_snoozed_until',
                                     'checkin_reminder_due_at', 'last_checkin_reminder_sent_at', 'checkin_reminder_snoozed_until'])

    # Broadcast WebSocket update
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'queue_updates',
            {
                'type': 'queue_update',
                'update_type': 'started',
                'entry_id': queue_entry.id,
                'user_id': queue_entry.user.id,
                'machine_id': machine.id,
                'machine_name': machine.name,
                'triggering_user_id': request.user.id,
            }
        )
    except Exception as e:
        print(f"WebSocket broadcast failed: {e}")

    messages.success(request, f'✅ Checked in! Your measurement on {machine.name} has started. Good luck!')
    return redirect('check_in_check_out')


@require_queue_status('running', redirect_to='check_in_check_out')
@atomic_operation
def check_out_job(request, queue_entry):
    """
    User checks out to complete their measurement (RUNNING → COMPLETED).

    Requirements (enforced by decorators):
    - User must own the entry (@require_queue_status)
    - Entry status must be 'running' (@require_queue_status)
    - Entry exists (@require_queue_status)
    """
    # Validate assigned machine (simple check since we don't need full machine_available validation)
    if not queue_entry.assigned_machine:
        messages.error(request, 'Cannot check out - no machine assigned.')
        return redirect('check_in_check_out')

    # Complete the job
    queue_entry.status = 'completed'
    queue_entry.completed_at = timezone.now()
    queue_entry.save()

    # Auto-clear checkout reminder and admin_checkout notifications
    auto_clear_notifications(related_queue_entry=queue_entry)

    # Always archive completed measurements
    try:
        # Calculate actual duration in hours
        duration_hours = None
        if queue_entry.started_at and queue_entry.completed_at:
            duration_delta = queue_entry.completed_at - queue_entry.started_at
            duration_hours = round(duration_delta.total_seconds() / 3600, 2)

        ArchivedMeasurement.objects.create(
            user=queue_entry.user,
            machine=queue_entry.assigned_machine,
            machine_name=queue_entry.assigned_machine.name if queue_entry.assigned_machine else "Unknown Machine",
            related_queue_entry=queue_entry,
            title=queue_entry.title,
            notes=queue_entry.description,
            measurement_date=queue_entry.completed_at,
            archived_at=timezone.now(),
            status='completed',
            duration_hours=duration_hours
        )
    except Exception as e:
        # Don't fail the checkout if archiving fails
        print(f'Archive creation failed: {str(e)}')

    # Update machine status
    machine = queue_entry.assigned_machine

    # Check if there's someone else in the queue
    next_entry = QueueEntry.objects.filter(
        assigned_machine=machine,
        status='queued',
        queue_position=1
    ).first()

    # Check if machine is unavailable (marked by admin)
    if not machine.is_available:
        # Machine is unavailable - set to maintenance
        machine.current_status = 'maintenance'
        machine.estimated_available_time = None
    elif next_entry:
        # Machine status becomes idle, but may have cooldown time
        machine.current_status = 'idle'
        if machine.cooldown_hours > 0:
            machine.estimated_available_time = timezone.now() + timedelta(hours=machine.cooldown_hours)
        else:
            machine.estimated_available_time = None
    else:
        # Queue is empty, machine becomes idle
        machine.current_status = 'idle'
        machine.estimated_available_time = None

    machine.current_user = None
    machine.save()

    # print(f"[USER CHECKOUT] Completed checkout for {queue_entry.title} on {machine.name}")
    # print(f"[USER CHECKOUT] Machine status after checkout: {machine.current_status}, is_available: {machine.is_available}")

    # DIRECTLY notify the next person in line - bypass all complex logic
    # Only notify if machine is available (not in maintenance)
    if next_entry and machine.is_available:
        # print(f"[USER CHECKOUT] DIRECTLY creating notification for {next_entry.user.username}")
        try:
            from .models import Notification
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            # Create notification directly in database
            notif = Notification.objects.create(
                recipient=next_entry.user,
                notification_type='ready_for_check_in',
                title='Ready for Check-In!',
                message=f'The machine {machine.name} is now available! You can check in to start your measurement "{next_entry.title}".',
                related_queue_entry=next_entry,
                related_machine=machine,
            )
            # print(f"[USER CHECKOUT] Created notification {notif.id} in database")

            # Send via WebSocket immediately
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f'user_{next_entry.user.id}_notifications',
                    {
                        'type': 'notification',
                        'notification_id': notif.id,
                        'notification_type': 'ready_for_check_in',
                        'title': notif.title,
                        'message': notif.message,
                        'created_at': notif.created_at.isoformat(),
                    }
                )
                # print(f"[USER CHECKOUT] WebSocket sent for notification {notif.id}")
            except Exception as ws_err:
                # print(f"[USER CHECKOUT] WebSocket failed but notification {notif.id} still in DB: {ws_err}")
                pass

            # Send via Slack if enabled (don't wait for it)
            if settings.SLACK_ENABLED:
                try:
                    notifications.send_slack_dm(next_entry.user, notif.title, notif.message, notif)
                    # print(f"[USER CHECKOUT] Slack sent for notification {notif.id}")
                except Exception as slack_err:
                    # print(f"[USER CHECKOUT] Slack failed but notification {notif.id} still in DB: {slack_err}")
                    pass

        except Exception as e:
            print(f"[USER CHECKOUT] ERROR creating notification: {e}")
            import traceback
            traceback.print_exc()

    # No need to cancel reminder - middleware checks status automatically
    # (Reminder won't send because entry status changed from 'running' to 'completed')

    # Reorder queue (skip notifications since we already sent them)
    # print(f"[USER CHECKOUT] Calling reorder_queue for {machine.name}")
    from .matching_algorithm import reorder_queue
    reorder_queue(machine, notify=False)

    # Broadcast WebSocket update
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'queue_updates',
            {
                'type': 'queue_update',
                'update_type': 'completed',
                'entry_id': queue_entry.id,
                'user_id': queue_entry.user.id,
                'machine_id': machine.id,
                'machine_name': machine.name,
                'triggering_user_id': request.user.id,
            }
        )
    except Exception as e:
        print(f"WebSocket broadcast failed: {e}")

    messages.success(request, f'🎉 Checked out! Your measurement on {machine.name} is complete and archived.')
    return redirect('check_in_check_out')


@login_required
def snooze_checkout_reminder(request, entry_id):
    """
    Snooze checkout reminder for 6 hours.

    This is triggered when a user clicks the notification link.
    It silences reminders for 6 hours, after which they resume at 2-hour intervals.

    Requirements:
    - User must own the entry
    - Entry must be running
    """
    # Check if entry exists and belongs to current user
    queue_entry = get_object_or_404(QueueEntry, id=entry_id)
    if queue_entry.user != request.user:
        messages.warning(request, 'This notification is not for your account. Returning to home page.')
        return redirect('home')

    # Only allow snoozing for running entries
    if queue_entry.status != 'running':
        messages.info(request, 'This measurement is no longer running.')
        return redirect('check_in_check_out')

    # Set snooze time to 48 hours from now
    queue_entry.reminder_snoozed_until = timezone.now() + timedelta(hours=48)
    queue_entry.save(update_fields=['reminder_snoozed_until'])

    # NOTE: Do NOT auto-clear notifications here - only clear when user actually checks out
    messages.success(request, f'✅ Checkout reminder snoozed for 48 hours. You can continue your measurement on {queue_entry.assigned_machine.name}.')
    return redirect('check_in_check_out')


@login_required
def snooze_checkin_reminder(request, entry_id):
    """
    Snooze check-in reminder for 24 hours.

    This is triggered when a user clicks the "did you forget to check in" notification link.
    It silences reminders for 24 hours, after which they resume at 6-hour intervals.

    Requirements:
    - User must own the entry
    - Entry must be queued at position 1 (ON DECK)
    """
    # Check if entry exists and belongs to current user
    queue_entry = get_object_or_404(QueueEntry, id=entry_id)
    if queue_entry.user != request.user:
        messages.warning(request, 'This notification is not for your account. Returning to home page.')
        return redirect('home')

    # Only allow snoozing for position 1 queued entries
    if queue_entry.status != 'queued' or queue_entry.queue_position != 1:
        messages.info(request, 'This entry is no longer at position 1 or ready for check-in.')
        return redirect('check_in_check_out')

    # Set snooze time to 48 hours from now
    queue_entry.checkin_reminder_snoozed_until = timezone.now() + timedelta(hours=48)
    queue_entry.save(update_fields=['checkin_reminder_snoozed_until'])

    # NOTE: Do NOT auto-clear notifications here - only clear when user actually checks in
    messages.success(request, f'✅ Check-in reminder snoozed for 48 hours for "{queue_entry.title}" on {queue_entry.assigned_machine.name}.')
    return redirect('check_in_check_out')


@require_queue_status('running', redirect_to='check_in_check_out')
@atomic_operation
def undo_check_in(request, queue_entry):
    """
    Undo a check-in to move running entry back to on-deck position (RUNNING → QUEUED at position 1).

    This moves the running entry back to position 1 and bumps all other queued entries down by 1.
    Sets the machine back to idle status.

    Requirements (enforced by decorators):
    - User must own the entry (@require_queue_status)
    - Entry status must be 'running' (@require_queue_status)
    - Entry exists (@require_queue_status)
    """
    # Validate assigned machine
    if not queue_entry.assigned_machine:
        messages.error(request, 'Cannot undo check-in - no machine assigned.')
        return redirect('check_in_check_out')

    machine = queue_entry.assigned_machine

    # Refresh machine from database to get latest state
    machine.refresh_from_db()

    # Check if machine is in maintenance mode (business rule for undo specifically)
    if machine.current_status == 'maintenance':
        messages.error(request, f'Cannot undo check-in - {machine.name} is under maintenance. Please contact an administrator.')
        return redirect('check_in_check_out')

    # Find the entry that was at position 1 (will be bumped to position 2)
    existing_queued = QueueEntry.objects.filter(
        assigned_machine=machine,
        status='queued'
    ).order_by('queue_position')

    was_on_deck = existing_queued.filter(queue_position=1).first()

    # Bump all existing queued entries down by 1 position
    # Update in REVERSE order to avoid UNIQUE constraint violations
    existing_queued_list = list(existing_queued)
    for entry in reversed(existing_queued_list):
        entry.queue_position += 1
        entry.save(update_fields=['queue_position'])

    # Move this entry back to queued status at position 1
    queue_entry.status = 'queued'
    queue_entry.queue_position = 1
    queue_entry.started_at = None
    # Clear checkout reminder fields
    queue_entry.reminder_due_at = None
    queue_entry.last_reminder_sent_at = None
    queue_entry.reminder_snoozed_until = None
    queue_entry.save()

    # Refresh machine again to ensure we're working with latest data
    machine.refresh_from_db()

    # Update machine status to idle
    machine.current_status = 'idle'
    machine.current_user = None
    machine.estimated_available_time = None
    machine.save()

    # Final refresh to ensure all updates are committed
    machine.refresh_from_db()
    queue_entry.refresh_from_db()

    # Auto-clear any running-related notifications
    auto_clear_notifications(related_queue_entry=queue_entry)

    # Clear check-in reminders for the entry that was bumped from position 1
    from .notifications import notify_bumped_from_on_deck, notify_queue_position_change, check_and_notify_on_deck_status
    if was_on_deck:
        was_on_deck.refresh_from_db()  # Refresh to get updated queue_position
        # Clear check-in reminders (no longer at position 1)
        was_on_deck.checkin_reminder_due_at = None
        was_on_deck.last_checkin_reminder_sent_at = None
        was_on_deck.checkin_reminder_snoozed_until = None
        was_on_deck.save(update_fields=['checkin_reminder_due_at', 'last_checkin_reminder_sent_at', 'checkin_reminder_snoozed_until'])
        notify_bumped_from_on_deck(was_on_deck, reason='measurement undone')

    # Initialize check-in reminders for the entry now at position 1
    check_and_notify_on_deck_status(machine)

    # Notify other users who were pushed back in the queue (if they have the preference enabled)
    for entry in existing_queued:
        if was_on_deck is None or entry.id != was_on_deck.id:  # Skip the one already notified above
            entry.refresh_from_db()
            old_position = entry.queue_position - 1  # They were at position-1 before the bump
            notify_queue_position_change(entry, old_position, entry.queue_position)

    # DO NOT notify the user who undid their own check-in (they already know)

    # Broadcast WebSocket update
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'queue_updates',
            {
                'type': 'queue_update',
                'update_type': 'undo_checkin',
                'entry_id': queue_entry.id,
                'user_id': queue_entry.user.id,
                'machine_id': machine.id,
                'machine_name': machine.name,
                'triggering_user_id': request.user.id,
            }
        )
    except Exception as e:
        print(f"WebSocket broadcast failed: {e}")

    messages.success(request, f'Check-in undone! Your measurement on {machine.name} has been moved back to position #1 (on deck).')
    return redirect('check_in_check_out')


@login_required
def check_in_check_out(request):
    """
    Combined check-in/check-out page.
    Shows:
    - ON DECK entries (position #1, queued) split into Ready / Waiting
    - RUNNING entries split into Ready to Check Out / Currently Running
    """

    # ---------------- On Deck ----------------
    on_deck_qs = QueueEntry.objects.filter(
        user=request.user,
        status='queued',
        queue_position=1
    ).select_related('assigned_machine').order_by('assigned_machine__name')
    on_deck_list = list(on_deck_qs)

    ready_to_check_in = [
        e for e in on_deck_list
        if e.assigned_machine and e.assigned_machine.current_status == 'idle'
    ]
    waiting_entries = [
        e for e in on_deck_list
        if e.assigned_machine and e.assigned_machine.current_status != 'idle'
    ]

    # ---------------- Running ----------------
    running_qs = QueueEntry.objects.filter(
        user=request.user,
        status='running'
    ).select_related('assigned_machine').order_by('assigned_machine__name')

    ready_to_check_out = []
    currently_running = []

    now = timezone.now()
    for entry in running_qs:
        if entry.started_at and entry.estimated_duration_hours:
            end_time = entry.started_at + timedelta(hours=entry.estimated_duration_hours)
            if now >= end_time:
                ready_to_check_out.append(entry)
            else:
                currently_running.append(entry)
        else:
            # fallback: treat as currently running
            currently_running.append(entry)

    context = {
        'ready_to_check_in': ready_to_check_in,
        'waiting_entries': waiting_entries,
        'ready_to_check_out': ready_to_check_out,
        'currently_running': currently_running,
    }

    return render(request, 'calendarEditor/check_in_check_out.html', context)


# ====================
# LEGACY VIEWS (Scheduled for removal - Old ScheduleEntry system)
# ====================
# These views use the old ScheduleEntry model which has been replaced
# by the QueueEntry system. Kept temporarily for backwards compatibility.
# TODO: Remove in v2.0 after data migration

@login_required
def schedule_list(request):
    """LEGACY: Schedule list view - uses old ScheduleEntry model."""
    upcoming_entries = ScheduleEntry.objects.filter(
        user=request.user,
        start_datetime__gte=timezone.now()
    ).order_by('start_datetime')

    past_entries = ScheduleEntry.objects.filter(
        user=request.user,
        start_datetime__lt=timezone.now()
    ).order_by('-start_datetime')[:10]

    context = {
        'upcoming_entries': upcoming_entries,
        'past_entries': past_entries,
    }

    return render(request, 'legacy_archive/schedule_list.html', context)


@login_required
def create_schedule(request):
    """LEGACY: Create schedule entry - uses old ScheduleEntry model."""
    if request.method == 'POST':
        form = ScheduleEntryForm(request.POST)
        if form.is_valid():
            schedule_entry = form.save(commit=False)
            schedule_entry.user = request.user
            schedule_entry.save()
            messages.success(request, 'Schedule entry created successfully!')
            return redirect('schedule')
    else:
        form = ScheduleEntryForm()

    return render(request, 'legacy_archive/create_schedule.html', {'form': form})


@login_required
def edit_schedule(request, pk):
    """LEGACY: Edit schedule entry - uses old ScheduleEntry model."""
    schedule_entry = get_object_or_404(ScheduleEntry, pk=pk, user=request.user)

    if request.method == 'POST':
        form = ScheduleEntryForm(request.POST, instance=schedule_entry)
        if form.is_valid():
            form.save()
            messages.success(request, 'Schedule entry updated successfully!')
            return redirect('schedule')
    else:
        form = ScheduleEntryForm(instance=schedule_entry)

    return render(request, 'legacy_archive/edit_schedule.html', {
        'form': form,
        'schedule_entry': schedule_entry
    })


@login_required
def delete_schedule(request, pk):
    """LEGACY: Delete schedule entry - uses old ScheduleEntry model."""
    schedule_entry = get_object_or_404(ScheduleEntry, pk=pk, user=request.user)

    if request.method == 'POST':
        schedule_entry.delete()
        messages.success(request, 'Schedule entry deleted successfully!')
        return redirect('schedule')

    return render(request, 'legacy_archive/delete_schedule.html', {
        'schedule_entry': schedule_entry
    })


# ===== Queue Appeal Management =====

def send_rush_job_notification(queue_entry, request):
    """
    Send email and in-app notification to all admin users about a queue appeal submission.

    Args:
        queue_entry: QueueEntry instance with is_rush_job=True
        request: HTTP request object to build absolute URLs
    """
    # Send in-app notifications to admins
    notifications.notify_admins_rush_job(queue_entry)

    # Get all staff users (admins)
    admin_emails = User.objects.filter(is_staff=True).values_list('email', flat=True)
    admin_emails = [email for email in admin_emails if email]  # Filter out empty emails

    if not admin_emails:
        return  # No admin emails to send to

    # Build email content
    subject = f'Queue Appeal: {queue_entry.title} by {queue_entry.user.username}'

    rush_job_url = request.build_absolute_uri(reverse('admin_rush_jobs'))

    message = f"""
A queue appeal has been submitted and requires your review.

User: {queue_entry.user.username} ({queue_entry.user.email})
Device Name: {queue_entry.title}
Measurement Description: {queue_entry.description}

Requirements:
- Temperature: {queue_entry.required_min_temp}K - {queue_entry.required_max_temp or 'N/A'}K
- B-field: X={queue_entry.required_b_field_x}T, Y={queue_entry.required_b_field_y}T, Z={queue_entry.required_b_field_z}T
- Direction: {queue_entry.get_required_b_field_direction_display()}
- DC Lines: {queue_entry.required_dc_lines}
- RF Lines: {queue_entry.required_rf_lines}
- Daughterboard: {queue_entry.required_daughterboard or 'Any'}
- Optical: {'Yes' if queue_entry.requires_optical else 'No'}

Assigned Machine: {queue_entry.assigned_machine.name if queue_entry.assigned_machine else 'None'}
Queue Position: {queue_entry.queue_position}
Estimated Start: {queue_entry.estimated_start_time.strftime('%Y-%m-%d %H:%M') if queue_entry.estimated_start_time else 'N/A'}

Appeal Justification: {queue_entry.special_requirements or 'None'}

To review and manage queue appeals, visit:
{rush_job_url}

Submitted: {queue_entry.rush_job_submitted_at.strftime('%Y-%m-%d %H:%M')}
"""

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            admin_emails,
            fail_silently=True,
        )
    except Exception as e:
        # Log error but don't fail the request
        print(f"Error sending rush job notification: {e}")


def is_staff(user):
    """Check if user is staff/admin."""
    return user.is_staff


# ====================
# LEGACY ADMIN VIEWS (Duplicated by admin_views.py)
# ====================
# These views have been superseded by newer implementations in admin_views.py
# Kept temporarily for backwards compatibility with old URL routes.
# TODO: Remove in v2.0 after confirming no external links use these routes

@user_passes_test(is_staff)
def admin_rush_jobs(request):
    """
    LEGACY: Admin view to manage rush job requests.
    Shows all rush job requests grouped by machine.
    Superseded by admin_views.admin_rush_jobs()
    """
    # Get all rush job entries that are still queued
    rush_entries = QueueEntry.objects.filter(
        is_rush_job=True,
        status='queued'
    ).select_related('assigned_machine', 'user').order_by('assigned_machine', 'queue_position')

    # Group by machine
    machines_with_rush_jobs = {}
    for entry in rush_entries:
        machine = entry.assigned_machine
        if machine not in machines_with_rush_jobs:
            machines_with_rush_jobs[machine] = {
                'machine': machine,
                'rush_entries': [],
                'all_queued_entries': []
            }
        machines_with_rush_jobs[machine]['rush_entries'].append(entry)

    # Get all queued entries for each machine (to show context)
    for machine_data in machines_with_rush_jobs.values():
        machine = machine_data['machine']
        machine_data['all_queued_entries'] = QueueEntry.objects.filter(
            assigned_machine=machine,
            status='queued'
        ).select_related('user').order_by('queue_position')

    return render(request, 'calendarEditor/legacy/admin_rush_jobs.html', {
        'machines_with_rush_jobs': machines_with_rush_jobs.values(),
        'total_rush_jobs': rush_entries.count(),
    })


@user_passes_test(is_staff)
def admin_move_queue_entry(request, entry_id, direction):
    """
    LEGACY: Move a queue entry up or down in the queue.
    Superseded by admin_views.move_queue_up() and admin_views.move_queue_down()

    Args:
        entry_id: ID of the QueueEntry to move
        direction: 'up' or 'down'
    """
    if direction == 'up':
        success = move_queue_entry_up(entry_id)
    elif direction == 'down':
        success = move_queue_entry_down(entry_id)
    else:
        messages.error(request, 'Invalid direction.')
        return redirect('admin_rush_jobs')

    if success:
        # Broadcast queue update to all connected users (gracefully fails if Redis unavailable)
        try:
            entry = QueueEntry.objects.get(id=entry_id)
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    'queue_updates',
                    {
                        'type': 'queue_update',
                        'update_type': 'moved',
                        'entry_id': entry.id,
                        'user_id': entry.user.id,
                        'machine_id': entry.assigned_machine.id if entry.assigned_machine else None,
                        'triggering_user_id': request.user.id,
                    }
                )
            except Exception as e:
                # WebSocket broadcast failed (Redis likely not running) - continue anyway
                print(f"WebSocket broadcast failed: {e}")
        except QueueEntry.DoesNotExist:
            pass

        messages.success(request, f'Queue entry moved {direction} successfully.')
    else:
        messages.error(request, f'Could not move entry {direction}. It may already be at the {direction} position.')

    return redirect('admin_rush_jobs')


@user_passes_test(is_staff)
def admin_set_queue_position(request, entry_id):
    """
    LEGACY: Set a queue entry to a specific position.
    Superseded by admin_views queue management functions

    Args:
        entry_id: ID of the QueueEntry to reposition
    """
    if request.method == 'POST':
        new_position = request.POST.get('new_position')
        try:
            new_position = int(new_position)
            if set_queue_position(entry_id, new_position):
                # Broadcast queue update to all connected users (gracefully fails if Redis unavailable)
                try:
                    entry = QueueEntry.objects.get(id=entry_id)
                    try:
                        channel_layer = get_channel_layer()
                        async_to_sync(channel_layer.group_send)(
                            'queue_updates',
                            {
                                'type': 'queue_update',
                                'update_type': 'moved',
                                'entry_id': entry.id,
                                'user_id': entry.user.id,
                                'machine_id': entry.assigned_machine.id if entry.assigned_machine else None,
                                'triggering_user_id': request.user.id,
                            }
                        )
                    except Exception as e:
                        # WebSocket broadcast failed (Redis likely not running) - continue anyway
                        print(f"WebSocket broadcast failed: {e}")
                except QueueEntry.DoesNotExist:
                    pass

                messages.success(request, f'Queue entry moved to position {new_position}.')
            else:
                messages.error(request, 'Could not set queue position. Invalid position or entry not found.')
        except (ValueError, TypeError):
            messages.error(request, 'Invalid position number.')

    return redirect('admin_rush_jobs')


# ====================
# Preset Management Views
# ====================

@login_required
def load_preset_ajax(request, preset_id):
    """AJAX endpoint to load preset data for form auto-population."""
    try:
        preset = get_object_or_404(QueuePreset, id=preset_id)

        # Check permissions: users can load their own presets or any public preset
        is_owner = (preset.creator and preset.creator == request.user) or (preset.creator_username == request.user.username)
        if not preset.is_public and not is_owner:
            return JsonResponse({'error': 'Permission denied'}, status=403)

        # Check if user is following this preset
        prefs = NotificationPreference.get_or_create_for_user(request.user)
        is_following = preset.is_public and prefs.followed_presets.filter(id=preset.id).exists()

        # Return preset data as JSON
        data = {
            'title': preset.title,
            'description': preset.description,
            'required_min_temp': preset.required_min_temp,
            'required_max_temp': preset.required_max_temp,
            'required_b_field_x': preset.required_b_field_x,
            'required_b_field_y': preset.required_b_field_y,
            'required_b_field_z': preset.required_b_field_z,
            'required_b_field_direction': preset.required_b_field_direction,
            'required_dc_lines': preset.required_dc_lines,
            'required_rf_lines': preset.required_rf_lines,
            'required_daughterboard': preset.required_daughterboard,
            'requires_optical': preset.requires_optical,
            'estimated_duration_hours': preset.estimated_duration_hours,
            'can_edit': preset.can_edit(request.user),
            'preset_id': preset.id,
            'is_public': preset.is_public,
            'is_following': is_following,
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def get_editable_presets_ajax(request):
    """AJAX endpoint to get list of presets the user can edit."""
    # User's own presets (private or public)
    own_presets = QueuePreset.objects.filter(creator=request.user)

    # If admin, include public presets by others
    if request.user.is_staff:
        other_public = QueuePreset.objects.filter(is_public=True).exclude(creator=request.user)
        editable_presets = own_presets | other_public
    else:
        editable_presets = own_presets

    # Order: private first, then by creator username, then preset name (case-insensitive)
    editable_presets = editable_presets.order_by('is_public', F('creator_username').asc(), F('name').asc())

    presets_data = [
        {
            'id': preset.id,
            'display_name': preset.display_name,
            'is_public': preset.is_public,
            'creator_username': preset.creator_username,
        }
        for preset in editable_presets
    ]

    return JsonResponse({'presets': presets_data})


@login_required
def get_viewable_presets_ajax(request):
    """AJAX endpoint to get list of ALL presets the user can view (for dropdown)."""

    # Single QuerySet for everything the user can see
    all_presets = QueuePreset.objects.select_related('creator').filter(
        Q(is_public=True) | Q(creator=request.user)
    ).order_by('creator__username', 'name')  # Order by creator first, then preset name

    presets_data = [
        {
            'id': p.id,
            'display_name': f"{p.display_name} ({'Private' if not p.is_public else 'Public'})",
            'creator_username': p.creator.username if p.creator else 'Unknown',
            'is_public': p.is_public,
        } for p in all_presets
    ]

    return JsonResponse({'presets': presets_data})


@login_required
def delete_preset(request, preset_id):
    """Delete a preset (only creator and admins for public presets)."""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('submit_queue')

    preset = get_object_or_404(QueuePreset, id=preset_id)

    # Check permissions
    if not preset.can_edit(request.user):
        messages.error(request, 'You do not have permission to delete this preset.')
        return redirect('submit_queue')

    preset_name = preset.display_name
    preset_id = preset.id
    preset_is_public = preset.is_public
    preset_creator_id = preset.creator.id if preset.creator else None

    # Capture follower user IDs before deletion (for notifications)
    follower_ids = list(preset.followers.values_list('user_id', flat=True)) if preset.is_public else []

    # Auto-clear all notifications related to this preset (before deletion)
    auto_clear_notifications(related_preset=preset)

    # Delete the preset
    preset.delete()

    # Broadcast preset update to all connected users (gracefully fails if Redis unavailable)
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'queue_updates',
            {
                'type': 'preset_update',
                'update_type': 'deleted',
                'preset_id': preset_id,
                'triggering_user_id': request.user.id,
            }
        )
    except Exception as e:
        # WebSocket broadcast failed (Redis likely not running) - continue anyway
        print(f"WebSocket broadcast failed: {e}")

    # Send notifications for preset deletion
    try:
        preset_data = {
            'display_name': preset_name,
            'is_public': preset_is_public,
            'creator_id': preset_creator_id,
            'follower_ids': follower_ids,
        }
        notifications.notify_preset_deleted(preset_data, request.user)
    except Exception as e:
        print(f"Notification generation failed: {e}")

    messages.success(request, f'Preset "{preset_name}" deleted successfully.')

    # Redirect to admin-presets if coming from admin page
    referer = request.META.get('HTTP_REFERER', '')
    if request.user.is_staff and 'admin-presets' in referer:
        return redirect('admin_presets')
    return redirect('submit_queue')


@login_required
def follow_preset(request, preset_id):
    """Follow a preset to receive notifications when it's edited or deleted."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    preset = get_object_or_404(QueuePreset, id=preset_id)

    # Only public presets can be followed
    if not preset.is_public:
        return JsonResponse({'error': 'Only public presets can be followed'}, status=400)

    # Get or create notification preferences
    prefs = NotificationPreference.get_or_create_for_user(request.user)

    # Add preset to followed list
    prefs.followed_presets.add(preset)

    # Auto-enable followed preset notifications if not already enabled
    if not prefs.notify_followed_preset_edited or not prefs.notify_followed_preset_deleted:
        prefs.notify_followed_preset_edited = True
        prefs.notify_followed_preset_deleted = True
        prefs.save()

    # Add Django message for display after page reload
    messages.success(request, f'You are now following "{preset.display_name}" and will receive notifications about changes to it.')

    return JsonResponse({
        'followed': True,
        'message': f'Now following "{preset.display_name}". You\'ll be notified of changes.'
    })


@login_required
def unfollow_preset(request, preset_id):
    """Unfollow a preset to stop receiving notifications."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    preset = get_object_or_404(QueuePreset, id=preset_id)

    # Get notification preferences
    prefs = NotificationPreference.get_or_create_for_user(request.user)

    # Remove preset from followed list
    prefs.followed_presets.remove(preset)

    # If user is no longer following any presets, turn off followed preset notifications
    if prefs.followed_presets.count() == 0:
        prefs.notify_followed_preset_edited = False
        prefs.notify_followed_preset_deleted = False
        prefs.save()

    # Add Django message for display after page reload
    messages.success(request, f'You have unfollowed "{preset.display_name}" and will no longer receive notifications about it.')

    return JsonResponse({
        'followed': False,
        'message': f'Unfollowed "{preset.display_name}".'
    })


@login_required
def create_preset(request):
    """Create a new preset."""
    if request.method == 'POST':
        form = QueuePresetForm(request.POST)
        if form.is_valid():
            preset = form.save(commit=False)
            preset.creator = request.user
            preset.last_edited_by = request.user
            preset.save()

            # Auto-follow own preset (for both public and private presets)
            prefs = NotificationPreference.get_or_create_for_user(request.user)
            if preset.is_public:
                prefs.followed_presets.add(preset)
                # Enable follow notifications if not already enabled
                if not prefs.notify_followed_preset_edited or not prefs.notify_followed_preset_deleted:
                    prefs.notify_followed_preset_edited = True
                    prefs.notify_followed_preset_deleted = True
                    prefs.save()

            # Broadcast preset update to all connected users (gracefully fails if Redis unavailable)
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    'queue_updates',
                    {
                        'type': 'preset_update',
                        'update_type': 'created',
                        'preset_id': preset.id,
                        'preset_data': {
                            'id': preset.id,
                            'display_name': preset.display_name,
                            'is_public': preset.is_public,
                        },
                        'triggering_user_id': request.user.id,
                    }
                )
            except Exception as e:
                # WebSocket broadcast failed (Redis likely not running) - continue anyway
                print(f"WebSocket broadcast failed: {e}")

            # Send notifications for preset creation
            try:
                notifications.notify_preset_created(preset, request.user)
            except Exception as e:
                print(f"Notification generation failed: {e}")

            visibility = 'public' if preset.is_public else 'private'
            messages.success(request, f'Preset "{preset.display_name}" created successfully as {visibility}!')
            return redirect(f"{reverse('submit_queue')}?selected_preset={preset.id}")
    else:
        form = QueuePresetForm()

    return render(request, 'calendarEditor/preset_form.html', {
        'form': form,
        'mode': 'create',
        'page_title': 'Create New Preset'
    })


@login_required
def edit_preset_view(request, preset_id):
    """Edit an existing preset."""
    preset = get_object_or_404(QueuePreset, id=preset_id)

    # Check permissions
    if not preset.can_edit(request.user):
        messages.error(request, 'You do not have permission to edit this preset.')
        return redirect('submit_queue')

    if request.method == 'POST':
        form = QueuePresetForm(request.POST, instance=preset)
        if form.is_valid():
            # Capture original values before saving
            original_preset = QueuePreset.objects.get(id=preset.id)

            # Detect field changes
            changed_fields = []
            field_mapping = {
                'name': 'Preset Name',
                'title': 'Device Name',
                'description': 'Description',
                'required_min_temp': 'Min Temperature',
                'required_max_temp': 'Max Temperature',
                'required_b_field_x': 'B-field X',
                'required_b_field_y': 'B-field Y',
                'required_b_field_z': 'B-field Z',
                'required_b_field_direction': 'B-field Direction',
                'required_dc_lines': 'DC Lines',
                'required_rf_lines': 'RF Lines',
                'required_daughterboard': 'Daughterboard',
                'requires_optical': 'Optical',
                'is_public': 'Visibility',
                'estimated_duration_hours': 'Duration',
            }

            for field_name, label in field_mapping.items():
                old_value = getattr(original_preset, field_name)
                new_value = form.cleaned_data.get(field_name)

                if old_value != new_value:
                    # Format the change description
                    if field_name == 'is_public':
                        old_str = 'Public' if old_value else 'Private'
                        new_str = 'Public' if new_value else 'Private'
                        changed_fields.append(f"{label}: {old_str} → {new_str}")
                    elif field_name == 'requires_optical':
                        old_str = 'Yes' if old_value else 'No'
                        new_str = 'Yes' if new_value else 'No'
                        changed_fields.append(f"{label}: {old_str} → {new_str}")
                    elif field_name in ['required_min_temp', 'required_max_temp']:
                        old_str = f"{old_value}K" if old_value is not None else "None"
                        new_str = f"{new_value}K" if new_value is not None else "None"
                        changed_fields.append(f"{label}: {old_str} → {new_str}")
                    elif field_name in ['required_b_field_x', 'required_b_field_y', 'required_b_field_z']:
                        old_str = f"{old_value}T" if old_value is not None else "0T"
                        new_str = f"{new_value}T" if new_value is not None else "0T"
                        changed_fields.append(f"{label}: {old_str} → {new_str}")
                    elif field_name == 'estimated_duration_hours':
                        old_str = f"{old_value}h" if old_value is not None else "None"
                        new_str = f"{new_value}h" if new_value is not None else "None"
                        changed_fields.append(f"{label}: {old_str} → {new_str}")
                    else:
                        old_str = str(old_value) if old_value else "None"
                        new_str = str(new_value) if new_value else "None"
                        # Truncate long values
                        if len(old_str) > 30:
                            old_str = old_str[:27] + "..."
                        if len(new_str) > 30:
                            new_str = new_str[:27] + "..."
                        changed_fields.append(f"{label}: {old_str} → {new_str}")

            # Create change summary (truncate if too long)
            if changed_fields:
                change_summary = "; ".join(changed_fields)
                if len(change_summary) > 200:
                    # Show only first few changes if too many
                    change_summary = "; ".join(changed_fields[:3]) + f" (and {len(changed_fields) - 3} more)"
            else:
                change_summary = None

            preset = form.save(commit=False)
            preset.last_edited_by = request.user
            preset.save()

            # Broadcast preset update to all connected users (gracefully fails if Redis unavailable)
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    'queue_updates',
                    {
                        'type': 'preset_update',
                        'update_type': 'edited',
                        'preset_id': preset.id,
                        'preset_data': {
                            'id': preset.id,
                            'display_name': preset.display_name,
                            'is_public': preset.is_public,
                        },
                        'triggering_user_id': request.user.id,
                    }
                )
            except Exception as e:
                # WebSocket broadcast failed (Redis likely not running) - continue anyway
                print(f"WebSocket broadcast failed: {e}")

            # Send notifications for preset edit with change summary
            try:
                notifications.notify_preset_edited(preset, request.user, changes=change_summary)
            except Exception as e:
                print(f"Notification generation failed: {e}")

            messages.success(request, f'Preset "{preset.display_name}" updated successfully!')

            # Redirect back to admin-presets if launched from there, otherwise submit_queue
            from_admin = request.GET.get('from_admin', 'false')
            if from_admin == 'true':
                return redirect('admin_presets')
            else:
                # Redirect back to submit_queue with that preset selected
                return redirect(f"{reverse('submit_queue')}?selected_preset={preset.id}")

    else:
        form = QueuePresetForm(instance=preset)

    # Pass from_admin parameter to template for Cancel button routing
    from_admin = request.GET.get('from_admin', 'false')
    return render(request, 'calendarEditor/preset_form.html', {
        'form': form,
        'mode': 'edit',
        'preset': preset,
        'page_title': f'Edit Preset: {preset.name}',
        'from_admin': from_admin
    })

@login_required
def view_preset(request, preset_id):
    """View a preset in read-only mode."""
    preset = get_object_or_404(QueuePreset, id=preset_id)

    # Check permissions
    if not preset.can_view(request.user):
        messages.error(request, 'You do not have permission to view this preset.')
        return redirect('submit_queue')

    # Create a form instance but we'll make it read-only in the template
    form = QueuePresetForm(instance=preset)

    # Pass from_admin parameter to template for Cancel button routing
    from_admin = request.GET.get('from_admin', 'false')
    return render(request, 'calendarEditor/preset_form.html', {
        'form': form,
        'mode': 'view',
        'preset': preset,
        'page_title': f'View Preset: {preset.name}',
        'from_admin': from_admin
    })

@login_required
def copy_preset(request, preset_id):
    """Copy an existing preset as a new preset."""
    source_preset = get_object_or_404(QueuePreset, id=preset_id)

    # Check if user can view this preset (public OR their own)
    is_owner = (source_preset.creator and source_preset.creator == request.user) or (source_preset.creator_username == request.user.username)
    if not source_preset.is_public and not is_owner:
        messages.error(request, 'You do not have permission to view this preset.')
        return redirect('submit_queue')

    if request.method == 'POST':
        # Handle form submission to create the copy
        form = QueuePresetForm(request.POST)
        if form.is_valid():
            preset = form.save(commit=False)
            preset.creator = request.user
            preset.last_edited_by = request.user
            preset.save()

            # Auto-follow own preset (for both public and private presets)
            prefs = NotificationPreference.get_or_create_for_user(request.user)
            if preset.is_public:
                prefs.followed_presets.add(preset)
                # Enable follow notifications if not already enabled
                if not prefs.notify_followed_preset_edited or not prefs.notify_followed_preset_deleted:
                    prefs.notify_followed_preset_edited = True
                    prefs.notify_followed_preset_deleted = True
                    prefs.save()

            # Broadcast preset update to all connected users (gracefully fails if Redis unavailable)
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    'queue_updates',
                    {
                        'type': 'preset_update',
                        'update_type': 'created',
                        'preset_id': preset.id,
                        'preset_data': {
                            'id': preset.id,
                            'display_name': preset.display_name,
                            'is_public': preset.is_public,
                        },
                        'triggering_user_id': request.user.id,
                    }
                )
            except Exception as e:
                # WebSocket broadcast failed (Redis likely not running) - continue anyway
                print(f"WebSocket broadcast failed: {e}")

            visibility = 'public' if preset.is_public else 'private'
            messages.success(
                request,
                f'Preset "{preset.display_name}" created successfully as {visibility}!'
            )

            # ✅ Redirect back to submit_queue with this new preset preselected
            return redirect(f"{reverse('submit_queue')}?selected_preset={preset.id}")

    else:
        # Pre-fill form with source preset data
        # Truncate name if needed (max 75 chars, " - copy" is 7 chars)
        max_name_length = 75
        suffix = ' - copy'
        available_chars = max_name_length - len(suffix)
        truncated_name = source_preset.name[:available_chars] if len(source_preset.name) > available_chars else source_preset.name

        initial_data = {
            'name': f'{truncated_name}{suffix}',
            'is_public': False,  # Default to private
            'title': source_preset.title,
            'description': source_preset.description,
            'required_min_temp': source_preset.required_min_temp,
            'required_max_temp': source_preset.required_max_temp,
            'required_b_field_x': source_preset.required_b_field_x,
            'required_b_field_y': source_preset.required_b_field_y,
            'required_b_field_z': source_preset.required_b_field_z,
            'required_b_field_direction': source_preset.required_b_field_direction,
            'required_dc_lines': source_preset.required_dc_lines,
            'required_rf_lines': source_preset.required_rf_lines,
            'required_daughterboard': source_preset.required_daughterboard,
            'requires_optical': source_preset.requires_optical,
        }
        form = QueuePresetForm(initial=initial_data)

    return render(request, 'calendarEditor/preset_form.html', {
        'form': form,
        'mode': 'create',
        'page_title': f'Copy Preset: {source_preset.name}'
    })


# ====================
# NOTIFICATION SETTINGS
# ====================

@login_required
def notifications_page(request):
    """View for displaying the notifications page."""
    return render(request, 'calendarEditor/notifications_page.html')


@login_required
def notification_settings(request):
    """View for managing user notification preferences."""
    from .models import NotificationPreference
    from userRegistration.forms import NotificationPreferenceForm

    # Get or create notification preferences for this user
    prefs, created = NotificationPreference.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = NotificationPreferenceForm(request.POST, instance=prefs, user=request.user)
        if form.is_valid():
            # Save without committing to ensure critical notifications stay True
            saved_prefs = form.save(commit=False)
            # Critical queue notifications (always on)
            saved_prefs.notify_on_deck = True
            saved_prefs.notify_ready_for_check_in = True
            saved_prefs.notify_checkin_reminder = True
            saved_prefs.notify_checkout_reminder = True
            # Critical appeal notifications (always on)
            saved_prefs.notify_appeal_approved = True
            saved_prefs.notify_appeal_rejected = True
            # Critical account status notifications (always on)
            saved_prefs.notify_account_approved = True
            saved_prefs.notify_account_unapproved = True
            saved_prefs.notify_account_promoted = True
            saved_prefs.notify_account_demoted = True
            saved_prefs.notify_account_info_changed = True

            # Force admin notifications to remain True if user is staff
            if request.user.is_staff or request.user.is_superuser:
                saved_prefs.notify_admin_new_user = True
                saved_prefs.notify_admin_rush_job = True
                saved_prefs.notify_database_restored = True
                saved_prefs.notify_developer_feedback = True

            saved_prefs.save()
            messages.success(request, 'Notification preferences updated successfully!')
            return redirect('notification_settings')
        else:
            # Log validation errors
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Notification form validation failed: {form.errors}')
            messages.error(request, 'Failed to save preferences. Please check the form for errors.')
    else:
        form = NotificationPreferenceForm(instance=prefs, user=request.user)

    # Get followed presets for display
    followed_presets = prefs.followed_presets.all().order_by('display_name')

    return render(request, 'calendarEditor/notification_settings.html', {
        'form': form,
        'prefs': prefs,
        'followed_presets': followed_presets,
    })


@login_required
def reset_notification_preferences(request):
    """Reset user notification preferences to default values."""
    from .models import NotificationPreference

    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    # Get the user's notification preferences
    prefs = NotificationPreference.get_or_create_for_user(request.user)

    # Reset to default values based on user type
    if request.user.is_superuser:
        prefs.notify_public_preset_created = False
        prefs.notify_public_preset_edited = False
        prefs.notify_public_preset_deleted = False
        prefs.notify_private_preset_edited = False
        prefs.notify_followed_preset_edited = False
        prefs.notify_followed_preset_deleted = False
        prefs.notify_queue_added = False
        prefs.notify_queue_position_change = False
        prefs.notify_queue_cancelled = False
        prefs.notify_on_deck = False
        prefs.notify_ready_for_check_in = False
        prefs.notify_checkin_reminder = False
        prefs.notify_checkout_reminder = False
        prefs.notify_machine_queue_changes = False
        prefs.notify_admin_check_in = False
        prefs.notify_admin_checkout = False
        prefs.notify_admin_edit_entry = False
        prefs.notify_admin_moved_entry = False
        prefs.notify_machine_status_change = False
        prefs.notify_appeal_approved = False
        prefs.notify_appeal_rejected = False
        prefs.notify_account_approved = False
        prefs.notify_account_unapproved = False
        prefs.notify_account_promoted = False
        prefs.notify_account_demoted = False
        prefs.notify_account_info_changed = False
        prefs.notify_admin_new_user = False
        prefs.notify_admin_rush_job = False
        prefs.notify_database_restored = False
        prefs.notify_developer_feedback = False    
    elif request.user.is_staff:
        # Admin defaults (minimal notifications)
        prefs.notify_public_preset_created = False
        prefs.notify_public_preset_edited = False
        prefs.notify_public_preset_deleted = False
        prefs.notify_private_preset_edited = False
        prefs.notify_followed_preset_edited = True
        prefs.notify_followed_preset_deleted = True
        prefs.notify_queue_added = True
        prefs.notify_queue_position_change = False
        prefs.notify_queue_cancelled = True
        prefs.notify_on_deck = True
        prefs.notify_ready_for_check_in = True
        prefs.notify_checkin_reminder = True
        prefs.notify_checkout_reminder = True
        prefs.notify_machine_queue_changes = False
        prefs.notify_admin_check_in = True
        prefs.notify_admin_checkout = True
        prefs.notify_admin_edit_entry = True
        prefs.notify_admin_moved_entry = True
        prefs.notify_machine_status_change = True
        prefs.notify_appeal_approved = True
        prefs.notify_appeal_rejected = True
        prefs.notify_account_approved = True
        prefs.notify_account_unapproved = True
        prefs.notify_account_promoted = True
        prefs.notify_account_demoted = True
        prefs.notify_account_info_changed = True
        prefs.notify_admin_new_user = True
        prefs.notify_admin_rush_job = True
        prefs.notify_database_restored = True
        prefs.notify_developer_feedback = True
    else:
        # Regular user defaults (all notifications enabled)
        prefs.notify_public_preset_created = False
        prefs.notify_public_preset_edited = False
        prefs.notify_public_preset_deleted = False
        prefs.notify_private_preset_edited = True
        prefs.notify_followed_preset_edited = True
        prefs.notify_followed_preset_deleted = True
        prefs.notify_queue_added = True
        prefs.notify_queue_position_change = True
        prefs.notify_queue_cancelled = True
        prefs.notify_on_deck = True
        prefs.notify_ready_for_check_in = True
        prefs.notify_checkin_reminder = True
        prefs.notify_checkout_reminder = True
        prefs.notify_machine_queue_changes = False
        prefs.notify_admin_check_in = True
        prefs.notify_admin_checkout = True
        prefs.notify_admin_edit_entry = True
        prefs.notify_admin_moved_entry = True
        prefs.notify_machine_status_change = True
        prefs.notify_appeal_approved = True
        prefs.notify_appeal_rejected = True
        prefs.notify_account_approved = True
        prefs.notify_account_unapproved = True
        prefs.notify_account_promoted = True
        prefs.notify_account_demoted = True
        prefs.notify_account_info_changed = True

    # Delivery preferences (same for all users)
    prefs.email_notifications = True
    prefs.in_app_notifications = True
    prefs.slack_notifications = True

    prefs.save()

    messages.success(request, 'Notification preferences have been reset to defaults!')
    return JsonResponse({'success': True, 'message': 'Preferences reset successfully'})


# ===== Notification API Endpoints =====

@login_required
def notification_list_api(request):
    """API endpoint to get user's notifications."""
    from .models import Notification

    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')[:50]

    notification_data = [{
        'id': notif.id,
        'notification_type': notif.notification_type,
        'title': notif.title,
        'message': notif.message,
        'is_read': notif.is_read,
        'created_at': notif.created_at.isoformat(),
        'url': notif.get_notification_url(),
    } for notif in notifications]

    return JsonResponse({'notifications': notification_data})


@login_required
def notification_count_api(request):
    """
    Lightweight API endpoint returning only the count of unread notifications.
    Much more efficient than fetching all notifications just to count them.
    Returns: {"unread_count": N}
    """
    from .models import Notification

    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()

    return JsonResponse({'unread_count': count})


@login_required
@require_http_methods(["POST"])
def notification_mark_read_api(request):
    """API endpoint to mark a notification as read."""
    from .models import Notification
    import json

    try:
        data = json.loads(request.body)
        notification_id = data.get('notification_id')

        # First check if notification exists
        try:
            notification = Notification.objects.get(id=notification_id)
        except Notification.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)

        # Check if it belongs to the current user
        if notification.recipient != request.user:
            return JsonResponse({
                'success': False,
                'error': 'This notification is not for your account',
                'wrong_user': True
            }, status=403)

        notification.is_read = True
        notification.save()

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def notification_mark_all_read_api(request):
    """API endpoint to mark all notifications as read."""
    from .models import Notification

    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)

    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def notification_dismiss_api(request):
    """API endpoint to dismiss (delete) a single notification."""
    from .models import Notification
    import json

    try:
        data = json.loads(request.body)
        notification_id = data.get('notification_id')

        # First check if notification exists
        try:
            notification = Notification.objects.get(id=notification_id)
        except Notification.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)

        # Check if it belongs to the current user
        if notification.recipient != request.user:
            return JsonResponse({
                'success': False,
                'error': 'This notification is not for your account',
                'wrong_user': True
            }, status=403)

        notification.delete()

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def notification_clear_read_api(request):
    """API endpoint to clear (delete) all read notifications."""
    from .models import Notification

    deleted_count = Notification.objects.filter(recipient=request.user, is_read=True).delete()[0]

    return JsonResponse({'success': True, 'deleted_count': deleted_count})


# ====================
# ARCHIVE VIEWS
# ====================

@login_required
def archive_list(request):
    """Display archive of completed measurements with filters."""
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

    # Get all archived measurements (all users can see all archives)
    archives = ArchivedMeasurement.objects.all()

    # Get filter parameters
    year = request.GET.get('year')
    month = request.GET.get('month')
    day = request.GET.get('day')
    machine_id = request.GET.get('machine')
    user_id = request.GET.get('user')

    # Apply filters
    if year:
        archives = archives.filter(measurement_date__year=year)
    if month:
        archives = archives.filter(measurement_date__month=month)
    if day:
        archives = archives.filter(measurement_date__day=day)
    if machine_id:
        archives = archives.filter(machine_id=machine_id)
    if user_id and request.user.is_staff:  # Only admins can filter by user
        archives = archives.filter(user_id=user_id)

    # Get available years/months/days for filter dropdowns (from all archives)
    all_archives = ArchivedMeasurement.objects.all()
    available_years = sorted(set(all_archives.values_list('measurement_date__year', flat=True).distinct()), reverse=True)

    # Get available days based on selected year and month
    available_days = []
    if year and month:
        days_query = all_archives.filter(measurement_date__year=year, measurement_date__month=month)
        available_days = sorted(set(days_query.values_list('measurement_date__day', flat=True).distinct()))

    # Get machines for filter
    machines = Machine.objects.all().order_by('name')

    # Get users for filter (admin only)
    users = User.objects.all().order_by('username') if request.user.is_staff else None

    # Pagination
    per_page = request.GET.get('per_page', '25')  # Default to 25 entries per page
    try:
        per_page = int(per_page)
        if per_page not in [10, 25, 50, 100]:
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    # Order archives by date (newest first)
    archives_ordered = archives.order_by('-measurement_date')

    # Create paginator
    paginator = Paginator(archives_ordered, per_page)
    page_number = request.GET.get('page', 1)

    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)

    context = {
        'archives': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'per_page': per_page,
        'machines': machines,
        'users': users,
        'available_years': available_years,
        'available_days': available_days,
        'selected_year': year,
        'selected_month': month,
        'selected_day': day,
        'selected_machine': machine_id,
        'selected_user': user_id,
    }

    return render(request, 'calendarEditor/archive_list.html', context)


@login_required
@staff_member_required
def archive_create(request):
    """Create a new archive entry manually (staff/superuser only)."""
    if request.method == 'POST':
        form = ArchivedMeasurementForm(request.POST, request.FILES)
        if form.is_valid():
            archive = form.save(commit=False)
            archive.user = request.user

            # Get machine from POST data
            machine_id = request.POST.get('machine')
            if machine_id:
                archive.machine = get_object_or_404(Machine, id=machine_id)
                archive.save()
                messages.success(request, 'Measurement archived successfully!')
                return redirect('archive_list')
            else:
                messages.error(request, 'Please select a machine.')
    else:
        # Pre-populate measurement_date with current time
        initial_data = {
            'measurement_date': timezone.now().strftime('%Y-%m-%dT%H:%M')
        }
        form = ArchivedMeasurementForm(initial=initial_data)

    machines = Machine.objects.all().order_by('name')

    context = {
        'form': form,
        'machines': machines,
    }

    return render(request, 'calendarEditor/archive_create.html', context)


@login_required
def save_to_archive(request, queue_entry_id):
    """Save a completed queue entry to the archive."""
    # Check if entry exists and belongs to current user
    queue_entry = get_object_or_404(QueueEntry, id=queue_entry_id)
    if queue_entry.user != request.user:
        messages.warning(request, 'This queue entry is not for your account. Returning to home page.')
        return redirect('home')

    if request.method == 'POST':
        form = ArchivedMeasurementForm(request.POST, request.FILES)
        if form.is_valid():
            archive = form.save(commit=False)
            archive.user = request.user
            archive.machine = queue_entry.assigned_machine
            archive.related_queue_entry = queue_entry

            # Set duration from queue entry if not provided in form
            if not archive.duration_hours and queue_entry.estimated_duration_hours:
                archive.duration_hours = queue_entry.estimated_duration_hours

            # Create preset snapshot from queue entry
            preset_snapshot = {
                'title': queue_entry.title,
                'description': queue_entry.description,
                'required_min_temp': queue_entry.required_min_temp,
                'required_max_temp': queue_entry.required_max_temp,
                'required_b_field_x': queue_entry.required_b_field_x,
                'required_b_field_y': queue_entry.required_b_field_y,
                'required_b_field_z': queue_entry.required_b_field_z,
                'required_b_field_direction': queue_entry.required_b_field_direction,
                'required_dc_lines': queue_entry.required_dc_lines,
                'required_rf_lines': queue_entry.required_rf_lines,
                'requires_optical': queue_entry.requires_optical,
                'estimated_duration_hours': queue_entry.estimated_duration_hours,
            }
            archive.preset_snapshot = preset_snapshot

            archive.save()
            messages.success(request, 'Queue entry archived successfully!')
            return redirect('archive_list')
    else:
        # Pre-populate form with queue entry data
        initial_data = {
            'title': queue_entry.title,
            'notes': queue_entry.description,
            'measurement_date': queue_entry.completed_at or timezone.now(),
            'duration_hours': queue_entry.estimated_duration_hours,
        }
        form = ArchivedMeasurementForm(initial=initial_data)

    context = {
        'form': form,
        'queue_entry': queue_entry,
    }

    return render(request, 'calendarEditor/save_to_archive.html', context)


@login_required
def download_archive_file(request, archive_id):
    """Download an archived measurement file."""
    from django.http import FileResponse, Http404
    import os

    archive = get_object_or_404(ArchivedMeasurement, id=archive_id)

    # All logged-in users can download any archive file
    if not archive.uploaded_file:
        messages.error(request, 'No file attached to this archive entry.')
        return redirect('archive_list')

    try:
        file_path = archive.uploaded_file.path
        if os.path.exists(file_path):
            response = FileResponse(open(file_path, 'rb'))
            response['Content-Disposition'] = f'attachment; filename="{archive.get_file_name()}"'
            return response
        else:
            raise Http404("File not found")
    except Exception as e:
        messages.error(request, f'Error downloading file: {str(e)}')
        return redirect('archive_list')


@login_required
@staff_member_required
def delete_archive(request, archive_id):
    """Delete a single archive entry (admin only)."""
    if request.method == 'POST':
        archive = get_object_or_404(ArchivedMeasurement, id=archive_id)

        # Delete the uploaded file if it exists
        if archive.uploaded_file:
            try:
                archive.uploaded_file.delete()
            except Exception as e:
                messages.warning(request, f'File deleted but error occurred: {str(e)}')

        archive.delete()
        messages.success(request, f'Archive entry "{archive.title}" has been deleted.')

    return redirect('archive_list')


@login_required
@staff_member_required
def bulk_delete_archives(request):
    """Bulk delete archive entries (admin only)."""
    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        archive_ids = request.POST.getlist('archive_ids')

        if not archive_ids:
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'No archive entries selected for deletion.'})
            messages.error(request, 'No archive entries selected for deletion.')
            return redirect('archive_list')

        # Get all archives to delete
        archives = ArchivedMeasurement.objects.filter(id__in=archive_ids)
        count = archives.count()

        if count == 0:
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'No valid archive entries found to delete.'})
            messages.error(request, 'No valid archive entries found to delete.')
            return redirect('archive_list')

        # Delete files first
        for archive in archives:
            if archive.uploaded_file:
                try:
                    archive.uploaded_file.delete()
                except Exception as e:
                    # Continue even if file deletion fails
                    pass

        # Delete the archive entries
        archives.delete()

        success_msg = f'Successfully deleted {count} archive {"entry" if count == 1 else "entries"}.'

        if is_ajax:
            return JsonResponse({'success': True, 'count': count, 'message': success_msg})

        messages.success(request, success_msg)

    return redirect('archive_list')


def token_login(request, token):
    """
    Handle secure navigation from Slack notifications with smart re-authentication.

    Security model:
    - If user is already logged in as the CORRECT user → Direct redirect to page
    - If user is logged in as DIFFERENT user → Auto-logout and prompt re-auth
    - If user is not logged in → Show login page with hint about which user to use
    - Token is reusable (not consumed on use)
    - Token expires after 24 hours for security
    """
    from .models import OneTimeLoginToken
    from django.contrib import messages
    from django.contrib.auth import logout

    try:
        # Get the token
        login_token = OneTimeLoginToken.objects.get(token=token)

        # Check if token is expired (but not if it's used - tokens are reusable)
        if timezone.now() > login_token.expires_at:
            messages.error(request, 'Expired link -- more than 24 hours after send.')
            return redirect('login')

        intended_user = login_token.user
        redirect_url = login_token.redirect_url

        # Case 1: Already logged in as CORRECT user
        if request.user.is_authenticated and request.user.id == intended_user.id:
            # Perfect match! Direct redirect to intended page
            return redirect(redirect_url)

        # Case 2: Logged in as DIFFERENT user - auto-logout and prompt re-auth
        if request.user.is_authenticated and request.user.id != intended_user.id:
            wrong_user = request.user.username
            # Logout the current (wrong) user
            logout(request)

            # Store ONLY the token in session, not the redirect URL
            # This forces them to come back through the token link after logging in
            request.session['token_auth_hint'] = intended_user.username
            request.session['pending_token'] = token

            messages.warning(
                request,
                f'You were logged in as {wrong_user}. This link is for {intended_user.username}. '
                f'Please log in as {intended_user.username} to continue.'
            )
            # Redirect to login WITHOUT ?next parameter to prevent wrong user from accessing the page
            return redirect('login')

        # Case 3: Not logged in - show login with hint
        # Store the token in session so we can validate after login
        request.session['token_auth_hint'] = intended_user.username
        request.session['pending_token'] = token

        messages.info(
            request,
            f'Please log in as {intended_user.username} to view this notification.'
        )
        return redirect('login')

    except OneTimeLoginToken.DoesNotExist:
        messages.error(request, 'Invalid notification link.')
        return redirect('login')


def machine_status_api(request):
    """
    API endpoint to get current machine status and temperatures.

    Returns cached temperature data that is updated by the temperature gateway
    script running on the university network. This endpoint no longer tries to
    read from machines directly since Render cannot reach local IPs.
    """
    # OPTIMIZED: Prefetch running entries to avoid N+1 queries in get_display_status()
    from django.db.models import Prefetch
    machines = Machine.objects.prefetch_related(
        Prefetch('queue_entries',
                 queryset=QueueEntry.objects.filter(status='running'),
                 to_attr='running_entries_cache')
    ).order_by('name')

    data = []
    for machine in machines:
        # Just return cached values - the temperature gateway updates these
        # No longer trying to read from machines directly (Render can't reach local IPs)

        data.append({
            'id': machine.id,
            'name': machine.name,
            'temperature': machine.get_live_temperature(),
            'status': machine.get_display_status(prefetch_running=machine.running_entries_cache),
            'is_online': machine.is_online(),
            'last_update': machine.last_temp_update.isoformat() if machine.last_temp_update else None,
        })

    return JsonResponse({'machines': data})


def api_check_reminders(request):
    """
    API endpoint for checking and sending pending reminders.

    This endpoint is called by GitHub Actions every 5 minutes to ensure
    reminders are sent even when the server is asleep on Render free tier.

    Returns JSON with:
    - checked: number of entries checked
    - sent: number of reminders sent
    """
    from django.utils import timezone
    from django.db.models import Q
    from .middleware import CheckReminderMiddleware

    # Run the same logic as middleware
    middleware = CheckReminderMiddleware(lambda x: x)

    now = timezone.now()
    twelve_hours_ago = now - timedelta(hours=12)

    # Count pending reminders before (entries that need a reminder)
    pending_before = QueueEntry.objects.filter(
        Q(reminder_due_at__lte=now) &  # Past initial reminder time
        Q(status='running') &  # Still running
        (
            Q(last_reminder_sent_at__isnull=True) |  # Never sent
            Q(last_reminder_sent_at__lte=twelve_hours_ago)  # Sent 12+ hours ago
        )
    ).count()

    # Check and send reminders
    try:
        middleware._check_pending_reminders()

        # Count what's left after (should be fewer if any were sent)
        # Recalculate since last_reminder_sent_at was updated
        now_after = timezone.now()
        twelve_hours_ago_after = now_after - timedelta(hours=12)
        pending_after = QueueEntry.objects.filter(
            Q(reminder_due_at__lte=now_after) &
            Q(status='running') &
            (
                Q(last_reminder_sent_at__isnull=True) |
                Q(last_reminder_sent_at__lte=twelve_hours_ago_after)
            )
        ).count()

        sent = pending_before - pending_after

        return JsonResponse({
            'success': True,
            'checked': pending_before,
            'sent': sent,
            'timestamp': now_after.isoformat(),
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat(),
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def update_machine_temperatures(request):
    """
    API endpoint for temperature gateway to update machine temperatures.
    
    This endpoint accepts temperature readings from a script running on the
    university network that can access the lab machines' local IPs.
    
    Authentication: Requires X-API-Key header matching TEMPERATURE_GATEWAY_API_KEY
    
    POST /api/update-machine-temperatures/
    Body:
    {
        "machines": [
            {"id": 1, "temperature": 4.2, "online": true},
            {"id": 2, "temperature": null, "online": false},
            ...
        ]
    }
    
    Returns:
    {
        "success": true,
        "updated": 5,
        "errors": []
    }
    """
    import json
    from django.utils import timezone
    
    # Check API key authentication
    api_key = request.headers.get('X-API-Key')
    expected_key = settings.TEMPERATURE_GATEWAY_API_KEY
    
    if not expected_key:
        return JsonResponse({
            'success': False,
            'error': 'Temperature gateway API key not configured on server'
        }, status=500)
    
    if api_key != expected_key:
        return JsonResponse({
            'success': False,
            'error': 'Invalid API key'
        }, status=401)
    
    # Parse request body
    try:
        data = json.loads(request.body)
        machines_data = data.get('machines', [])
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON in request body'
        }, status=400)
    
    # Update each machine
    updated_count = 0
    errors = []
    
    for machine_data in machines_data:
        try:
            machine_id = machine_data.get('id')
            temperature = machine_data.get('temperature')
            online = machine_data.get('online', True)
            
            # Get the machine
            try:
                machine = Machine.objects.get(id=machine_id)
            except Machine.DoesNotExist:
                errors.append(f"Machine {machine_id} not found")
                continue
            
            # Update fields
            machine.cached_temperature = temperature
            machine.cached_online = online
            machine.last_temp_update = timezone.now()
            machine.save(update_fields=['cached_temperature', 'cached_online', 'last_temp_update'])
            
            updated_count += 1
            
        except Exception as e:
            errors.append(f"Error updating machine {machine_data.get('id', 'unknown')}: {str(e)}")
    
    return JsonResponse({
        'success': True,
        'updated': updated_count,
        'errors': errors,
        'timestamp': timezone.now().isoformat(),
    })


@login_required
def export_my_measurements(request):
    """
    Export user's own archived measurements to CSV file.
    Available to any authenticated user.
    """
    import csv
    from django.http import HttpResponse
    from datetime import datetime
    
    # Get user's measurements
    measurements = ArchivedMeasurement.objects.filter(
        user=request.user
    ).select_related('machine').order_by('-measurement_date')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="my_measurements_{request.user.username}_{datetime.now().strftime("%Y-%m-%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Machine', 'Measurement Date',
        'Title', 'Duration (hours)', 'Notes', 'Archived At'
    ])

    for m in measurements:
        # Use machine_name field as fallback if machine was deleted
        machine_display = m.machine.name if m.machine else (m.machine_name or 'Deleted Machine')
        writer.writerow([
            m.id,
            machine_display,
            m.measurement_date.strftime('%Y-%m-%d %H:%M:%S'),
            m.title,
            m.duration_hours if m.duration_hours is not None else '',
            m.notes,
            m.archived_at.strftime('%Y-%m-%d %H:%M:%S')
        ])

    return response


@login_required
def check_in_out_data_json(request):
    """
    Lightweight JSON endpoint for check-in/check-out page DOM updates.
    Returns minimal data needed to update the page without full reload.
    OPTIMIZED: Prevents 50KB+ HTML downloads on every queue update.
    """
    # Get user's entries organized by status
    ready_to_check_out = QueueEntry.objects.filter(
        user=request.user,
        status='running',
        assigned_machine__current_status__in=['idle', 'cooldown']
    ).select_related('assigned_machine').order_by('started_at')

    currently_running = QueueEntry.objects.filter(
        user=request.user,
        status='running'
    ).exclude(
        assigned_machine__current_status__in=['idle', 'cooldown']
    ).select_related('assigned_machine').order_by('started_at')

    ready_to_check_in = QueueEntry.objects.filter(
        user=request.user,
        status='queued',
        queue_position=1,
        assigned_machine__current_status='idle'
    ).select_related('assigned_machine')

    waiting_entries = QueueEntry.objects.filter(
        user=request.user,
        status='queued',
        queue_position=1
    ).exclude(
        assigned_machine__current_status='idle'
    ).select_related('assigned_machine')

    # Serialize to minimal JSON (only essential fields)
    def serialize_entry(entry):
        return {
            'id': entry.id,
            'title': entry.title[:80],
            'description': entry.description[:150] if entry.description else '',
            'machine_name': entry.assigned_machine.name if entry.assigned_machine else 'No machine',
            'machine_status': entry.assigned_machine.current_status if entry.assigned_machine else 'unknown',
            'machine_available': entry.assigned_machine.is_available if entry.assigned_machine else False,
            'estimated_duration': entry.estimated_duration_hours,
            'started_at': entry.started_at.isoformat() if entry.started_at else None,
        }

    return JsonResponse({
        'ready_to_check_out': [serialize_entry(e) for e in ready_to_check_out],
        'currently_running': [serialize_entry(e) for e in currently_running],
        'ready_to_check_in': [serialize_entry(e) for e in ready_to_check_in],
        'waiting_entries': [serialize_entry(e) for e in waiting_entries],
    })


@login_required
def my_queue_data_json(request):
    """
    Lightweight JSON endpoint for my_queue page DOM updates.
    Returns minimal data needed to update the page without full reload.
    OPTIMIZED: Prevents 50KB+ HTML downloads on every queue update.
    """
    queued = QueueEntry.objects.filter(
        user=request.user, status='queued'
    ).select_related('assigned_machine').order_by('assigned_machine', 'queue_position')

    running = QueueEntry.objects.filter(
        user=request.user, status='running'
    ).select_related('assigned_machine')

    completed = QueueEntry.objects.filter(
        user=request.user, status='completed'
    ).select_related('assigned_machine').order_by('-completed_at')[:10]

    # Serialize entries
    def serialize_entry(entry):
        return {
            'id': entry.id,
            'title': entry.title[:80],
            'machine_name': entry.assigned_machine.name if entry.assigned_machine else 'Unassigned',
            'machine_id': entry.assigned_machine.id if entry.assigned_machine else None,
            'queue_position': entry.queue_position,
            'status': entry.status,
            'estimated_duration': entry.estimated_duration_hours,
            'started_at': entry.started_at.isoformat() if entry.started_at else None,
            'completed_at': entry.completed_at.isoformat() if entry.completed_at else None,
        }

    return JsonResponse({
        'queued': [serialize_entry(e) for e in queued],
        'running': [serialize_entry(e) for e in running],
        'completed': [serialize_entry(e) for e in completed],
    })


def health_check(request):
    """
    Health check endpoint for monitoring services (UptimeRobot, etc.)

    Lightweight check that keeps Render web server awake WITHOUT querying the database.
    This prevents unnecessary database compute usage while still monitoring site availability.

    Database health is checked separately by GitHub Actions via /api/check-reminders/
    which runs hourly and actually needs to wake the database for reminder processing.

    ALWAYS returns 200 to keep UptimeRobot happy and prevent false alarms.
    """
    from channels.layers import get_channel_layer

    health_status = {
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'service': 'render-web-server',
        'note': 'Database health checked hourly by GitHub Actions'
    }

    # Optionally test cache and channels if needed, but skip database query
    # to prevent keeping Neon database awake 24/7 from frequent health checks

    # ALWAYS return 200 - keeps Render awake without waking database
    return JsonResponse(health_status, status=200)


def parse_user_agent(request):
    """
    Parse request headers to extract device info.

    Returns dict with browser, OS, device type, and platform flags.
    """
    from user_agents import parse

    ua_string = request.META.get('HTTP_USER_AGENT', '')
    user_agent = parse(ua_string)

    return {
        'browser': f"{user_agent.browser.family} {user_agent.browser.version_string}",
        'os': f"{user_agent.os.family} {user_agent.os.version_string}",
        'device': user_agent.device.family,
        'is_mobile': user_agent.is_mobile,
        'is_tablet': user_agent.is_tablet,
        'is_pc': user_agent.is_pc,
        'timestamp': timezone.now().isoformat(),
    }


@login_required
def submit_feedback(request):
    """Submit feedback (bugs, feature requests, opinions)."""
    from .forms import FeedbackForm
    from .models import Feedback
    from . import notifications

    # Check feedback limits (completed feedbacks don't count)
    active_feedback_count = Feedback.objects.filter(
        user=request.user
    ).exclude(status='completed').count()

    # Set limit based on user role
    if hasattr(request.user, 'profile') and request.user.profile.is_developer:
        feedback_limit = 300
    else:
        feedback_limit = 30

    if active_feedback_count >= feedback_limit:
        messages.error(request, f'You have reached your feedback limit of {feedback_limit} active submissions. Please wait for existing feedback to be completed before submitting more.')
        return redirect('home')

    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.user = request.user

            # Auto-collect device info
            feedback.device_info = parse_user_agent(request)

            # Determine user level
            if request.user.is_superuser:
                feedback.user_level = 'admin'
            elif hasattr(request.user, 'profile') and request.user.profile.is_developer:
                feedback.user_level = 'developer'
            elif request.user.is_staff:
                feedback.user_level = 'staff'
            else:
                feedback.user_level = 'user'

            feedback.save()

            # Send notification to developers
            notify_developers_new_feedback(feedback)

            messages.success(request, 'Thank you for your feedback!')
            return redirect('home')
    else:
        form = FeedbackForm()

    return render(request, 'calendarEditor/feedback/submit_feedback.html', {
        'form': form
    })


def notify_developers_new_feedback(feedback):
    """Notify all developers when new feedback is submitted."""
    from userRegistration.models import UserProfile
    from . import notifications

    # Get all developers
    developers = UserProfile.objects.filter(is_developer=True).select_related('user')

    # Get all superusers
    superusers = User.objects.filter(is_superuser=True)

    # Combine recipients
    developer_users = [profile.user for profile in developers]
    all_recipients = list(set(list(developer_users) + list(superusers)))

    # Build detailed message based on feedback type
    if feedback.feedback_type == 'bug':
        details = f"What happened: {feedback.description[:200]}..."
        if feedback.replication_steps:
            details += f"\n\nReplication steps: {feedback.replication_steps[:200]}..."
    elif feedback.feedback_type == 'feature':
        details = f"Feature name: {feedback.title}\n\nDescription: {feedback.description[:200]}..."
    else:  # opinion
        details = f"Topic: {feedback.title}\n\nOpinion: {feedback.description[:200]}..."

    # Create notification for each recipient (includes Slack DM automatically)
    for recipient in all_recipients:
        # Use detailed message for both in-app and Slack
        full_message = f"{feedback.user.username} submitted a {feedback.get_feedback_type_display()}\n\n{details}"

        notifications.create_notification(
            recipient=recipient,
            notification_type='developer_new_feedback',
            title=f'New {feedback.get_feedback_type_display()}: {feedback.title}',
            message=full_message,
            triggering_user=feedback.user,
        )



@login_required
def test_form_protector(request):
    """Test page for FormProtector utility"""
    return render(request, 'calendarEditor/test_form_protector.html')

