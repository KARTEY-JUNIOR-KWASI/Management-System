#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "🚀 Starting Intelligence Nexus Render Build Protocol..."

# Signal build phase to settings.py
export IS_BUILD_PHASE=True

# Install dependencies
echo "📦 Installing internal dependencies..."
pip install -r requirements.txt

# Apply migrations (Only if database is linked)
if [ -n "$DATABASE_URL" ]; then
  echo "📡 Synchronizing database schemas..."
  python manage.py migrate
else
  echo "⚠️ Skipping database synchronization: DATABASE_URL not detected."
fi

# Collect static files
echo "🎨 Collecting institutional static assets..."
python manage.py collectstatic --no-input

echo "✅ Render Build Protocol Completed Successfully."
