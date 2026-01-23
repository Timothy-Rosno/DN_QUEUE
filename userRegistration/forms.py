from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from .models import UserProfile
from calendarEditor.models import NotificationPreference

# Validator to allow only ASCII characters (including spaces)
ascii_username_validator = RegexValidator(
    regex=r'^[\x20-\x7E]+$',
    message='Username can only contain ASCII characters (letters, numbers, spaces, and standard punctuation).'
)

class UserRegistrationForm(UserCreationForm):
    # Override username field to allow ASCII characters (including spaces)
    username = forms.CharField(
        max_length=150,
        required=True,
        label='Username',
        help_text='Slack username preferred (Churchill Lab)',
        validators=[ascii_username_validator],
    )
    email = forms.EmailField(
        required=True,
        help_text="Slack account email preferred (Churchill Lab)"
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        help_text="from Slack"
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        help_text="(Optional)"
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

    def clean_username(self):
        """Allow ASCII characters in username, including spaces."""
        username = self.cleaned_data.get('username')
        # Check if username already exists (case-insensitive to avoid duplicates)
        from django.contrib.auth.models import User
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('A user with that username already exists.')
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']

        if commit:
            # Bypass Django's default username validators to allow ASCII characters (including spaces)
            from django.contrib.auth.models import User
            User._meta.get_field('username').validators = []
            user.save()
        return user

class UserProfileForm(forms.ModelForm):
    # Security question fields (for registration)
    security_answer = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.PasswordInput(attrs={'autocomplete': 'off'}),
        label='Security Answer',
        help_text='This will be used for password recovery (case-insensitive)'
    )

    class Meta:
        model = UserProfile
        fields = ('phone_number', 'organization', 'organization_other', 'department', 'department_other', 'notes', 'slack_member_id', 'security_question', 'security_question_custom')
        widgets = {
            'phone_number': forms.TextInput(attrs={
                'type': 'tel',
                'maxlength': '15',
            }),
            'organization': forms.Select(),
            'organization_other': forms.TextInput(attrs={
                'maxlength': '100',
            }),
            'department': forms.Select(),
            'department_other': forms.TextInput(attrs={
                'maxlength': '100',
            }),
            'notes': forms.Textarea(attrs={
                'rows': 3,
                'maxlength': '500',
            }),
            'slack_member_id': forms.TextInput(attrs={
                'maxlength': '50',
                'placeholder': 'e.g., U01234ABCD (leave blank for auto-lookup)'
            }),
            'security_question': forms.Select(),
            'security_question_custom': forms.TextInput(attrs={
                'maxlength': '200',
                'placeholder': 'Enter your custom question'
            }),
        }
        labels = {
            'phone_number': 'Phone Number',
            'organization': 'Organization',
            'organization_other': 'Organization Name',
            'department': 'Department',
            'department_other': 'Department Name',
            'notes': 'Notes',
        }
        help_texts = {
            'phone_number': 'Required',
            'organization': 'Required',
            'department': 'Select your department (if applicable)',
            'notes': '(Optional)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make security question required for new registrations and force custom question
        if not self.instance.pk:
            # Force custom question for new registrations
            self.fields['security_question'].initial = 'custom'
            self.fields['security_question'].widget = forms.HiddenInput()
            self.fields['security_question_custom'].required = True
            self.fields['security_question_custom'].label = 'Security Question'
            self.fields['security_answer'].required = True
        else:
            # For existing profiles, make security question fields optional (not shown in profile template)
            self.fields['security_question_custom'].required = False
            self.fields['security_question'].required = False

        # Organization and phone_number are ALWAYS required (model has blank=False)
        # department, department_other, organization_other, notes are optional
        self.fields['organization_other'].required = False
        self.fields['department'].required = False
        self.fields['department_other'].required = False
        self.fields['notes'].required = False

    def clean(self):
        cleaned_data = super().clean()
        organization = cleaned_data.get('organization')
        organization_other = cleaned_data.get('organization_other')
        department = cleaned_data.get('department')
        department_other = cleaned_data.get('department_other')
        security_question = cleaned_data.get('security_question')
        security_question_custom = cleaned_data.get('security_question_custom')

        # If "Other" organization is selected, organization_other is required
        if organization == 'other' and not organization_other:
            self.add_error('organization_other', 'Please enter your organization name.')

        # If "Other" department is selected, department_other is required
        if department == 'other' and not department_other:
            self.add_error('department_other', 'Please enter your department name.')

        # If custom security question is selected, custom question text is required
        if security_question == 'custom' and not security_question_custom:
            self.add_error('security_question_custom', 'Please enter your custom security question.')

        return cleaned_data

class NotificationPreferenceForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Add admin fields if user is staff
        if user and (user.is_staff or user.is_superuser):
            self.fields['notify_admin_new_user'] = forms.BooleanField(
                required=False,
                label='New user signup',
                help_text='Critical notification - cannot be disabled',
                widget=forms.CheckboxInput(attrs={'disabled': True}),
                initial=self.instance.notify_admin_new_user if self.instance.pk else True
            )
            self.fields['notify_admin_rush_job'] = forms.BooleanField(
                required=False,
                label='Rush job/Queue appeal submitted',
                help_text='Critical notification - cannot be disabled',
                widget=forms.CheckboxInput(attrs={'disabled': True}),
                initial=self.instance.notify_admin_rush_job if self.instance.pk else True
            )
            self.fields['notify_database_restored'] = forms.BooleanField(
                required=False,
                label='Database restored',
                help_text='Critical notification - cannot be disabled',
                widget=forms.CheckboxInput(attrs={'disabled': True}),
                initial=self.instance.notify_database_restored if self.instance.pk else True
            )

        # Add developer fields if user has developer permissions
        # For now, we'll show this to all staff/superusers, but this could be refined
        # with a specific permission check like: user.has_perm('calendarEditor.view_feedback')
        if user and (user.is_staff or user.is_superuser):
            self.fields['notify_developer_feedback'] = forms.BooleanField(
                required=False,
                label='User feedback submitted',
                help_text='Critical notification - cannot be disabled',
                widget=forms.CheckboxInput(attrs={'disabled': True}),
                initial=self.instance.notify_developer_feedback if self.instance.pk else True
            )

    class Meta:
        model = NotificationPreference
        fields = (
            # Preset notifications
            'notify_public_preset_created',
            'notify_public_preset_edited',
            'notify_public_preset_deleted',
            'notify_private_preset_edited',
            # Followed preset notifications
            'notify_followed_preset_edited',
            'notify_followed_preset_deleted',
            # Queue notifications
            'notify_queue_added',
            'notify_queue_position_change',
            'notify_queue_cancelled',
            'notify_on_deck',
            'notify_ready_for_check_in',
            'notify_checkin_reminder',
            'notify_checkout_reminder',
            # Machine queue notifications
            'notify_machine_queue_changes',
            # Admin action notifications
            'notify_admin_check_in',
            'notify_admin_checkout',
            'notify_admin_edit_entry',
            'notify_admin_moved_entry',
            'notify_machine_status_change',
            # Queue appeal notifications
            'notify_appeal_approved',
            'notify_appeal_rejected',
            # Account status notifications
            'notify_account_approved',
            'notify_account_unapproved',
            'notify_account_promoted',
            'notify_account_demoted',
            'notify_account_info_changed',
            # Delivery preferences
            'in_app_notifications',
            'slack_notifications',
            'email_notifications',
        )
        labels = {
            'notify_public_preset_created': 'Public preset created',
            'notify_public_preset_edited': 'Public preset edited',
            'notify_public_preset_deleted': 'Public preset deleted',
            'notify_private_preset_edited': 'Your private preset edited by admins',
            'notify_followed_preset_edited': 'Presets you follow are edited',
            'notify_followed_preset_deleted': 'Presets you follow are deleted',
            'notify_queue_added': 'Queue entry successfully added',
            'notify_queue_position_change': 'Queue position changes',
            'notify_queue_cancelled': 'Queue entry cancelled',
            'notify_on_deck': 'When you\'re ON DECK (next in line)',
            'notify_ready_for_check_in': 'Machine available for check-in',
            'notify_checkin_reminder': 'Reminder to check in',
            'notify_checkout_reminder': 'Time to check out',
            'notify_machine_queue_changes': 'Entries added to machines you\'re queued for',
            'notify_admin_check_in': 'Admin checks you in',
            'notify_admin_checkout': 'Admin checks you out',
            'notify_admin_edit_entry': 'Admin edits your queue entry',
            'notify_admin_moved_entry': 'Admin moves your queue entry',
            'notify_machine_status_change': 'Admin changes machine status',
            'notify_appeal_approved': 'Queue appeal approved',
            'notify_appeal_rejected': 'Queue appeal rejected',
            'notify_account_approved': 'Account approved',
            'notify_account_unapproved': 'Account unapproved',
            'notify_account_promoted': 'Promoted to staff',
            'notify_account_demoted': 'Demoted from staff',
            'notify_account_info_changed': 'Account information changed by admin',
            'in_app_notifications': 'Show notifications in app',
            'slack_notifications': 'Send notifications via Slack',
            'email_notifications': 'Send notifications via email',
        }
        help_texts = {
            'notify_on_deck': 'Critical notification - cannot be disabled',
            'notify_ready_for_check_in': 'Critical notification - cannot be disabled',
            'notify_checkin_reminder': 'Critical notification - cannot be disabled',
            'notify_checkout_reminder': 'Critical notification - cannot be disabled',
            'notify_appeal_approved': 'Critical notification - cannot be disabled',
            'notify_appeal_rejected': 'Critical notification - cannot be disabled',
            'notify_account_approved': 'Critical notification - cannot be disabled',
            'notify_account_unapproved': 'Critical notification - cannot be disabled',
            'notify_account_promoted': 'Critical notification - cannot be disabled',
            'notify_account_demoted': 'Critical notification - cannot be disabled',
            'notify_account_info_changed': 'Critical notification - cannot be disabled',
            'email_notifications': 'Email delivery not yet implemented',
        }
        widgets = {
            'notify_on_deck': forms.CheckboxInput(attrs={'disabled': True}),
            'notify_ready_for_check_in': forms.CheckboxInput(attrs={'disabled': True}),
            'notify_checkin_reminder': forms.CheckboxInput(attrs={'disabled': True}),
            'notify_checkout_reminder': forms.CheckboxInput(attrs={'disabled': True}),
            'notify_appeal_approved': forms.CheckboxInput(attrs={'disabled': True}),
            'notify_appeal_rejected': forms.CheckboxInput(attrs={'disabled': True}),
            'notify_account_approved': forms.CheckboxInput(attrs={'disabled': True}),
            'notify_account_unapproved': forms.CheckboxInput(attrs={'disabled': True}),
            'notify_account_promoted': forms.CheckboxInput(attrs={'disabled': True}),
            'notify_account_demoted': forms.CheckboxInput(attrs={'disabled': True}),
            'in_app_notifications': forms.CheckboxInput(attrs={'disabled': True}),
            'notify_account_info_changed': forms.CheckboxInput(attrs={'disabled': True}),
        }


class ChangeSecurityQuestionForm(forms.Form):
    """Form for changing security question - requires password verification."""
    current_password = forms.CharField(
        max_length=128,
        required=True,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
        label='Current Password',
        help_text='Enter your current password to verify your identity'
    )

    new_security_question = forms.ChoiceField(
        choices=UserProfile.SECURITY_QUESTIONS,
        required=True,
        label='New Security Question'
    )

    new_security_question_custom = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your custom security question',
            'autocomplete': 'off'
        }),
        label='Custom Question'
    )

    new_security_answer = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label='New Security Answer',
        help_text='Your answer will be used for password recovery (case-insensitive)'
    )

    new_security_answer_confirm = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label='Confirm New Answer'
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        """Verify the current password matches."""
        password = self.cleaned_data.get('current_password')
        if not self.user.check_password(password):
            raise forms.ValidationError('Incorrect password. Please try again.')
        return password

    def clean(self):
        cleaned_data = super().clean()
        new_question = cleaned_data.get('new_security_question')
        new_custom = cleaned_data.get('new_security_question_custom')
        new_answer = cleaned_data.get('new_security_answer')
        confirm_answer = cleaned_data.get('new_security_answer_confirm')

        # If custom question is selected, custom text is required
        if new_question == 'custom' and not new_custom:
            self.add_error('new_security_question_custom', 'Please enter your custom security question.')

        # Verify answers match
        if new_answer and confirm_answer and new_answer != confirm_answer:
            self.add_error('new_security_answer_confirm', 'Answers do not match.')

        return cleaned_data


class AdminEditUserForm(forms.Form):
    """Form for admins to edit all user information."""
    username = forms.CharField(
        max_length=150,
        required=True,
        label='Username',
        validators=[ascii_username_validator],
    )
    email = forms.EmailField(
        required=True,
        label='Email'
    )
    first_name = forms.CharField(
        max_length=30,
        required=False,
        label='First Name'
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        label='Last Name'
    )
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        label='Phone Number',
        widget=forms.TextInput(attrs={'type': 'tel', 'maxlength': '15'}),
        help_text='Optional'
    )
    organization = forms.ChoiceField(
        choices=UserProfile.ORGANIZATION_CHOICES,
        required=True,
        label='Organization',
        widget=forms.Select()
    )
    organization_other = forms.CharField(
        max_length=100,
        required=False,
        label='Organization Name',
        widget=forms.TextInput(attrs={'maxlength': '100'})
    )
    department = forms.ChoiceField(
        choices=UserProfile.DEPARTMENT_CHOICES,
        required=False,
        label='Department',
        widget=forms.Select()
    )
    department_other = forms.CharField(
        max_length=100,
        required=False,
        label='Department Name',
        widget=forms.TextInput(attrs={'maxlength': '100'})
    )
    notes = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'maxlength': '500'}),
        label='Notes',
        help_text='Optional'
    )
    slack_member_id = forms.CharField(
        max_length=50,
        required=False,
        label='Slack Member ID'
    )
    security_question = forms.ChoiceField(
        choices=UserProfile.SECURITY_QUESTIONS,
        required=False,
        label='Security Question'
    )
    security_question_custom = forms.CharField(
        max_length=200,
        required=False,
        label='Custom Security Question'
    )
    security_answer = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label='New Security Answer (leave blank to keep current)',
        help_text='Only fill this if you want to change the security answer'
    )

    def __init__(self, user_instance, *args, **kwargs):
        self.user_instance = user_instance
        super().__init__(*args, **kwargs)

        # Pre-populate fields with current user data
        if user_instance:
            self.fields['username'].initial = user_instance.username
            self.fields['email'].initial = user_instance.email
            self.fields['first_name'].initial = user_instance.first_name
            self.fields['last_name'].initial = user_instance.last_name

            if hasattr(user_instance, 'profile'):
                profile = user_instance.profile
                self.fields['phone_number'].initial = profile.phone_number
                self.fields['organization'].initial = profile.organization
                self.fields['organization_other'].initial = profile.organization_other
                self.fields['department'].initial = profile.department
                self.fields['department_other'].initial = profile.department_other
                self.fields['notes'].initial = profile.notes
                self.fields['slack_member_id'].initial = profile.slack_member_id
                self.fields['security_question'].initial = profile.security_question
                self.fields['security_question_custom'].initial = profile.security_question_custom

    def clean_username(self):
        """Validate that username is unique (except for current user)."""
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exclude(id=self.user_instance.id).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        security_question = cleaned_data.get('security_question')
        security_question_custom = cleaned_data.get('security_question_custom')
        organization = cleaned_data.get('organization')
        organization_other = cleaned_data.get('organization_other')
        department = cleaned_data.get('department')
        department_other = cleaned_data.get('department_other')

        # If custom question is selected, custom text is required
        if security_question == 'custom' and not security_question_custom:
            self.add_error('security_question_custom', 'Please enter a custom security question.')

        # If "Other" organization is selected, organization_other is required
        if organization == 'other' and not organization_other:
            self.add_error('organization_other', 'Please enter the organization name.')

        # If "Other" department is selected, department_other is required
        if department == 'other' and not department_other:
            self.add_error('department_other', 'Please enter the department name.')

        return cleaned_data
