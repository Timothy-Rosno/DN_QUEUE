from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import ScheduleEntry, QueueEntry, Machine, QueuePreset, NotificationPreference, ArchivedMeasurement
from django.utils import timezone
from .matching_algorithm import get_matching_machines


class QueueEntryForm(forms.ModelForm):
    DAUGHTERBOARD_CHOICES = [
        ('', 'Any'),
        ('QBoard I', 'QBoard I'),
        ('QBoard II', 'QBoard II'),
        ('Montana Puck', 'Montana Puck'),
    ]

    required_daughterboard = forms.ChoiceField(
        choices=DAUGHTERBOARD_CHOICES,
        required=False,
        label='Daughterboard Type',
        help_text='Select the required daughterboard type (leave as "Any" if no specific requirement)'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dynamically calculate min/max values from all machines
        from django.db.models import Min, Max
        machine_stats = Machine.objects.aggregate(
            min_temp_min=Min('min_temp'),
            max_temp_max=Max('max_temp'),
            dc_lines_max=Max('dc_lines'),
            rf_lines_max=Max('rf_lines'),
            b_field_x_max=Max('b_field_x'),
            b_field_y_max=Max('b_field_y'),
            b_field_z_max=Max('b_field_z')
        )

        # Use fallback values if no machines exist
        min_temp_min = machine_stats['min_temp_min'] or 0.01
        max_temp_max = machine_stats['max_temp_max'] or 350
        dc_lines_max = machine_stats['dc_lines_max'] or 48
        rf_lines_max = machine_stats['rf_lines_max'] or 32
        b_field_x_max = machine_stats['b_field_x_max'] or 1
        b_field_y_max = machine_stats['b_field_y_max'] or 1
        b_field_z_max = machine_stats['b_field_z_max'] or 12

        # Calculate step based on smallest temperature precision
        # If min_temp_min = 0.001, step should be 0.001 (allowing 0.001, 0.002, 0.123, etc.)
        # If min_temp_min = 0.1, step should be 0.1 (allowing 0.1, 0.2, 1.5, etc.)
        import decimal
        decimal_places = abs(decimal.Decimal(str(min_temp_min)).as_tuple().exponent)
        temp_step = 10 ** (-decimal_places) if decimal_places > 0 else 1

        # Override field definitions with dynamic values
        self.fields['required_min_temp'] = forms.FloatField(
            validators=[MinValueValidator(min_temp_min), MaxValueValidator(max_temp_max)],
            widget=forms.NumberInput(attrs={'min': str(min_temp_min), 'max': str(max_temp_max), 'step': str(temp_step)}),
            label='Minimum Temperature (K) (ex. 10 mK = 0.01 K)',
            help_text=f'Lowest temperature you need to reach (range: {min_temp_min}-{max_temp_max} K)'
        )

        # DEPRECATED: Maximum temperature field has been removed as it was confusing to users
        # self.fields['required_max_temp'] = forms.FloatField(
        #     required=False,
        #     validators=[MinValueValidator(min_temp_min), MaxValueValidator(max_temp_max)],
        #     widget=forms.NumberInput(attrs={'min': str(min_temp_min), 'max': str(max_temp_max), 'step': '0.01'}),
        #     label='Maximum Temperature (K) - optional',
        #     help_text='Leave blank if you only need minimum temperature'
        # )

        self.fields['required_dc_lines'] = forms.IntegerField(
            initial=0,
            validators=[MinValueValidator(0), MaxValueValidator(dc_lines_max)],
            widget=forms.NumberInput(attrs={'min': '0', 'max': str(dc_lines_max)}),
            label='Minimum DC Lines Needed',
            help_text=f'Minimum number of DC lines your experiment needs (max: {dc_lines_max})'
        )

        self.fields['required_rf_lines'] = forms.IntegerField(
            initial=0,
            validators=[MinValueValidator(0), MaxValueValidator(rf_lines_max)],
            widget=forms.NumberInput(attrs={'min': '0', 'max': str(rf_lines_max)}),
            label='Minimum RF Lines Needed',
            help_text=f'Minimum number of RF lines your experiment needs (max: {rf_lines_max})'
        )

        self.fields['required_b_field_x'] = forms.FloatField(
            required=False,
            initial=0,
            validators=[MinValueValidator(0), MaxValueValidator(b_field_x_max)],
            widget=forms.NumberInput(attrs={'min': '0', 'max': str(b_field_x_max), 'step': '0.01'}),
            label='B-field X (Tesla)'
        )

        self.fields['required_b_field_y'] = forms.FloatField(
            required=False,
            initial=0,
            validators=[MinValueValidator(0), MaxValueValidator(b_field_y_max)],
            widget=forms.NumberInput(attrs={'min': '0', 'max': str(b_field_y_max), 'step': '0.01'}),
            label='B-field Y (Tesla)'
        )

        self.fields['required_b_field_z'] = forms.FloatField(
            required=False,
            initial=0,
            validators=[MinValueValidator(0), MaxValueValidator(b_field_z_max)],
            widget=forms.NumberInput(attrs={'min': '0', 'max': str(b_field_z_max), 'step': '0.01'}),
            label='B-field Z (Tesla)'
        )

    class Meta:
        model = QueueEntry
        fields = ('title', 'description',
                  'required_min_temp',  # 'required_max_temp',  # DEPRECATED - removed from forms
                  'required_b_field_x', 'required_b_field_y', 'required_b_field_z',
                  'required_b_field_direction',
                  'required_dc_lines', 'required_rf_lines',
                  'required_daughterboard',
                  'requires_optical',
                  'special_requirements',
                  'is_rush_job')
        widgets = {
            'title': forms.TextInput(attrs={'maxlength': '500', 'class': 'char-counter-input'}),
            'description': forms.Textarea(attrs={'rows': 3, 'minlength': '50', 'maxlength': '500', 'class': 'char-counter-input'}),
            'special_requirements': forms.Textarea(attrs={'rows': 3, 'maxlength': '500', 'class': 'char-counter-input'}),
        }
        labels = {
            'title': 'Device Name',
            'description': 'Measurement Description',
            'required_b_field_direction': 'B-field Direction',
            'requires_optical': 'Requires Optical Capabilities (not yet used in matching)',
            'is_rush_job': 'Rush Job Appeal',
        }
        help_texts = {
            'title': 'Name of the device being measured (minimum 3 characters)',
            'description': 'Detailed description of the measurement (minimum 50 characters). Example: 2D sweep from -10V to +10V applied bias, temperature sweep 0.01 K to 10 K',
            'required_b_field_direction': 'Required B-field direction',
            'requires_optical': 'Check if your experiment requires optical measurement capabilities (not yet implemented for machine matching)',
            'is_rush_job': 'Check to request priority review and potential queue reordering by admins',
        }

    def clean_title(self):
        """Validate title (Device Name) has minimum 3 characters."""
        title = self.cleaned_data.get('title')
        if title and len(title) < 3:
            raise forms.ValidationError("Not long enough.")
        return title

    def clean_description(self):
        """Validate description (Measurement Description) has minimum 50 characters."""
        description = self.cleaned_data.get('description')
        if not description:
            raise forms.ValidationError("This field is required.")
        if len(description) < 50:
            raise forms.ValidationError("Not long enough (minimum 50 characters).")
        return description

    def clean(self):
        cleaned_data = super().clean()
        min_temp = cleaned_data.get('required_min_temp')
        max_temp = cleaned_data.get('required_max_temp')
        duration = cleaned_data.get('estimated_duration_hours')
        dc_lines = cleaned_data.get('required_dc_lines', 0)
        rf_lines = cleaned_data.get('required_rf_lines', 0)

        # Validate temperature range
        if min_temp and max_temp:
            if max_temp < min_temp:
                raise forms.ValidationError("Maximum temperature must be greater than minimum temperature.")

        # Validate minimum temperature is positive
        if min_temp and min_temp < 0:
            raise forms.ValidationError("Temperature cannot be negative.")

        # Validate duration
        if duration and duration <= 0:
            raise forms.ValidationError("Duration must be positive.")

        # Validate connection requirements are non-negative
        if dc_lines < 0:
            raise forms.ValidationError("DC lines cannot be negative.")
        if rf_lines < 0:
            raise forms.ValidationError("RF lines cannot be negative.")

        # Note: Machine compatibility is checked in the view using find_best_machine()
        # which validates all criteria including new fields like daughterboard and optical

        return cleaned_data


class ScheduleEntryForm(forms.ModelForm):
    class Meta:
        model = ScheduleEntry
        fields = ('title', 'description', 'start_datetime', 'end_datetime',
                  'location', 'attendees', 'special_requirements', 'status')
        widgets = {
            'start_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'special_requirements': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_datetime = cleaned_data.get('start_datetime')
        end_datetime = cleaned_data.get('end_datetime')

        if start_datetime and end_datetime:
            if end_datetime <= start_datetime:
                raise forms.ValidationError("End time must be after start time.")
            if start_datetime < timezone.now():
                raise forms.ValidationError("Cannot schedule events in the past.")

        return cleaned_data


class QueuePresetForm(forms.ModelForm):
    """Form for creating and editing queue presets (excludes is_rush_job and special_requirements)."""
    DAUGHTERBOARD_CHOICES = [
        ('', 'Any'),
        ('QBoard I', 'QBoard I'),
        ('QBoard II', 'QBoard II'),
        ('Montana Puck', 'Montana Puck'),
    ]

    required_daughterboard = forms.ChoiceField(
        choices=DAUGHTERBOARD_CHOICES,
        required=False,
        label='Daughterboard Type',
        help_text='Select the required daughterboard type (leave as "Any" if no specific requirement)'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dynamically calculate min/max values from all machines (same as QueueEntryForm)
        from django.db.models import Min, Max
        machine_stats = Machine.objects.aggregate(
            min_temp_min=Min('min_temp'),
            max_temp_max=Max('max_temp'),
            dc_lines_max=Max('dc_lines'),
            rf_lines_max=Max('rf_lines'),
            b_field_x_max=Max('b_field_x'),
            b_field_y_max=Max('b_field_y'),
            b_field_z_max=Max('b_field_z')
        )

        # Use fallback values if no machines exist
        min_temp_min = machine_stats['min_temp_min'] or 0.01
        max_temp_max = machine_stats['max_temp_max'] or 350
        dc_lines_max = machine_stats['dc_lines_max'] or 48
        rf_lines_max = machine_stats['rf_lines_max'] or 32
        b_field_x_max = machine_stats['b_field_x_max'] or 1
        b_field_y_max = machine_stats['b_field_y_max'] or 1
        b_field_z_max = machine_stats['b_field_z_max'] or 12

        # Calculate step based on smallest temperature precision (same as QueueEntryForm)
        import decimal
        decimal_places = abs(decimal.Decimal(str(min_temp_min)).as_tuple().exponent)
        temp_step = 10 ** (-decimal_places) if decimal_places > 0 else 1

        # Override field definitions with dynamic values (all optional for presets)
        self.fields['title'] = forms.CharField(
            max_length=75,
            required=False,
            label='Device Name (optional)',
            help_text='Name of the device being measured (optional)',
            widget=forms.TextInput(attrs={'maxlength': '75', 'class': 'char-counter-input'})
        )

        self.fields['required_min_temp'] = forms.FloatField(
            required=False,
            validators=[MinValueValidator(min_temp_min), MaxValueValidator(max_temp_max)],
            widget=forms.NumberInput(attrs={'min': str(min_temp_min), 'max': str(max_temp_max), 'step': str(temp_step)}),
            label='Minimum Temperature (K) (ex. 10 mK = 0.01 K) (optional)',
            help_text=f'Lowest temperature you need to reach (range: {min_temp_min}-{max_temp_max} K) (optional)'
        )

        self.fields['required_max_temp'] = forms.FloatField(
            required=False,
            validators=[MinValueValidator(min_temp_min), MaxValueValidator(max_temp_max)],
            widget=forms.NumberInput(attrs={'min': str(min_temp_min), 'max': str(max_temp_max), 'step': str(temp_step)}),
            label='Maximum Temperature (K) (optional)',
            help_text='Leave blank if you only need minimum temperature'
        )

        self.fields['required_dc_lines'] = forms.IntegerField(
            required=False,
            initial=0,
            validators=[MinValueValidator(0), MaxValueValidator(dc_lines_max)],
            widget=forms.NumberInput(attrs={'min': '0', 'max': str(dc_lines_max)}),
            label='Minimum DC Lines Needed (optional)',
            help_text=f'Minimum number of DC lines your experiment needs (max: {dc_lines_max}) (optional)'
        )

        self.fields['required_rf_lines'] = forms.IntegerField(
            required=False,
            initial=0,
            validators=[MinValueValidator(0), MaxValueValidator(rf_lines_max)],
            widget=forms.NumberInput(attrs={'min': '0', 'max': str(rf_lines_max)}),
            label='Minimum RF Lines Needed (optional)',
            help_text=f'Minimum number of RF lines your experiment needs (max: {rf_lines_max}) (optional)'
        )

        self.fields['required_b_field_x'] = forms.FloatField(
            required=False,
            initial=0,
            validators=[MinValueValidator(0), MaxValueValidator(b_field_x_max)],
            widget=forms.NumberInput(attrs={'min': '0', 'max': str(b_field_x_max), 'step': '0.01'}),
            label='B-field X (Tesla) (optional)'
        )

        self.fields['required_b_field_y'] = forms.FloatField(
            required=False,
            initial=0,
            validators=[MinValueValidator(0), MaxValueValidator(b_field_y_max)],
            widget=forms.NumberInput(attrs={'min': '0', 'max': str(b_field_y_max), 'step': '0.01'}),
            label='B-field Y (Tesla) (optional)'
        )

        self.fields['required_b_field_z'] = forms.FloatField(
            required=False,
            initial=0,
            validators=[MinValueValidator(0), MaxValueValidator(b_field_z_max)],
            widget=forms.NumberInput(attrs={'min': '0', 'max': str(b_field_z_max), 'step': '0.01'}),
            label='B-field Z (Tesla) (optional)'
        )

    class Meta:
        model = QueuePreset
        fields = ('name', 'is_public', 'title', 'description',
                  'required_min_temp', 'required_max_temp',
                  'required_b_field_x', 'required_b_field_y', 'required_b_field_z',
                  'required_b_field_direction',
                  'required_dc_lines', 'required_rf_lines',
                  'required_daughterboard',
                  'requires_optical')
        widgets = {
            'name': forms.TextInput(attrs={'maxlength': '500', 'class': 'char-counter-input'}),
            'description': forms.Textarea(attrs={'rows': 3, 'maxlength': '500', 'class': 'char-counter-input'}),
        }
        labels = {
            'name': 'Preset Name',
            'is_public': 'Make Public',
            'description': 'Measurement Description (optional)',
            'required_b_field_direction': 'B-field Direction (optional)',
            'requires_optical': 'Requires Optical Capabilities (optional)',
        }
        help_texts = {
            'name': 'A short name to identify this preset (required)',
            'is_public': 'Public presets are visible to all users. Only you and admins can edit your public presets (unchecked = private)',
            'description': 'Detailed description of the measurement (optional)',
            'required_b_field_direction': 'Required B-field direction',
            'requires_optical': 'Check if your experiment requires optical measurement capabilities',
        }

    def clean(self):
        cleaned_data = super().clean()
        min_temp = cleaned_data.get('required_min_temp')
        max_temp = cleaned_data.get('required_max_temp')
        dc_lines = cleaned_data.get('required_dc_lines')
        rf_lines = cleaned_data.get('required_rf_lines')

        # Set defaults for empty fields
        if dc_lines is None:
            cleaned_data['required_dc_lines'] = 0
            dc_lines = 0
        if rf_lines is None:
            cleaned_data['required_rf_lines'] = 0
            rf_lines = 0

        # Validate temperature range (only if both are provided)
        if min_temp is not None and max_temp is not None:
            if max_temp < min_temp:
                raise forms.ValidationError("Maximum temperature must be greater than minimum temperature.")

        # Validate minimum temperature is positive (only if provided)
        if min_temp is not None and min_temp < 0:
            raise forms.ValidationError("Temperature cannot be negative.")

        # Validate connection requirements are non-negative
        if dc_lines < 0:
            raise forms.ValidationError("DC lines cannot be negative.")
        if rf_lines < 0:
            raise forms.ValidationError("RF lines cannot be negative.")

        return cleaned_data


class NotificationPreferenceForm(forms.ModelForm):
    """Form for managing user notification preferences."""

    class Meta:
        model = NotificationPreference
        fields = (
            # Preset notifications
            'notify_public_preset_created',
            'notify_public_preset_edited',
            'notify_public_preset_deleted',
            'notify_private_preset_edited',
            'notify_followed_preset_edited',
            'notify_followed_preset_deleted',
            # Queue notifications
            'notify_queue_position_change',
            'notify_on_deck',  # REQUIRED - cannot be disabled
            'notify_ready_for_check_in',  # REQUIRED - cannot be disabled
            'notify_checkout_reminder',  # REQUIRED - cannot be disabled
            # Machine queue notifications
            'notify_machine_queue_changes',
            # Delivery preferences
            'email_notifications',
            'in_app_notifications',
            # Admin notifications
            'notify_admin_new_user',
            'notify_admin_rush_job',
        )
        labels = {
            # Preset notifications
            'notify_public_preset_created': 'Public Preset Created',
            'notify_public_preset_edited': 'Public Preset Edited',
            'notify_public_preset_deleted': 'Public Preset Deleted',
            'notify_private_preset_edited': 'Your Private Preset Edited by Others',
            'notify_followed_preset_edited': 'Presets You Follow Are Edited',
            'notify_followed_preset_deleted': 'Presets You Follow Are Deleted',
            # Queue notifications
            'notify_queue_position_change': 'Queue Position Changes',
            'notify_on_deck': 'ON DECK - You\'re Next! (REQUIRED)',
            'notify_ready_for_check_in': 'Ready for Check-In (REQUIRED)',
            'notify_checkout_reminder': 'Time for Check-Out Reminder (REQUIRED)',
            # Machine queue notifications
            'notify_machine_queue_changes': 'New Entries Added to Your Machine Queue',
            # Delivery preferences
            'email_notifications': 'Email Notifications (future feature)',
            'in_app_notifications': 'In-App Notifications',
            # Admin notifications
            'notify_admin_new_user': 'New User Registrations',
            'notify_admin_rush_job': 'Rush Job Requests',
        }
        help_texts = {
            'notify_public_preset_created': 'Get notified when new public presets are created',
            'notify_public_preset_edited': 'Get notified when public presets are edited',
            'notify_public_preset_deleted': 'Get notified when public presets are deleted',
            'notify_private_preset_edited': 'Get notified when someone else edits your private presets',
            'notify_followed_preset_edited': 'Get notified when presets you follow are edited',
            'notify_followed_preset_deleted': 'Get notified when presets you follow are deleted',
            'notify_queue_position_change': 'Get notified when your queue position moves up or down',
            'notify_on_deck': '⚠️ REQUIRED: You will always be notified when you\'re #1 in line',
            'notify_ready_for_check_in': '⚠️ REQUIRED: You will be notified when the machine becomes available and you can check in',
            'notify_checkout_reminder': '⚠️ REQUIRED: You will be notified when your estimated measurement time has elapsed and you should check out',
            'notify_machine_queue_changes': 'Get notified when others add jobs to machines where you have queued entries (can be noisy)',
            'email_notifications': 'Receive notifications via email (not yet implemented)',
            'in_app_notifications': 'Show notifications in the web interface',
            'notify_admin_new_user': 'Get notified when new users register (staff/superuser only)',
            'notify_admin_rush_job': 'Get notified when users submit rush job requests (staff/superuser only)',
        }
        widgets = {
            'notify_on_deck': forms.CheckboxInput(attrs={'disabled': 'disabled', 'checked': 'checked'}),
            'notify_ready_for_check_in': forms.CheckboxInput(attrs={'disabled': 'disabled', 'checked': 'checked'}),
            'notify_checkout_reminder': forms.CheckboxInput(attrs={'disabled': 'disabled', 'checked': 'checked'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make critical notifications required (always checked, disabled)
        self.fields['notify_on_deck'].required = True
        self.fields['notify_on_deck'].disabled = True

        self.fields['notify_ready_for_check_in'].required = True
        self.fields['notify_ready_for_check_in'].disabled = True

        self.fields['notify_checkout_reminder'].required = True
        self.fields['notify_checkout_reminder'].disabled = True

    def clean_notify_on_deck(self):
        """Ensure ON DECK notification is always enabled."""
        # Always return True for ON DECK notifications
        return True

    def clean_notify_ready_for_check_in(self):
        """Ensure Ready for Check-In notification is always enabled."""
        # Always return True for Ready for Check-In notifications
        return True

    def clean_notify_checkout_reminder(self):
        """Ensure checkout reminder notification is always enabled."""
        # Always return True for checkout reminder notifications
        return True

    def clean(self):
        """Validate that at least one notification delivery method is enabled."""
        cleaned_data = super().clean()
        email_notif = cleaned_data.get('email_notifications')
        in_app_notif = cleaned_data.get('in_app_notifications')

        if not email_notif and not in_app_notif:
            raise forms.ValidationError(
                "You must enable at least one notification delivery method "
                "(Email Notifications or In-App Notifications)."
            )

        return cleaned_data


class ArchivedMeasurementForm(forms.ModelForm):
    """Form for creating and editing archived measurements."""

    class Meta:
        model = ArchivedMeasurement
        fields = ('title', 'notes', 'measurement_date', 'duration_hours', 'uploaded_file')
        widgets = {
            'title': forms.TextInput(attrs={'maxlength': '500', 'class': 'char-counter-input'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'maxlength': '500', 'class': 'char-counter-input'}),
            'measurement_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'duration_hours': forms.NumberInput(attrs={'min': '0', 'step': '0.1'}),
            'uploaded_file': forms.FileInput(attrs={'accept': '.csv,.txt,.dat,.xlsx,.pdf,.zip,.png,.jpg'}),
        }
        labels = {
            'title': 'Measurement Title',
            'notes': 'Notes',
            'measurement_date': 'Measurement Date',
            'duration_hours': 'Duration (hours)',
            'uploaded_file': 'Upload File (optional)',
        }
        help_texts = {
            'title': 'A descriptive title for this archived measurement',
            'notes': 'Additional notes or observations about this measurement',
            'measurement_date': 'Date and time when the measurement was taken',
            'duration_hours': 'Duration of the measurement in hours (optional)',
            'uploaded_file': 'Upload measurement data file (CSV, TXT, DAT, Excel, PDF, ZIP, images)',
        }

    def clean_title(self):
        """Validate title has minimum 3 characters."""
        title = self.cleaned_data.get('title')
        if title and len(title) < 3:
            raise forms.ValidationError("Title must be at least 3 characters long.")
        return title
