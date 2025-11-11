from django.contrib import admin
from django.utils import timezone
from .models import Machine, QueueEntry, ScheduleEntry, QueuePreset, Notification, NotificationPreference
from .matching_algorithm import reorder_queue


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ('name', 'current_status', 'is_available', 'min_temp', 'max_temp',
                    'b_field_z', 'b_field_direction', 'optical_capabilities', 'get_queue_count')
    list_filter = ('current_status', 'is_available', 'b_field_direction', 'optical_capabilities', 'location')
    search_fields = ('name', 'description', 'location', 'daughterboard_type')
    readonly_fields = ('created_at', 'updated_at', 'get_queue_count')
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'description', 'location')
        }),
        ('Temperature Specs (Kelvin)', {
            'fields': ('min_temp', 'max_temp')
        }),
        ('Magnetic Field Specs (Tesla)', {
            'fields': ('b_field_x', 'b_field_y', 'b_field_z', 'b_field_direction')
        }),
        ('Connections', {
            'fields': ('dc_lines', 'rf_lines', 'daughterboard_type')
        }),
        ('Optical Capabilities', {
            'fields': ('optical_capabilities',)
        }),
        ('Operational', {
            'fields': ('cooldown_hours', 'current_status', 'is_available',
                      'current_user', 'estimated_available_time')
        }),
        ('Info', {
            'fields': ('created_at', 'updated_at', 'get_queue_count')
        }),
    )

    def get_queue_count(self, obj):
        return obj.get_queue_count()
    get_queue_count.short_description = 'Queue Count'


@admin.register(QueueEntry)
class QueueEntryAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'assigned_machine', 'queue_position', 'status',
                    'required_min_temp', 'requires_optical', 'estimated_duration_hours', 'submitted_at')
    list_filter = ('status', 'assigned_machine', 'requires_optical', 'required_b_field_direction', 'submitted_at')
    search_fields = ('title', 'description', 'user__username', 'required_daughterboard')
    readonly_fields = ('submitted_at', 'created_at', 'updated_at', 'estimated_start_time')
    date_hierarchy = 'submitted_at'

    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'title', 'description')
        }),
        ('Temperature Requirements', {
            'fields': ('required_min_temp', 'required_max_temp')
        }),
        ('Magnetic Field Requirements', {
            'fields': ('required_b_field_x', 'required_b_field_y', 'required_b_field_z',
                      'required_b_field_direction')
        }),
        ('Connection Requirements', {
            'fields': ('required_dc_lines', 'required_rf_lines', 'required_daughterboard')
        }),
        ('Optical Requirements', {
            'fields': ('requires_optical',)
        }),
        ('Duration', {
            'fields': ('estimated_duration_hours',)
        }),
        ('Assignment', {
            'fields': ('assigned_machine', 'queue_position', 'status', 'priority')
        }),
        ('Timing', {
            'fields': ('submitted_at', 'estimated_start_time', 'started_at', 'completed_at')
        }),
        ('Additional', {
            'fields': ('special_requirements', 'created_at', 'updated_at')
        }),
    )

    actions = ['start_entry', 'complete_entry', 'cancel_entry']

    def start_entry(self, request, queryset):
        for entry in queryset:
            if entry.status == 'queued' and entry.queue_position == 1:
                entry.status = 'running'
                entry.started_at = timezone.now()
                if entry.assigned_machine:
                    entry.assigned_machine.current_status = 'running'
                    entry.assigned_machine.current_user = entry.user
                    entry.assigned_machine.estimated_available_time = timezone.now() + timezone.timedelta(hours=entry.estimated_duration_hours)
                    entry.assigned_machine.save()
                entry.save()
                reorder_queue(entry.assigned_machine)
        self.message_user(request, f"{queryset.count()} entries started.")
    start_entry.short_description = "Start selected queued entries (position 1 only)"

    def complete_entry(self, request, queryset):
        for entry in queryset:
            if entry.status == 'running':
                entry.status = 'completed'
                entry.completed_at = timezone.now()
                if entry.assigned_machine:
                    entry.assigned_machine.current_status = 'cooldown'
                    entry.assigned_machine.current_user = None
                    entry.assigned_machine.estimated_available_time = timezone.now() + timezone.timedelta(hours=entry.assigned_machine.cooldown_hours)
                    entry.assigned_machine.save()
                entry.save()
        self.message_user(request, f"{queryset.count()} entries completed.")
    complete_entry.short_description = "Complete selected running entries"

    def cancel_entry(self, request, queryset):
        from . import notifications

        for entry in queryset:
            machine = entry.assigned_machine
            was_running = entry.status == 'running'
            user = entry.user

            # Cancel queued or running entries
            if entry.status in ['queued', 'running']:
                entry.status = 'cancelled'
                entry.save()

                # If entry was running, reset machine status and notify user
                if was_running and machine:
                    machine.current_status = 'idle'
                    machine.current_user = None
                    machine.estimated_available_time = None
                    machine.save()

                    # Notify user that machine status changed to idle
                    try:
                        notifications.notify_machine_status_changed(entry, request.user)
                    except Exception as e:
                        print(f"User notification for machine status change failed: {e}")

                # Reorder queue and notify next person if they're now on-deck
                if machine:
                    reorder_queue(machine)
                    try:
                        notifications.check_and_notify_on_deck_status(machine)
                    except Exception as e:
                        print(f"On-deck notification failed: {e}")

        self.message_user(request, f"{queryset.count()} entries cancelled.")
    cancel_entry.short_description = "Cancel selected entries (queued or running)"

    def delete_model(self, request, obj):
        """Override delete to handle machine status when deleting a single entry."""
        from . import notifications

        machine = obj.assigned_machine
        was_running = obj.status == 'running'
        user = obj.user

        # Notify user if their running measurement is being deleted by admin
        if was_running and machine:
            try:
                notifications.notify_machine_status_changed(obj, request.user)
            except Exception as e:
                print(f"User notification for machine status change failed: {e}")

        # Delete the entry
        super().delete_model(request, obj)

        # If entry was running, reset machine status
        if was_running and machine:
            machine.current_status = 'idle'
            machine.current_user = None
            machine.estimated_available_time = None
            machine.save()

        # Reorder queue and notify next person if they're now on-deck
        if machine:
            reorder_queue(machine)
            try:
                notifications.check_and_notify_on_deck_status(machine)
            except Exception as e:
                print(f"On-deck notification failed: {e}")

    def delete_queryset(self, request, queryset):
        """Override bulk delete to handle machine status updates."""
        from . import notifications

        # Track machines that need reordering
        affected_machines = set()

        for entry in queryset:
            machine = entry.assigned_machine
            was_running = entry.status == 'running'
            user = entry.user

            if machine:
                affected_machines.add(machine)

                # If entry was running, notify user and reset machine status
                if was_running:
                    # Notify user that machine status changed to idle
                    try:
                        notifications.notify_machine_status_changed(entry, request.user)
                    except Exception as e:
                        print(f"User notification for machine status change failed: {e}")

                    machine.current_status = 'idle'
                    machine.current_user = None
                    machine.estimated_available_time = None
                    machine.save()

        # Delete all entries
        super().delete_queryset(request, queryset)

        # Reorder queues and notify for all affected machines
        for machine in affected_machines:
            reorder_queue(machine)
            try:
                notifications.check_and_notify_on_deck_status(machine)
            except Exception as e:
                print(f"On-deck notification failed: {e}")


@admin.register(ScheduleEntry)
class ScheduleEntryAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'start_datetime', 'end_datetime', 'status', 'location')
    list_filter = ('status', 'start_datetime', 'created_at')
    search_fields = ('title', 'description', 'user__username', 'location')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'start_datetime'


@admin.register(QueuePreset)
class QueuePresetAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'creator', 'is_public', 'last_edited_by', 'last_edited_at', 'created_at')
    list_filter = ('is_public', 'creator', 'last_edited_at', 'created_at')
    search_fields = ('name', 'display_name', 'title', 'description', 'creator__username')
    readonly_fields = ('display_name', 'created_at', 'last_edited_at')

    fieldsets = (
        ('Preset Info', {
            'fields': ('name', 'display_name', 'creator', 'is_public', 'last_edited_by')
        }),
        ('Experiment Info', {
            'fields': ('title', 'description')
        }),
        ('Temperature Requirements', {
            'fields': ('required_min_temp', 'required_max_temp')
        }),
        ('Magnetic Field Requirements', {
            'fields': ('required_b_field_x', 'required_b_field_y', 'required_b_field_z',
                      'required_b_field_direction')
        }),
        ('Connection Requirements', {
            'fields': ('required_dc_lines', 'required_rf_lines', 'required_daughterboard')
        }),
        ('Optical Requirements', {
            'fields': ('requires_optical',)
        }),
        ('Duration', {
            'fields': ('estimated_duration_hours',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_edited_at')
        }),
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'notification_type', 'title', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('recipient__username', 'title', 'message')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Notification Info', {
            'fields': ('recipient', 'notification_type', 'title', 'message', 'is_read')
        }),
        ('Related Objects', {
            'fields': ('related_preset', 'related_queue_entry', 'related_machine', 'triggering_user')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'notify_on_deck', 'notify_ready_for_check_in', 'notify_checkout_reminder', 'email_notifications', 'in_app_notifications')
    list_filter = ('notify_on_deck', 'notify_ready_for_check_in', 'notify_checkout_reminder', 'email_notifications', 'in_app_notifications')
    search_fields = ('user__username',)

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Preset Notifications', {
            'fields': ('notify_public_preset_created', 'notify_public_preset_edited',
                      'notify_public_preset_deleted', 'notify_private_preset_edited')
        }),
        ('Queue Notifications', {
            'fields': ('notify_queue_position_change', 'notify_on_deck',
                      'notify_ready_for_check_in', 'notify_checkout_reminder')
        }),
        ('Machine Queue Notifications', {
            'fields': ('notify_machine_queue_changes',)
        }),
        ('Delivery Preferences', {
            'fields': ('email_notifications', 'in_app_notifications')
        }),
    )
