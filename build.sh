#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Convert static assets
python manage.py collectstatic --no-input

# Apply any outstanding database migrations
python manage.py migrate

# Create initial admin user if not exists
python create_admin.py

