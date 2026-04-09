# exit on error
set -o errexit

# Signal build phase to settings.py
export IS_BUILD_PHASE=True

# Install dependencies
pip install -r requirements.txt

# Run migrations (This fixes the 500 errors)
python manage.py migrate

# Collect static files (This fixes missing CSS/JS)
python manage.py collectstatic --no-input
