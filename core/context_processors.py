from .models import Notification, SchoolConfiguration

def school_config(request):
    """Injects institutional metadata globally."""
    config = SchoolConfiguration.get_config()
    return {'school_config': config}

def unread_notifications(request):
    if request.user.is_authenticated:
        # Get notifications where user is in recipients and is_read is False
        # Since is_read is on the Notification, we'll just check that.
        unread = Notification.objects.filter(recipients=request.user, is_read=False).order_by('-created_at')
        return {
            'unread_notifications': unread[:5],  # Top 5 for dropdown
            'unread_notifications_count': unread.count()
        }
    return {}

def infrastructure_status(request):
    """Identifies the active institutional infrastructure for the dashboard."""
    from django.conf import settings
    db_engine = settings.DATABASES['default']['ENGINE']
    
    if 'postgresql' in db_engine:
        engine_type = 'PostgreSQL (Enterprise)'
    elif 'sqlite' in db_engine:
        engine_type = 'SQLite (Local/Ephemeral)'
    else:
        engine_type = 'External Engine'
        
    return {
        'DATABASE_ENGINE_TYPE': engine_type,
        'IS_PERSISTENT': 'postgresql' in db_engine
    }
