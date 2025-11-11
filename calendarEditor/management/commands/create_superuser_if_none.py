"""
Management command to create a superuser if none exists.
This is used during Render deployment since Shell is a paid feature.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a superuser if none exists (for Render free tier deployment)'

    def handle(self, *args, **options):
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.SUCCESS('Superuser already exists - skipping'))
            return

        # Get credentials from environment variables or use defaults
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin')

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Superuser created successfully!\n'
                f'Username: {username}\n'
                f'Password: {password}\n'
                f'Email: {email}'
            )
        )
