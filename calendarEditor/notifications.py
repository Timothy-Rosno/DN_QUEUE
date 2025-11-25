"""
Notification system helpers for creating and managing user notifications.
"""
from django.contrib.auth.models import User
from django.db.models import Q
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.conf import settings
import requests
from .models import Notification, NotificationPreference, QueueEntry, QueuePreset, Machine


def lookup_slack_member_id(user):
    """
    Automatically look up a user's Slack member ID using Slack API.
    Tries in order: Django user ID → email → display name

    Args:
        user: Django User object

    Returns:
        str: Slack member ID (e.g., 'U01234ABCD') or None if not found
    """
    if not settings.SLACK_ENABLED:
        return None

    try:
        # Get all users from Slack
        response = requests.get(
            'https://slack.com/api/users.list',
            headers={
                'Authorization': f'Bearer {settings.SLACK_BOT_TOKEN}',
            },
            timeout=10
        )

        result = response.json()
        if not result.get('ok'):
            print(f"Slack API error in users.list: {result.get('error', 'Unknown error')}")
            return None

        slack_users = result.get('members', [])

        # Strategy 1: Try to match by email
        if user.email:
            for slack_user in slack_users:
                if not slack_user.get('deleted') and not slack_user.get('is_bot'):
                    profile = slack_user.get('profile', {})
                    if profile.get('email', '').lower() == user.email.lower():
                        member_id = slack_user.get('id')
                        print(f"Found Slack member ID for {user.username} by email: {member_id}")
                        return member_id

        # Strategy 2: Try to match by display name or real name
        user_full_name = f"{user.first_name} {user.last_name}".strip().lower()
        if user_full_name:
            for slack_user in slack_users:
                if not slack_user.get('deleted') and not slack_user.get('is_bot'):
                    profile = slack_user.get('profile', {})
                    slack_real_name = profile.get('real_name', '').lower()
                    slack_display_name = profile.get('display_name', '').lower()

                    if user_full_name == slack_real_name or user_full_name == slack_display_name:
                        member_id = slack_user.get('id')
                        print(f"Found Slack member ID for {user.username} by name: {member_id}")
                        return member_id

        # Strategy 3: Try to match by username
        if user.username:
            for slack_user in slack_users:
                if not slack_user.get('deleted') and not slack_user.get('is_bot'):
                    slack_name = slack_user.get('name', '').lower()
                    profile = slack_user.get('profile', {})
                    slack_display_name = profile.get('display_name', '').lower()

                    if user.username.lower() == slack_name or user.username.lower() == slack_display_name:
                        member_id = slack_user.get('id')
                        print(f"Found Slack member ID for {user.username} by username: {member_id}")
                        return member_id

        print(f"Could not find Slack member ID for {user.username}")
        return None

    except Exception as e:
        print(f"Error looking up Slack member ID for {user.username}: {e}")
        return None


def send_slack_dm(user, title, message, notification=None):
    """
    Send a Slack direct message to a user with a secure login link.
    Automatically looks up and caches Slack member ID if not set.

    Args:
        user: Django User object
        title: Notification title
        message: Notification message
        notification: Optional Notification object (for generating secure login link)

    Returns:
        bool: True if sent successfully, False otherwise
    """
    if not settings.SLACK_ENABLED:
        return False

    try:
        # Check if user has profile
        if not hasattr(user, 'profile'):
            return False

        slack_member_id = user.profile.slack_member_id

        # If no member ID set, try to look it up automatically
        if not slack_member_id:
            slack_member_id = lookup_slack_member_id(user)
            if slack_member_id:
                # Cache the found member ID
                user.profile.slack_member_id = slack_member_id
                user.profile.save()
                print(f"Cached Slack member ID for {user.username}: {slack_member_id}")
            else:
                # Couldn't find member ID
                return False

        # Format message for Slack
        slack_text = f"*{title}*\n{message}"

        # Add secure login link if notification is provided
        if notification:
            from .models import OneTimeLoginToken
            from django.urls import reverse

            # Get the action URL for this notification
            action_url = notification.get_notification_url()

            # Create a secure one-time login token
            login_token = OneTimeLoginToken.create_for_notification(
                user=user,
                notification=notification,
                redirect_url=action_url
            )

            # Build the full URL with token
            token_path = reverse('token_login', kwargs={'token': login_token.token})
            full_url = f"{settings.BASE_URL}{token_path}"

            # Append link to message
            slack_text += f"\n\n<{full_url}|View Details>"

        # Send message via Slack API
        response = requests.post(
            'https://slack.com/api/chat.postMessage',
            headers={
                'Authorization': f'Bearer {settings.SLACK_BOT_TOKEN}',
                'Content-Type': 'application/json'
            },
            json={
                'channel': slack_member_id,  # DM using member ID
                'text': slack_text,
                'unfurl_links': False,
                'unfurl_media': False,
            },
            timeout=5
        )

        result = response.json()
        if not result.get('ok'):
            print(f"Slack API error: {result.get('error', 'Unknown error')}")
            return False

        return True

    except Exception as e:
        print(f"Failed to send Slack DM to {user.username}: {e}")
        return False


def create_notification(recipient, notification_type, title, message, **kwargs):
    """
    Create a notification for a user and send via WebSocket and Slack.

    Args:
        recipient: User object who will receive the notification
        notification_type: Type of notification (from Notification.NOTIFICATION_TYPES)
        title: Short title for the notification
        message: Detailed message
        **kwargs: Optional related objects (related_preset, related_queue_entry, related_machine, triggering_user)

    Returns:
        Notification object
    """
    print(f"[CREATE_NOTIFICATION] Creating notification for {recipient.username}, type={notification_type}")

    try:
        notification = Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            related_preset=kwargs.get('related_preset'),
            related_queue_entry=kwargs.get('related_queue_entry'),
            related_machine=kwargs.get('related_machine'),
            triggering_user=kwargs.get('triggering_user'),
        )
        print(f"[CREATE_NOTIFICATION] Notification {notification.id} created in database")
    except Exception as e:
        print(f"[CREATE_NOTIFICATION] ERROR creating notification in database: {e}")
        import traceback
        traceback.print_exc()
        raise

    # Send via WebSocket
    try:
        print(f"[CREATE_NOTIFICATION] Attempting WebSocket send...")
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user_{recipient.id}_notifications',
            {
                'type': 'notification',
                'notification_id': notification.id,
                'notification_type': notification_type,
                'title': title,
                'message': message,
                'created_at': notification.created_at.isoformat(),
            }
        )
        print(f"[CREATE_NOTIFICATION] WebSocket send completed")
    except Exception as e:
        print(f"[CREATE_NOTIFICATION] WebSocket send failed: {e}")
        import traceback
        traceback.print_exc()

    # Send via Slack if enabled and user has Slack ID
    try:
        print(f"[CREATE_NOTIFICATION] Attempting Slack send (SLACK_ENABLED={settings.SLACK_ENABLED})...")
        if settings.SLACK_ENABLED:
            send_slack_dm(recipient, title, message, notification)
            print(f"[CREATE_NOTIFICATION] Slack send completed")
        else:
            print(f"[CREATE_NOTIFICATION] Slack disabled, skipping")
    except Exception as e:
        print(f"[CREATE_NOTIFICATION] Slack send failed: {e}")
        import traceback
        traceback.print_exc()

    print(f"[CREATE_NOTIFICATION] Returning notification {notification.id}")
    return notification


def notify_preset_created(preset, triggering_user):
    """Notify users about a newly created public preset."""
    if not preset.is_public:
        return

    # Get all users except the creator
    if preset.creator:
        users = User.objects.exclude(id=preset.creator.id).filter(is_active=True)
    else:
        users = User.objects.filter(is_active=True)

    for user in users:
        prefs = NotificationPreference.get_or_create_for_user(user)
        if prefs.notify_public_preset_created and prefs.in_app_notifications:
            create_notification(
                recipient=user,
                notification_type='preset_created',
                title='New Public Preset Created',
                message=f'{triggering_user.username} created public preset "{preset.display_name}"',
                related_preset=preset,
                triggering_user=triggering_user,
            )


def notify_preset_edited(preset, triggering_user, changes=None):
    """Notify users about preset edits with change details."""
    notified_users = set()  # Track who we've notified to avoid duplicates

    # Build the change message suffix
    change_msg = ""
    if changes:
        change_msg = f": {changes}"

    if preset.is_public:
        # First, notify users following this specific preset
        followers = preset.followers.exclude(user=triggering_user).filter(user__is_active=True)
        for prefs in followers:
            user = prefs.user
            if prefs.notify_followed_preset_edited and prefs.in_app_notifications:
                create_notification(
                    recipient=user,
                    notification_type='preset_edited',
                    title='Followed Preset Updated',
                    message=f'{triggering_user.username} changed preset "{preset.display_name}"{change_msg}',
                    related_preset=preset,
                    triggering_user=triggering_user,
                )
                notified_users.add(user.id)

        # Then, notify all other users with public preset edit notifications enabled
        # (excluding followers to avoid duplicate notifications)
        users = User.objects.exclude(id=triggering_user.id).filter(is_active=True).exclude(id__in=notified_users)
        for user in users:
            prefs = NotificationPreference.get_or_create_for_user(user)
            if prefs.notify_public_preset_edited and prefs.in_app_notifications:
                create_notification(
                    recipient=user,
                    notification_type='preset_edited',
                    title='Public Preset Updated',
                    message=f'{triggering_user.username} changed preset "{preset.display_name}"{change_msg}',
                    related_preset=preset,
                    triggering_user=triggering_user,
                )
    else:
        # Private preset - notify the owner if someone else edited it
        if preset.creator and preset.creator != triggering_user:
            prefs = NotificationPreference.get_or_create_for_user(preset.creator)
            if prefs.notify_private_preset_edited and prefs.in_app_notifications:
                create_notification(
                    recipient=preset.creator,
                    notification_type='preset_edited',
                    title='Your Private Preset Was Edited',
                    message=f'{triggering_user.username} changed your private preset "{preset.display_name}"{change_msg}',
                    related_preset=preset,
                    triggering_user=triggering_user,
                )


def notify_preset_deleted(preset_data, triggering_user):
    """
    Notify users about preset deletion.

    Args:
        preset_data: Dict with preset info (since preset is deleted, we can't use the object)
                    Should contain: 'display_name', 'is_public', 'creator_id', 'follower_ids' (optional)
        triggering_user: User who deleted the preset
    """
    if preset_data.get('is_public'):
        notified_users = set()  # Track who we've notified to avoid duplicates

        # First, notify users who were following this preset
        follower_ids = preset_data.get('follower_ids', [])
        if follower_ids:
            followers = User.objects.filter(id__in=follower_ids, is_active=True).exclude(id=triggering_user.id)
            for user in followers:
                prefs = NotificationPreference.get_or_create_for_user(user)
                if prefs.notify_followed_preset_deleted and prefs.in_app_notifications:
                    create_notification(
                        recipient=user,
                        notification_type='preset_deleted',
                        title='Followed Preset Deleted',
                        message=f'{triggering_user.username} deleted public preset "{preset_data["display_name"]}" that you were following',
                        triggering_user=triggering_user,
                    )
                    notified_users.add(user.id)

        # Then, notify all other users with public preset deletion notifications enabled
        # (excluding followers to avoid duplicate notifications)
        users = User.objects.exclude(id=triggering_user.id).filter(is_active=True).exclude(id__in=notified_users)
        for user in users:
            prefs = NotificationPreference.get_or_create_for_user(user)
            if prefs.notify_public_preset_deleted and prefs.in_app_notifications:
                create_notification(
                    recipient=user,
                    notification_type='preset_deleted',
                    title='Public Preset Deleted',
                    message=f'{triggering_user.username} deleted public preset "{preset_data["display_name"]}"',
                    triggering_user=triggering_user,
                )
    else:
        # Private preset - notify the owner if someone else deleted it
        creator_id = preset_data.get('creator_id')
        if creator_id and creator_id != triggering_user.id:
            try:
                creator = User.objects.get(id=creator_id)
                prefs = NotificationPreference.get_or_create_for_user(creator)
                if prefs.notify_private_preset_edited and prefs.in_app_notifications:
                    create_notification(
                        recipient=creator,
                        notification_type='preset_deleted',
                        title='Your Private Preset Was Deleted',
                        message=f'{triggering_user.username} deleted your private preset "{preset_data["display_name"]}"',
                        triggering_user=triggering_user,
                    )
            except User.DoesNotExist:
                pass


def notify_on_deck(queue_entry, reason=None):
    """
    Notify a user that they're now ON DECK (position #1 in queue).
    This is a CRITICAL notification that always sends regardless of user preferences.

    Args:
        queue_entry: The queue entry at position #1
        reason: Optional reason why machine isn't ready (e.g., 'maintenance', 'running', 'cooldown', 'disconnected')
    """
    user = queue_entry.user
    machine = queue_entry.assigned_machine
    print(f"[NOTIFY_ON_DECK] Creating notification for user {user.username}, reason={reason}")

    # Build message based on reason
    if reason == 'maintenance':
        message = f'Your request "{queue_entry.title}" is now #1 in line for {machine.name}. The machine is currently in maintenance mode - you will be notified when it becomes available.'
    elif reason == 'running':
        message = f'Your request "{queue_entry.title}" is now #1 in line for {machine.name}. The machine is currently running another measurement - you will be notified when it becomes available.'
    elif reason == 'cooldown':
        message = f'Your request "{queue_entry.title}" is now #1 in line for {machine.name}. The machine is currently in cooldown - you will be notified when it becomes available.'
    elif reason == 'disconnected':
        message = f'Your request "{queue_entry.title}" is now #1 in line for {machine.name}. The machine is currently disconnected - you will be notified when it becomes available.'
    elif reason == 'unavailable':
        message = f'Your request "{queue_entry.title}" is now #1 in line for {machine.name}. The machine is currently unavailable - you will be notified when it becomes available.'
    else:
        message = f'Your request "{queue_entry.title}" is now #1 in line for {machine.name}. Get ready!'

    # Always send this critical notification - it's essential for queue system to work
    notif = create_notification(
        recipient=user,
        notification_type='on_deck',
        title='ON DECK - You\'re Next!',
        message=message,
        related_queue_entry=queue_entry,
        related_machine=machine,
    )
    print(f"[NOTIFY_ON_DECK] Notification created with ID {notif.id}")


def notify_bumped_from_on_deck(queue_entry, reason='priority request'):
    """
    Notify a user that they were bumped from ON DECK position (position #1).
    This is always sent regardless of user preferences since it's critical info.

    Args:
        queue_entry: The QueueEntry that was bumped from position #1
        reason: Reason for being bumped (e.g., 'priority request', 'rush job', 'admin action')
    """
    user = queue_entry.user
    prefs = NotificationPreference.get_or_create_for_user(user)

    if prefs.in_app_notifications:
        create_notification(
            recipient=user,
            notification_type='queue_moved',
            title=f'Queue Position Changed',
            message=f'Your request "{queue_entry.title}" was moved from position #1 due to a {reason} taking precedence on {queue_entry.assigned_machine.name}. We apologize for the inconvenience. You are now at position #{queue_entry.queue_position}.',
            related_queue_entry=queue_entry,
            related_machine=queue_entry.assigned_machine,
        )


def notify_ready_for_check_in(queue_entry, bypass_preferences=False):
    """
    Notify user when the machine becomes available and they can check in.

    This is the primary "Time for Check-In" notification sent when:
    - User is at position #1 (ON DECK)
    - Machine status changes to 'idle' (becomes available)
    - Previous job completes or is cancelled

    This is a CRITICAL notification that always sends regardless of user preferences.

    Args:
        queue_entry: The queue entry at position #1
        bypass_preferences: Deprecated - notification always sends
    """
    user = queue_entry.user
    print(f"[NOTIFY_READY] Creating notification for user {user.username}")
    # Always send this critical notification - it's essential for queue system to work
    notif = create_notification(
        recipient=user,
        notification_type='ready_for_check_in',
        title='Ready for Check-In!',
        message=f'The machine {queue_entry.assigned_machine.name} is now available. You can check in to start your measurement "{queue_entry.title}"!',
        related_queue_entry=queue_entry,
        related_machine=queue_entry.assigned_machine,
    )
    print(f"[NOTIFY_READY] Notification created with ID {notif.id}")


def notify_queue_position_change(queue_entry, old_position, new_position):
    """Notify user when their queue position changes."""
    user = queue_entry.user
    prefs = NotificationPreference.get_or_create_for_user(user)

    if prefs.notify_queue_position_change and prefs.in_app_notifications:
        direction = "up" if new_position < old_position else "down"
        create_notification(
            recipient=user,
            notification_type='queue_moved',
            title=f'Queue Position Changed',
            message=f'Your request "{queue_entry.title}" moved {direction} from position #{old_position} to #{new_position} on {queue_entry.assigned_machine.name}',
            related_queue_entry=queue_entry,
            related_machine=queue_entry.assigned_machine,
        )


def notify_machine_queue_addition(queue_entry, triggering_user):
    """Notify users waiting in the same machine queue about a new addition."""
    machine = queue_entry.assigned_machine

    # Get all users with queued entries on this machine (excluding the new entry's user)
    affected_users = User.objects.filter(
        queue_entries__assigned_machine=machine,
        queue_entries__status='queued'
    ).exclude(id=queue_entry.user.id).distinct()

    for user in affected_users:
        prefs = NotificationPreference.get_or_create_for_user(user)
        if prefs.notify_machine_queue_changes and prefs.in_app_notifications:
            create_notification(
                recipient=user,
                notification_type='queue_added',
                title='New Entry Added to Queue',
                message=f'{triggering_user.username} added "{queue_entry.title}" to {machine.name} queue',
                related_queue_entry=queue_entry,
                related_machine=machine,
                triggering_user=triggering_user,
            )


def notify_queue_added(queue_entry):
    """Notify user when their queue entry is successfully added."""
    user = queue_entry.user
    prefs = NotificationPreference.get_or_create_for_user(user)

    if prefs.notify_queue_added and prefs.in_app_notifications:
        machine = queue_entry.assigned_machine
        position_text = f" at position #{queue_entry.queue_position}" if queue_entry.queue_position else ""
        create_notification(
            recipient=user,
            notification_type='queue_added',
            title='Queue Entry Added',
            message=f'Your request "{queue_entry.title}" has been added to {machine.name}{position_text}',
            related_queue_entry=queue_entry,
            related_machine=machine,
        )


def notify_queue_cancelled(queue_entry, reason=None):
    """Notify user when their queue entry is cancelled."""
    user = queue_entry.user
    prefs = NotificationPreference.get_or_create_for_user(user)

    if prefs.notify_queue_cancelled and prefs.in_app_notifications:
        machine = queue_entry.assigned_machine
        message_text = f'Your request "{queue_entry.title}" on {machine.name} has been cancelled'
        if reason:
            message_text += f' - {reason}'

        create_notification(
            recipient=user,
            notification_type='queue_cancelled',
            title='Queue Entry Cancelled',
            message=message_text,
            related_queue_entry=queue_entry,
            related_machine=machine,
        )


def notify_checkout_reminder(queue_entry):
    """
    Notify user when their estimated measurement time has elapsed and they should check out.

    This notification is sent:
    - First time: when estimated duration expires
    - Repeat: every 2 hours (except 12 AM - 6 AM) until checkout
    - Unless: user clicks the notification to snooze for 6 hours

    Clicking the notification snoozes reminders for 6 hours.
    """
    user = queue_entry.user
    prefs = NotificationPreference.get_or_create_for_user(user)

    if prefs.notify_checkout_reminder and prefs.in_app_notifications:
        create_notification(
            recipient=user,
            notification_type='checkout_reminder',
            title='Measurement Time Expired',
            message=f'Predicted measurement time expired for "{queue_entry.title}" on {queue_entry.assigned_machine.name} -- did you forget to check out? (Click to snooze for 6 hours)',
            related_queue_entry=queue_entry,
            related_machine=queue_entry.assigned_machine,
        )


def notify_checkin_reminder(queue_entry):
    """
    Notify user when they're at position 1 but haven't checked in yet.

    This notification is sent:
    - First time: when entry becomes ready for check-in (machine available)
    - Repeat: every 6 hours until check-in
    - Unless: user clicks the notification to snooze for 24 hours
    - No time restrictions (sent 24/7)

    Clicking the notification snoozes reminders for 24 hours.
    """
    user = queue_entry.user
    prefs = NotificationPreference.get_or_create_for_user(user)

    # Using notify_ready_for_check_in preference since it's the same concept
    if prefs.notify_ready_for_check_in and prefs.in_app_notifications:
        create_notification(
            recipient=user,
            notification_type='checkin_reminder',
            title='Did You Forget to Check In?',
            message=f'"{queue_entry.title}" is ready for check-in on {queue_entry.assigned_machine.name}. The machine is available now. (Click to snooze for 24 hours)',
            related_queue_entry=queue_entry,
            related_machine=queue_entry.assigned_machine,
        )


def notify_machine_status_changed(queue_entry, admin_user):
    """
    Notify user when admin changes machine status to idle while they have a running measurement.

    This is sent when the machine becomes idle (due to admin action) and the user
    needs to check out their measurement.

    Args:
        queue_entry: The QueueEntry that is running
        admin_user: The admin User who changed the machine status
    """
    user = queue_entry.user
    prefs = NotificationPreference.get_or_create_for_user(user)

    if prefs.notify_machine_status_change and prefs.in_app_notifications:
        create_notification(
            recipient=user,
            notification_type='machine_status_changed',
            title='Time to Check Out',
            message=f'Administrator {admin_user.username} changed the machine status to idle. Please check out from "{queue_entry.title}" on {queue_entry.assigned_machine.name}.',
            related_queue_entry=queue_entry,
            related_machine=queue_entry.assigned_machine,
            triggering_user=admin_user,
        )


def notify_admin_check_in(queue_entry, admin_user):
    """
    Notify user when an admin checks them in.

    This notification informs the user that their measurement was started by an administrator.

    Args:
        queue_entry: The QueueEntry that was checked in
        admin_user: The admin User who performed the check-in
    """
    user = queue_entry.user
    prefs = NotificationPreference.get_or_create_for_user(user)

    if prefs.notify_admin_check_in and prefs.in_app_notifications:
        create_notification(
            recipient=user,
            notification_type='admin_check_in',
            title='Admin Check-In',
            message=f'Administrator {admin_user.username} checked you in to start "{queue_entry.title}" on {queue_entry.assigned_machine.name}.',
            related_queue_entry=queue_entry,
            related_machine=queue_entry.assigned_machine,
            triggering_user=admin_user,
        )


def notify_admin_checkout(queue_entry, admin_user):
    """
    Notify user when an admin checks them out.

    This notification informs the user that their measurement was ended by an administrator.

    Args:
        queue_entry: The QueueEntry that was checked out
        admin_user: The admin User who performed the checkout
    """
    user = queue_entry.user
    prefs = NotificationPreference.get_or_create_for_user(user)

    if prefs.notify_admin_checkout and prefs.in_app_notifications:
        create_notification(
            recipient=user,
            notification_type='admin_checkout',
            title='Admin Check-Out',
            message=f'Administrator {admin_user.username} checked you out from "{queue_entry.title}" on {queue_entry.assigned_machine.name}.',
            related_queue_entry=queue_entry,
            related_machine=queue_entry.assigned_machine,
            triggering_user=admin_user,
        )


def notify_admin_edit_entry(queue_entry, admin_user, changes_summary):
    """
    Notify user when an admin edits their queue entry.

    This notification informs the user that their queue entry was modified by an administrator.

    Args:
        queue_entry: The QueueEntry that was edited
        admin_user: The admin User who performed the edit
        changes_summary: String describing what was changed (e.g., "title, machine assignment")
    """
    user = queue_entry.user
    prefs = NotificationPreference.get_or_create_for_user(user)

    if prefs.notify_admin_edit_entry and prefs.in_app_notifications:
        create_notification(
            recipient=user,
            notification_type='admin_edit_entry',
            title='Admin Edited Your Entry',
            message=f'Administrator {admin_user.username} edited your queue entry "{queue_entry.title}". Changes: {changes_summary}',
            related_queue_entry=queue_entry,
            related_machine=queue_entry.assigned_machine,
            triggering_user=admin_user,
        )


def notify_admin_moved_entry(queue_entry, admin_user, old_position, new_position):
    """
    Notify user when an admin manually moves their queue entry.

    Special handling for moves TO position 1:
    - Notifies user they're now On Deck
    - If machine is ready (idle, available, online, not in cooldown), also tells them they can check in

    Args:
        queue_entry: The QueueEntry that was moved
        admin_user: The admin User who moved it
        old_position: Previous queue position
        new_position: New queue position
    """
    user = queue_entry.user
    machine = queue_entry.assigned_machine
    prefs = NotificationPreference.get_or_create_for_user(user)

    # Check if user wants these notifications
    if not (prefs.notify_admin_moved_entry and prefs.in_app_notifications):
        return

    # Build the message based on the move
    if new_position == 1:
        # Moved TO position 1 - special handling
        # Simple: if machine is idle, they can check in
        machine_is_ready = (machine.current_status == 'idle')

        title = 'Admin Moved You to On Deck!'

        if machine_is_ready:
            message = f'Administrator {admin_user.username} moved your request "{queue_entry.title}" to position #1 on {machine.name}. The machine is ready - you can check in now!'
        else:
            message = f'Administrator {admin_user.username} moved your request "{queue_entry.title}" to position #1 (On Deck) on {machine.name}. Get ready - you\'re next!'

    else:
        # Regular move notification
        direction = "up" if new_position < old_position else "down"
        title = 'Admin Moved Your Queue Entry'
        message = f'Administrator {admin_user.username} moved your request "{queue_entry.title}" from position #{old_position} to #{new_position} on {machine.name}'

    create_notification(
        recipient=user,
        notification_type='admin_moved_entry',
        title=title,
        message=message,
        related_queue_entry=queue_entry,
        related_machine=machine,
        triggering_user=admin_user,
    )


def check_and_notify_on_deck_status(machine):
    """
    Check if there's a queue entry at position #1 for this machine and notify the user.

    Notification logic:
    - If already in position 1 (has active on_deck/ready_for_check_in notification), don't notify again
    - If newly moved to position 1, check machine status and notify appropriately
    - If machine is idle: Send "Ready for Check-In" notification
    - If machine is not idle (running, cooldown, maintenance): Send "On Deck" notification
    - If someone was bumped out of position 1, clear their position 1 notifications

    This is called after queue reordering or when an entry completes.
    """
    from .models import Notification

    print(f"[CHECK_ON_DECK] Called for machine {machine.name}")
    print(f"[CHECK_ON_DECK] Machine status: {machine.current_status}, is_available: {machine.is_available}")

    try:
        # Get the entry at position #1
        on_deck_entry = QueueEntry.objects.filter(
            assigned_machine=machine,
            status='queued',
            queue_position=1
        ).first()

        if not on_deck_entry:
            print(f"[CHECK_ON_DECK] No entry at position #1")
        else:
            print(f"[CHECK_ON_DECK] Found position #1: {on_deck_entry.title} for user {on_deck_entry.user.username}")

        # Get all queued entries for this machine to find who was bumped
        all_queued = QueueEntry.objects.filter(
            assigned_machine=machine,
            status='queued',
            queue_position__gt=1
        )

        # Clear position 1 notifications for anyone who is no longer at position 1
        for entry in all_queued:
            # Check if they have active on_deck or ready_for_check_in notifications
            has_position_1_notif = Notification.objects.filter(
                recipient=entry.user,
                related_queue_entry=entry,
                notification_type__in=['on_deck', 'ready_for_check_in'],
                is_read=False
            ).exists()

            if has_position_1_notif:
                # They were bumped out of position 1 - clear their notifications and notify them
                auto_clear_notifications(
                    related_queue_entry=entry,
                    notification_type='on_deck'
                )
                auto_clear_notifications(
                    related_queue_entry=entry,
                    notification_type='ready_for_check_in'
                )

                # Send notification about being bumped out of first position
                user = entry.user
                prefs = NotificationPreference.get_or_create_for_user(user)

                if prefs.notify_queue_position_change and prefs.in_app_notifications:
                    create_notification(
                        recipient=user,
                        notification_type='queue_moved',
                        title=f'Queue Position Changed',
                        message=f'Your request "{entry.title}" was moved from position #1 to #{entry.queue_position} on {entry.assigned_machine.name} due to queue reordering.',
                        related_queue_entry=entry,
                        related_machine=entry.assigned_machine,
                    )

        if on_deck_entry:
            # Simple logic: if machine is idle, user can check in. Otherwise, they're on deck.
            # (If machine is unavailable, nothing should be assigned to it anyway)
            print(f"[CHECK_ON_DECK] Machine status: {machine.current_status}")

            machine_is_ready = (machine.current_status == 'idle')

            correct_notif_type = 'ready_for_check_in' if machine_is_ready else 'on_deck'
            print(f"[CHECK_ON_DECK] machine_is_ready={machine_is_ready}, will send: {correct_notif_type}")

            # Determine reason for not being ready (for on_deck notification message)
            on_deck_reason = None
            if not machine_is_ready:
                if machine.current_status == 'maintenance':
                    on_deck_reason = 'maintenance'
                elif machine.current_status == 'running':
                    on_deck_reason = 'running'
                elif machine.current_status == 'cooldown':
                    on_deck_reason = 'cooldown'
                print(f"[CHECK_ON_DECK] Not ready reason: {on_deck_reason}")

            # Check what notification the user currently has (check for any unread position 1 notifications)
            existing_notif = Notification.objects.filter(
                recipient=on_deck_entry.user,
                related_queue_entry=on_deck_entry,
                notification_type__in=['on_deck', 'ready_for_check_in'],
                is_read=False  # Only check unread notifications
            ).first()

            if existing_notif:
                print(f"[CHECK_ON_DECK] Found existing notification: {existing_notif.notification_type}")
                # User already has a position 1 notification
                if existing_notif.notification_type == correct_notif_type:
                    # Same notification type - don't send duplicate
                    print(f"[CHECK_ON_DECK] Same type as existing, skipping duplicate")
                    return
                else:
                    # Machine status changed! Clear old notification and send new one
                    # Example: had "on_deck", now machine is ready → send "ready_for_check_in"
                    print(f"[CHECK_ON_DECK] Deleting old notification and sending new one")
                    existing_notif.delete()
            else:
                print(f"[CHECK_ON_DECK] No existing notification found")

            # Send the appropriate notification based on machine status
            if machine_is_ready:
                # Machine is fully ready - user can check in immediately
                print(f"[CHECK_ON_DECK] Calling notify_ready_for_check_in")
                notify_ready_for_check_in(on_deck_entry)
                print(f"[CHECK_ON_DECK] notify_ready_for_check_in completed")

                # Initialize check-in reminder (send first reminder immediately, then every 6 hours)
                from django.utils import timezone
                on_deck_entry.checkin_reminder_due_at = timezone.now()  # First reminder due immediately
                on_deck_entry.last_checkin_reminder_sent_at = None  # Reset counter
                on_deck_entry.checkin_reminder_snoozed_until = None  # Clear any snooze
                on_deck_entry.save(update_fields=['checkin_reminder_due_at', 'last_checkin_reminder_sent_at', 'checkin_reminder_snoozed_until'])
                print(f"[CHECK_ON_DECK] Initialized check-in reminder for {on_deck_entry.title}")
            else:
                # Machine is busy, unavailable, offline, in maintenance, or cooling down - user is on deck but must wait
                print(f"[CHECK_ON_DECK] Calling notify_on_deck with reason={on_deck_reason}")
                notify_on_deck(on_deck_entry, reason=on_deck_reason)
                print(f"[CHECK_ON_DECK] notify_on_deck completed")

                # Clear check-in reminder since machine isn't ready yet
                on_deck_entry.checkin_reminder_due_at = None
                on_deck_entry.last_checkin_reminder_sent_at = None
                on_deck_entry.checkin_reminder_snoozed_until = None
                on_deck_entry.save(update_fields=['checkin_reminder_due_at', 'last_checkin_reminder_sent_at', 'checkin_reminder_snoozed_until'])
                print(f"[CHECK_ON_DECK] Cleared check-in reminder for {on_deck_entry.title} (machine not ready)")
    except Exception as e:
        print(f"[CHECK_ON_DECK] ERROR: {e}")
        import traceback
        traceback.print_exc()


def get_unread_count(user):
    """Get count of unread notifications for a user."""
    return Notification.objects.filter(recipient=user, is_read=False).count()


def mark_notification_read(notification_id, user):
    """Mark a notification as read."""
    try:
        notification = Notification.objects.get(id=notification_id, recipient=user)
        notification.is_read = True
        notification.save()
        return True
    except Notification.DoesNotExist:
        return False


def mark_all_read(user):
    """Mark all notifications as read for a user."""
    Notification.objects.filter(recipient=user, is_read=False).update(is_read=True)


def notify_admins_new_user(new_user):
    """
    Notify all admin/staff users when a new user signs up.

    Args:
        new_user: The User object that was just created
    """
    # Get all staff/admin users
    admin_users = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))

    for admin in admin_users:
        prefs = NotificationPreference.get_or_create_for_user(admin)
        if prefs.notify_admin_new_user and prefs.in_app_notifications:
            create_notification(
                recipient=admin,
                notification_type='admin_new_user',
                title='New User Signup',
                message=f'New user "{new_user.username}" has signed up and is pending approval.',
                triggering_user=new_user,
            )


def notify_admins_rush_job(queue_entry):
    """
    Notify all admin/staff users when a rush job is submitted.

    Args:
        queue_entry: The QueueEntry that was marked as rush job
    """
    # Get all staff/admin users
    admin_users = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))

    for admin in admin_users:
        prefs = NotificationPreference.get_or_create_for_user(admin)
        if prefs.notify_admin_rush_job and prefs.in_app_notifications:
            create_notification(
                recipient=admin,
                notification_type='admin_rush_job',
                title='Rush Job Submitted',
                message=f'{queue_entry.user.username} submitted a rush job request for "{queue_entry.title}" on {queue_entry.assigned_machine.name}. Review needed.',
                related_queue_entry=queue_entry,
                related_machine=queue_entry.assigned_machine,
                triggering_user=queue_entry.user,
            )


def notify_admins_rush_job_deleted(queue_entry_title, machine_name, deleting_user):
    """
    Notify all admin/staff users when a rush job is deleted/cancelled by a user.

    Args:
        queue_entry_title: Title of the deleted rush job
        machine_name: Name of the machine the job was for
        deleting_user: User who deleted the rush job
    """
    # Get all staff/admin users
    admin_users = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))

    for admin in admin_users:
        prefs = NotificationPreference.get_or_create_for_user(admin)
        if prefs.notify_admin_rush_job and prefs.in_app_notifications:
            create_notification(
                recipient=admin,
                notification_type='admin_rush_job',
                title='Rush Job Cancelled',
                message=f'{deleting_user.username} cancelled their rush job request: "{queue_entry_title}" for {machine_name}.',
                triggering_user=deleting_user,
            )


def notify_admins_rush_job_approved(queue_entry, approving_admin):
    """
    Notify all admin/staff users on Slack when a rush job is approved.
    This sends a Slack-only notification (no web notification) to inform admins the task is complete.

    Args:
        queue_entry: The QueueEntry that was approved
        approving_admin: The admin who approved it
    """
    # Get all staff/admin users
    admin_users = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))

    title = 'Rush Job Approved'
    message = f'✓ {approving_admin.username} approved rush job "{queue_entry.title}" by {queue_entry.user.username} on {queue_entry.assigned_machine.name}. Moved to position 1.'

    for admin in admin_users:
        prefs = NotificationPreference.get_or_create_for_user(admin)
        if prefs.notify_admin_rush_job:
            # Send Slack-only notification (no web notification needed)
            send_slack_dm(admin, title, message)


def notify_admins_rush_job_rejected(queue_entry, rejecting_admin, rejection_reason):
    """
    Notify all admin/staff users on Slack when a rush job is rejected.
    This sends a Slack-only notification (no web notification) to inform admins the task is complete.

    Args:
        queue_entry: The QueueEntry that was rejected
        rejecting_admin: The admin who rejected it
        rejection_reason: The reason for rejection
    """
    # Get all staff/admin users
    admin_users = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))

    title = 'Rush Job Rejected'
    message = f'✗ {rejecting_admin.username} rejected rush job "{queue_entry.title}" by {queue_entry.user.username}.\nReason: {rejection_reason}'

    for admin in admin_users:
        prefs = NotificationPreference.get_or_create_for_user(admin)
        if prefs.notify_admin_rush_job:
            # Send Slack-only notification (no web notification needed)
            send_slack_dm(admin, title, message)


def auto_clear_notifications(notification_type=None, related_queue_entry=None,
                             related_preset=None, triggering_user=None, recipient=None):
    """
    Auto-mark notifications as read when the corresponding task is completed.

    Args:
        notification_type: Type of notification to clear (optional)
        related_queue_entry: QueueEntry to filter by (optional)
        related_preset: QueuePreset to filter by (optional)
        triggering_user: User who triggered the notification (optional)
        recipient: Specific recipient to clear notifications for (optional)

    Returns:
        Number of notifications marked as read
    """
    from .models import Notification

    # Start with unread notifications
    notifications = Notification.objects.filter(is_read=False)

    # Apply filters
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)

    if related_queue_entry:
        notifications = notifications.filter(related_queue_entry=related_queue_entry)

    if related_preset:
        notifications = notifications.filter(related_preset=related_preset)

    if triggering_user:
        notifications = notifications.filter(triggering_user=triggering_user)

    if recipient:
        notifications = notifications.filter(recipient=recipient)

    # Mark all matching notifications as read
    count = notifications.update(is_read=True)

    return count
