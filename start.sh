#!/usr/bin/env bash
set -o errexit

# Create data directory if it doesn't exist
# Note: On Render with persistent disk, this will be the mount point
# On first deploy without disk, we'll create it locally (not persistent)
if [ ! -d "/opt/render/project/data" ]; then
    echo "Creating data directory at /opt/render/project/data"
    mkdir -p /opt/render/project/data
    echo "⚠️  WARNING: Persistent disk not detected. Database will not persist across deployments."
    echo "⚠️  Add a persistent disk in Render dashboard: Settings → Disks → Add Disk"
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
