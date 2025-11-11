#!/usr/bin/env bash
set -o errexit

# Ensure the data directory exists (mounted by Render)
if [ ! -d "/opt/render/project/data" ]; then
    echo "ERROR: Persistent disk not mounted at /opt/render/project/data"
    exit 1
fi

# Run migrations (disk is now available)
echo "Running database migrations..."
python manage.py migrate --noinput

# Load initial data if database is empty
echo "Loading initial data if needed..."
python manage.py load_initial_data

# Create superuser if none exists
echo "Creating superuser if needed..."
python manage.py create_superuser_if_none

# Start the application
echo "Starting Daphne server..."
exec daphne -b 0.0.0.0 -p $PORT mysite.asgi:application
