#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Run migrations (This fixes the 500 errors)
python manage.py migrate

# Collect static files (This fixes missing CSS/JS)
python manage.py collectstatic --no-input
