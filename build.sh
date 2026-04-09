# Exit on error
set -o errexit

echo "🚀 Starting Intelligence Nexus Build Protocol..."

# Signal build phase to settings.py (Suppresses production DB checks)
export IS_BUILD_PHASE=True

# Install dependencies
echo "📦 Installing internal dependencies..."
pip install -r requirements.txt

# Convert static assets
echo "🎨 Collecting institutional static assets..."
python manage.py collectstatic --no-input

# Apply any outstanding database migrations
echo "📡 Synchronizing database schemas..."
python manage.py migrate

# Create initial admin user if not exists
echo "🔑 Verifying administrative credentials..."
python create_admin.py

echo "✅ Build Protocol Completed Successfully."

