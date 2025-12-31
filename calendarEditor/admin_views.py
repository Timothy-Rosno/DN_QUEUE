from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from django.db.models import Count, Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.db import transaction
from django.conf import settings
from userRegistration.models import UserProfile
from .models import Machine, QueueEntry, QueuePreset, ArchivedMeasurement, Notification, NotificationPreference
from .notifications import auto_clear_notifications
from .views import reorder_queue
from . import notifications
from .forms import QueueEntryForm
from .matching_algorithm import find_best_machine, get_compatible_machines, set_queue_position


@staff_member_required
@never_cache
def admin_dashboard(request):
    """Main admin dashboard with overview stats."""
    # Get stats - exclude staff/superusers from pending count
    pending_users = UserProfile.objects.filter(
        Q(status='pending') | Q(status='rejected')  # Count both pending and rejected as needing attention
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
@never_cache
def admin_users(request):
    """User management page with improved status filtering."""
    # Get filter from query params
    status_filter = request.GET.get('status', 'all')

    # Base queryset - only users with profiles
    users = User.objects.select_related('profile').filter(profile__isnull=False)

    # Apply filters
    if status_filter == 'pending':
        # Pending users: status='pending' AND not staff/superuser
        users = users.filter(
            profile__status='pending'
        ).exclude(
            Q(is_staff=True) | Q(is_superuser=True)
        )
    elif status_filter == 'rejected':
        # Rejected users: status='rejected' AND not staff/superuser
        users = users.filter(
            profile__status='rejected'
        ).exclude(
            Q(is_staff=True) | Q(is_superuser=True)
        )
    elif status_filter == 'approved':
        users = users.filter(profile__status='approved')
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

    # Split users into unapproved (pending + rejected) and approved for the new design
    unapproved_users = []
    approved_users = []

    for user_item in users:
        if user_item.is_staff or user_item.is_superuser:
            approved_users.append(user_item)
        elif user_item.profile.status == 'approved':
            approved_users.append(user_item)
        else:  # pending or rejected
            unapproved_users.append(user_item)

    # Sort alphabetically by username
    unapproved_users.sort(key=lambda u: u.username.lower())
    approved_users.sort(key=lambda u: u.username.lower())

    # === PER-USER ANALYTICS (OPTIMIZED) ===
    from .models import PageView, QueueEntry, Feedback
    from django.db.models import Max, Count, Q
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()
    days_filter = 30  # Default to last 30 days for admin-users
    start_date = now - timedelta(days=days_filter)

    # OPTIMIZED: Single aggregated query instead of N+1 queries
    all_users = User.objects.select_related('profile').annotate(
        page_views_period=Count(
            'pageview__id',
            filter=Q(pageview__created_at__gte=start_date) if start_date else Q(),
            distinct=True
        ),
        page_views_all_time=Count('pageview__id', distinct=True),
        last_seen=Max('pageview__created_at'),
        queue_entries_period=Count(
            'queue_entries__id',
            filter=Q(queue_entries__created_at__gte=start_date) if start_date else Q(),
            distinct=True
        ),
        queue_entries_all_time=Count('queue_entries__id', distinct=True),
        feedback_submitted_period=Count(
            'feedback_submissions__id',
            filter=Q(feedback_submissions__created_at__gte=start_date) if start_date else Q(),
            distinct=True
        ),
        feedback_submitted_all_time=Count('feedback_submissions__id', distinct=True),
    )
    # Don't filter - show all users including those with 0 activity

    # Build per-user stats from annotated query
    per_user_stats = []
    for user in all_users:
        # Build roles list
        roles = []
        if user.is_superuser:
            roles.append('Admin')
            roles.append('Developer')
            roles.append('Staff')
        elif hasattr(user, 'profile') and user.profile.is_developer:
            roles.append('Developer')
            roles.append('Staff')
        elif user.is_staff:
            roles.append('Staff')

        if not roles:
            roles.append('User')

        per_user_stats.append({
            'user': user,
            'page_views': user.page_views_period,
            'queue_submissions': user.queue_entries_period,
            'feedback_count': user.feedback_submitted_period,
            'last_activity': user.last_seen,
            'roles': roles,
        })

    # Sort by page views (most active first)
    per_user_stats.sort(key=lambda x: x['page_views'], reverse=True)

    context = {
        'users': users,
        'unapproved_users': unapproved_users,
        'approved_users': approved_users,
        'status_filter': status_filter,
        'search_query': search_query,
        'per_user_stats': per_user_stats,
        'days_filter': days_filter,
    }

    return render(request, 'calendarEditor/admin/admin_users.html', context)


@staff_member_required
def approve_user(request, user_id):
    """Approve a user (set status to 'approved')."""
    user = get_object_or_404(User, id=user_id)

    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)

    if profile.status != 'approved':
        profile.status = 'approved'
        profile.is_approved = True  # Keep legacy field in sync
        profile.approved_by = request.user
        profile.approved_at = timezone.now()
        profile.save()

        # Auto-clear all "new user signup" notifications for this user
        auto_clear_notifications(
            notification_type='admin_new_user',
            triggering_user=user
        )

        # Send notification to the user via the notification system (Slack first, then email fallback)
        notifications.create_notification(
            recipient=user,
            notification_type='account_approved',
            title='Your account has been approved!',
            message=f'Great news! Your account has been approved by {request.user.username}. You can now log in and access all features of the scheduler system.',
            triggering_user=request.user,
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
    """Reject/unapprove a user (set status to 'rejected'). Staff can only be unapproved by superusers."""
    user = get_object_or_404(User, id=user_id)

    # Only superusers can unapprove staff users
    if (user.is_staff or user.is_superuser) and not request.user.is_superuser:
        messages.error(request, f'Only superusers can unapprove staff users.')
        return redirect('admin_users')

    try:
        profile = user.profile
        if profile.status == 'approved':
            # Unapprove an approved user -> set to 'pending'
            profile.status = 'pending'
            profile.is_approved = False  # Keep legacy field in sync
            profile.approved_by = None
            profile.approved_at = None
            profile.save()

            # Send notification to the user via the notification system (Slack first, then email fallback)
            notifications.create_notification(
                recipient=user,
                notification_type='account_unapproved',
                title='Your account has been unapproved',
                message=f'Your account has been unapproved by {request.user.username}. You will need to contact an administrator for more information.',
                triggering_user=request.user,
            )

            messages.success(request, f'User {user.username} has been unapproved.')
        elif profile.status == 'pending':
            # Reject a pending user -> set to 'rejected'
            profile.status = 'rejected'
            profile.is_approved = False  # Keep legacy field in sync
            profile.save()

            # Auto-clear all "new user signup" notifications for this user (task completed)
            auto_clear_notifications(
                notification_type='admin_new_user',
                triggering_user=user
            )

            # Send notification to the user via the notification system (Slack first, then email fallback)
            notifications.create_notification(
                recipient=user,
                notification_type='account_unapproved',
                title='Your account has been rejected',
                message=f'Your account request has been rejected by {request.user.username}. Contact an administrator if you believe this is a mistake.',
                triggering_user=request.user,
            )

            messages.success(request, f'User {user.username} has been rejected.')
        else:
            messages.info(request, f'User {user.username} is already rejected.')
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
                if profile.status != 'approved':
                    profile.status = 'approved'
                    profile.is_approved = True  # Keep legacy field in sync
                    profile.approved_by = request.user
                    profile.approved_at = timezone.now()
                    profile.save()
            except UserProfile.DoesNotExist:
                pass

            # Send notification to the user via the notification system (Slack first, then email fallback)
            notifications.create_notification(
                recipient=user,
                notification_type='account_promoted',
                title='You have been promoted to staff',
                message=f'Congratulations! Admin {request.user.username} has promoted you to staff. You now have access to administrative features.',
                triggering_user=request.user,
            )

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

            # Send notification to the user via the notification system (Slack first, then email fallback)
            notifications.create_notification(
                recipient=user,
                notification_type='account_demoted',
                title='You have been demoted from staff',
                message=f'Admin {request.user.username} has demoted you from staff to regular user. You no longer have access to administrative features.',
                triggering_user=request.user,
            )

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
def admin_edit_user_info(request, user_id=None):
    """Edit all user information (username, email, name, security question, etc.)."""
    from userRegistration.forms import AdminEditUserForm

    if user_id:
        # Edit existing user
        user_to_edit = get_object_or_404(User, id=user_id)

        if request.method == 'POST':
            form = AdminEditUserForm(user_to_edit, request.POST)
            if form.is_valid():
                # Track changes for notification
                changed_fields = []

                # Check user model field changes
                if user_to_edit.username != form.cleaned_data['username']:
                    changed_fields.append(f"Username: {user_to_edit.username} → {form.cleaned_data['username']}")
                if user_to_edit.email != form.cleaned_data['email']:
                    changed_fields.append(f"Email: {user_to_edit.email} → {form.cleaned_data['email']}")
                if user_to_edit.first_name != form.cleaned_data['first_name']:
                    changed_fields.append(f"First Name: {user_to_edit.first_name} → {form.cleaned_data['first_name']}")
                if user_to_edit.last_name != form.cleaned_data['last_name']:
                    changed_fields.append(f"Last Name: {user_to_edit.last_name} → {form.cleaned_data['last_name']}")

                # Update user model fields
                user_to_edit.username = form.cleaned_data['username']
                user_to_edit.email = form.cleaned_data['email']
                user_to_edit.first_name = form.cleaned_data['first_name']
                user_to_edit.last_name = form.cleaned_data['last_name']
                user_to_edit.save()

                # Update profile fields
                try:
                    profile = user_to_edit.profile
                except UserProfile.DoesNotExist:
                    profile = UserProfile.objects.create(user=user_to_edit)

                # Check profile field changes
                if profile.phone_number != form.cleaned_data['phone_number']:
                    changed_fields.append(f"Phone Number: {profile.phone_number or '(empty)'} → {form.cleaned_data['phone_number'] or '(empty)'}")
                if profile.department != form.cleaned_data['department']:
                    changed_fields.append(f"Department: {profile.department or '(empty)'} → {form.cleaned_data['department'] or '(empty)'}")
                if profile.notes != form.cleaned_data['notes']:
                    changed_fields.append(f"Notes: {profile.notes or '(empty)'} → {form.cleaned_data['notes'] or '(empty)'}")
                if profile.slack_member_id != form.cleaned_data['slack_member_id']:
                    changed_fields.append(f"Slack Member ID: {profile.slack_member_id or '(empty)'} → {form.cleaned_data['slack_member_id'] or '(empty)'}")
                if profile.security_question != form.cleaned_data['security_question']:
                    changed_fields.append("Security Question changed")
                if profile.security_question_custom != form.cleaned_data['security_question_custom']:
                    changed_fields.append("Custom Security Question changed")
                if form.cleaned_data['security_answer']:
                    changed_fields.append("Security Answer changed")

                profile.phone_number = form.cleaned_data['phone_number']
                profile.department = form.cleaned_data['department']
                profile.notes = form.cleaned_data['notes']
                profile.slack_member_id = form.cleaned_data['slack_member_id']
                profile.security_question = form.cleaned_data['security_question']
                profile.security_question_custom = form.cleaned_data['security_question_custom']

                # Update security answer if provided
                if form.cleaned_data['security_answer']:
                    profile.set_security_answer(form.cleaned_data['security_answer'])

                profile.save()

                # Send notification if any fields were changed
                if changed_fields:
                    changes_text = "\n".join(f"• {change}" for change in changed_fields)
                    notifications.create_notification(
                        recipient=user_to_edit,
                        notification_type='account_info_changed',
                        title='Admin changed your account information',
                        message=f'Admin {request.user.username} updated your account information:\n\n{changes_text}',
                        triggering_user=request.user,
                    )

                messages.success(request, f'User information for {user_to_edit.username} updated successfully.')
                return redirect('admin_users')
        else:
            form = AdminEditUserForm(user_to_edit)

        context = {
            'form': form,
            'user_to_edit': user_to_edit,
        }
        return render(request, 'calendarEditor/admin/admin_edit_user_info.html', context)
    else:
        # Display dropdown to select user
        all_users = User.objects.select_related('profile').order_by('username')
        context = {
            'all_users': all_users,
        }
        return render(request, 'calendarEditor/admin/admin_select_user_to_edit.html', context)


@staff_member_required
@never_cache
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
            old_status = machine.current_status
            old_is_available = machine.is_available
            machine.current_status = request.POST.get('current_status', machine.current_status)
            machine.is_available = request.POST.get('is_available') == 'on'
            machine.description = request.POST.get('description', machine.description)
            machine.location = request.POST.get('location', machine.location)

            # Auto-set unavailable when machine is put in maintenance mode
            if machine.current_status == 'maintenance':
                machine.is_available = False

            machine.save()

            # Notify position 1 user when machine goes TO maintenance (unavailable)
            if machine.current_status == 'maintenance' and old_status != 'maintenance':
                next_entry = QueueEntry.objects.filter(
                    assigned_machine=machine,
                    status='queued',
                    queue_position=1
                ).first()

                if next_entry:
                    # Send on_deck notification (machine not available)
                    notifications.check_and_notify_on_deck_status(machine)

            # Notify position 1 user when machine goes back to idle + available
            if machine.current_status == 'idle' and machine.is_available and (old_status != 'idle' or not old_is_available):
                next_entry = QueueEntry.objects.filter(
                    assigned_machine=machine,
                    status='queued',
                    queue_position=1
                ).first()

                if next_entry:
                    # Send ready for check-in notification
                    notifications.check_and_notify_on_deck_status(machine)

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
            # Auto-set unavailable when machine is in maintenance mode
            if machine.current_status == 'maintenance':
                machine.is_available = False
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
    """Delete a machine. Active queue entries are automatically archived as 'orphaned'."""
    if request.method == 'POST':
        machine = get_object_or_404(Machine, id=machine_id)
        machine_name = machine.name

        # Find all active queue entries (queued or running) for this machine
        active_entries = QueueEntry.objects.filter(
            assigned_machine=machine,
            status__in=['queued', 'running']
        )
        active_queue_count = active_entries.count()

        # Check if user confirmed the deletion
        confirmed = request.POST.get('confirmed') == 'true'

        if active_queue_count > 0 and not confirmed:
            # Return to edit page with warning - template will show confirmation modal
            messages.warning(request, f'Machine "{machine_name}" has {active_queue_count} active queue entries that will be archived as orphaned. Confirm deletion to proceed.')
            return redirect(f'/schedule/admin-machines/edit/{machine_id}/?delete_confirm=1&active_count={active_queue_count}')

        # Archive all active queue entries as 'orphaned' before deleting the machine
        orphaned_count = 0
        if active_queue_count > 0:
            try:
                for entry in active_entries:
                    # Create an archived measurement for this orphaned entry
                    ArchivedMeasurement.objects.create(
                        user=entry.user,
                        machine=None,  # Machine FK will be NULL since we're about to delete it
                        machine_name=machine_name,  # Preserve machine name as string
                        related_queue_entry=entry,
                        title=entry.title,
                        notes=entry.description,
                        measurement_date=entry.started_at if entry.status == 'running' else entry.submitted_at,
                        archived_at=timezone.now(),
                        status='orphaned'  # Mark as orphaned since machine was deleted
                    )

                    # Notify the user that their entry was orphaned
                    try:
                        notifications.create_notification(
                            recipient=entry.user,
                            notification_type='queue_cancelled',
                            title='Entry Orphaned - Machine Deleted',
                            message=f'Your {"running measurement" if entry.status == "running" else "queue entry"} "{entry.title}" on {machine_name} has been orphaned because the machine was deleted by an administrator.',
                            related_queue_entry=entry,
                        )
                    except Exception as notif_error:
                        print(f"Failed to notify user about orphaned entry: {notif_error}")

                    # Update the queue entry status to cancelled (since machine is gone)
                    entry.status = 'cancelled'
                    entry.save(update_fields=['status'])

                    orphaned_count += 1
            except Exception as e:
                messages.error(request, f'Error archiving queue entries: {str(e)}')
                return redirect('admin_machines')

        # Before deleting, preserve machine_name in all existing archived measurements
        try:
            archives = ArchivedMeasurement.objects.filter(machine=machine)
            for archive in archives:
                if not archive.machine_name:  # Only update if not already set
                    archive.machine_name = machine_name
                    archive.save(update_fields=['machine_name'])
        except Exception as e:
            print(f'Warning: Failed to preserve machine name in archives: {str(e)}')

        # Delete the machine (archives will have machine FK set to NULL due to SET_NULL)
        machine.delete()

        if orphaned_count > 0:
            messages.success(request, f'Machine "{machine_name}" has been deleted. {orphaned_count} active queue entries have been archived as orphaned.')
        else:
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

    # Notify the user that their entry was canceled by admin
    try:
        if was_running:
            notifications.create_notification(
                recipient=entry_user,
                notification_type='queue_cancelled',
                title='Measurement Canceled by Admin',
                message=f'Administrator {request.user.username} canceled your running measurement "{entry_title}" on {machine_name}.',
                related_queue_entry=queue_entry,
                related_machine=machine,
            )
        else:
            # Notify for queued entry cancellation
            notifications.create_notification(
                recipient=entry_user,
                notification_type='queue_cancelled',
                title='Queue Entry Canceled by Admin',
                message=f'Administrator {request.user.username} canceled your queue entry "{entry_title}" on {machine_name}.',
                related_queue_entry=queue_entry,
                related_machine=machine,
            )
    except Exception as e:
        print(f"User notification for admin-canceled entry failed: {e}")

    # If canceling a running measurement, clean up machine status
    if was_running and machine:
        machine.current_status = 'idle'
        machine.current_user = None
        machine.estimated_available_time = None
        machine.save()

    # Reorder the queue for the machine
    if machine:
        reorder_queue(machine)

        # If a running measurement was cancelled, notify position 1 they can now check in
        # (reorder_queue won't do this because position 1 didn't change)
        if was_running:
            try:
                notifications.check_and_notify_on_deck_status(machine)
            except Exception as e:
                print(f"On-deck notification after cancel failed: {e}")

    messages.success(request, f'Entry "{entry_title}" has been canceled and archived.')
    return redirect('admin_queue')


@staff_member_required
@never_cache
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
@never_cache
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
        old_position = entry.queue_position if entry.queue_position is not None else "unknown"

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

        # Step 1: Set target entry to NULL to avoid conflicts
        entry.queue_position = None
        entry.save()

        # Step 2: Reassign positions to all other entries in REVERSE order
        queued_entries_list = list(queued_entries)
        for idx in range(len(queued_entries_list) - 1, -1, -1):
            other_entry = queued_entries_list[idx]
            other_entry.queue_position = idx + 2  # Positions start at 2
            other_entry.save()

        # Step 3: Set this entry to position 1 and remove rush job flag
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
            current_on_deck.refresh_from_db()
            notifications.notify_bumped_from_on_deck(current_on_deck, reason='rush job')

        # Notify the rush job user they've been moved to position 1
        notifications.notify_admin_moved_entry(entry, request.user, old_position, 1)

        # Notify all admins on Slack that rush job has been approved (task complete)
        notifications.notify_admins_rush_job_approved(entry, request.user)

        messages.success(request, f'Rush job "{entry.title}" approved and moved to position 1 on {machine.name}.')
    else:
        messages.error(request, 'Cannot approve this entry.')

    return redirect('admin_rush_jobs')


@staff_member_required
def reject_rush_job(request, entry_id):
    """Reject a rush job with optional custom rejection message."""
    entry = get_object_or_404(QueueEntry, id=entry_id)

    if entry.is_rush_job:
        # Get rejection message from POST data (default to "Insufficient justification")
        rejection_message = request.POST.get('rejection_message', 'Insufficient justification').strip()
        if not rejection_message:
            rejection_message = 'Insufficient justification'

        entry.is_rush_job = False
        entry.save()

        # Auto-clear rush job notifications for this entry
        auto_clear_notifications(
            notification_type='admin_rush_job',
            related_queue_entry=entry
        )

        # Send notification to user with rejection message
        notifications.create_notification(
            recipient=entry.user,
            notification_type='queue_cancelled',
            title=f'Rush Job/Special Request Appeal Rejected: {entry.title}',
            message=f'Your rush job appeal for "{entry.title}" has been rejected by {request.user.username}.\n\nReason: {rejection_message}\n\nYour job remains in the queue at its current position.',
            related_queue_entry=entry,
            related_machine=entry.assigned_machine,
            triggering_user=request.user,
        )

        # Notify all admins on Slack that rush job has been rejected (task complete)
        notifications.notify_admins_rush_job_rejected(entry, request.user, rejection_message)

        messages.success(request, f'Rush job appeal for "{entry.title}" has been rejected. User notified.')
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
            old_position = entry.queue_position if entry.queue_position is not None else "unknown"

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

            # Step 1: Set the target entry to NULL first to avoid conflicts
            entry.queue_position = None
            entry.save()

            # Step 2: Reassign positions to all other entries in REVERSE order
            # This prevents UNIQUE constraint violations (update highest positions first)
            queued_entries_list = list(queued_entries)
            for idx in range(len(queued_entries_list) - 1, -1, -1):
                other_entry = queued_entries_list[idx]
                other_entry.queue_position = idx + 2  # Positions start at 2
                other_entry.save()

            # Step 3: Set the target entry to position 1
            entry.queue_position = 1
            entry.save()

            # Broadcast WebSocket update for real-time page refresh
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync

                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    'queue_updates',
                    {
                        'type': 'queue_update',
                        'update_type': 'moved_to_first',
                        'entry_id': entry.id,
                        'user_id': entry.user.id,
                        'machine_id': machine.id,
                        'machine_name': machine.name,
                        'triggering_user_id': request.user.id,
                    }
                )
            except Exception as e:
                # Don't fail the operation if WebSocket broadcast fails
                print(f"WebSocket broadcast error in queue_next: {e}")

            # Notify the person who was bumped from position #1
            if current_on_deck:
                current_on_deck.refresh_from_db()
                notifications.notify_bumped_from_on_deck(current_on_deck, reason='priority request')

            # Notify the moved entry with admin-specific notification
            notifications.notify_admin_moved_entry(entry, request.user, old_position, 1)

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

        if entry.status == 'queued' and entry.assigned_machine and entry.queue_position is not None and entry.queue_position > 1:
            machine = entry.assigned_machine
            current_pos = entry.queue_position

            # Find entry above
            entry_above = QueueEntry.objects.filter(
                assigned_machine=machine,
                status='queued',
                queue_position=current_pos - 1
            ).first()

            if entry_above:
                # Swap positions using NULL as temporary value to avoid UNIQUE constraint violation
                new_pos = current_pos - 1

                # Step 1: Set entry to NULL temporarily
                entry.queue_position = None
                entry.save()

                # Step 2: Update entry_above to the old position
                entry_above.queue_position = current_pos
                entry_above.save()

                # Step 3: Set entry to its new position
                entry.queue_position = new_pos
                entry.save()

                # Broadcast WebSocket update for real-time page refresh
                try:
                    from channels.layers import get_channel_layer
                    from asgiref.sync import async_to_sync

                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        'queue_updates',
                        {
                            'type': 'queue_update',
                            'update_type': 'position_changed',
                            'entry_id': entry.id,
                            'user_id': entry.user.id,
                            'machine_id': machine.id,
                            'machine_name': machine.name,
                            'triggering_user_id': request.user.id,
                        }
                    )
                except Exception as e:
                    # Don't fail the operation if WebSocket broadcast fails
                    print(f"WebSocket broadcast error in move_queue_up: {e}")

                # Notify only the moved entry with admin-specific notification
                notifications.notify_admin_moved_entry(entry, request.user, current_pos, new_pos)

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

        if entry.status == 'queued' and entry.assigned_machine and entry.queue_position is not None:
            machine = entry.assigned_machine
            current_pos = entry.queue_position

            # Find entry below
            entry_below = QueueEntry.objects.filter(
                assigned_machine=machine,
                status='queued',
                queue_position=current_pos + 1
            ).first()

            if entry_below:
                # Swap positions using NULL as temporary value to avoid UNIQUE constraint violation
                new_pos = current_pos + 1

                # Step 1: Set entry to NULL temporarily
                entry.queue_position = None
                entry.save()

                # Step 2: Update entry_below to the old position
                entry_below.queue_position = current_pos
                entry_below.save()

                # Step 3: Set entry to its new position
                entry.queue_position = new_pos
                entry.save()

                # Broadcast WebSocket update for real-time page refresh
                try:
                    from channels.layers import get_channel_layer
                    from asgiref.sync import async_to_sync

                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        'queue_updates',
                        {
                            'type': 'queue_update',
                            'update_type': 'position_changed',
                            'entry_id': entry.id,
                            'user_id': entry.user.id,
                            'machine_id': machine.id,
                            'machine_name': machine.name,
                            'triggering_user_id': request.user.id,
                        }
                    )
                except Exception as e:
                    # Don't fail the operation if WebSocket broadcast fails
                    print(f"WebSocket broadcast error in move_queue_down: {e}")

                # Notify only the moved entry with admin-specific notification
                notifications.notify_admin_moved_entry(entry, request.user, current_pos, new_pos)

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

    if queue_entry.queue_position is None or queue_entry.queue_position != 1:
        messages.error(request, f'Cannot check in - job is position #{queue_entry.queue_position if queue_entry.queue_position is not None else "unknown"}. Only ON DECK (position #1) jobs can be checked in.')
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

    # Set checkout reminder fields
    queue_entry.reminder_due_at = queue_entry.started_at + timedelta(hours=queue_entry.estimated_duration_hours)
    queue_entry.last_reminder_sent_at = None
    queue_entry.reminder_snoozed_until = None

    # Clear check-in reminder fields (no longer at position 1)
    queue_entry.checkin_reminder_due_at = None
    queue_entry.last_checkin_reminder_sent_at = None
    queue_entry.checkin_reminder_snoozed_until = None

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
                'machine_name': machine.name,
                'triggering_user_id': request.user.id,
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
        import traceback
        traceback.print_exc()

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

    print(f"[ADMIN CHECKOUT] Completed checkout for {queue_entry.title} on {machine.name}")
    print(f"[ADMIN CHECKOUT] Machine status after checkout: {machine.current_status}, is_available: {machine.is_available}")

    # DIRECTLY notify the next person in line - bypass all complex logic
    if next_entry:
        print(f"[ADMIN CHECKOUT] DIRECTLY creating notification for {next_entry.user.username}")
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
            print(f"[ADMIN CHECKOUT] Created notification {notif.id} in database")

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
                print(f"[ADMIN CHECKOUT] WebSocket sent for notification {notif.id}")
            except Exception as ws_err:
                print(f"[ADMIN CHECKOUT] WebSocket failed but notification {notif.id} still in DB: {ws_err}")

            # Send via Slack if enabled (don't wait for it)
            if settings.SLACK_ENABLED:
                try:
                    notifications.send_slack_dm(next_entry.user, notif.title, notif.message, notif)
                    print(f"[ADMIN CHECKOUT] Slack sent for notification {notif.id}")
                except Exception as slack_err:
                    print(f"[ADMIN CHECKOUT] Slack failed but notification {notif.id} still in DB: {slack_err}")

        except Exception as e:
            print(f"[ADMIN CHECKOUT] ERROR creating notification: {e}")
            import traceback
            traceback.print_exc()

    # No need to cancel reminder - middleware checks status automatically
    # (Reminder won't send because entry status changed from 'running' to 'completed')

    # Reorder queue (skip notifications since we already sent them)
    print(f"[ADMIN CHECKOUT] Calling reorder_queue for {machine.name}")
    from .matching_algorithm import reorder_queue
    reorder_queue(machine, notify=False)

    # Notify the user that an admin checked them out
    notifications.notify_admin_checkout(queue_entry, request.user)

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
                'machine_name': machine.name,
                'triggering_user_id': request.user.id,
            }
        )
    except Exception as e:
        print(f"WebSocket broadcast failed: {e}")

    messages.success(request, f'🎉 Job completed! "{queue_entry.title}" by {queue_entry.user.username} is now archived.')
    return redirect('admin_queue')


@staff_member_required
def admin_undo_check_in(request, entry_id):
    """
    Admin override: Undo a check-in to move running entry back to on-deck position (RUNNING → QUEUED at position 1).

    Similar to user undo_check_in but admin can undo any user's job and notifies the user about admin action.
    """
    from datetime import timedelta
    from django.utils import timezone
    from . import notifications

    if request.method != 'POST':
        return redirect('admin_queue')

    queue_entry = get_object_or_404(QueueEntry, id=entry_id)

    # Validate entry can be undone
    if queue_entry.status != 'running':
        messages.error(request, f'Cannot undo check-in - job status is "{queue_entry.get_status_display()}". Only running jobs can be undone.')
        return redirect('admin_queue')

    if not queue_entry.assigned_machine:
        messages.error(request, 'Cannot undo check-in - no machine assigned.')
        return redirect('admin_queue')

    machine = queue_entry.assigned_machine
    entry_user = queue_entry.user
    entry_title = queue_entry.title

    # Refresh machine from database to get latest state
    machine.refresh_from_db()

    # Find the entry that was at position 1 (will be bumped to position 2)
    was_on_deck = QueueEntry.objects.filter(
        assigned_machine=machine,
        status='queued',
        queue_position=1
    ).first()

    # Bump all existing queued entries down by 1 position
    existing_queued = QueueEntry.objects.filter(
        assigned_machine=machine,
        status='queued'
    ).order_by('queue_position')

    # Update in REVERSE order to avoid UNIQUE constraint violations
    existing_queued_list = list(existing_queued)
    for entry in reversed(existing_queued_list):
        if entry.queue_position is not None:
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
    if was_on_deck:
        was_on_deck.refresh_from_db()  # Refresh to get updated queue_position
        was_on_deck.checkin_reminder_due_at = None
        was_on_deck.last_checkin_reminder_sent_at = None
        was_on_deck.checkin_reminder_snoozed_until = None
        was_on_deck.save(update_fields=['checkin_reminder_due_at', 'last_checkin_reminder_sent_at', 'checkin_reminder_snoozed_until'])

    # Notify the user that admin undid their check-in
    try:
        notifications.create_notification(
            recipient=entry_user,
            notification_type='admin_checkout',  # Reusing admin_checkout type for admin undo
            title='Check-In Undone by Admin',
            message=f'Administrator {request.user.username} undid your check-in for "{entry_title}" on {machine.name}. Your measurement has been moved back to position #1 (on deck).',
            related_queue_entry=queue_entry,
            related_machine=machine,
        )
    except Exception as e:
        print(f"User notification for admin undo check-in failed: {e}")

    # Initialize check-in reminders for the entry now at position 1
    notifications.check_and_notify_on_deck_status(machine)

    # Broadcast WebSocket update
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
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

    messages.success(request, f'✅ Check-in undone! "{entry_title}" by {entry_user.username} has been moved back to position #1 (on deck) on {machine.name}.')
    return redirect('admin_queue')


@staff_member_required
@never_cache
def admin_presets(request):
    """Admin page for managing all presets (public and private)."""
    from .models import QueuePreset
    from django.db.models import Case, When, Value, CharField
    from django.contrib.auth.models import User
    from userRegistration.models import UserProfile

    # Get all presets, organized by public/private, then by creator username
    presets = QueuePreset.objects.select_related('creator').all().order_by(
        '-is_public',  # Public first (True > False in descending order)
        'creator_username',  # Then by creator username
        'name'  # Then by preset name
    )

    # Check which creator usernames correspond to approved accounts
    # This will be used to determine if superusers can delete orphaned presets
    approved_usernames = set()
    for user in User.objects.all():
        try:
            # Check if user has an approved profile
            if hasattr(user, 'profile') and user.profile.status == 'approved':
                approved_usernames.add(user.username)
        except UserProfile.DoesNotExist:
            # User has no profile, not approved
            pass

    # Group presets by public/private and then by user
    public_presets = {}
    private_presets = {}

    for preset in presets:
        username = preset.creator_username or 'Unknown User'

        # Add attribute to check if creator is still an approved account
        preset.creator_is_approved = username in approved_usernames

        if preset.is_public:
            if username not in public_presets:
                public_presets[username] = []
            public_presets[username].append(preset)
        else:
            if username not in private_presets:
                private_presets[username] = []
            private_presets[username].append(preset)

    # Sort usernames alphabetically for display (case-insensitive)
    # Also sort presets within each user group by name (case-insensitive)
    public_presets = dict(sorted(public_presets.items(), key=lambda x: x[0].lower()))
    for username in public_presets:
        public_presets[username] = sorted(public_presets[username], key=lambda p: p.name.lower())

    private_presets = dict(sorted(private_presets.items(), key=lambda x: x[0].lower()))
    for username in private_presets:
        private_presets[username] = sorted(private_presets[username], key=lambda p: p.name.lower())

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
    Both queued and running entries can be edited.
    Allows manual machine reassignment and queue position editing.
    """
    queue_entry = get_object_or_404(QueueEntry, id=entry_id)

    # Get return URL from query parameter (default to admin_queue)
    return_url = request.GET.get('return_to', 'admin_queue')
    # Validate return_url to prevent open redirect
    allowed_returns = ['admin_queue', 'admin_rush_jobs']
    if return_url not in allowed_returns:
        return_url = 'admin_queue'

    # Allow editing both queued and running entries
    if queue_entry.status not in ['queued', 'running']:
        messages.error(request, f'Cannot edit entry with status "{queue_entry.status}". Only queued and running entries can be edited.')
        return redirect(return_url)

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
        'queue_position': queue_entry.queue_position,
    }

    if request.method == 'POST':
        # Check if this is a confirmation submit (after showing machine change warning)
        confirmed = request.POST.get('confirmed') == 'true'

        form = QueueEntryForm(request.POST, instance=queue_entry)

        if form.is_valid():
            # Save form but don't commit yet
            edited_entry = form.save(commit=False)

            # Check for manual machine selection
            manual_machine_id = request.POST.get('manual_machine_id')
            old_machine = queue_entry.assigned_machine

            if manual_machine_id:
                # Admin manually selected a machine
                try:
                    selected_machine = Machine.objects.get(id=manual_machine_id)
                    # Verify this machine is compatible
                    compatible_machines = get_compatible_machines(edited_entry)
                    if selected_machine not in compatible_machines:
                        messages.error(request, f'Selected machine "{selected_machine.name}" is not compatible with the requirements.')

                        # Calculate adjusted queue count for each machine
                        for machine in compatible_machines:
                            current_count = QueueEntry.objects.filter(
                                assigned_machine=machine, status='queued'
                            ).count()

                            if machine.id == queue_entry.assigned_machine.id and queue_entry.status == 'queued':
                                machine.adjusted_queue_count = current_count
                            else:
                                machine.adjusted_queue_count = current_count + 1

                        # Get compatible machines again for the form
                        context = {
                            'queue_entry': queue_entry,
                            'form': form,
                            'compatible_machines': compatible_machines,
                            'max_queue_position': QueueEntry.objects.filter(
                                assigned_machine=old_machine, status='queued'
                            ).count() if old_machine else 1,
                        }
                        return render(request, 'calendarEditor/admin/admin_edit_entry.html', context)
                    target_machine = selected_machine
                except Machine.DoesNotExist:
                    messages.error(request, 'Selected machine not found.')
                    return redirect('admin_queue')
            else:
                # No manual selection - use best-fit algorithm
                best_machine, compatibility_score = find_best_machine(edited_entry, return_details=True)

                # If machine would change and user hasn't confirmed, show warning
                if best_machine != old_machine and not confirmed:
                    compatible_machines = get_compatible_machines(edited_entry)

                    # Calculate adjusted queue count for each machine
                    for machine in compatible_machines:
                        current_count = QueueEntry.objects.filter(
                            assigned_machine=machine, status='queued'
                        ).count()

                        if machine.id == queue_entry.assigned_machine.id and queue_entry.status == 'queued':
                            machine.adjusted_queue_count = current_count
                        else:
                            machine.adjusted_queue_count = current_count + 1

                    context = {
                        'queue_entry': queue_entry,
                        'form': form,
                        'show_machine_warning': True,
                        'old_machine': old_machine,
                        'new_machine': best_machine,
                        'compatibility_score': compatibility_score,
                        'compatible_machines': compatible_machines,
                        'max_queue_position': QueueEntry.objects.filter(
                            assigned_machine=old_machine, status='queued'
                        ).count() if old_machine else 1,
                    }
                    return render(request, 'calendarEditor/admin/admin_edit_entry.html', context)

                # Check if we have a compatible machine
                if best_machine is None:
                    messages.error(request, 'No compatible machines found for these requirements. Please adjust the requirements.')
                    form.add_error(None, 'No compatible machines found for these requirements.')

                    compatible_machines = []
                    # No need to calculate adjusted counts for empty list

                    context = {
                        'queue_entry': queue_entry,
                        'form': form,
                        'compatible_machines': compatible_machines,
                        'max_queue_position': 1,
                    }
                    return render(request, 'calendarEditor/admin/admin_edit_entry.html', context)

                target_machine = best_machine

            # Save the machine assignment
            edited_entry.assigned_machine = target_machine

            # Handle queue position changes
            queue_position_action = request.POST.get('queue_position_action')
            manual_position = request.POST.get('manual_queue_position')
            old_position = queue_entry.queue_position
            status_changed_from_running = False

            # Check if reassigning a running entry to a machine that already has a running job
            if queue_entry.status == 'running' and old_machine != target_machine:
                # Check if target machine has a running job
                target_has_running = QueueEntry.objects.filter(
                    assigned_machine=target_machine,
                    status='running'
                ).exists()

                if target_has_running:
                    # Convert this entry to queued status
                    edited_entry.status = 'queued'
                    edited_entry.started_at = None
                    edited_entry.reminder_due_at = None
                    edited_entry.last_reminder_sent_at = None
                    edited_entry.reminder_snoozed_until = None
                    status_changed_from_running = True

                    # Update old machine status to idle
                    if old_machine:
                        old_machine.current_status = 'idle'
                        old_machine.current_user = None
                        old_machine.estimated_available_time = None
                        old_machine.save()

            # Save the entry first
            edited_entry.save()

            # If machine changed, handle queue reassignment
            if old_machine != target_machine:
                # Remove from old machine's queue and reorder
                if old_machine:
                    reorder_queue(old_machine)
                # Add to new machine's queue and reorder
                reorder_queue(target_machine)

            # Handle queue position changes (for queued entries, or entries that just became queued)
            if queue_entry.status == 'queued' or status_changed_from_running:
                if queue_position_action == 'first':
                    # Move to position 1
                    set_queue_position(edited_entry.id, 1)
                elif queue_position_action == 'last':
                    # Move to last position
                    max_pos = QueueEntry.objects.filter(
                        assigned_machine=target_machine, status='queued'
                    ).count()
                    set_queue_position(edited_entry.id, max_pos)
                elif queue_position_action == 'custom' and manual_position:
                    # Move to specific position
                    try:
                        new_pos = int(manual_position)
                        set_queue_position(edited_entry.id, new_pos)
                    except (ValueError, TypeError):
                        pass  # Invalid position, ignore

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
            if old_machine != target_machine:
                changes.append(f'machine assignment (moved to {target_machine.name})')
            if status_changed_from_running:
                changes.append('status (converted from running to queued due to target machine conflict)')

            # Refresh from DB to get updated queue position
            edited_entry.refresh_from_db()
            if original_values['queue_position'] != edited_entry.queue_position and (queue_entry.status == 'queued' or status_changed_from_running):
                changes.append(f'queue position (moved to #{edited_entry.queue_position})')

            # Create change summary for notification
            if changes:
                changes_summary = ', '.join(changes)
            else:
                changes_summary = 'minor updates'

            # Send notification to user
            notifications.notify_admin_edit_entry(edited_entry, request.user, changes_summary)

            messages.success(request, f'Queue entry "{edited_entry.title}" updated successfully.')
            return redirect(return_url)

        else:
            # Form has validation errors - get compatible machines for re-render
            compatible_machines = get_compatible_machines(queue_entry)

            # Calculate adjusted queue count for each machine
            for machine in compatible_machines:
                current_count = QueueEntry.objects.filter(
                    assigned_machine=machine, status='queued'
                ).count()

                if machine.id == queue_entry.assigned_machine.id and queue_entry.status == 'queued':
                    machine.adjusted_queue_count = current_count
                else:
                    machine.adjusted_queue_count = current_count + 1

            context = {
                'queue_entry': queue_entry,
                'form': form,
                'compatible_machines': compatible_machines,
                'max_queue_position': QueueEntry.objects.filter(
                    assigned_machine=queue_entry.assigned_machine, status='queued'
                ).count() if queue_entry.assigned_machine else 1,
            }
            return render(request, 'calendarEditor/admin/admin_edit_entry.html', context)

    else:
        # GET request - show form
        form = QueueEntryForm(instance=queue_entry)

        # Get compatible machines based on current requirements
        compatible_machines = get_compatible_machines(queue_entry)

        # Calculate adjusted queue count for each machine
        # This accounts for this entry being moved TO that machine
        for machine in compatible_machines:
            current_count = QueueEntry.objects.filter(
                assigned_machine=machine, status='queued'
            ).count()

            # If this is the current machine and entry is queued, count stays same
            # If this is a different machine, count increases by 1 (this entry will be added)
            if machine.id == queue_entry.assigned_machine.id and queue_entry.status == 'queued':
                machine.adjusted_queue_count = current_count
            else:
                # Entry will be added to this machine's queue
                machine.adjusted_queue_count = current_count + 1

        # Get max queue position for current machine
        max_queue_position = QueueEntry.objects.filter(
            assigned_machine=queue_entry.assigned_machine, status='queued'
        ).count() if queue_entry.assigned_machine else 1

        context = {
            'queue_entry': queue_entry,
            'form': form,
            'compatible_machines': compatible_machines,
            'max_queue_position': max_queue_position,
        }
        return render(request, 'calendarEditor/admin/admin_edit_entry.html', context)


# ====================
# STORAGE & ARCHIVE MANAGEMENT
# ====================

@staff_member_required
def admin_storage_stats(request):
    """
    API endpoint for storage statistics.
    Returns JSON with database size, usage percentage, and status.
    """
    from .storage_utils import get_storage_stats

    stats = get_storage_stats()
    return JsonResponse(stats)


@staff_member_required
def admin_render_usage_stats(request):
    """
    API endpoint for Render usage statistics.
    Returns JSON with request counts, estimated uptime, and status.
    """
    from .render_usage import get_render_usage_stats

    stats = get_render_usage_stats()
    return JsonResponse(stats)


@staff_member_required
def admin_render_usage(request):
    """
    Render usage management page for staff.
    Shows uptime usage, request counts, and status against free tier limits.
    """
    from .render_usage import get_render_usage_stats
    import calendar

    stats = get_render_usage_stats()

    # Get total days in current month
    now = timezone.now()
    days_in_month = calendar.monthrange(now.year, now.month)[1]

    # Calculate average requests per day
    avg_requests_per_day = 0
    if stats['days_this_month'] > 0:
        avg_requests_per_day = stats['requests_this_month'] / stats['days_this_month']

    context = {
        'requests_this_month': stats['requests_this_month'],
        'estimated_uptime_hours': stats['estimated_uptime_hours'],
        'max_uptime_hours': stats['max_uptime_hours'],
        'uptime_percentage': stats['uptime_percentage'],
        'hours_remaining': stats['hours_remaining'],
        'days_this_month': stats['days_this_month'],
        'days_remaining': stats['days_remaining'],
        'uptime_status': stats['status'],
        'days_in_month': days_in_month,
        'avg_requests_per_day': avg_requests_per_day,
    }

    return render(request, 'calendarEditor/admin/render_usage.html', context)


@staff_member_required
def admin_database_management(request):
    """
    Database management page for staff.
    Shows Turso usage stats against monthly limits and storage breakdown.
    """
    import os
    from .storage_utils import get_storage_stats, get_storage_breakdown, format_size_mb
    from .turso_api_client import TursoAPIClient

    # Get Turso usage metrics from API
    turso_client = TursoAPIClient()
    turso_usage = turso_client.get_usage_metrics()

    # Turso plan limits (Free tier defaults)
    turso_limits = {
        'storage_mb': int(os.environ.get('TURSO_MAX_STORAGE_MB', 5120)),  # 5GB
        'rows_read_monthly': int(os.environ.get('TURSO_MAX_ROWS_READ', 500_000_000)),  # 500M
        'rows_written_monthly': int(os.environ.get('TURSO_MAX_ROWS_WRITTEN', 10_000_000)),  # 10M
    }

    # Calculate usage percentages
    turso_stats = None
    if turso_usage:
        turso_stats = {
            'rows_read': turso_usage['rows_read'],
            'rows_written': turso_usage['rows_written'],
            'storage_mb': turso_usage['storage_bytes'] / (1024 * 1024),
            'databases': turso_usage.get('databases', 0),
            'rows_read_percent': (turso_usage['rows_read'] / turso_limits['rows_read_monthly'] * 100),
            'rows_written_percent': (turso_usage['rows_written'] / turso_limits['rows_written_monthly'] * 100),
            'storage_percent': (turso_usage['storage_bytes'] / (turso_limits['storage_mb'] * 1024 * 1024) * 100),
        }

    # Get storage statistics (fallback if API unavailable)
    storage_stats = get_storage_stats()

    # Get storage breakdown
    breakdown_data = get_storage_breakdown()

    # Get archive count
    archive_count = ArchivedMeasurement.objects.count()
    estimated_archive_size_mb = (archive_count * 1.5) / 1024

    context = {
        'turso_usage': turso_stats,
        'turso_limits': turso_limits,
        'turso_org_slug': os.environ.get('TURSO_ORG_SLUG', 'unknown'),
        'storage_stats': storage_stats,
        'storage_breakdown': breakdown_data['breakdown'],
        'total_estimated_mb': breakdown_data['total_estimated_mb'],
        'archive_count': archive_count,
        'estimated_archive_size_mb': round(estimated_archive_size_mb, 2),
        'format_size_mb': format_size_mb,
    }

    return render(request, 'calendarEditor/admin/archive_management.html', context)


# Keep old name as alias for backwards compatibility (can be removed later)
admin_archive_management = admin_database_management


@login_required
def admin_export_archive(request):
    """
    Export all archived measurements to CSV or JSON file.
    Available to all authenticated users.
    """
    import json
    from django.http import HttpResponse
    from datetime import datetime
    
    # Get format from query param (default to json)
    export_format = request.GET.get('format', 'json')
    
    # Get all archived measurements with related data
    measurements = ArchivedMeasurement.objects.select_related(
        'user', 'machine'
    ).all().order_by('-measurement_date')
    
    if export_format == 'csv':
        # Export as CSV
        import csv
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="archive_backup_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'User', 'Machine', 'Measurement Date',
            'Title', 'Duration (hours)', 'Notes', 'Archived At'
        ])

        for m in measurements:
            # Use machine_name field as fallback if machine was deleted
            machine_display = m.machine.name if m.machine else (m.machine_name or 'Deleted Machine')
            writer.writerow([
                m.id,
                m.user.username,
                machine_display,
                m.measurement_date.strftime('%Y-%m-%d %H:%M:%S'),
                m.title,
                m.duration_hours if m.duration_hours is not None else '',
                m.notes,
                m.archived_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    
    else:
        # Export as JSON (default)
        data = []
        for m in measurements:
            # Use machine_name field as fallback if machine was deleted
            machine_display = m.machine.name if m.machine else (m.machine_name or 'Deleted Machine')
            machine_id = m.machine.id if m.machine else None
            data.append({
                'id': m.id,
                'user': m.user.username,
                'user_id': m.user.id,
                'machine': machine_display,
                'machine_id': machine_id,
                'measurement_date': m.measurement_date.isoformat(),
                'title': m.title,
                'duration_hours': m.duration_hours,
                'notes': m.notes,
                'archived_at': m.archived_at.isoformat(),
            })
        
        response = HttpResponse(
            json.dumps(data, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="archive_backup_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.json"'
        
        return response


def _create_full_database_export():
    """
    Internal function to create full database export.
    Returns backup data dictionary.
    """
    from django.core import serializers
    from django.contrib.auth.models import User
    from userRegistration.models import UserProfile
    from datetime import datetime
    import json

    # Models to backup (in dependency order for restore)
    models_to_backup = [
        ('auth.User', User),
        ('userRegistration.UserProfile', UserProfile),
        ('calendarEditor.Machine', Machine),
        ('calendarEditor.QueuePreset', QueuePreset),
        ('calendarEditor.QueueEntry', QueueEntry),
        ('calendarEditor.ArchivedMeasurement', ArchivedMeasurement),
        ('calendarEditor.NotificationPreference', NotificationPreference),
        ('calendarEditor.Notification', Notification),
    ]

    backup_data = {
        'export_date': datetime.now().isoformat(),
        'export_type': 'full_database_backup',
        'django_version': '4.2.25',
        'models': {}
    }

    # Serialize each model
    for model_name, model_class in models_to_backup:
        try:
            queryset = model_class.objects.all()
            serialized = serializers.serialize('json', queryset)
            backup_data['models'][model_name] = json.loads(serialized)
        except Exception as e:
            backup_data['models'][model_name] = {
                'error': str(e),
                'count': 0
            }

    return backup_data


@staff_member_required
def admin_export_full_database(request):
    """
    Export complete database backup for disaster recovery.
    Includes all models: users, machines, queue entries, presets, archives, notifications.
    Staff/superuser only - requires login.
    """
    from django.http import HttpResponse
    from datetime import datetime
    import json

    backup_data = _create_full_database_export()

    # Create response
    response = HttpResponse(
        json.dumps(backup_data, indent=2),
        content_type='application/json'
    )
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    response['Content-Disposition'] = f'attachment; filename="full_database_backup_{timestamp}.json"'

    return response


def api_export_database_backup(request):
    """
    API endpoint for automated database backups (GitHub Actions, etc.)
    Requires BACKUP_API_KEY in Authorization header.
    """
    from django.http import HttpResponse, JsonResponse
    from django.conf import settings
    from datetime import datetime
    import json

    # Check API key
    backup_api_key = getattr(settings, 'BACKUP_API_KEY', None)
    if not backup_api_key:
        return JsonResponse({'error': 'Backup API not configured'}, status=500)

    # Verify authorization header
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return JsonResponse({'error': 'Missing or invalid Authorization header'}, status=401)

    provided_key = auth_header.replace('Bearer ', '')
    if provided_key != backup_api_key:
        return JsonResponse({'error': 'Invalid API key'}, status=403)

    # Create backup
    backup_data = _create_full_database_export()

    # Return as JSON
    response = HttpResponse(
        json.dumps(backup_data, indent=2),
        content_type='application/json'
    )

    return response


@staff_member_required
def admin_list_github_backups(request):
    """
    List available database backups from GitHub repository.
    Fetches from the database-backups branch.
    """
    from django.http import JsonResponse
    from django.conf import settings
    import requests

    github_token = settings.GITHUB_TOKEN
    github_repo = settings.GITHUB_REPO

    if not github_token or not github_repo:
        return JsonResponse({
            'error': 'GitHub integration not configured. Set GITHUB_TOKEN and GITHUB_REPO environment variables.'
        }, status=500)

    # Fetch contents of backups directory from database-backups branch
    api_url = f'https://api.github.com/repos/{github_repo}/contents/backups?ref=database-backups'
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=10)

        if response.status_code == 404:
            return JsonResponse({
                'backups': [],
                'message': 'No backups found. The database-backups branch may not exist yet.'
            })

        if response.status_code != 200:
            return JsonResponse({
                'error': f'GitHub API error: {response.status_code}'
            }, status=response.status_code)

        files = response.json()

        # Filter for JSON backup files and sort by name (newest first)
        backups = []
        for f in files:
            if f['name'].endswith('.json') and f['name'].startswith('database_backup_'):
                backups.append({
                    'name': f['name'],
                    'size': f['size'],
                    'download_url': f['download_url'],
                    'sha': f['sha']
                })

        # Sort by filename (which includes timestamp) - newest first
        backups.sort(key=lambda x: x['name'], reverse=True)

        return JsonResponse({'backups': backups})

    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'GitHub API request timed out'}, status=504)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
def admin_download_github_backup(request, filename):
    """
    Download a specific backup file from GitHub.
    """
    from django.http import HttpResponse, JsonResponse
    from django.conf import settings
    import requests

    github_token = settings.GITHUB_TOKEN
    github_repo = settings.GITHUB_REPO

    if not github_token or not github_repo:
        return JsonResponse({
            'error': 'GitHub integration not configured'
        }, status=500)

    # Validate filename to prevent path traversal
    if '/' in filename or '..' in filename:
        return JsonResponse({'error': 'Invalid filename'}, status=400)

    # Fetch file content from GitHub
    api_url = f'https://api.github.com/repos/{github_repo}/contents/backups/{filename}?ref=database-backups'
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3.raw'
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=30)

        if response.status_code == 404:
            return JsonResponse({'error': 'Backup file not found'}, status=404)

        if response.status_code != 200:
            return JsonResponse({
                'error': f'GitHub API error: {response.status_code}'
            }, status=response.status_code)

        # Return as downloadable file
        http_response = HttpResponse(
            response.content,
            content_type='application/json'
        )
        http_response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return http_response

    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'Download timed out'}, status=504)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def admin_restore_github_backup(request, filename):
    """
    Restore database directly from a GitHub cloud backup.
    Downloads the backup from GitHub and performs the restore.
    Supports both Replace and Merge modes.
    """
    from django.core import serializers
    from django.db import transaction, connection
    from django.http import JsonResponse
    from django.conf import settings
    from django.contrib.auth.models import User
    import requests
    import json

    # Check if this is AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    # Get import mode and silent restore flag
    import_mode = request.POST.get('import_mode', 'merge')
    silent_restore = request.POST.get('silent_restore', 'false').lower() == 'true'

    # Get GitHub settings
    github_token = settings.GITHUB_TOKEN
    github_repo = settings.GITHUB_REPO

    if not github_token or not github_repo:
        error_msg = 'GitHub integration not configured'
        if is_ajax:
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)
        return redirect('admin_database_management')

    # Validate filename to prevent path traversal
    if '/' in filename or '..' in filename:
        error_msg = 'Invalid filename'
        if is_ajax:
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)
        return redirect('admin_database_management')

    # Fetch file content from GitHub
    api_url = f'https://api.github.com/repos/{github_repo}/contents/backups/{filename}?ref=database-backups'
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3.raw'
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=60)

        if response.status_code == 404:
            error_msg = 'Backup file not found in GitHub'
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg})
            messages.error(request, error_msg)
            return redirect('admin_database_management')

        if response.status_code != 200:
            error_msg = f'GitHub API error: {response.status_code}'
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg})
            messages.error(request, error_msg)
            return redirect('admin_database_management')

        # Parse JSON backup
        backup_data = json.loads(response.content.decode('utf-8'))

        # Validate backup structure
        if 'export_type' not in backup_data or backup_data['export_type'] != 'full_database_backup':
            error_msg = 'Invalid backup file format. Expected full database backup.'
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg})
            messages.error(request, error_msg)
            return redirect('admin_database_management')

        if 'models' not in backup_data:
            error_msg = 'Invalid backup file structure. Missing models data.'
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg})
            messages.error(request, error_msg)
            return redirect('admin_database_management')

        # Extract backup date from filename for notification
        # Format: database_backup_2024-01-15_06-30-00.json
        backup_date = filename
        match = __import__('re').match(r'database_backup_(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})\.json', filename)
        if match:
            backup_date = f"{match.group(1)} {match.group(2)}:{match.group(3)}"

        # Models to restore (in dependency order)
        models_order = [
            'auth.User',
            'userRegistration.UserProfile',
            'calendarEditor.Machine',
            'calendarEditor.QueuePreset',
            'calendarEditor.QueueEntry',
            'calendarEditor.ArchivedMeasurement',
            'calendarEditor.NotificationPreference',
            'calendarEditor.Notification',
        ]

        restored_counts = {}
        skipped_counts = {}

        with transaction.atomic():
            # REPLACE MODE: Clear all data first
            if import_mode == 'replace':
                for model_name in reversed(models_order):
                    if model_name in backup_data['models']:
                        model_label = model_name.split('.')
                        app_label, model_class_name = model_label[0], model_label[1]

                        from django.apps import apps
                        try:
                            model_class = apps.get_model(app_label, model_class_name)
                            # Don't delete superusers OR current user to prevent lockout
                            if model_name == 'auth.User':
                                # Keep all superusers AND the current logged-in user
                                deleted_count = model_class.objects.filter(
                                    is_superuser=False
                                ).exclude(
                                    pk=request.user.pk
                                ).delete()[0]
                                print(f"Deleted {deleted_count} non-superuser users (kept current user ID {request.user.pk})")
                            else:
                                deleted_count = model_class.objects.all().delete()[0]
                                print(f"Deleted {deleted_count} {model_name} records")
                        except Exception as e:
                            print(f"Warning: Could not clear {model_name}: {e}")

                # Clear database connection cache to ensure clean slate
                # This was in the WORKING version (0088b14)
                connection.close()
                connection.connect()

            # Restore models in correct order
            for model_name in models_order:
                if model_name not in backup_data['models']:
                    continue

                model_data = backup_data['models'][model_name]

                if isinstance(model_data, dict) and 'error' in model_data:
                    continue

                restored_count = 0
                skipped_count = 0

                try:
                    for obj_data in model_data:
                        try:
                            # In merge mode, skip existing objects to avoid conflicts
                            if import_mode == 'merge':
                                obj_pk = obj_data.get('pk')
                                model_label = model_name.split('.')
                                app_label, model_class_name = model_label[0], model_label[1]

                                from django.apps import apps
                                model_class = apps.get_model(app_label, model_class_name)

                                if model_class.objects.filter(pk=obj_pk).exists():
                                    skipped_count += 1
                                    continue
                            # In replace mode, restore all objects (deleted ones were already removed)

                            for deserialized_obj in serializers.deserialize('json', json.dumps([obj_data])):
                                # The deserialized object's save() handles PK conflicts automatically
                                deserialized_obj.save()
                                restored_count += 1

                        except Exception as e:
                            import traceback
                            print(f"Error restoring object from {model_name}: {e}")
                            print(f"Traceback: {traceback.format_exc()}")
                            skipped_count += 1
                            continue

                    restored_counts[model_name] = restored_count
                    if skipped_count > 0:
                        skipped_counts[model_name] = skipped_count

                except Exception as e:
                    error_msg = f'Error restoring {model_name}: {str(e)}'
                    if is_ajax:
                        return JsonResponse({'success': False, 'error': error_msg})
                    messages.error(request, error_msg)
                    return redirect('admin_database_management')

        # Prepare success message
        total_restored = sum(restored_counts.values())
        total_skipped = sum(skipped_counts.values())

        success_msg = f'Database restore completed. '
        if import_mode == 'replace':
            success_msg += f'Restored {total_restored} records in replace mode.'
        else:
            success_msg += f'Restored {total_restored} records, skipped {total_skipped} existing records.'

        # Notify ALL users about the restore (unless silent_restore is enabled)
        if not silent_restore:
            admin_name = request.user.get_full_name() or request.user.username
            all_users = User.objects.filter(is_active=True)

            for user in all_users:
                notifications.create_notification(
                    recipient=user,
                    notification_type='database_restored',
                    title='Database Restored',
                    message=f'Database backup from {backup_date} was restored by {admin_name}. Your queue entries and data may have been updated.'
                )

        if is_ajax:
            return JsonResponse({
                'success': True,
                'message': success_msg,
                'restored': restored_counts,
                'skipped': skipped_counts
            })

        messages.success(request, success_msg)

    except requests.exceptions.Timeout:
        error_msg = 'Download from GitHub timed out'
        if is_ajax:
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)
    except json.JSONDecodeError:
        error_msg = 'Invalid JSON in backup file'
        if is_ajax:
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)
    except Exception as e:
        error_msg = f'Error restoring database: {str(e)}'
        if is_ajax:
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)

    return redirect('admin_database_management')


@staff_member_required
def admin_clear_archive_with_backup(request):
    """
    Automatically download backup before clearing archive.
    Triggers download in browser, then redirects to actual delete page.
    """
    import json
    from django.http import HttpResponse
    from datetime import datetime

    # Get all archived measurements
    measurements = ArchivedMeasurement.objects.select_related('user', 'machine').all().order_by('-measurement_date')

    # Export as JSON
    data = []
    for m in measurements:
        data.append({
            'id': m.id,
            'user': m.user.username,
            'user_id': m.user.id,
            'machine': m.machine.name,
            'machine_id': m.machine.id,
            'measurement_date': m.measurement_date.isoformat(),
            'title': m.title,
            'notes': m.notes,
            'archived_at': m.archived_at.isoformat(),
        })

    # Create response with backup file
    response = HttpResponse(
        json.dumps(data, indent=2),
        content_type='application/json'
    )
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    response['Content-Disposition'] = f'attachment; filename="archive_backup_before_delete_{timestamp}.json"'

    return response


@staff_member_required
@require_http_methods(["POST"])
def admin_clear_archive(request):
    """
    Clear all archived measurements.
    Requires exact confirmation text and sends notifications to all users.
    Staff/superuser only.
    """
    from django.contrib.auth.models import User
    from django.http import JsonResponse

    # Check if this is AJAX request (for Thanos modal)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    # Check confirmation
    confirmation = request.POST.get('confirmation', '').strip()
    if confirmation != 'CONFIRM DELETE':
        if is_ajax:
            return JsonResponse({
                'success': False,
                'error': 'Incorrect confirmation text. Please type exactly "CONFIRM DELETE".'
            })

        # Create notification for incorrect confirmation
        notifications.create_notification(
            recipient=request.user,
            notification_type='admin_action',
            title='Archive Delete Failed',
            message=f'Incorrect confirmation text entered. Expected "CONFIRM DELETE", got "{confirmation}". Archive was not deleted.'
        )
        messages.error(request, 'Incorrect confirmation text. Archive not deleted.')
        return redirect('admin_database_management')

    # Get count before deletion
    count = ArchivedMeasurement.objects.count()

    if count == 0:
        if is_ajax:
            return JsonResponse({
                'success': False,
                'error': 'Archive is already empty.'
            })
        messages.info(request, 'Archive is already empty.')
        return redirect('admin_database_management')

    # Delete all archived measurements
    try:
        ArchivedMeasurement.objects.all().delete()

        # Send notification to all active users
        active_users = User.objects.filter(is_active=True)
        admin_name = request.user.get_full_name() or request.user.username

        for user in active_users:
            notifications.create_notification(
                recipient=user,
                notification_type='admin_action',
                title='Archive Cleared',
                message=(
                    f"The archived measurements database has been cleared by {admin_name} "
                    f"to free up space. {count} measurements were removed. "
                    f"Contact administrators if you need access to old archived data."
                )
            )

        if is_ajax:
            return JsonResponse({
                'success': True,
                'count': count,
                'message': f'Successfully deleted {count} archived measurements. All users have been notified.'
            })

        messages.success(
            request,
            f'Successfully deleted {count} archived measurements. All users have been notified.'
        )

    except Exception as e:
        if is_ajax:
            return JsonResponse({
                'success': False,
                'error': f'Error clearing archive: {str(e)}'
            })
        messages.error(request, f'Error clearing archive: {str(e)}')

    return redirect('admin_database_management')


@staff_member_required
@require_http_methods(["POST"])
def admin_import_database(request):
    """
    Import and restore database from backup file.
    Supports both Replace mode (clear then restore) and Merge mode (skip existing).
    Staff-only access.
    """
    from django.core import serializers
    from django.db import transaction, connection
    from django.http import JsonResponse
    import json

    # Check if this is AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    # Validate file upload
    if 'backup_file' not in request.FILES:
        error_msg = 'No backup file provided.'
        if is_ajax:
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)
        return redirect('admin_database_management')

    backup_file = request.FILES['backup_file']
    import_mode = request.POST.get('import_mode', 'merge')  # 'merge' or 'replace'
    silent_restore = request.POST.get('silent_restore', 'false').lower() == 'true'

    # Validate file size (max 50MB)
    max_size = 50 * 1024 * 1024  # 50MB
    if backup_file.size > max_size:
        error_msg = f'File too large. Maximum size is 50MB.'
        if is_ajax:
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)
        return redirect('admin_database_management')

    # Validate file type
    if not backup_file.name.endswith('.json'):
        error_msg = 'Invalid file type. Only .json files are accepted.'
        if is_ajax:
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)
        return redirect('admin_database_management')

    try:
        # Read and parse JSON
        file_content = backup_file.read().decode('utf-8')
        backup_data = json.loads(file_content)

        # Validate backup structure
        if 'export_type' not in backup_data or backup_data['export_type'] != 'full_database_backup':
            error_msg = 'Invalid backup file format. Expected full database backup.'
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg})
            messages.error(request, error_msg)
            return redirect('admin_database_management')

        if 'models' not in backup_data:
            error_msg = 'Invalid backup file structure. Missing models data.'
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg})
            messages.error(request, error_msg)
            return redirect('admin_database_management')

        # Models to restore (in dependency order)
        models_order = [
            'auth.User',
            'userRegistration.UserProfile',
            'calendarEditor.Machine',
            'calendarEditor.QueuePreset',
            'calendarEditor.QueueEntry',
            'calendarEditor.ArchivedMeasurement',
            'calendarEditor.NotificationPreference',
            'calendarEditor.Notification',
        ]

        restored_counts = {}
        skipped_counts = {}

        with transaction.atomic():
            # REPLACE MODE: Clear all data first
            if import_mode == 'replace':
                # Clear data in reverse order (to respect foreign keys)
                for model_name in reversed(models_order):
                    if model_name in backup_data['models']:
                        model_label = model_name.split('.')
                        app_label, model_class_name = model_label[0], model_label[1]

                        # Get model class
                        from django.apps import apps
                        try:
                            model_class = apps.get_model(app_label, model_class_name)
                            # Don't delete superusers OR current user to prevent lockout
                            if model_name == 'auth.User':
                                # Keep all superusers AND the current logged-in user
                                deleted_count = model_class.objects.filter(
                                    is_superuser=False
                                ).exclude(
                                    pk=request.user.pk
                                ).delete()[0]
                                print(f"Deleted {deleted_count} non-superuser users (kept current user ID {request.user.pk})")
                            else:
                                deleted_count = model_class.objects.all().delete()[0]
                                print(f"Deleted {deleted_count} {model_name} records")
                        except Exception as e:
                            print(f"Warning: Could not clear {model_name}: {e}")

                # Clear database connection cache to ensure clean slate
                # This was in the WORKING version (0088b14)
                connection.close()
                connection.connect()

            # Restore models in correct order
            for model_name in models_order:
                if model_name not in backup_data['models']:
                    continue

                model_data = backup_data['models'][model_name]

                # Skip if error in backup
                if isinstance(model_data, dict) and 'error' in model_data:
                    continue

                restored_count = 0
                skipped_count = 0

                try:
                    # Deserialize and restore objects
                    for obj_data in model_data:
                        try:
                            # In merge mode, skip existing objects to avoid conflicts
                            if import_mode == 'merge':
                                obj_pk = obj_data.get('pk')
                                model_label = model_name.split('.')
                                app_label, model_class_name = model_label[0], model_label[1]

                                from django.apps import apps
                                model_class = apps.get_model(app_label, model_class_name)

                                if model_class.objects.filter(pk=obj_pk).exists():
                                    skipped_count += 1
                                    continue
                            # In replace mode, restore all objects (deleted ones were already removed)

                            # Deserialize single object
                            for deserialized_obj in serializers.deserialize('json', json.dumps([obj_data])):
                                # In replace mode, use save() to insert
                                # The deserialized object's save() handles PK conflicts automatically
                                deserialized_obj.save()
                                restored_count += 1

                        except Exception as e:
                            # Log error but continue with other objects
                            import traceback
                            print(f"Error restoring object from {model_name}: {e}")
                            print(f"Traceback: {traceback.format_exc()}")
                            skipped_count += 1
                            continue

                    restored_counts[model_name] = restored_count
                    if skipped_count > 0:
                        skipped_counts[model_name] = skipped_count

                except Exception as e:
                    error_msg = f'Error restoring {model_name}: {str(e)}'
                    if is_ajax:
                        return JsonResponse({'success': False, 'error': error_msg})
                    messages.error(request, error_msg)
                    return redirect('admin_database_management')

        # Prepare success message
        total_restored = sum(restored_counts.values())
        total_skipped = sum(skipped_counts.values())

        success_msg = f'Database restore completed. '
        if import_mode == 'replace':
            success_msg += f'Restored {total_restored} records in replace mode.'
        else:
            success_msg += f'Restored {total_restored} records, skipped {total_skipped} existing records.'

        # Extract backup date from filename if available
        import re
        backup_filename = backup_file.name
        backup_date = 'uploaded file'
        match = re.match(r'database_backup_(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})\.json', backup_filename)
        if match:
            backup_date = f"{match.group(1)} {match.group(2)}:{match.group(3)}"

        # Notify ALL users about the restore (unless silent_restore is enabled)
        if not silent_restore:
            from django.contrib.auth.models import User
            admin_name = request.user.get_full_name() or request.user.username
            all_users = User.objects.filter(is_active=True)

            for user in all_users:
                notifications.create_notification(
                    recipient=user,
                    notification_type='database_restored',
                    title='Database Restored',
                    message=f'Database backup from {backup_date} was restored by {admin_name}. Your queue entries and data may have been updated.'
                )

        if is_ajax:
            return JsonResponse({
                'success': True,
                'message': success_msg,
                'restored': restored_counts,
                'skipped': skipped_counts
            })

        messages.success(request, success_msg)

    except json.JSONDecodeError:
        error_msg = 'Invalid JSON file format.'
        if is_ajax:
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)
    except Exception as e:
        error_msg = f'Error importing database: {str(e)}'
        if is_ajax:
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)

    return redirect('admin_database_management')


# ============================================================================
# DEVELOPER VIEWS - Tasks, Data, and Promotions
# ============================================================================

@staff_member_required
@never_cache
def developer_tasks(request):
    """Developer task management page - view and manage feedback."""
    from .models import Feedback
    from django.db.models import Case, When, IntegerField

    # Only developers and superusers can access
    if not (hasattr(request.user, 'profile') and request.user.profile.is_developer) and not request.user.is_superuser:
        messages.error(request, 'Developer access required.')
        return redirect('admin_dashboard')

    # Priority ordering: critical (0) > high (1) > medium (2) > low (3)
    priority_order = Case(
        When(priority='critical', then=0),
        When(priority='high', then=1),
        When(priority='medium', then=2),
        When(priority='low', then=3),
        output_field=IntegerField(),
    )

    # Separate feedback by status
    # Order by priority (critical first), then by date submitted (older first, newer lower)
    new_feedback = Feedback.objects.select_related('user', 'reviewed_by').filter(status='new').order_by(priority_order, 'created_at')
    reviewed_feedback = Feedback.objects.select_related('user', 'reviewed_by').filter(status='reviewed').order_by(priority_order, 'created_at')

    # Organize completed feedback by type (alphabetically), then by date (newest first)
    completed_bugs = Feedback.objects.select_related('user', 'reviewed_by').filter(status='completed', feedback_type='bug').order_by('-created_at')
    completed_features = Feedback.objects.select_related('user', 'reviewed_by').filter(status='completed', feedback_type='feature').order_by('-created_at')
    completed_opinions = Feedback.objects.select_related('user', 'reviewed_by').filter(status='completed', feedback_type='opinion').order_by('-created_at')

    context = {
        'new_feedback': new_feedback,
        'reviewed_feedback': reviewed_feedback,
        'completed_bugs': completed_bugs,
        'completed_features': completed_features,
        'completed_opinions': completed_opinions,
    }

    return render(request, 'calendarEditor/admin/developer_tasks.html', context)


@staff_member_required
def update_feedback_status(request, feedback_id):
    """Update feedback status (developer action)."""
    from .models import Feedback, Notification

    if not (hasattr(request.user, 'profile') and request.user.profile.is_developer) and not request.user.is_superuser:
        messages.error(request, 'Developer access required.')
        return redirect('admin_dashboard')

    feedback = get_object_or_404(Feedback, id=feedback_id)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        priority = request.POST.get('priority')
        developer_notes = request.POST.get('developer_notes', '')
        feedback_message = request.POST.get('feedback_message', '')

        if new_status in dict(Feedback.STATUS_CHOICES):
            feedback.status = new_status
            if new_status in ['reviewed', 'completed'] and not feedback.reviewed_by:
                feedback.reviewed_by = request.user
                feedback.reviewed_at = timezone.now()

        if priority in dict(Feedback.PRIORITY_CHOICES):
            feedback.priority = priority

        if developer_notes:
            feedback.developer_notes = developer_notes

        feedback.save()

        # Send notification to user when completed (always, with custom or default message)
        if new_status == 'completed':
            message_to_send = feedback_message if feedback_message else f'Your feedback "{feedback.title}" has been reviewed and completed. Thank you for your contribution!'
            Notification.objects.create(
                recipient=feedback.user,
                notification_type='feedback_completed',
                title=f'Feedback Update: {feedback.title}',
                message=message_to_send,
            )

        messages.success(request, f'Feedback #{feedback.id} updated.')

    return redirect('developer_tasks')


@staff_member_required
def delete_feedback(request, feedback_id):
    """Delete a completed feedback (developer action)."""
    from .models import Feedback

    if not (hasattr(request.user, 'profile') and request.user.profile.is_developer) and not request.user.is_superuser:
        messages.error(request, 'Developer access required.')
        return redirect('admin_dashboard')

    feedback = get_object_or_404(Feedback, id=feedback_id)

    # Only allow deleting completed feedback
    if feedback.status != 'completed':
        messages.error(request, 'Only completed feedback can be deleted.')
        return redirect('developer_tasks')

    if request.method == 'POST':
        feedback_title = feedback.title
        feedback.delete()
        messages.success(request, f'Completed feedback "{feedback_title}" has been deleted.')

    return redirect('developer_tasks')


@staff_member_required
def clear_all_completed_feedback(request):
    """Clear all completed feedback (developer action)."""
    from .models import Feedback

    if not (hasattr(request.user, 'profile') and request.user.profile.is_developer) and not request.user.is_superuser:
        messages.error(request, 'Developer access required.')
        return redirect('admin_dashboard')

    if request.method == 'POST':
        count = Feedback.objects.filter(status='completed').delete()[0]
        messages.success(request, f'Cleared {count} completed feedback items.')

    return redirect('developer_tasks')


@staff_member_required
@never_cache
def developer_data(request):
    """Developer analytics dashboard with comprehensive per-user and global data."""
    from .models import PageView, UserActivity, QueueEntry, Feedback
    from django.db.models import Count, Max, Min, Q
    from datetime import timedelta

    # Only developers and superusers can access
    if not (hasattr(request.user, 'profile') and request.user.profile.is_developer) and not request.user.is_superuser:
        messages.error(request, 'Developer access required.')
        return redirect('admin_dashboard')

    now = timezone.now()

    # Get date range from request (default to last 30 days for filtered views)
    days_filter = int(request.GET.get('days', 30))
    if days_filter == 0:  # All time
        start_date = None
    else:
        start_date = now - timedelta(days=days_filter)

    # === CURRENTLY ONLINE USERS (OPTIMIZED) ===
    online_threshold = now - timedelta(minutes=15)
    online_users_data = []

    # Get users with recent page views - use select_related to avoid N+1 queries
    recent_views = PageView.objects.filter(
        created_at__gte=online_threshold,
        user__isnull=False
    ).select_related('user', 'user__profile').order_by('user', '-created_at').distinct('user')

    # Process users (already have latest view per user from distinct)
    for latest_view in recent_views:
        user = latest_view.user

        browser = 'Unknown'
        os = 'Unknown'
        device_type = 'Unknown'
        ip_address = 'Unknown'

        if isinstance(latest_view.device_info, dict):
            browser_full = latest_view.device_info.get('browser', 'Unknown')
            # Extract browser family, handling mobile browsers properly
            browser_parts = browser_full.split() if browser_full else []
            if browser_parts:
                if browser_parts[0] == 'Mobile' and len(browser_parts) > 1:
                    browser = browser_parts[1]
                elif len(browser_parts) > 1 and browser_parts[-1] == 'Mobile':
                    browser = browser_parts[0]
                else:
                    browser = browser_parts[0]
            else:
                browser = 'Unknown'
            os = latest_view.device_info.get('os', 'Unknown')

            # Determine device type
            if latest_view.device_info.get('is_mobile'):
                device_type = 'Mobile'
            elif latest_view.device_info.get('is_tablet'):
                device_type = 'Tablet'
            elif latest_view.device_info.get('is_pc'):
                device_type = 'Desktop'

            ip_address = latest_view.device_info.get('ip_address', 'Unknown')

        # Build roles list
        roles = []
        if user.is_superuser:
            roles.append('Admin')
            roles.append('Developer')
            roles.append('Staff')
        elif hasattr(user, 'profile') and user.profile.is_developer:
            roles.append('Developer')
            roles.append('Staff')
        elif user.is_staff:
            roles.append('Staff')

        if not roles:
            roles.append('User')

        # Count page views for this user in the last 15 min
        page_count = PageView.objects.filter(
            user=user,
            created_at__gte=online_threshold
        ).count()

        online_users_data.append({
            'username': user.username,
            'last_seen': latest_view.created_at,
            'page_count': page_count,
            'browser': browser,
            'os': os,
            'device_type': device_type,
            'ip_address': ip_address,
            'roles': roles,
        })

    # Sort by last seen (most recent first)
    online_users_data.sort(key=lambda x: x['last_seen'], reverse=True)

    # === PER-USER ANALYTICS (OPTIMIZED) ===
    # Use aggregation to calculate all stats in a few queries instead of N+1 queries
    from django.db.models import Exists, OuterRef, Subquery

    # Get all users with aggregated stats
    all_users = User.objects.select_related('profile').annotate(
        # Page view stats
        page_views_period=Count(
            'pageview__id',
            filter=Q(pageview__created_at__gte=start_date) if start_date else Q(),
            distinct=True
        ),
        page_views_all_time=Count('pageview__id', distinct=True),
        last_seen=Max('pageview__created_at'),
        # Queue entry stats
        queue_entries_period=Count(
            'queue_entries__id',
            filter=Q(queue_entries__created_at__gte=start_date) if start_date else Q(),
            distinct=True
        ),
        queue_entries_all_time=Count('queue_entries__id', distinct=True),
        # Feedback stats
        feedback_submitted_period=Count(
            'feedback_submissions__id',
            filter=Q(feedback_submissions__created_at__gte=start_date) if start_date else Q(),
            distinct=True
        ),
        feedback_submitted_all_time=Count('feedback_submissions__id', distinct=True),
    )
    # Don't filter - show all users including those with 0 activity

    # Build per_user_stats from annotated queryset
    per_user_stats = []
    for user in all_users:
        # Build roles list
        roles = []
        if user.is_superuser:
            roles.append('Admin')
            roles.append('Developer')
            roles.append('Staff')
        elif hasattr(user, 'profile') and user.profile.is_developer:
            roles.append('Developer')
            roles.append('Staff')
        elif user.is_staff:
            roles.append('Staff')

        if not roles:
            roles.append('User')

        per_user_stats.append({
            'user': user,  # Include user object for template
            'username': user.username,
            'email': user.email,
            'roles': roles,
            'last_seen': user.last_seen,
            # Period data (what user requested)
            'page_views_period': user.page_views_period,
            'queue_entries_period': user.queue_entries_period,
            'feedback_submitted_period': user.feedback_submitted_period,
            # All-time data (for comparison)
            'page_views_all_time': user.page_views_all_time,
            'queue_entries_all_time': user.queue_entries_all_time,
            'feedback_submitted_all_time': user.feedback_submitted_all_time,
            # Also keep these for the "Top 10 Recently Active Users" table
            'page_views': user.page_views_period,
            'queue_submissions': user.queue_entries_period,
            'feedback_count': user.feedback_submitted_period,
            'last_activity': user.last_seen,
            'is_online': user.last_seen and user.last_seen >= online_threshold,
        })

    # Sort by last seen (most recent first)
    per_user_stats.sort(key=lambda x: x['last_seen'] if x['last_seen'] else timezone.datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    # === GLOBAL ANALYTICS ===
    # Page views
    page_views_query = PageView.objects.all()
    if start_date:
        page_views_filtered = page_views_query.filter(created_at__gte=start_date)
    else:
        page_views_filtered = page_views_query

    page_views_all_time = page_views_query.count()
    page_views_period = page_views_filtered.count()

    # API endpoints to exclude from top pages (tracked separately)
    api_endpoint_patterns = ['api/machine-status', 'notifications/api/list', 'schedule/api']

    # Count API endpoint hits using contains
    api_hits = {}
    api_hits['API Machine Status'] = page_views_filtered.filter(path__contains='api/machine-status').count()
    api_hits['Notifications API'] = page_views_filtered.filter(path__contains='notifications/api/list').count()
    api_hits['Schedule API'] = page_views_filtered.filter(path__contains='schedule/api').count()

    # Top pages (excluding API endpoints using Q objects for OR conditions)
    top_pages_qs = page_views_filtered
    for pattern in api_endpoint_patterns:
        top_pages_qs = top_pages_qs.exclude(path__contains=pattern)

    top_pages = top_pages_qs.values('page_title').annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    # Queue stats
    queue_all = QueueEntry.objects.all()
    if start_date:
        queue_filtered = queue_all.filter(created_at__gte=start_date)
    else:
        queue_filtered = queue_all

    queue_stats = {
        'total_period': queue_filtered.count(),
        'total_all_time': queue_all.count(),
        'completed_period': queue_filtered.filter(status='completed').count(),
        'completed_all_time': queue_all.filter(status='completed').count(),
    }

    # Feedback stats
    feedback_all = Feedback.objects.all()
    if start_date:
        feedback_filtered = feedback_all.filter(created_at__gte=start_date)
    else:
        feedback_filtered = feedback_all

    feedback_stats = {
        'total': feedback_all.count(),
        'total_period': feedback_filtered.count(),
        'new': feedback_all.filter(status='new').count(),
        'reviewed': feedback_all.filter(status='reviewed').count(),
        'completed': feedback_all.filter(status='completed').count(),
    }

    # Device/Browser breakdown (CACHED to avoid iterating through all PageViews)
    # Cache key based on filter period to invalidate when changing filters
    from django.core.cache import cache
    cache_key = f'analytics_device_browser_{days_filter}'
    cached_data = cache.get(cache_key)

    if cached_data:
        mobile_count = cached_data['mobile_count']
        desktop_count = cached_data['desktop_count']
        tablet_count = cached_data['tablet_count']
        top_browsers = cached_data['top_browsers']
        browser_device_stats = cached_data['browser_device_stats']
    else:
        # Only iterate if cache miss - sample up to 10,000 recent views for efficiency
        device_views = page_views_filtered.order_by('-created_at')[:10000]
        mobile_count = 0
        desktop_count = 0
        tablet_count = 0

        browser_counts = {}
        browser_device_breakdown = {}
        generic_browsers = {'Mobile', 'Other', 'Unknown', 'Generic', 'Tablet', 'Desktop', 'Android', 'iPhone', 'iPad'}

        for pv in device_views:
            device_info = pv.device_info
            if isinstance(device_info, dict):
                if device_info.get('is_mobile'):
                    mobile_count += 1
                elif device_info.get('is_tablet'):
                    tablet_count += 1
                elif device_info.get('is_pc'):
                    desktop_count += 1

                browser = device_info.get('browser', 'Unknown')
                browser_parts = browser.split() if browser else []
                if browser_parts:
                    if browser_parts[0] == 'Mobile' and len(browser_parts) > 1:
                        browser_family = browser_parts[1]
                    elif len(browser_parts) > 1 and browser_parts[-1] == 'Mobile':
                        browser_family = browser_parts[0]
                    else:
                        browser_family = browser_parts[0]
                else:
                    browser_family = 'Unknown'

                if browser_family not in generic_browsers:
                    browser_counts[browser_family] = browser_counts.get(browser_family, 0) + 1

                    device_type = 'Desktop'
                    if device_info.get('is_mobile'):
                        device_type = 'Mobile'
                    elif device_info.get('is_tablet'):
                        device_type = 'Tablet'

                    key = f"{browser_family} on {device_type}"
                    browser_device_breakdown[key] = browser_device_breakdown.get(key, 0) + 1

        top_browsers = sorted(browser_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        browser_device_stats = sorted(browser_device_breakdown.items(), key=lambda x: x[1], reverse=True)[:10]

        # Cache for 5 minutes
        cache.set(cache_key, {
            'mobile_count': mobile_count,
            'desktop_count': desktop_count,
            'tablet_count': tablet_count,
            'top_browsers': top_browsers,
            'browser_device_stats': browser_device_stats,
        }, 300)

    # User type breakdown
    user_types = {
        'total': User.objects.count(),
        'staff': User.objects.filter(is_staff=True).count(),
        'developers': UserProfile.objects.filter(is_developer=True).count(),
        'active_period': page_views_filtered.filter(user__isnull=False).values('user').distinct().count(),
    }

    # === PEAK USAGE TIMES ===
    # Use SQLite's strftime function (Turso-compatible)
    from django.db.models import Func, IntegerField

    # Custom function for extracting hour using SQLite's strftime
    class Hour(Func):
        function = 'CAST'
        template = "%(function)s(strftime('%%H', %(expressions)s) AS INTEGER)"
        output_field = IntegerField()

    # Custom function for extracting weekday using SQLite's strftime
    class Weekday(Func):
        function = 'CAST'
        template = "%(function)s(strftime('%%w', %(expressions)s) AS INTEGER)"
        output_field = IntegerField()

    # Hour of day breakdown (0-23)
    hourly_views = page_views_filtered.annotate(
        hour=Hour('created_at')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')

    hour_labels = [f"{h['hour']}:00" for h in hourly_views]
    hour_counts = [h['count'] for h in hourly_views]

    # Day of week breakdown (0=Sunday, 6=Saturday in SQLite)
    daily_views = page_views_filtered.annotate(
        weekday=Weekday('created_at')
    ).values('weekday').annotate(
        count=Count('id')
    ).order_by('weekday')

    # SQLite strftime %w returns 0=Sunday, 6=Saturday
    day_map = {0: 'Sunday', 1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 4: 'Thursday', 5: 'Friday', 6: 'Saturday'}
    day_labels = [day_map.get(d['weekday'], 'Unknown') for d in daily_views]
    day_counts = [d['count'] for d in daily_views]

    # === SESSION DURATION (CACHED) ===
    cache_key_session = f'analytics_session_duration_{days_filter}'
    avg_session_duration = cache.get(cache_key_session)

    if avg_session_duration is None:
        # Sample up to 5000 sessions for efficiency
        sessions = page_views_filtered.values('session_key').annotate(
            first_view=Min('created_at'),
            last_view=Max('created_at'),
            view_count=Count('id')
        ).filter(view_count__gt=1).order_by('-last_view')[:5000]

        session_durations = []
        for session in sessions:
            duration = (session['last_view'] - session['first_view']).total_seconds() / 60  # minutes
            if duration < 120:  # Ignore sessions longer than 2 hours (likely stale)
                session_durations.append(duration)

        avg_session_duration = sum(session_durations) / len(session_durations) if session_durations else 0
        cache.set(cache_key_session, avg_session_duration, 300)  # Cache 5 minutes

    # === USER RETENTION ===
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    dau = PageView.objects.filter(
        created_at__gte=today_start,
        user__isnull=False
    ).values('user').distinct().count()

    wau = PageView.objects.filter(
        created_at__gte=week_start,
        user__isnull=False
    ).values('user').distinct().count()

    mau = PageView.objects.filter(
        created_at__gte=month_start,
        user__isnull=False
    ).values('user').distinct().count()

    # New vs Returning users (this period)
    new_users_period = User.objects.filter(date_joined__gte=start_date).count() if start_date else 0
    returning_users = page_views_filtered.filter(user__isnull=False).exclude(
        user__date_joined__gte=start_date
    ).values('user').distinct().count() if start_date else 0

    # === QUEUE METRICS (CACHED) ===
    # Calculate average wait time (time from submission to completion)
    cache_key_queue = f'analytics_queue_wait_{days_filter}'
    avg_queue_wait_time = cache.get(cache_key_queue)

    if avg_queue_wait_time is None:
        # Sample up to 1000 recent completed entries for efficiency
        completed_queue_entries = queue_filtered.filter(
            status='completed',
            updated_at__isnull=False
        ).order_by('-updated_at')[:1000]

        wait_times = []
        for entry in completed_queue_entries:
            wait_time = (entry.updated_at - entry.created_at).total_seconds() / 3600  # hours
            if wait_time < 168:  # Ignore entries over 1 week
                wait_times.append(wait_time)

        avg_queue_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0
        cache.set(cache_key_queue, avg_queue_wait_time, 300)  # Cache 5 minutes

    # Queue completion rate
    total_queue_submissions = queue_filtered.count()
    completed_queue_count = queue_filtered.filter(status='completed').count()
    queue_completion_rate = (completed_queue_count / total_queue_submissions * 100) if total_queue_submissions > 0 else 0

    # Most popular machines
    popular_machines = queue_filtered.filter(
        assigned_machine__isnull=False
    ).values(
        'assigned_machine__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:5]

    # === TOP 10 ACTIVE USERS ===
    top_10_users = per_user_stats[:10] if len(per_user_stats) >= 10 else per_user_stats

    # === FEEDBACK RESPONSE TIME (CACHED) ===
    cache_key_feedback = f'analytics_feedback_times_{days_filter}'
    cached_feedback_times = cache.get(cache_key_feedback)

    if cached_feedback_times:
        avg_feedback_review_time = cached_feedback_times['review_time']
        avg_feedback_completion_time = cached_feedback_times['completion_time']
    else:
        # Sample up to 500 recent feedback items for efficiency
        feedback_to_reviewed = Feedback.objects.filter(
            status__in=['reviewed', 'completed'],
            reviewed_at__isnull=False
        ).order_by('-reviewed_at')[:500]

        review_times = []
        for fb in feedback_to_reviewed:
            time_diff = (fb.reviewed_at - fb.created_at).total_seconds() / 3600  # hours
            if time_diff < 720:  # Ignore outliers over 30 days
                review_times.append(time_diff)

        avg_feedback_review_time = sum(review_times) / len(review_times) if review_times else 0

        feedback_to_completed = Feedback.objects.filter(
            status='completed',
            reviewed_at__isnull=False,
            updated_at__isnull=False
        ).order_by('-updated_at')[:500]

        completion_times = []
        for fb in feedback_to_completed:
            time_diff = (fb.updated_at - fb.reviewed_at).total_seconds() / 3600  # hours
            if time_diff < 720:  # Ignore outliers over 30 days
                completion_times.append(time_diff)

        avg_feedback_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0

        cache.set(cache_key_feedback, {
            'review_time': avg_feedback_review_time,
            'completion_time': avg_feedback_completion_time,
        }, 300)  # Cache 5 minutes

    # === ERROR STATISTICS ===
    from .models import ErrorLog

    error_logs_filtered = ErrorLog.objects.all()
    if start_date:
        error_logs_filtered = error_logs_filtered.filter(created_at__gte=start_date)

    total_errors = error_logs_filtered.count()
    error_404_count = error_logs_filtered.filter(error_type='404').count()
    error_500_count = error_logs_filtered.filter(error_type='500').count()
    error_403_count = error_logs_filtered.filter(error_type='403').count()

    # Most common error paths
    top_error_paths = error_logs_filtered.values('path', 'error_type').annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    # Recent errors (last 10)
    recent_errors = error_logs_filtered.select_related('user').order_by('-created_at')[:10]

    # Get Turso database usage metrics
    import os
    from .turso_api_client import TursoAPIClient

    turso_client = TursoAPIClient()
    turso_usage = turso_client.get_usage_metrics()

    # Turso plan limits (Free tier defaults)
    turso_limits = {
        'storage_mb': int(os.environ.get('TURSO_MAX_STORAGE_MB', 5120)),  # 5GB
        'rows_read_monthly': int(os.environ.get('TURSO_MAX_ROWS_READ', 500_000_000)),  # 500M
        'rows_written_monthly': int(os.environ.get('TURSO_MAX_ROWS_WRITTEN', 10_000_000)),  # 10M
    }

    # Calculate usage percentages
    turso_stats = None
    if turso_usage:
        turso_stats = {
            'rows_read': turso_usage['rows_read'],
            'rows_written': turso_usage['rows_written'],
            'storage_mb': turso_usage['storage_bytes'] / (1024 * 1024),
            'databases': turso_usage.get('databases', 0),
            'rows_read_percent': (turso_usage['rows_read'] / turso_limits['rows_read_monthly'] * 100),
            'rows_written_percent': (turso_usage['rows_written'] / turso_limits['rows_written_monthly'] * 100),
            'storage_percent': (turso_usage['storage_bytes'] / (turso_limits['storage_mb'] * 1024 * 1024) * 100),
        }

    context = {
        'days_filter': days_filter,
        'online_users_data': online_users_data,
        'users_online': len(online_users_data),
        'per_user_stats': per_user_stats,
        'page_views_period': page_views_period,
        'page_views_all_time': page_views_all_time,
        'top_pages': top_pages,
        'queue_stats': queue_stats,
        'feedback_stats': feedback_stats,
        'user_types': user_types,
        'device_breakdown': {
            'mobile': mobile_count,
            'desktop': desktop_count,
            'tablet': tablet_count,
        },
        'top_browsers': top_browsers,
        'browser_device_stats': browser_device_stats,
        'api_hits': api_hits,
        'turso_usage': turso_stats,
        'turso_limits': turso_limits,
        'turso_org_slug': os.environ.get('TURSO_ORG_SLUG', 'unknown'),
        # Peak usage times
        'hour_labels': hour_labels,
        'hour_counts': hour_counts,
        'day_labels': day_labels,
        'day_counts': day_counts,
        # Session metrics
        'avg_session_duration': round(avg_session_duration, 2),
        # User retention
        'dau': dau,
        'wau': wau,
        'mau': mau,
        'new_users_period': new_users_period,
        'returning_users': returning_users,
        # Queue metrics
        'avg_queue_wait_time': round(avg_queue_wait_time, 2),
        'queue_completion_rate': round(queue_completion_rate, 1),
        'popular_machines': popular_machines,
        # Top users
        'top_10_users': top_10_users,
        # Feedback response time
        'avg_feedback_review_time': round(avg_feedback_review_time, 2),
        'avg_feedback_completion_time': round(avg_feedback_completion_time, 2),
        # Error statistics
        'total_errors': total_errors,
        'error_404_count': error_404_count,
        'error_500_count': error_500_count,
        'error_403_count': error_403_count,
        'top_error_paths': top_error_paths,
        'recent_errors': recent_errors,
    }

    return render(request, 'calendarEditor/admin/developer_data.html', context)


@staff_member_required
def promote_to_developer(request, user_id):
    """Promote a staff user to developer (superuser only)."""
    if not request.user.is_superuser:
        messages.error(request, 'Only superusers can promote users to developer.')
        return redirect('admin_users')

    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)

        # Must be staff first
        if not user.is_staff:
            messages.error(request, f'{user.username} must be staff before becoming developer.')
            return redirect('admin_users')

        try:
            profile = user.profile
            if profile.is_developer:
                messages.info(request, f'{user.username} is already a developer.')
            else:
                profile.is_developer = True
                profile.developer_promoted_by = request.user
                profile.developer_promoted_at = timezone.now()
                profile.save()

                # Send notification
                notifications.create_notification(
                    recipient=user,
                    notification_type='account_promoted',
                    title='You have been promoted to developer',
                    message=f'Congratulations! Admin {request.user.username} has promoted you to developer. You now have access to the Tasks and Data pages.',
                    triggering_user=request.user,
                )

                messages.success(request, f'{user.username} promoted to developer!')
        except UserProfile.DoesNotExist:
            messages.error(request, f'{user.username} does not have a profile.')

    return redirect('admin_users')


@staff_member_required
def demote_from_developer(request, user_id):
    """Demote a developer back to staff (superuser only)."""
    if not request.user.is_superuser:
        messages.error(request, 'Only superusers can demote developers.')
        return redirect('admin_users')

    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)

        try:
            profile = user.profile
            if not profile.is_developer:
                messages.info(request, f'{user.username} is not a developer.')
            else:
                profile.is_developer = False
                profile.save()

                # Send notification
                notifications.create_notification(
                    recipient=user,
                    notification_type='account_demoted',
                    title='Developer role removed',
                    message=f'Admin {request.user.username} has removed your developer role. You no longer have access to the Tasks and Data pages, but retain staff privileges.',
                    triggering_user=request.user,
                )

                messages.success(request, f'{user.username} demoted from developer to staff.')
        except UserProfile.DoesNotExist:
            messages.error(request, f'{user.username} does not have a profile.')

    return redirect('admin_users')
