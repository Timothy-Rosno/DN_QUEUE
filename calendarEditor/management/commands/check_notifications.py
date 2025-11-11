"""
Management command to diagnose and fix notification preferences.

This command helps identify why notifications (especially Rush Jobs) might not be working.

Usage:
    python manage.py check_notifications           # Check all notification settings
    python manage.py check_notifications --fix     # Fix any issues found
    python manage.py check_notifications --user USERNAME  # Check specific user
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from calendarEditor.models import NotificationPreference


class Command(BaseCommand):
    help = 'Diagnose and fix notification preference issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Automatically fix any issues found',
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Check specific user by username',
        )
        parser.add_argument(
            '--admins-only',
            action='store_true',
            help='Only check admin/staff users',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Notification Preferences Diagnostic ===\n'))

        # Determine which users to check
        if options['user']:
            users = User.objects.filter(username=options['user'])
            if not users.exists():
                self.stdout.write(self.style.ERROR(f"User '{options['user']}' not found"))
                return
        elif options['admins_only']:
            users = User.objects.filter(is_staff=True) | User.objects.filter(is_superuser=True)
        else:
            users = User.objects.all()

        issues_found = 0
        issues_fixed = 0

        for user in users:
            # Get or create preferences
            prefs, created = NotificationPreference.objects.get_or_create(user=user)

            # Check if user is admin
            is_admin = user.is_staff or user.is_superuser

            # Display user info
            user_type = '👑 ADMIN' if is_admin else '👤 USER'
            self.stdout.write(f'\n{user_type}: {user.username} ({user.email})')

            if created:
                self.stdout.write(self.style.WARNING('  ⚠️  No preferences found - created new record with defaults'))
                issues_found += 1
                if options['fix']:
                    issues_fixed += 1

            # Check critical settings
            problems = []

            # Check if in-app notifications are disabled
            if not prefs.in_app_notifications:
                problems.append('❌ In-app notifications are DISABLED')
                if options['fix']:
                    prefs.in_app_notifications = True
                    problems[-1] += ' → FIXED'
                    issues_fixed += 1

            # Admin-specific checks
            if is_admin:
                if not prefs.notify_admin_rush_job:
                    problems.append('❌ Rush job notifications are DISABLED')
                    if options['fix']:
                        prefs.notify_admin_rush_job = True
                        problems[-1] += ' → FIXED'
                        issues_fixed += 1

                if not prefs.notify_admin_new_user:
                    problems.append('⚠️  New user notifications are disabled')
                    if options['fix']:
                        prefs.notify_admin_new_user = True
                        problems[-1] += ' → FIXED'
                        issues_fixed += 1

            # Check admin action preferences (for regular users)
            if not is_admin:
                if not prefs.notify_admin_check_in:
                    problems.append('⚠️  Admin check-in notifications are disabled')
                if not prefs.notify_admin_checkout:
                    problems.append('⚠️  Admin check-out notifications are disabled')

            # Display results
            if problems:
                issues_found += len(problems)
                for problem in problems:
                    self.stdout.write(f'  {problem}')
            else:
                self.stdout.write(self.style.SUCCESS('  ✅ All notification preferences look good'))

            # Show key settings
            if is_admin:
                self.stdout.write(f'  📊 Key settings:')
                self.stdout.write(f'     - In-app: {"✓" if prefs.in_app_notifications else "✗"}')
                self.stdout.write(f'     - Rush jobs: {"✓" if prefs.notify_admin_rush_job else "✗"}')
                self.stdout.write(f'     - New users: {"✓" if prefs.notify_admin_new_user else "✗"}')

            # Save if we made any fixes
            if options['fix'] and problems:
                prefs.save()

        # Summary
        self.stdout.write(self.style.SUCCESS(f'\n=== Summary ==='))
        self.stdout.write(f'Users checked: {users.count()}')
        self.stdout.write(f'Issues found: {issues_found}')

        if options['fix']:
            self.stdout.write(self.style.SUCCESS(f'Issues fixed: {issues_fixed}'))
            if issues_fixed > 0:
                self.stdout.write(self.style.SUCCESS('\n✅ Fixes applied successfully!'))
        else:
            if issues_found > 0:
                self.stdout.write(self.style.WARNING(f'\nRun with --fix to automatically fix these issues'))

        # Additional diagnostic info
        self.stdout.write(self.style.SUCCESS('\n=== Additional Diagnostics ==='))

        # Check if any admins exist
        admin_count = User.objects.filter(is_staff=True).count()
        self.stdout.write(f'Total admin/staff users: {admin_count}')

        # Check admins with rush job notifications enabled
        admins_with_rush = NotificationPreference.objects.filter(
            user__is_staff=True,
            notify_admin_rush_job=True,
            in_app_notifications=True
        ).count()
        self.stdout.write(f'Admins with rush job notifications enabled: {admins_with_rush}/{admin_count}')

        if admins_with_rush == 0 and admin_count > 0:
            self.stdout.write(self.style.ERROR('\n⚠️  WARNING: No admins will receive rush job notifications!'))
            self.stdout.write(self.style.WARNING('Run with --fix --admins-only to enable rush job notifications for all admins'))
