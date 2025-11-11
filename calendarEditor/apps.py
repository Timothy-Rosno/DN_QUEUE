from django.apps import AppConfig
import threading
import time
import os


class CalendareditorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "calendarEditor"
    temperature_thread_started = False

    def ready(self):
        """Called when Django starts - start background temperature updater."""
        # Only run in the main process (not in reloader or other processes)
        if os.environ.get('RUN_MAIN') != 'true':
            return

        # Prevent multiple threads from starting
        if CalendareditorConfig.temperature_thread_started:
            return

        CalendareditorConfig.temperature_thread_started = True

        # Start background thread
        thread = threading.Thread(target=self.update_temperatures_loop, daemon=True)
        thread.start()
        print("Temperature updater started in background")

    def update_temperatures_loop(self):
        """Background thread that continuously updates machine temperatures."""
        # Import here to avoid AppRegistryNotReady error
        from .models import Machine

        # Wait a bit for Django to fully start up
        time.sleep(2)

        while True:
            try:
                machines = Machine.objects.exclude(api_type='none')
                for machine in machines:
                    try:
                        machine.update_temperature_cache()
                    except Exception as e:
                        # Silently continue on error - don't crash the thread
                        pass

                # Wait 5 seconds before next update
                time.sleep(5)
            except Exception as e:
                # If database connection fails, wait and retry
                time.sleep(10)
