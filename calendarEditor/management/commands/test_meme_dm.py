"""
Management command to test sending an image/GIF via Slack DM.

This validates image delivery through the notification system in isolation
(no QueueEntry/appeal side effects) before it's relied on by the appeal
escalation feature.

Usage:
    python manage.py test_meme_dm --email quantumdeviceslab@gmail.com
    python manage.py test_meme_dm --username timothy
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.conf import settings
from calendarEditor import notifications


class Command(BaseCommand):
    help = 'Send a test Slack DM with an embedded meme image/GIF to a specific user'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            default='quantumdeviceslab@gmail.com',
            help='Email of the user to send the test meme DM to (default: quantumdeviceslab@gmail.com)',
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Username of the user to send the test meme DM to (overrides --email if given)',
        )

    def handle(self, *args, **options):
        if not settings.SLACK_ENABLED:
            raise CommandError('SLACK_ENABLED is False - set SLACK_BOT_TOKEN to test Slack delivery.')

        if options['username']:
            try:
                user = User.objects.get(username=options['username'])
            except User.DoesNotExist:
                raise CommandError(f"No user found with username '{options['username']}'")
        else:
            email = options['email']
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                raise CommandError(f"No user found with email '{email}'")
            except User.MultipleObjectsReturned:
                raise CommandError(f"Multiple users found with email '{email}' - use --username instead")

        image_url = notifications.get_random_meme_url()
        self.stdout.write(f'Sending test meme DM to {user.username} ({user.email})')
        self.stdout.write(f'Image URL: {image_url}')

        notifications.send_slack_dm(
            user,
            title='Test Meme Delivery',
            message='This is a test of image/GIF delivery via Slack Block Kit.',
            image_url=image_url,
        )

        self.stdout.write(self.style.SUCCESS(
            'Slack DM dispatched in a background thread - check the console/logs for "Slack API error" '
            'if it failed, or check Slack directly to confirm the image rendered.'
        ))
