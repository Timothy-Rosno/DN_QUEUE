from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password

class UserProfile(models.Model):
    SECURITY_QUESTIONS = [
        ('pet', 'What was the name of your first pet?'),
        ('city', 'What city were you born in?'),
        ('school', 'What was the name of your elementary school?'),
        ('teacher', 'What was your favorite teacher\'s name?'),
        ('food', 'What is your favorite food?'),
        ('book', 'What is your favorite book?'),
        ('childhood_friend', 'What was the name of your childhood best friend?'),
        ('street', 'What street did you grow up on?'),
        ('custom', 'Create your own question'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('rejected', 'Rejected'),
        ('approved', 'Approved'),
    ]

    ORGANIZATION_CHOICES = [
        ('', ''),  # Empty choice for initial state
        ('montana', 'Montana State University'),
        ('uark', 'University of Arkansas, Fayetteville'),
        ('vtech', 'Virginia Tech'),
        ('other', 'Other'),
    ]

    DEPARTMENT_CHOICES = [
        ('', ''),  # Empty choice
        ('physics', 'Physics'),
        ('materials', 'Materials Science'),
        ('engineering', 'Engineering'),
        ('chemistry', 'Chemistry'),
        ('other', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=15, blank=False)
    organization = models.CharField(max_length=20, choices=ORGANIZATION_CHOICES, blank=False)
    organization_other = models.CharField(max_length=100, blank=True, help_text="Custom organization name")
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES, blank=True)
    department_other = models.CharField(max_length=100, blank=True, help_text="Custom department name")
    notes = models.CharField(max_length=500, blank=True, help_text="Additional information about the user (max 500 characters)")

    # New status field (replaces is_approved boolean)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', help_text="User approval status")

    # Legacy field - kept for migration compatibility, will be removed later
    is_approved = models.BooleanField(default=False, help_text="Has this user been approved by an admin?")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_users')
    approved_at = models.DateTimeField(null=True, blank=True)

    # Slack integration
    slack_member_id = models.CharField(max_length=50, blank=True, help_text="Slack member ID (e.g., U01234ABCD) for DM notifications")

    # Security question for password reset
    security_question = models.CharField(max_length=50, choices=SECURITY_QUESTIONS, blank=True)
    security_question_custom = models.CharField(max_length=200, blank=True, help_text="Custom security question")
    security_answer_hash = models.CharField(max_length=128, blank=True, help_text="Hashed security answer")

    # Developer role (promoted by superusers from staff)
    is_developer = models.BooleanField(default=False, help_text="Has developer access to feedback and analytics")
    developer_promoted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='promoted_developers')
    developer_promoted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_security_question_text(self):
        """Get the actual question text (either predefined or custom)."""
        if self.security_question == 'custom':
            return self.security_question_custom
        return dict(self.SECURITY_QUESTIONS).get(self.security_question, '')

    def set_security_answer(self, answer):
        """Hash and store the security answer (case-insensitive)."""
        self.security_answer_hash = make_password(answer.lower().strip())

    def check_security_answer(self, answer):
        """Check if the provided answer matches the stored hash (case-insensitive)."""
        return check_password(answer.lower().strip(), self.security_answer_hash)

    def save(self, *args, **kwargs):
        """Override save to ensure superusers are always approved."""
        # Superusers should always be approved
        if self.user.is_superuser:
            self.status = 'approved'
            self.is_approved = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
