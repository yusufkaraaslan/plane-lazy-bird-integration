#!/bin/bash
set -e

echo "Running Plane migrations..."
python manage.py migrate --noinput

echo "Running plane_lazy_bird migrations..."
python manage.py migrate plane_lazy_bird --noinput

echo "Starting Plane API server..."
exec python manage.py runserver 0.0.0.0:8000
