from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from django.db.models import Count, Q
from userRegistration.models import UserProfile
from .models import Machine, QueueEntry, QueuePreset, ArchivedMeasurement, Notification
from .notifications import auto_clear_notifications
from .views import reorder_queue
from . import notifications
from .forms import QueueEntryForm
from .matching_algorithm import find_best_machine


@staff_member_required
def admin_dashboard(request):
    """Main admin dashboard with overview stats."""
    # Get stats - exclude staff/superusers from pending count
    pending_users = UserProfile.objects.filter(
        is_approved=False
    ).exclude(
        Q(user__is_staff=True) | Q(user__is_superuser=True)
    ).count()
    total_users = User.objects.count()
    total_machines = Machine.objects.count()
    active_machines = Machine.objects.filter(is_available=True).count()
    queued_entries = QueueEntry.objects.filter(status='queued').count()
    running_entries = QueueEntry.objects.filter(status='running').count()
    rush_jobs = QueueEntry.objects.filter(is_rush_job=True, status='queued').count()
    total_presets = QueuePreset.objects.count()

    context = {
        'pending_users': pending_users,
        'total_users': total_users,
        'total_machines': total_machines,
        'active_machines': active_machines,
        'queued_entries': queued_entries,
        'running_entries': running_entries,
        'rush_jobs': rush_jobs,
        'total_presets': total_presets,
    }

    return render(request, 'calendarEditor/admin/admin_dashboard.html', context)


@staff_member_required
def admin_users(request):
    """User management page."""
    # Get filter from query params
    status_filter = request.GET.get('status', 'all')

    # Base queryset - only users with profiles
    users = User.objects.select_related('profile').filter(profile__isnull=False)

    # Apply filters
    if status_filter == 'pending':
        # Pending users: not approved AND not staff/superuser
        users = users.filter(
            profile__is_approved=False
        ).exclude(
            Q(is_staff=True) | Q(is_superuser=True)
        )
    elif status_filter == 'approved':
        users = users.filter(profile__is_approved=True)
    elif status_filter == 'staff':
        users = users.filter(is_staff=True)

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )

    users = users.order_by('-date_joined')

    context = {
        'users': users,
        'status_filter': status_filter,
        'search_query': search_query,
    }

    return render(request, 'calendarEditor/admin/admin_users.html', context)


@staff_member_required
def approve_user(request, user_id):
    """Approve a user."""
    user = get_object_or_404(User, id=user_id)

    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)

    if not profile.is_approved:
        profile.is_approved = True
        profile.approved_by = request.user
        profile.approved_at = timezone.now()
        profile.save()

        # Auto-clear all "new user signup" notifications for this user
        auto_clear_notifications(
            notification_type='admin_new_user',
            triggering_user=user
        )

        messages.success(request, f'User {user.username} has been approved.')
    else:
        messages.info(request, f'User {user.username} is already approved.')

    # Redirect back with preserved query parameters
    referer = request.META.get('HTTP_REFERER', '')
    if referer and '/admin-users/' in referer:
        # Extract and preserve query parameters from referer
        from urllib.parse import urlparse, parse_qs, urlencode
        parsed = urlparse(referer)
        if parsed.query:
            return redirect(f"{reverse('admin_users')}?{parsed.query}")

    return redirect('admin_users')


@staff_member_required
def reject_user(request, user_id):
    """Reject/unapprove a user. Staff can only be unapproved by superusers."""
    user = get_object_or_404(User, id=user_id)

    # Only superusers can unapprove staff users
    if (user.is_staff or user.is_superuser) and not request.user.is_superuser:
        messages.error(request, f'Only superusers can unapprove staff users.')
        return redirect('admin_users')

    try:
        profile = user.profile
        if profile.is_approved:
            profile.is_approved = False
            profile.approved_by = None
            profile.approved_at = None
            profile.save()
            messages.success(request, f'User {user.username} has been unapproved.')
        else:
            messages.info(request, f'User {user.username} is already unapproved.')
    except UserProfile.DoesNotExist:
        messages.error(request, f'User {user.username} does not have a profile.')

    # Redirect back with preserved query parameters
    referer = request.META.get('HTTP_REFERER', '')
    if referer and '/admin-users/' in referer:
        from urllib.parse import urlparse
        parsed = urlparse(referer)
        if parsed.query:
            return redirect(f"{reverse('admin_users')}?{parsed.query}")

    return redirect('admin_users')


@staff_member_required
def delete_user(request, user_id):
    """Delete a user (with confirmation). Staff can only be deleted by superusers."""
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        username = user.username

        # Only superusers can delete staff users
        if (user.is_staff or user.is_superuser) and not request.user.is_superuser:
            messages.error(request, f'Only superusers can delete staff users.')
            return redirect('admin_users')

        user.delete()
        messages.success(request, f'User {username} has been deleted.')

    # Redirect back with preserved query parameters
    referer = request.META.get('HTTP_REFERER', '')
    if referer and '/admin-users/' in referer:
        from urllib.parse import urlparse
        parsed = urlparse(referer)
        if parsed.query:
            return redirect(f"{reverse('admin_users')}?{parsed.query}")

    return redirect('admin_users')


@staff_member_required
def promote_to_staff(request, user_id):
    """Promote a user to staff (superuser only)."""
    if not request.user.is_superuser:
        messages.error(request, 'Only superusers can promote users to staff.')
        return redirect('admin_users')

    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)

        if user.is_staff:
            messages.info(request, f'{user.username} is already a staff member.')
        else:
            user.is_staff = True
            user.save()

            # Auto-approve staff users
            try:
                profile = user.profile
                if not profile.is_approved:
                    profile.is_approved = True
                    profile.approved_by = request.user
                    profile.approved_at = timezone.now()
                    profile.save()
            except UserProfile.DoesNotExist:
                pass

            messages.success(request, f'{user.username} has been promoted to staff.')

    # Redirect back with preserved query parameters
    referer = request.META.get('HTTP_REFERER', '')
    if referer and '/admin-users/' in referer:
        from urllib.parse import urlparse
        parsed = urlparse(referer)
        if parsed.query:
            return redirect(f"{reverse('admin_users')}?{parsed.query}")

    return redirect('admin_users')


@staff_member_required
def demote_from_staff(request, user_id):
    """Demote a staff user to regular user (superuser only)."""
    if not request.user.is_superuser:
        messages.error(request, 'Only superusers can demote staff users.')
        return redirect('admin_users')

    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)

        if user.is_superuser:
            messages.error(request, 'Cannot demote superusers. Please use Django admin.')
            return redirect('admin_users')

        if not user.is_staff:
            messages.info(request, f'{user.username} is not a staff member.')
        else:
            user.is_staff = False
            user.save()
            messages.success(request, f'{user.username} has been demoted to regular user.')

    # Redirect back with preserved query parameters
    referer = request.META.get('HTTP_REFERER', '')
    if referer and '/admin-users/' in referer:
        from urllib.parse import urlparse
        parsed = urlparse(referer)
        if parsed.query:
            return redirect(f"{reverse('admin_users')}?{parsed.query}")

    return redirect('admin_users')


@staff_member_required
def admin_machines(request):
    """Machine management page."""
    machines = Machine.objects.all().annotate(
        queue_count=Count('queue_entries', filter=Q(queue_entries__status='queued'))
    ).order_by('name')

    # Add live temperature and status to each machine
    machine_data = []
    for machine in machines:
        machine_data.append({
            'machine': machine,
            'queue_count': machine.queue_count,
            'live_temp': machine.get_live_temperature(),
            'display_status': machine.get_display_status(),
        })

    context = {
        'machines': machines,
        'machine_data': machine_data,
    }

    return render(request, 'calendarEditor/admin/admin_machines.html', context)


@staff_member_required
def edit_machine(request, machine_id):
    """Custom machine edit page."""
    machine = get_object_or_404(Machine, id=machine_id)

    if request.method == 'POST':
        # Get form data
        try:
            machine.name = request.POST.get('name', machine.name)
            machine.min_temp = float(request.POST.get('min_temp', machine.min_temp))
            machine.max_temp = float(request.POST.get('max_temp', machine.max_temp))
            machine.b_field_x = float(request.POST.get('b_field_x', machine.b_field_x))
            machine.b_field_y = float(request.POST.get('b_field_y', machine.b_field_y))
            machine.b_field_z = float(request.POST.get('b_field_z', machine.b_field_z))
            machine.b_field_direction = request.POST.get('b_field_direction', machine.b_field_direction)
            machine.dc_lines = int(request.POST.get('dc_lines', machine.dc_lines))
            machine.rf_lines = int(request.POST.get('rf_lines', machine.rf_lines))
            machine.daughterboard_type = request.POST.get('daughterboard_type', machine.daughterboard_type)
            machine.optical_capabilities = request.POST.get('optical_capabilities', machine.optical_capabilities)
            machine.cooldown_hours = int(request.POST.get('cooldown_hours', machine.cooldown_hours))
            machine.current_status = request.POST.get('current_status', machine.current_status)
            machine.is_available = request.POST.get('is_available') == 'on'
            machine.description = request.POST.get('description', machine.description)
            machine.location = request.POST.get('location', machine.location)

            machine.save()
            messages.success(request, f'Machine "{machine.name}" updated successfully.')
            return redirect('admin_machines')
        except (ValueError, TypeError) as e:
            messages.error(request, f'Error updating machine: {str(e)}')

    context = {
        'machine': machine,
    }

    return render(request, 'calendarEditor/admin/edit_machine.html', context)


@staff_member_required
def add_machine(request):
    """Custom machine creation page."""
    if request.method == 'POST':
        # Get form data and create new machine
        try:
            machine = Machine(
                name=request.POST.get('name'),
                min_temp=float(request.POST.get('min_temp')),
                max_temp=float(request.POST.get('max_temp')),
                b_field_x=float(request.POST.get('b_field_x', 0)),
                b_field_y=float(request.POST.get('b_field_y', 0)),
                b_field_z=float(request.POST.get('b_field_z', 0)),
                b_field_direction=request.POST.get('b_field_direction', 'none'),
                dc_lines=int(request.POST.get('dc_lines', 0)),
                rf_lines=int(request.POST.get('rf_lines', 0)),
                daughterboard_type=request.POST.get('daughterboard_type', ''),
                optical_capabilities=request.POST.get('optical_capabilities', 'none'),
                cooldown_hours=int(request.POST.get('cooldown_hours')),
                current_status=request.POST.get('current_status', 'idle'),
                is_available=request.POST.get('is_available') == 'on',
                description=request.POST.get('description', ''),
                location=request.POST.get('location', ''),
            )
            machine.save()
            messages.success(request, f'Machine "{machine.name}" created successfully.')
            return redirect('admin_machines')
        except (ValueError, TypeError) as e:
            messages.error(request, f'Error creating machine: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error creating machine: {str(e)}')

    return render(request, 'calendarEditor/admin/add_machine.html')


@staff_member_required
def delete_machine(request, machine_id):
    """Delete a machine."""
    if request.method == 'POST':
        machine = get_object_or_404(Machine, id=machine_id)
        machine_name = machine.name

        # Check if machine has any queue entries
        queue_count = QueueEntry.objects.filter(assigned_machine=machine).count()
        if queue_count > 0:
            messages.error(request, f'Cannot delete machine "{machine_name}" - it has {queue_count} queue entries assigned. Please reassign or remove these entries first.')
            return redirect('edit_machine', machine_id=machine_id)

        machine.delete()
        messages.success(request, f'Machine "{machine_name}" has been deleted.')
        return redirect('admin_machines')

    # If not POST, redirect back to edit page
    return redirect('edit_machine', machine_id=machine_id)


@staff_member_required
def admin_cancel_entry(request, entry_id):
    """Cancel (and archive) a queue entry - admin version."""
    if request.method != 'POST':
        return redirect('admin_queue')

    queue_entry = get_object_or_404(QueueEntry, id=entry_id)

    if queue_entry.status not in ['queued', 'running']:
        messages.error(request, 'Can only cancel queued or running entries.')
        return redirect('admin_queue')

    machine = queue_entry.assigned_machine
    is_rush = queue_entry.is_rush_job
    was_running = (queue_entry.status == 'running')
    entry_title = queue_entry.title
    machine_name = machine.name if machine else "Unknown Machine"
    entry_user = queue_entry.user

    # Cancel the entry
    queue_entry.status = 'cancelled'
    queue_entry.save()

    # Auto-clear all notifications related to this cancelled queue entry
    auto_clear_notifications(related_queue_entry=queue_entry)

    # Always archive canceled measurements
    try:
        ArchivedMeasurement.objects.create(
            user=entry_user,
            machine=machine,
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
        machine.current_status = 'idle'
        machine.current_user = None
        machine.estimated_available_time = None
        machine.save()

        # Notify the user that their running measurement was canceled by admin
        try:
            notifications.create_notification(
                recipient=entry_user,
                notification_type='queue_cancelled',
                title='❌ Measurement Canceled by Admin',
                message=f'Administrator {request.user.username} canceled your running measurement "{entry_title}" on {machine_name}.',
                related_queue_entry=queue_entry,
                related_machine=machine,
            )
        except Exception as e:
            print(f"User notification for admin-canceled measurement failed: {e}")

    # Reorder the queue for the machine
    if machine:
        reorder_queue(machine)

    messages.success(request, f'Entry "{entry_title}" has been canceled and archived.')
    return redirect('admin_queue')


@staff_member_required
def admin_queue(request):
    """Queue management page with machine overview."""
    # Get filter from query params
    status_filter = request.GET.get('status', 'queued')
    machine_filter = request.GET.get('machine', 'all')

    # Base queryset
    entries = QueueEntry.objects.select_related('user', 'assigned_machine').all()

    # Apply filters
    if status_filter != 'all':
        entries = entries.filter(status=status_filter)

    if machine_filter != 'all':
        entries = entries.filter(assigned_machine_id=machine_filter)

    # Order by machine, then running entries first (status != 'queued'), then by queue_position
    from django.db.models import Case, When, Value, IntegerField
    entries = entries.annotate(
        status_order=Case(
            When(status='running', then=Value(0)),
            When(status='queued', then=Value(1)),
            default=Value(2),
            output_field=IntegerField()
        )
    ).order_by('assigned_machine', 'status_order', 'queue_position', 'submitted_at')

    # Get all machines for filter dropdown and status overview
    machines = Machine.objects.all().order_by('name')

    # Build machine status overview
    machine_status_data = []
    for machine in machines:
        # Get running job
        running_job = QueueEntry.objects.filter(
            assigned_machine=machine,
            status='running'
        ).select_related('user').first()

        # Get on-deck job (position #1)
        on_deck_job = QueueEntry.objects.filter(
            assigned_machine=machine,
            status='queued',
            queue_position=1
        ).select_related('user').first()

        # Get queue count
        queue_count = QueueEntry.objects.filter(
            assigned_machine=machine,
            status='queued'
        ).count()

        machine_status_data.append({
            'machine': machine,
            'running_job': running_job,
            'on_deck_job': on_deck_job,
            'queue_count': queue_count,
            'live_temp': machine.get_live_temperature(),
            'display_status': machine.get_display_status(),
        })

    # Create a lookup dict for machines with running jobs (for template checks)
    machines_with_running_jobs = {
        machine.id: True
        for machine in machines
        if QueueEntry.objects.filter(assigned_machine=machine, status='running').exists()
    }

    # Organize entries by machine (including machines with no entries)
    machine_queue_data = []
    for machine in machines:
        # Always get running entry for this machine (Position 0), regardless of filter
        running_entry = QueueEntry.objects.filter(
            assigned_machine=machine,
            status='running'
        ).select_related('user').first()

        # Get entries for this machine from the filtered entries
        machine_entries = [entry for entry in entries if entry.assigned_machine == machine]

        # If there's a running entry and it's not already in the filtered list, add it at the beginning
        if running_entry and running_entry not in machine_entries:
            machine_entries.insert(0, running_entry)

        machine_queue_data.append({
            'machine': machine,
            'entries': machine_entries,
            'live_temp': machine.get_live_temperature(),
            'display_status': machine.get_display_status(),
        })

    # Add unassigned entries as a separate group
    unassigned_entries = [entry for entry in entries if entry.assigned_machine is None]
    if unassigned_entries:
        machine_queue_data.append({
            'machine': None,
            'entries': unassigned_entries,
        })

    context = {
        'entries': entries,
        'machine_queue_data': machine_queue_data,  # New: Organized by machine
        'status_filter': status_filter,
        'machine_filter': machine_filter,
        'machines': machines,
        'machine_status_data': machine_status_data,  # New: Machine overview data
        'machines_with_running_jobs': machines_with_running_jobs,  # For UI checks
    }

    return render(request, 'calendarEditor/admin/admin_queue.html', context)


@staff_member_required
def admin_rush_jobs(request):
    """Rush job approval page."""
    from .matching_algorithm import get_matching_machines

    rush_jobs = QueueEntry.objects.filter(
        is_rush_job=True,
        status='queued'
    ).select_related('user', 'assigned_machine').order_by('submitted_at')  # Oldest first

    # For each rush job, get matching machines
    rush_jobs_with_machines = []
    for job in rush_jobs:
        # Call get_matching_machines with individual parameters, not the QueueEntry object
        matching_machines = get_matching_machines(
            required_min_temp=job.required_min_temp,
            required_max_temp=job.required_max_temp,
            required_b_field_x=job.required_b_field_x,
            required_b_field_y=job.required_b_field_y,
            required_b_field_z=job.required_b_field_z
        )

        # Get live data for assigned machine if it exists
        live_temp = None
        display_status = None
        if job.assigned_machine:
            live_temp = job.assigned_machine.get_live_temperature()
            display_status = job.assigned_machine.get_display_status()

        rush_jobs_with_machines.append({
            'entry': job,
            'matching_machines': matching_machines,
            'live_temp': live_temp,
            'display_status': display_status,
        })

    context = {
        'rush_jobs_with_machines': rush_jobs_with_machines,
    }

    return render(request, 'calendarEditor/admin/admin_rush_jobs.html', context)


@staff_member_required
def approve_rush_job(request, entry_id):
    """Approve a rush job and queue it next."""
    from . import notifications

    entry = get_object_or_404(QueueEntry, id=entry_id)

    if entry.is_rush_job and entry.status == 'queued' and entry.assigned_machine:
        # Move to position 1 (queue next)
        machine = entry.assigned_machine

        # Find who is currently at position #1 (they will be bumped)
        current_on_deck = QueueEntry.objects.filter(
            assigned_machine=machine,
            status='queued',
            queue_position=1
        ).exclude(id=entry.id).first()

        queued_entries = QueueEntry.objects.filter(
            assigned_machine=machine,
            status='queued'
        ).exclude(id=entry.id).order_by('queue_position')

        # Shift all entries down
        for idx, other_entry in enumerate(queued_entries, start=2):
            other_entry.queue_position = idx
            other_entry.save()

        # Set this entry to position 1 and remove rush job flag
        entry.queue_position = 1
        entry.is_rush_job = False  # Remove from pending rush jobs list
        entry.save()

        # Auto-clear rush job notifications for this entry
        auto_clear_notifications(
            notification_type='admin_rush_job',
            related_queue_entry=entry
        )

        # Notify the person who was bumped from position #1
        if current_on_deck:
            current_on_deck.refresh_from_db()  # Get updated position
            notifications.notify_bumped_from_on_deck(current_on_deck, reason='rush job')

        # Notify the rush job user they're now on deck
        notifications.notify_on_deck(entry)

        messages.success(request, f'Rush job "{entry.title}" approved and moved to position 1 on {machine.name}.')
    else:
        messages.error(request, 'Cannot approve this entry.')

    return redirect('admin_rush_jobs')


@staff_member_required
def reject_rush_job(request, entry_id):
    """Reject a rush job (remove rush job flag)."""
    entry = get_object_or_404(QueueEntry, id=entry_id)

    if entry.is_rush_job:
        entry.is_rush_job = False
        entry.save()

        # Auto-clear rush job notifications for this entry
        auto_clear_notifications(
            notification_type='admin_rush_job',
            related_queue_entry=entry
        )

        messages.success(request, f'Rush job appeal for "{entry.title}" has been rejected.')
    else:
        messages.info(request, 'This entry is not marked as a rush job.')

    return redirect('admin_rush_jobs')


@staff_member_required
def reassign_machine(request, entry_id):
    """Reassign an entry to a different machine."""
    if request.method == 'POST':
        entry = get_object_or_404(QueueEntry, id=entry_id)
        new_machine_id = request.POST.get('machine_id')

        if new_machine_id:
            from .matching_algorithm import reorder_queue
            old_machine = entry.assigned_machine
            new_machine = get_object_or_404(Machine, id=new_machine_id)

            # Remove from old machine's queue
            if old_machine:
                reorder_queue(old_machine)

            # Assign to new machine
            entry.assigned_machine = new_machine
            entry.save()

            # Reorder new machine's queue
            reorder_queue(new_machine)

            messages.success(request, f'Entry "{entry.title}" reassigned to {new_machine.name}.')
        else:
            messages.error(request, 'No machine selected.')

    # Redirect based on referer
    referer = request.META.get('HTTP_REFERER', '')
    if 'rush' in referer:
        return redirect('admin_rush_jobs')
    else:
        return redirect('admin_queue')


@staff_member_required
def queue_next(request, entry_id):
    """Move an entry to position 1 in its machine's queue."""
    from . import notifications

    if request.method == 'POST':
        entry = get_object_or_404(QueueEntry, id=entry_id)

        if entry.status == 'queued' and entry.assigned_machine:
            machine = entry.assigned_machine

            # Find who is currently at position #1 (they will be bumped)
            current_on_deck = QueueEntry.objects.filter(
                assigned_machine=machine,
                status='queued',
                queue_position=1
            ).exclude(id=entry.id).first()

            queued_entries = QueueEntry.objects.filter(
                assigned_machine=machine,
                status='queued'
            ).exclude(id=entry.id).order_by('queue_position')

            # Shift all entries down
            for idx, other_entry in enumerate(queued_entries, start=2):
                other_entry.queue_position = idx
                other_entry.save()

            # Set this entry to position 1
            entry.queue_position = 1
            entry.save()

            # Notify the person who was bumped from position #1
            if current_on_deck:
                current_on_deck.refresh_from_db()  # Get updated position
                notifications.notify_bumped_from_on_deck(current_on_deck, reason='priority request')

            # Notify the user they're now on deck
            notifications.notify_on_deck(entry)

            messages.success(request, f'"{entry.title}" moved to position 1.')
        else:
            messages.error(request, 'Cannot queue this entry.')

    return redirect('admin_queue')


@staff_member_required
def move_queue_up(request, entry_id):
    """Move an entry up one position in the queue."""
    from . import notifications

    if request.method == 'POST':
        entry = get_object_or_404(QueueEntry, id=entry_id)

        if entry.status == 'queued' and entry.assigned_machine and entry.queue_position > 1:
            machine = entry.assigned_machine
            current_pos = entry.queue_position

            # Find entry above
            entry_above = QueueEntry.objects.filter(
                assigned_machine=machine,
                status='queued',
                queue_position=current_pos - 1
            ).first()

            if entry_above:
                # Remember if entry_above was at position #1 (they're being bumped)
                was_on_deck = (entry_above.queue_position == 1)

                # Swap positions
                new_pos = current_pos - 1
                entry.queue_position = new_pos
                entry_above.queue_position = current_pos
                entry.save()
                entry_above.save()

                # If entry moved to position 1, notify them they're on deck
                if new_pos == 1:
                    notifications.notify_on_deck(entry)

                # If entry_above was bumped from position #1, notify them
                if was_on_deck:
                    notifications.notify_bumped_from_on_deck(entry_above, reason='admin action')

                messages.success(request, f'"{entry.title}" moved up.')
            else:
                messages.warning(request, 'Cannot move up.')
        else:
            messages.error(request, 'Cannot move this entry.')

    return redirect('admin_queue')


@staff_member_required
def move_queue_down(request, entry_id):
    """Move an entry down one position in the queue."""
    from . import notifications

    if request.method == 'POST':
        entry = get_object_or_404(QueueEntry, id=entry_id)

        if entry.status == 'queued' and entry.assigned_machine:
            machine = entry.assigned_machine
            current_pos = entry.queue_position

            # Find entry below
            entry_below = QueueEntry.objects.filter(
                assigned_machine=machine,
                status='queued',
                queue_position=current_pos + 1
            ).first()

            if entry_below:
                # Remember if entry was at position #1 (they're being bumped)
                was_on_deck = (current_pos == 1)

                # Swap positions
                entry.queue_position = current_pos + 1
                entry_below.queue_position = current_pos
                entry.save()
                entry_below.save()

                # If entry was at position 1, they're being bumped
                if was_on_deck:
                    notifications.notify_bumped_from_on_deck(entry, reason='admin action')
                    # Notify entry_below they're now on deck
                    notifications.notify_on_deck(entry_below)

                messages.success(request, f'"{entry.title}" moved down.')
            else:
                messages.warning(request, 'Cannot move down.')
        else:
            messages.error(request, 'Cannot move this entry.')

    return redirect('admin_queue')


@staff_member_required
def admin_check_in(request, entry_id):
    """
    Admin override: Check in a user to start their measurement (ON DECK → RUNNING).

    Similar to user check_in_job but admin can start any user's job.
    """
    from datetime import timedelta
    from django.utils import timezone
    from . import notifications

    if request.method != 'POST':
        return redirect('admin_queue')

    queue_entry = get_object_or_404(QueueEntry, id=entry_id)

    # Validate entry can be checked in
    if queue_entry.status != 'queued':
        messages.error(request, f'Cannot check in - job status is "{queue_entry.get_status_display()}". Only queued jobs can be checked in.')
        return redirect('admin_queue')

    if queue_entry.queue_position != 1:
        messages.error(request, f'Cannot check in - job is position #{queue_entry.queue_position}. Only ON DECK (position #1) jobs can be checked in.')
        return redirect('admin_queue')

    if not queue_entry.assigned_machine:
        messages.error(request, 'Cannot check in - no machine assigned.')
        return redirect('admin_queue')

    # Check if machine is available and not in maintenance
    machine = queue_entry.assigned_machine

    if not machine.is_available:
        messages.error(request, f'Cannot check in - {machine.name} is currently unavailable. Please update machine settings first.')
        return redirect('admin_queue')

    if machine.current_status == 'maintenance':
        messages.error(request, f'Cannot check in - {machine.name} is under maintenance. Please update machine status first.')
        return redirect('admin_queue')

    # Check if machine already has a running job
    existing_running_job = QueueEntry.objects.filter(
        assigned_machine=machine,
        status='running'
    ).exclude(id=queue_entry.id).first()

    if existing_running_job:
        messages.error(request, f'Cannot check in - {machine.name} already has a running job by {existing_running_job.user.username}. Please complete that job first.')
        return redirect('admin_queue')

    # Start the job
    queue_entry.status = 'running'
    queue_entry.started_at = timezone.now()
    queue_entry.queue_position = None  # Remove from queue
    queue_entry.save()

    # Auto-clear queue status notifications (on_deck, ready_for_check_in, admin_check_in)
    auto_clear_notifications(related_queue_entry=queue_entry)

    # Update machine status
    machine.current_status = 'running'
    machine.current_user = queue_entry.user
    # Estimated available time = now + job duration + cooldown
    machine.estimated_available_time = timezone.now() + timedelta(
        hours=queue_entry.estimated_duration_hours + machine.cooldown_hours
    )
    machine.save()

    # Reorder queue (shift everyone up)
    # NOTE: reorder_queue() internally calls check_and_notify_on_deck_status()
    from .matching_algorithm import reorder_queue
    reorder_queue(machine)

    # Notify user that admin checked them in
    try:
        notifications.notify_admin_check_in(queue_entry, request.user)
    except Exception as e:
        print(f"Admin check-in notification failed: {e}")

    # Set reminder due time (replaces Celery scheduled task)
    queue_entry.reminder_due_at = queue_entry.started_at + timedelta(hours=queue_entry.estimated_duration_hours)
    queue_entry.reminder_sent = False
    queue_entry.save(update_fields=['reminder_due_at', 'reminder_sent'])

    # Broadcast WebSocket update
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'queue_updates',
            {
                'type': 'queue_update',
                'update_type': 'started',
                'entry_id': queue_entry.id,
                'user_id': queue_entry.user.id,
                'machine_id': machine.id,
            }
        )
    except Exception as e:
        print(f"WebSocket broadcast failed: {e}")

    messages.success(request, f'✅ Job started! "{queue_entry.title}" by {queue_entry.user.username} is now running on {machine.name}.')
    return redirect('admin_queue')


@staff_member_required
def admin_check_out(request, entry_id):
    """
    Admin override: Check out a user to complete their measurement (RUNNING → COMPLETED).

    Similar to user check_out_job but admin can complete any user's job.
    """
    from datetime import timedelta
    from django.utils import timezone
    from . import notifications

    if request.method != 'POST':
        return redirect('admin_queue')

    queue_entry = get_object_or_404(QueueEntry, id=entry_id)

    # Validate entry can be checked out
    if queue_entry.status != 'running':
        messages.error(request, f'Cannot check out - job status is "{queue_entry.get_status_display()}". Only running jobs can be checked out.')
        return redirect('admin_queue')

    if not queue_entry.assigned_machine:
        messages.error(request, 'Cannot check out - no machine assigned.')
        return redirect('admin_queue')

    # Complete the job
    queue_entry.status = 'completed'
    queue_entry.completed_at = timezone.now()
    queue_entry.save()

    # Auto-clear checkout reminder and admin_checkout notifications
    auto_clear_notifications(related_queue_entry=queue_entry)

    # Update machine status
    machine = queue_entry.assigned_machine

    # Check if there's someone else in the queue
    next_entry = QueueEntry.objects.filter(
        assigned_machine=machine,
        status='queued',
        queue_position=1
    ).first()

    if next_entry:
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

    # No need to cancel reminder - middleware checks status automatically
    # (Reminder won't send because entry status changed from 'running' to 'completed')

    # Reorder queue to ensure consistency (defensive programming)
    # NOTE: reorder_queue() internally calls check_and_notify_on_deck_status()
    from .matching_algorithm import reorder_queue
    reorder_queue(machine)

    # Notify the user that an admin checked them out
    notifications.notify_admin_checkout(queue_entry, request.user)

    # Notify next person if machine is available for check-in
    if next_entry:
        # If machine is immediately available (no cooldown), notify user they can check in
        if machine.current_status == 'idle':
            notifications.notify_ready_for_check_in(next_entry)

    # Broadcast WebSocket update
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'queue_updates',
            {
                'type': 'queue_update',
                'update_type': 'completed',
                'entry_id': queue_entry.id,
                'user_id': queue_entry.user.id,
                'machine_id': machine.id,
            }
        )
    except Exception as e:
        print(f"WebSocket broadcast failed: {e}")

    messages.success(request, f'🎉 Job completed! "{queue_entry.title}" by {queue_entry.user.username} is now archived.')
    return redirect('admin_queue')


@staff_member_required
def admin_presets(request):
    """Admin page for managing all presets (public and private)."""
    from .models import QueuePreset
    from django.db.models import Case, When, Value, CharField

    # Get all presets, organized by public/private, then by creator username
    presets = QueuePreset.objects.select_related('creator').all().order_by(
        '-is_public',  # Public first (True > False in descending order)
        'creator_username',  # Then by creator username
        'name'  # Then by preset name
    )

    # Group presets by public/private and then by user
    public_presets = {}
    private_presets = {}

    for preset in presets:
        username = preset.creator_username or 'Unknown User'

        if preset.is_public:
            if username not in public_presets:
                public_presets[username] = []
            public_presets[username].append(preset)
        else:
            if username not in private_presets:
                private_presets[username] = []
            private_presets[username].append(preset)

    # Sort usernames alphabetically for display
    public_presets = dict(sorted(public_presets.items()))
    private_presets = dict(sorted(private_presets.items()))

    context = {
        'public_presets': public_presets,
        'private_presets': private_presets,
        'total_public': sum(len(presets) for presets in public_presets.values()),
        'total_private': sum(len(presets) for presets in private_presets.values()),
        'current_user': request.user,  # Pass current user for permission checks
    }

    return render(request, 'calendarEditor/admin/admin_presets.html', context)


@staff_member_required
def admin_edit_entry(request, entry_id):
    """
    Admin page for editing queue entries.
    Only queued entries can be edited.
    """
    queue_entry = get_object_or_404(QueueEntry, id=entry_id)

    # Only allow editing queued entries
    if queue_entry.status != 'queued':
        messages.error(request, f'Cannot edit entry with status "{queue_entry.status}". Only queued entries can be edited.')
        return redirect('admin_queue')

    # Store original values for change tracking
    original_values = {
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
        'required_daughterboard': queue_entry.required_daughterboard,
        'requires_optical': queue_entry.requires_optical,
        'estimated_duration_hours': queue_entry.estimated_duration_hours,
        'special_requirements': queue_entry.special_requirements,
        'is_rush_job': queue_entry.is_rush_job,
        'assigned_machine': queue_entry.assigned_machine,
    }

    if request.method == 'POST':
        # Check if this is a confirmation submit (after showing machine change warning)
        confirmed = request.POST.get('confirmed') == 'true'

        form = QueueEntryForm(request.POST, instance=queue_entry)

        if form.is_valid():
            # Save form but don't commit yet
            edited_entry = form.save(commit=False)

            # Check if requirements still match current machine
            old_machine = queue_entry.assigned_machine
            best_machine, compatibility_score = find_best_machine(edited_entry, return_details=True)

            # If machine would change and user hasn't confirmed, show warning
            if best_machine != old_machine and not confirmed:
                context = {
                    'queue_entry': queue_entry,
                    'form': form,
                    'show_machine_warning': True,
                    'old_machine': old_machine,
                    'new_machine': best_machine,
                    'compatibility_score': compatibility_score,
                }
                return render(request, 'calendarEditor/admin/admin_edit_entry.html', context)

            # Check if we have a compatible machine
            if best_machine is None:
                messages.error(request, 'No compatible machines found for these requirements. Please adjust the requirements.')
                form.add_error(None, 'No compatible machines found for these requirements.')
                context = {
                    'queue_entry': queue_entry,
                    'form': form,
                }
                return render(request, 'calendarEditor/admin/admin_edit_entry.html', context)

            # Save the changes
            edited_entry.assigned_machine = best_machine
            edited_entry.save()

            # If machine changed, reorder queues
            if old_machine != best_machine:
                # Remove from old machine's queue and reorder
                if old_machine:
                    reorder_queue(old_machine)
                # Add to new machine's queue and reorder
                reorder_queue(best_machine)

            # Track changes for notification
            changes = []
            if original_values['title'] != edited_entry.title:
                changes.append('title')
            if original_values['description'] != edited_entry.description:
                changes.append('description')
            if (original_values['required_min_temp'] != edited_entry.required_min_temp or
                original_values['required_max_temp'] != edited_entry.required_max_temp):
                changes.append('temperature requirements')
            if (original_values['required_b_field_x'] != edited_entry.required_b_field_x or
                original_values['required_b_field_y'] != edited_entry.required_b_field_y or
                original_values['required_b_field_z'] != edited_entry.required_b_field_z or
                original_values['required_b_field_direction'] != edited_entry.required_b_field_direction):
                changes.append('B-field requirements')
            if (original_values['required_dc_lines'] != edited_entry.required_dc_lines or
                original_values['required_rf_lines'] != edited_entry.required_rf_lines):
                changes.append('connection requirements')
            if original_values['required_daughterboard'] != edited_entry.required_daughterboard:
                changes.append('daughterboard')
            if original_values['requires_optical'] != edited_entry.requires_optical:
                changes.append('optical requirements')
            if original_values['estimated_duration_hours'] != edited_entry.estimated_duration_hours:
                changes.append('duration')
            if original_values['special_requirements'] != edited_entry.special_requirements:
                changes.append('special requirements')
            if original_values['is_rush_job'] != edited_entry.is_rush_job:
                changes.append('rush job status')
            if old_machine != best_machine:
                changes.append(f'machine assignment (moved to {best_machine.name})')

            # Create change summary for notification
            if changes:
                changes_summary = ', '.join(changes)
            else:
                changes_summary = 'minor updates'

            # Send notification to user
            notifications.notify_admin_edit_entry(edited_entry, request.user, changes_summary)

            messages.success(request, f'Queue entry "{edited_entry.title}" updated successfully.')
            return redirect('admin_queue')

        else:
            # Form has validation errors
            context = {
                'queue_entry': queue_entry,
                'form': form,
            }
            return render(request, 'calendarEditor/admin/admin_edit_entry.html', context)

    else:
        # GET request - show form
        form = QueueEntryForm(instance=queue_entry)
        context = {
            'queue_entry': queue_entry,
            'form': form,
        }
        return render(request, 'calendarEditor/admin/admin_edit_entry.html', context)
