"""
Custom Django management command to run development server with Redis.

This command automatically starts Redis in the background before running
the Django development server, making it easy to run the full application
with real-time WebSocket support in a single command.

Usage:
    python manage.py runserver_with_redis
    python manage.py runserver_with_redis 0.0.0.0:8080
"""

import os
import sys
import subprocess
import socket
import atexit
import signal
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Run Django development server with Redis auto-start'

    redis_process = None

    def add_arguments(self, parser):
        # Accept all standard runserver arguments
        parser.add_argument(
            'addrport', nargs='?', default='127.0.0.1:8000',
            help='Optional port number, or ipaddr:port'
        )
        parser.add_argument(
            '--noreload', action='store_false', dest='use_reloader',
            default=True, help='Tells Django to NOT use the auto-reloader.',
        )
        parser.add_argument(
            '--nothreading', action='store_false', dest='use_threading',
            default=True,
            help='Tells Django to NOT use threading.',
        )

    def handle(self, *args, **options):
        # Print startup banner
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('  Django + Redis Development Server'))
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))

        # Check and start Redis
        if self.is_redis_running():
            self.stdout.write(self.style.SUCCESS('✓ Redis is already running'))
        else:
            self.stdout.write(self.style.WARNING('⚠ Redis not running, starting...'))
            if self.start_redis():
                self.stdout.write(self.style.SUCCESS('✓ Redis started successfully'))
                # Register cleanup handler
                atexit.register(self.cleanup_redis)
                signal.signal(signal.SIGINT, self.signal_handler)
                signal.signal(signal.SIGTERM, self.signal_handler)
            else:
                self.stdout.write(self.style.ERROR('✗ Failed to start Redis'))
                self.stdout.write(self.style.WARNING(
                    '  App will run but real-time updates will be disabled.\n'
                    '  To enable real-time updates, install Redis:\n'
                    '    macOS: brew install redis\n'
                    '    Linux: sudo apt-get install redis-server\n'
                ))

        # Start Django development server
        self.stdout.write(self.style.SUCCESS('\n✓ Starting Django development server...\n'))

        # Extract addrport for runserver
        addrport = options.get('addrport', '127.0.0.1:8000')

        try:
            # Call standard runserver command with options
            call_command(
                'runserver',
                addrport,
                use_reloader=options.get('use_reloader', True),
                use_threading=options.get('use_threading', True),
            )
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n\nShutting down...'))
            self.cleanup_redis()

    def is_redis_running(self):
        """Check if Redis is already running on localhost:6379."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 6379))
            sock.close()
            return result == 0
        except Exception:
            return False

    def start_redis(self):
        """Start Redis server as a background subprocess."""
        try:
            # Try to find redis-server in PATH
            redis_cmd = self.find_redis_command()
            if not redis_cmd:
                return False

            # Start Redis in background (daemonized)
            self.redis_process = subprocess.Popen(
                [redis_cmd, '--daemonize', 'yes'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Wait a moment for Redis to start
            import time
            time.sleep(0.5)

            # Verify it started
            return self.is_redis_running()

        except Exception as e:
            self.stderr.write(f'Error starting Redis: {e}')
            return False

    def find_redis_command(self):
        """Find the redis-server command."""
        # Common locations to check
        common_paths = [
            'redis-server',  # In PATH
            '/usr/local/bin/redis-server',  # Homebrew on macOS
            '/opt/homebrew/bin/redis-server',  # Homebrew on Apple Silicon
            '/usr/bin/redis-server',  # Linux
        ]

        for path in common_paths:
            try:
                # Check if command exists
                result = subprocess.run(
                    [path, '--version'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=2
                )
                if result.returncode == 0:
                    return path
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        return None

    def cleanup_redis(self):
        """Stop Redis subprocess if we started it."""
        if self.redis_process:
            try:
                # Try to shutdown Redis gracefully
                subprocess.run(['redis-cli', 'shutdown'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             timeout=2)
                self.stdout.write(self.style.SUCCESS('\n✓ Redis stopped'))
            except Exception:
                pass

    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.stdout.write(self.style.WARNING('\n\nReceived shutdown signal...'))
        self.cleanup_redis()
        sys.exit(0)
