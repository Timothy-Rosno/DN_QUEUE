from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MaxLengthValidator, MinLengthValidator
from datetime import timedelta, datetime
import os
import secrets

class Machine(models.Model):
    """Represents a lab equipment/fridge with specific capabilities."""
    STATUS_CHOICES = [
        ('idle', 'Idle'),
        ('running', 'Running'),
        ('cooldown', 'Cooldown'),
        ('maintenance', 'Maintenance'),
    ]

    B_FIELD_DIRECTION_CHOICES = [
        ('parallel_perpendicular', 'Parallel and Perpendicular'),
        ('perpendicular', 'Perpendicular Only'),
        ('parallel', 'Parallel Only'),
        ('none', 'None'),
    ]

    OPTICAL_CHOICES = [
        ('none', 'None'),
        ('available', 'Available'),
        ('with_work', 'With Some Work'),
        ('under_construction', 'Under Construction'),
    ]

    API_TYPE_CHOICES = [
        ('port5001', 'Port 5001 (Hidalgo/Griffin)'),
        ('quantum_design', 'Quantum Design (OptiCool/CryoCore)'),
        ('none', 'No API'),
    ]

    name = models.CharField(max_length=100, unique=True)

    # Network configuration for live monitoring
    ip_address = models.CharField(max_length=15, blank=True, help_text="IP address for temperature monitoring")
    api_type = models.CharField(max_length=20, choices=API_TYPE_CHOICES, default='none', help_text="Type of temperature API")
    api_port = models.IntegerField(null=True, blank=True, help_text="API port (e.g., 47101 for Quantum Design)")

    # Cached live monitoring data (updated by background task)
    cached_temperature = models.FloatField(null=True, blank=True, help_text="Cached temperature reading in Kelvin")
    cached_online = models.BooleanField(default=True, help_text="Cached online/offline status")
    last_temp_update = models.DateTimeField(null=True, blank=True, help_text="Last time temperature was updated")

    # Temperature specifications (in Kelvin)
    min_temp = models.FloatField(help_text="Minimum temperature in Kelvin")
    max_temp = models.FloatField(help_text="Maximum temperature in Kelvin")

    # Magnetic field specifications (in Tesla)
    b_field_x = models.FloatField(default=0, help_text="Max B-field in X direction (Tesla)")
    b_field_y = models.FloatField(default=0, help_text="Max B-field in Y direction (Tesla)")
    b_field_z = models.FloatField(default=0, help_text="Max B-field in Z direction (Tesla)")
    b_field_direction = models.CharField(
        max_length=30,
        choices=B_FIELD_DIRECTION_CHOICES,
        default='none',
        help_text="Available B-field directions"
    )

    # Connection specifications
    dc_lines = models.IntegerField(default=0, help_text="Number of DC lines available")
    rf_lines = models.IntegerField(default=0, help_text="Number of RF lines available")
    daughterboard_type = models.CharField(max_length=100, blank=True, help_text="Daughterboard type (e.g., QBoard I, QBoard II, Montana Puck)")

    # Optical capabilities
    optical_capabilities = models.CharField(
        max_length=30,
        choices=OPTICAL_CHOICES,
        default='none',
        help_text="Optical measurement capabilities"
    )

    # Operational characteristics
    cooldown_hours = models.IntegerField(help_text="Cooldown time in hours")

    # Current status
    current_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='idle')
    is_available = models.BooleanField(default=True)
    current_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='current_machine')
    estimated_available_time = models.DateTimeField(null=True, blank=True)

    # Additional info
    description = models.TextField(blank=True)
    location = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_current_status_display()})"

    def delete(self, *args, **kwargs):
        """
        Custom delete to handle queue entries properly:
        - Archived entries: Keep as is with machine name preserved
        - Running/Queued entries: Cancel and preserve machine name
        """
        # Get all queue entries for this machine
        queue_entries = self.queue_entries.all()

        for entry in queue_entries:
            # Save machine name to text field before deletion
            if not entry.machine_name_text:
                entry.machine_name_text = self.name

            # Cancel running or queued entries
            if entry.status in ['running', 'queued']:
                entry.status = 'cancelled'

            # Save the entry (assigned_machine will be set to None by SET_NULL)
            entry.save()

        # Now delete the machine
        super().delete(*args, **kwargs)

    class Meta:
        verbose_name = "Machine"
        verbose_name_plural = "Machines"
        ordering = ['name']

    def get_queue_count(self):
        """Return number of queued entries for this machine."""
        return self.queue_entries.filter(status='queued').count()

    def get_estimated_wait_time(self):
        """
        Calculate estimated wait time based on current status and queue.
        Returns the time until this machine will be available for a NEW request.
        """
        queued = self.queue_entries.filter(status='queued').order_by('queue_position')
        total_time = timedelta(0)

        # Add current job time if running or in cooldown
        if self.estimated_available_time and self.estimated_available_time > timezone.now():
            total_time = self.estimated_available_time - timezone.now()

        # Add all queued jobs (even if machine is currently idle)
        for entry in queued:
            total_time += timedelta(hours=entry.estimated_duration_hours)
            total_time += timedelta(hours=self.cooldown_hours)

        return total_time

    def update_temperature_cache(self):
        """
        Update cached temperature and online status from the machine's API.
        This should be called by a background task, not during page load.
        """
        if not self.ip_address or self.api_type == 'none':
            self.cached_temperature = None
            self.cached_online = False  # No API means we can't verify status
            # Don't update last_temp_update - leave it as None/stale
            self.save(update_fields=['cached_temperature', 'cached_online'])
            return

        import requests
        try:
            if self.api_type == 'port5001':
                url = f'http://{self.ip_address}:5001/channel/measurement/latest'
                response = requests.get(url, timeout=3)
                response.raise_for_status()
                data = response.json()
                self.cached_temperature = data.get('temperature')
                self.cached_online = True

            elif self.api_type == 'quantum_design':
                port = self.api_port or 47101
                url = f'http://{self.ip_address}:{port}/v1/sampleChamber/temperatureControllers/user1/thermometer/properties/sample'
                response = requests.get(url, timeout=3)
                response.raise_for_status()
                import json
                data = json.loads(response.content.decode('utf-8'))
                self.cached_temperature = data.get('sample', {}).get('temperature')
                self.cached_online = True

        except Exception:
            self.cached_online = False
            # Keep last known temperature if offline

        self.last_temp_update = timezone.now()
        self.save(update_fields=['cached_temperature', 'cached_online', 'last_temp_update'])

    def get_live_temperature(self):
        """
        Get cached temperature reading.
        Returns temperature in Kelvin, or None if unavailable.
        Health check: Returns None if data is stale (older than 60 seconds).
        """
        # Check if data is stale
        if self.last_temp_update:
            time_since_update = timezone.now() - self.last_temp_update
            if time_since_update > timedelta(seconds=60):
                return None  # Data is stale
        return self.cached_temperature

    def is_online(self):
        """
        Get cached online status.
        Returns True if machine is online, False otherwise.
        Health check: Returns False if data is stale (older than 60 seconds).
        """
        if not self.ip_address or self.api_type == 'none':
            return False  # No API means we can't verify it's online

        # Check if data is stale (gateway hasn't updated in 60 seconds)
        if self.last_temp_update:
            time_since_update = timezone.now() - self.last_temp_update
            if time_since_update > timedelta(seconds=60):
                return False  # Gateway is not running or machine disconnected

        return self.cached_online

    def get_display_status(self):
        """
        Get the display status for the machine.
        Returns status like: 'Connected - Measuring', 'Connected - Idle', 'Disconnected - Measuring',
        'Disconnected - Idle', or 'Disconnected - Maintenance'
        """
        # If admin has marked as unavailable, it's in maintenance
        if not self.is_available:
            return 'Disconnected - Maintenance'

        # Check if machine is measuring (has a running job)
        is_measuring = self.queue_entries.filter(status='running').exists()

        # Determine connected/disconnected status
        connection_status = 'Connected' if self.is_online() else 'Disconnected'

        # Combine with measuring state
        measuring_status = 'Measuring' if is_measuring else 'Idle'

        return f'{connection_status} - {measuring_status}'


class QueueEntry(models.Model):
    """Represents a user's request to use lab equipment."""
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    B_FIELD_DIRECTION_CHOICES = [
        ('', 'No Preference'),
        ('parallel_perpendicular', 'Parallel and Perpendicular'),
        ('perpendicular', 'Perpendicular Only'),
        ('parallel', 'Parallel Only'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='queue_entries')
    title = models.CharField(max_length=75, help_text="Experiment title/name")
    description = models.TextField(help_text="Experiment description", validators=[MinLengthValidator(50), MaxLengthValidator(500)])

    # User requirements
    required_min_temp = models.FloatField(help_text="Required minimum temperature (Kelvin)")
    required_max_temp = models.FloatField(null=True, blank=True, help_text="Required maximum temperature (Kelvin, optional)")
    required_b_field_x = models.FloatField(default=0, help_text="Required B-field X (Tesla)")
    required_b_field_y = models.FloatField(default=0, help_text="Required B-field Y (Tesla)")
    required_b_field_z = models.FloatField(default=0, help_text="Required B-field Z (Tesla)")
    required_b_field_direction = models.CharField(
        max_length=30,
        choices=B_FIELD_DIRECTION_CHOICES,
        blank=True,
        default='',
        help_text="Required B-field direction (if any)"
    )

    # Connection requirements
    required_dc_lines = models.IntegerField(default=0, help_text="Number of DC lines needed")
    required_rf_lines = models.IntegerField(default=0, help_text="Number of RF lines needed")
    required_daughterboard = models.CharField(max_length=100, blank=True, default='', help_text="Required daughterboard type (leave blank for any)")

    # Optical requirements
    requires_optical = models.BooleanField(default=False, help_text="Does this experiment require optical capabilities?")

    # Scheduling info
    estimated_duration_hours = models.FloatField(help_text="Estimated duration in hours")
    priority = models.IntegerField(default=0, help_text="Higher number = higher priority")

    # Assignment
    assigned_machine = models.ForeignKey(Machine, on_delete=models.SET_NULL, null=True, blank=True, related_name='queue_entries')
    machine_name_text = models.CharField(max_length=100, blank=True, default='', help_text="Machine name as text (preserved after machine deletion)")
    queue_position = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')

    # Timing
    submitted_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    estimated_start_time = models.DateTimeField(null=True, blank=True)

    # Checkout reminder tracking (replaces Celery scheduled tasks)
    reminder_due_at = models.DateTimeField(null=True, blank=True, help_text="When checkout reminder should be sent")
    last_reminder_sent_at = models.DateTimeField(null=True, blank=True, help_text="When the last checkout reminder was sent (for repeat reminders every 12 hours)")
    reminder_snoozed_until = models.DateTimeField(null=True, blank=True, help_text="When the checkout reminder snooze expires (user clicked notification link)")

    # Check-in reminder tracking (for position #1 entries that haven't checked in yet)
    checkin_reminder_due_at = models.DateTimeField(null=True, blank=True, help_text="When check-in reminder should be sent (for ON DECK entries)")
    last_checkin_reminder_sent_at = models.DateTimeField(null=True, blank=True, help_text="When the last check-in reminder was sent (for repeat reminders every 12 hours)")
    checkin_reminder_snoozed_until = models.DateTimeField(null=True, blank=True, help_text="When the check-in reminder snooze expires (user clicked notification link)")

    # Additional info
    special_requirements = models.TextField(blank=True, default='', help_text="Any special requirements or notes", validators=[MaxLengthValidator(500)])

    # Rush job information
    is_rush_job = models.BooleanField(default=False, help_text="Is this a rush job requiring priority review?")
    rush_job_submitted_at = models.DateTimeField(null=True, blank=True, help_text="When the rush job appeal was submitted")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        machine_name = self.assigned_machine.name if self.assigned_machine else "Unassigned"
        return f"{self.title} - {self.user.username} [{machine_name}] ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        """Override save to populate machine_name_text when machine is assigned."""
        if self.assigned_machine and not self.machine_name_text:
            self.machine_name_text = self.assigned_machine.name
        super().save(*args, **kwargs)

    def get_machine_display_name(self):
        """Get machine name for display (handles deleted machines)."""
        if self.assigned_machine:
            return self.assigned_machine.name
        elif self.machine_name_text:
            return f"{self.machine_name_text} (deleted)"
        else:
            return "No machine assigned"

    class Meta:
        verbose_name = "Queue Entry"
        verbose_name_plural = "Queue Entries"
        ordering = ['assigned_machine', 'queue_position', 'submitted_at']

    def calculate_estimated_start_time(self):
        """Calculate when this entry is estimated to start."""
        if not self.assigned_machine:
            return None

        if self.status == 'running':
            return self.started_at

        if self.status != 'queued':
            return None

        # Get all entries ahead in queue
        ahead_in_queue = QueueEntry.objects.filter(
            assigned_machine=self.assigned_machine,
            status='queued',
            queue_position__lt=self.queue_position
        ).order_by('queue_position')

        # Start with current time or machine's estimated available time
        start_time = timezone.now()
        if self.assigned_machine.estimated_available_time and self.assigned_machine.estimated_available_time > start_time:
            start_time = self.assigned_machine.estimated_available_time

        # Add time for all entries ahead
        for entry in ahead_in_queue:
            start_time += timedelta(hours=entry.estimated_duration_hours)
            start_time += timedelta(hours=self.assigned_machine.cooldown_hours)

        return start_time


class QueuePreset(models.Model):
    """Represents a saved preset for queue entry parameters."""
    B_FIELD_DIRECTION_CHOICES = [
        ('', 'No Preference'),
        ('parallel_perpendicular', 'Parallel and Perpendicular'),
        ('perpendicular', 'Perpendicular Only'),
        ('parallel', 'Parallel Only'),
    ]

    # Metadata
    name = models.CharField(max_length=75, help_text="User-provided preset name/nickname")
    display_name = models.CharField(max_length=500, help_text="Auto-generated formatted display name")
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_presets')
    creator_username = models.CharField(max_length=150, default='unknown', help_text="Username of the creator (preserved if user is deleted)")
    is_public = models.BooleanField(default=False, help_text="Is this preset accessible to all users?")

    # Edit tracking
    last_edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='edited_presets')
    last_edited_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Queue parameters (copied from QueueEntry, excluding is_rush_job and special_requirements)
    title = models.CharField(max_length=75, blank=True, default='', help_text="Experiment title/name")
    description = models.TextField(blank=True, default='', help_text="Experiment description", validators=[MaxLengthValidator(500)])

    # Temperature requirements
    required_min_temp = models.FloatField(null=True, blank=True, help_text="Required minimum temperature (Kelvin)")
    required_max_temp = models.FloatField(null=True, blank=True, help_text="Required maximum temperature (Kelvin, optional)")

    # B-field requirements
    required_b_field_x = models.FloatField(default=0, help_text="Required B-field X (Tesla)")
    required_b_field_y = models.FloatField(default=0, help_text="Required B-field Y (Tesla)")
    required_b_field_z = models.FloatField(default=0, help_text="Required B-field Z (Tesla)")
    required_b_field_direction = models.CharField(
        max_length=30,
        choices=B_FIELD_DIRECTION_CHOICES,
        blank=True,
        default='',
        help_text="Required B-field direction (if any)"
    )

    # Connection requirements
    required_dc_lines = models.IntegerField(default=0, help_text="Number of DC lines needed")
    required_rf_lines = models.IntegerField(default=0, help_text="Number of RF lines needed")
    required_daughterboard = models.CharField(max_length=100, blank=True, default='', help_text="Required daughterboard type (leave blank for any)")

    # Optical requirements
    requires_optical = models.BooleanField(default=False, help_text="Does this experiment require optical capabilities?")

    # Estimated duration (optional, will be auto-calculated if not provided)
    estimated_duration_hours = models.FloatField(null=True, blank=True, help_text="Estimated duration in hours (optional)")

    def __str__(self):
        return self.display_name

    class Meta:
        verbose_name = "Queue Preset"
        verbose_name_plural = "Queue Presets"
        ordering = ['is_public', 'name']  # Private first, then alphabetical

    def save(self, *args, **kwargs):
        """Auto-generate display_name on save."""
        # Set creator_username if creator exists (overwrite 'unknown' default)
        if self.creator and (not self.creator_username or self.creator_username == 'unknown'):
            self.creator_username = self.creator.username

        # Format: "Preset Name - (Auth. Creator) - (Ed. Editor Oct-20-2025)"
        editor_name = self.last_edited_by.username if self.last_edited_by else self.creator_username
        edit_date = self.last_edited_at.strftime('%b-%d-%Y') if self.last_edited_at else timezone.now().strftime('%b-%d-%Y')

        self.display_name = f"{self.name} - (Auth. {self.creator_username}) - (Ed. {editor_name} {edit_date})"
        super().save(*args, **kwargs)

    def can_edit(self, user):
        """Check if a user can edit this preset."""
        # Users can edit their own presets (private or public)
        # Check both creator object (if still exists) and username
        if self.creator and self.creator == user:
            return True
        if self.creator_username and self.creator_username == user.username:
            return True
        # Admins can edit any public preset
        if user.is_staff and self.is_public:
            return True
        return False

    def can_view(self, user):
        """Check if a user can view this preset."""
        # Users can view their own presets
        if self.creator and self.creator == user:
            return True
        if self.creator_username and self.creator_username == user.username:
            return True
        # Anyone can view public presets
        if self.is_public:
            return True
        # Admins can view any preset (including private ones)
        if user.is_staff:
            return True
        return False


# Keep old model for migration compatibility
class ScheduleEntry(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='schedule_entries')
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, validators=[MaxLengthValidator(500)])
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Additional data requested from user
    location = models.CharField(max_length=200, blank=True)
    attendees = models.IntegerField(default=1, help_text="Number of people attending")
    special_requirements = models.TextField(blank=True, help_text="Any special requirements or notes", validators=[MaxLengthValidator(500)])

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.user.username} ({self.start_datetime.strftime('%Y-%m-%d %H:%M')})"

    class Meta:
        verbose_name = "Schedule Entry"
        verbose_name_plural = "Schedule Entries"
        ordering = ['-start_datetime']

    def is_upcoming(self):
        return self.start_datetime > timezone.now()


class Notification(models.Model):
    """Represents a notification sent to a user."""
    NOTIFICATION_TYPES = [
        ('preset_created', 'Preset Created'),
        ('preset_edited', 'Preset Edited'),
        ('preset_deleted', 'Preset Deleted'),
        ('queue_added', 'Queue Entry Added'),
        ('queue_moved', 'Queue Entry Moved'),
        ('queue_cancelled', 'Queue Entry Cancelled'),
        ('on_deck', 'On Deck - You\'re Next!'),
        ('ready_for_check_in', 'Ready for Check-In'),
        ('checkin_reminder', 'Did You Forget to Check In?'),
        ('checkout_reminder', 'Time to Check Out'),
        ('machine_status_changed', 'Machine Status Changed - Time to Check Out'),
        ('admin_check_in', 'Admin Checked You In'),
        ('admin_checkout', 'Admin Checked You Out'),
        ('admin_edit_entry', 'Admin Edited Your Entry'),
        ('admin_moved_entry', 'Admin Moved Your Queue Entry'),
        ('account_approved', 'Account Approved'),
        ('account_unapproved', 'Account Unapproved'),
        ('account_promoted', 'Promoted to Staff'),
        ('account_demoted', 'Demoted from Staff'),
        ('account_info_changed', 'Account Information Changed'),
        # Admin-specific notifications
        ('admin_new_user', 'New User Signup'),
        ('admin_rush_job', 'Rush Job/Special Request Submitted'),
        # Database management notifications
        ('database_restored', 'Database Restored'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=500)
    message = models.TextField(validators=[MaxLengthValidator(500)])

    # Related objects (nullable for flexibility)
    related_preset = models.ForeignKey('QueuePreset', on_delete=models.SET_NULL, null=True, blank=True)
    related_queue_entry = models.ForeignKey('QueueEntry', on_delete=models.SET_NULL, null=True, blank=True)
    related_machine = models.ForeignKey('Machine', on_delete=models.SET_NULL, null=True, blank=True)
    triggering_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='triggered_notifications')

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f"{self.recipient.username} - {self.title}"

    def get_notification_url(self):
        """Return the URL to navigate to when notification is clicked."""
        from django.urls import reverse

        # Admin notifications
        if self.notification_type == 'admin_new_user':
            return reverse('admin_users')
        elif self.notification_type == 'admin_rush_job':
            return reverse('admin_rush_jobs')

        # Preset notifications - go to submit queue with preset loaded
        elif self.notification_type in ['preset_created', 'preset_edited', 'preset_deleted']:
            if self.related_preset:
                return f"{reverse('submit_queue')}?preset_id={self.related_preset.id}"
            return reverse('submit_queue')

        # Queue position changes and admin edits - go to My Queue
        elif self.notification_type in ['queue_moved', 'queue_added', 'queue_cancelled', 'admin_edit_entry']:
            return reverse('my_queue')

        # Checkout Reminder - go to snooze endpoint (silences for 48 hours)
        elif self.notification_type == 'checkout_reminder':
            if self.related_queue_entry:
                return reverse('snooze_checkout_reminder', kwargs={'entry_id': self.related_queue_entry.id})
            return reverse('check_in_check_out')

        # Check-in Reminder - go to snooze endpoint (silences for 48 hours)
        elif self.notification_type == 'checkin_reminder':
            if self.related_queue_entry:
                return reverse('snooze_checkin_reminder', kwargs={'entry_id': self.related_queue_entry.id})
            return reverse('check_in_check_out')

        # ON DECK, Ready for Check-In, Machine Status Changed, Admin Check-In, Admin Checkout - go to check-in/check-out page
        elif self.notification_type in ['on_deck', 'ready_for_check_in', 'machine_status_changed', 'admin_check_in', 'admin_checkout']:
            return reverse('check_in_check_out')

        # Account approval - go to home page
        elif self.notification_type == 'account_approved':
            return reverse('home')

        # Default fallback
        return reverse('my_queue')


class NotificationPreference(models.Model):
    """User preferences for what notifications they want to receive."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')

    # Preset notifications
    notify_public_preset_created = models.BooleanField(default=False, help_text="Notify when public presets are created")
    notify_public_preset_edited = models.BooleanField(default=False, help_text="Notify when public presets are edited")
    notify_public_preset_deleted = models.BooleanField(default=False, help_text="Notify when public presets are deleted")
    notify_private_preset_edited = models.BooleanField(default=True, help_text="Notify when your private presets are edited by others")

    # Followed preset notifications
    followed_presets = models.ManyToManyField('QueuePreset', related_name='followers', blank=True, help_text="Presets you're following for notifications")
    notify_followed_preset_edited = models.BooleanField(default=False, help_text="Notify when presets you follow are edited")
    notify_followed_preset_deleted = models.BooleanField(default=False, help_text="Notify when presets you follow are deleted")

    # Queue notifications
    notify_queue_added = models.BooleanField(default=True, help_text="Notify when your queue entry is successfully added")
    notify_queue_position_change = models.BooleanField(default=True, help_text="Notify when your queue position changes")
    notify_queue_cancelled = models.BooleanField(default=True, help_text="Notify when your queue entry is cancelled")
    notify_on_deck = models.BooleanField(default=True, help_text="Notify when you're next in line (ON DECK) - CRITICAL")
    notify_ready_for_check_in = models.BooleanField(default=True, help_text="Notify when the machine is available and you can check in - CRITICAL")
    notify_checkin_reminder = models.BooleanField(default=True, help_text="Notify when you forget to check in - CRITICAL")
    notify_checkout_reminder = models.BooleanField(default=True, help_text="Notify when your estimated measurement time has elapsed and you should check out - CRITICAL")

    # Machine queue notifications
    notify_machine_queue_changes = models.BooleanField(default=False, help_text="Notify when entries are added to machines you're queued for")

    # Admin action notifications (when admins perform actions on your entries)
    notify_admin_check_in = models.BooleanField(default=True, help_text="Notify when an admin checks you in")
    notify_admin_checkout = models.BooleanField(default=True, help_text="Notify when an admin checks you out")
    notify_admin_edit_entry = models.BooleanField(default=True, help_text="Notify when an admin edits your queue entry")
    notify_admin_moved_entry = models.BooleanField(default=True, help_text="Notify when an admin moves your queue entry")
    notify_machine_status_change = models.BooleanField(default=True, help_text="Notify when admin changes machine status affecting your measurement")

    # Account status notifications (critical - always sent)
    notify_account_approved = models.BooleanField(default=True, help_text="Notify when your account is approved - CRITICAL")
    notify_account_unapproved = models.BooleanField(default=True, help_text="Notify when your account is unapproved - CRITICAL")
    notify_account_promoted = models.BooleanField(default=True, help_text="Notify when you're promoted to staff - CRITICAL")
    notify_account_demoted = models.BooleanField(default=True, help_text="Notify when you're demoted from staff - CRITICAL")
    notify_account_info_changed = models.BooleanField(default=True, help_text="Notify when your account information is changed - CRITICAL")

    # Admin-only notifications (only relevant for staff users)
    notify_admin_new_user = models.BooleanField(default=True, help_text="[Admin] Notify when new users sign up - CRITICAL")
    notify_admin_rush_job = models.BooleanField(default=True, help_text="[Admin] Notify when rush jobs are submitted - CRITICAL")
    notify_database_restored = models.BooleanField(default=True, help_text="[Admin] Notify when database is restored - CRITICAL")

    # Delivery preferences (for future email/Slack integration)
    email_notifications = models.BooleanField(default=True, help_text="Send notifications via email")
    in_app_notifications = models.BooleanField(default=True, help_text="Show notifications in the app")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Notification Preferences - {self.user.username}"

    @classmethod
    def get_or_create_for_user(cls, user):
        """
        Get or create notification preferences for a user with defaults.

        Admin/staff users get minimal notifications by default (only their own queue activity).
        Regular users get all notifications enabled by default.
        """
        prefs, created = cls.objects.get_or_create(user=user)

        # If this is a new preference object for an admin/staff user, set admin-friendly defaults
        if created and (user.is_staff or user.is_superuser):
            # Turn off all preset notifications for admins
            prefs.notify_public_preset_created = False
            prefs.notify_public_preset_edited = False
            prefs.notify_public_preset_deleted = False
            prefs.notify_private_preset_edited = False

            # Turn off followed preset notifications (already off by default, but explicit)
            prefs.notify_followed_preset_edited = False
            prefs.notify_followed_preset_deleted = False

            # Turn off queue position changes
            prefs.notify_queue_position_change = False

            # Turn off machine queue changes
            prefs.notify_machine_queue_changes = False

            # Keep only critical admin notifications and their own queue completions:
            # - notify_on_deck = True (default, if admin uses queue themselves)
            # - notify_ready_for_check_in = True (default, if admin uses queue themselves)
            # - notify_checkout_reminder = True (default, if admin uses queue themselves)
            # - notify_admin_new_user = True (default, critical admin notification)
            # - notify_admin_rush_job = True (default, critical admin notification)
            # - in_app_notifications = True (default)
            # - email_notifications = True (default)

            prefs.save()

        return prefs


def archived_measurement_upload_path(instance, filename):
    """
    Generate upload path organized by year/month.
    Format: archived_measurements/YYYY/MM/username/filename
    """
    now = timezone.now()
    return os.path.join(
        'archived_measurements',
        str(now.year),
        f'{now.month:02d}',
        instance.user.username,
        filename
    )


class ArchivedMeasurement(models.Model):
    """Represents an archived measurement from a completed queue entry."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('archived', 'Archived'),
        ('orphaned', 'Orphaned (Machine Deleted)'),
    ]

    # Core relationships
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='archived_measurements', help_text="User who created this archive entry")
    machine = models.ForeignKey(Machine, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_measurements', help_text="Machine used for this measurement")
    machine_name = models.CharField(max_length=100, blank=True, help_text="Machine name (preserved if machine is deleted)")
    related_queue_entry = models.ForeignKey(QueueEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_measurements', help_text="Original queue entry (if archived from queue)")

    # Measurement metadata
    measurement_date = models.DateTimeField(default=timezone.now, help_text="Date when the measurement was taken")
    title = models.CharField(max_length=500, help_text="Title of the measurement", validators=[MaxLengthValidator(500)])
    notes = models.TextField(blank=True, help_text="Additional notes about this measurement", validators=[MaxLengthValidator(500)])
    duration_hours = models.FloatField(null=True, blank=True, help_text="Duration of measurement in hours")

    # Preset snapshot - stores the configuration used for this measurement
    preset_snapshot = models.JSONField(null=True, blank=True, help_text="JSON snapshot of the preset/configuration used")

    # File uploads - organized by year/month
    uploaded_file = models.FileField(upload_to=archived_measurement_upload_path, null=True, blank=True, help_text="Uploaded measurement data file")

    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published', help_text="Archive entry status")

    # Timestamps
    archived_at = models.DateTimeField(default=timezone.now, help_text="When this entry was added to the archive")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Archived Measurement"
        verbose_name_plural = "Archived Measurements"
        ordering = ['-measurement_date']
        indexes = [
            models.Index(fields=['user', '-measurement_date']),
            models.Index(fields=['machine', '-measurement_date']),
            models.Index(fields=['-measurement_date']),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.username} - {self.measurement_date.strftime('%Y-%m-%d')}"

    def get_file_name(self):
        """Return just the filename without the path."""
        if self.uploaded_file:
            return os.path.basename(self.uploaded_file.name)
        return None

    def get_file_size(self):
        """Return file size in human-readable format."""
        if self.uploaded_file and os.path.exists(self.uploaded_file.path):
            size_bytes = os.path.getsize(self.uploaded_file.path)
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.1f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.1f} TB"
        return None


class OneTimeLoginToken(models.Model):
    """
    One-time use tokens for secure auto-login from Slack notifications.

    These tokens are:
    - User-specific (only work for the intended user)
    - One-time use (marked as used after first access)
    - Time-limited (expire after 24 hours)
    - Non-shareable (tied to notification recipient)
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_tokens')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    notification = models.ForeignKey('Notification', on_delete=models.CASCADE, related_name='login_tokens', null=True, blank=True)
    redirect_url = models.CharField(max_length=500, help_text="Where to redirect after login")

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = "One-Time Login Token"
        verbose_name_plural = "One-Time Login Tokens"
        ordering = ['-created_at']

    def __str__(self):
        return f"Token for {self.user.username} - {'Used' if self.is_used else 'Active'}"

    @classmethod
    def create_for_notification(cls, user, notification, redirect_url):
        """
        Create a secure one-time login token for a notification.

        Args:
            user: User who will use this token
            notification: Related notification object
            redirect_url: Where to redirect after login

        Returns:
            OneTimeLoginToken instance
        """
        token = secrets.token_urlsafe(32)  # Cryptographically secure random token
        expires_at = timezone.now() + timedelta(hours=24)

        return cls.objects.create(
            user=user,
            token=token,
            notification=notification,
            redirect_url=redirect_url,
            expires_at=expires_at
        )

    def is_valid(self):
        """Check if token is still valid (not used and not expired)."""
        return not self.is_used and timezone.now() < self.expires_at

    def mark_as_used(self):
        """Mark token as used (can only be used once)."""
        self.is_used = True
        self.used_at = timezone.now()
        self.save()
