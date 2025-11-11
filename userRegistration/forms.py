from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile
from calendarEditor.models import NotificationPreference

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user

class UserProfileForm(forms.ModelForm):
    security_answer = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        help_text="Your answer will be used for password recovery (case-insensitive)"
    )

    class Meta:
        model = UserProfile
        fields = ('phone_number', 'department', 'notes', 'slack_member_id', 'security_question', 'security_question_custom')
        widgets = {
            'phone_number': forms.TextInput(attrs={
                'maxlength': '15',
                'placeholder': 'Max 15 characters'
            }),
            'department': forms.TextInput(attrs={
                'maxlength': '100',
                'placeholder': 'Max 100 characters'
            }),
            'notes': forms.Textarea(attrs={
                'rows': 3,
                'maxlength': '500',
                'placeholder': 'Max 500 characters'
            }),
            'slack_member_id': forms.TextInput(attrs={
                'maxlength': '50',
                'placeholder': 'e.g., U01234ABCD (leave blank for auto-lookup)'
            }),
            'security_question_custom': forms.TextInput(attrs={
                'placeholder': 'Enter your custom security question',
                'autocomplete': 'off'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make security question required for new registrations
        if not self.instance.pk:
            self.fields['security_question'].required = True
            self.fields['security_answer'].required = True

        # Set initial visibility for custom question field
        self.fields['security_question_custom'].required = False

    def clean(self):
        cleaned_data = super().clean()
        security_question = cleaned_data.get('security_question')
        security_question_custom = cleaned_data.get('security_question_custom')

        # If custom question is selected, custom text is required
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
                label='Rush job submitted',
                help_text='Critical notification - cannot be disabled',
                widget=forms.CheckboxInput(attrs={'disabled': True}),
                initial=self.instance.notify_admin_rush_job if self.instance.pk else True
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
            'notify_queue_position_change',
            'notify_on_deck',
            'notify_ready_for_check_in',
            'notify_checkout_reminder',
            # Machine queue notifications
            'notify_machine_queue_changes',
            # Admin action notifications
            'notify_admin_check_in',
            'notify_admin_checkout',
            'notify_admin_edit_entry',
            'notify_machine_status_change',
            # Delivery preferences
            'in_app_notifications',
            'email_notifications',
        )
        labels = {
            'notify_public_preset_created': 'Public preset created',
            'notify_public_preset_edited': 'Public preset edited',
            'notify_public_preset_deleted': 'Public preset deleted',
            'notify_private_preset_edited': 'Your private preset edited by others',
            'notify_followed_preset_edited': 'Presets you follow are edited',
            'notify_followed_preset_deleted': 'Presets you follow are deleted',
            'notify_queue_position_change': 'Queue position changes',
            'notify_on_deck': 'When you\'re ON DECK (next in line)',
            'notify_ready_for_check_in': 'Machine available for check-in',
            'notify_checkout_reminder': 'Time to check out',
            'notify_machine_queue_changes': 'Entries added to machines you\'re queued for',
            'notify_admin_check_in': 'Admin checks you in',
            'notify_admin_checkout': 'Admin checks you out',
            'notify_admin_edit_entry': 'Admin edits your queue entry',
            'notify_machine_status_change': 'Admin changes machine status',
            'in_app_notifications': 'Show notifications in app',
            'email_notifications': 'Send notifications via email',
        }
        help_texts = {
            'notify_on_deck': 'Critical notification - cannot be disabled',
            'notify_ready_for_check_in': 'Critical notification - cannot be disabled',
            'notify_checkout_reminder': 'Critical notification - cannot be disabled',
            'email_notifications': 'Email delivery not yet implemented',
        }
        widgets = {
            'notify_on_deck': forms.CheckboxInput(attrs={'disabled': True}),
            'notify_ready_for_check_in': forms.CheckboxInput(attrs={'disabled': True}),
            'notify_checkout_reminder': forms.CheckboxInput(attrs={'disabled': True}),
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
