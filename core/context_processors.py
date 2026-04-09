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
    import os
    db_engine = settings.DATABASES['default']['ENGINE']
    is_render = os.getenv('RENDER', 'False').lower() == 'true'
    
    if 'postgresql' in db_engine:
        engine_type = 'PostgreSQL (Enterprise)'
        status_mode = 'stable'
    elif 'sqlite' in db_engine:
        engine_type = 'SQLite (Temporary Vault)'
        # If on Render and using SQLite, this is a CRITICAL risk
        status_mode = 'critical' if is_render else 'warning'
    else:
        engine_type = 'External Engine'
        status_mode = 'stable'
        
    return {
        'DATABASE_ENGINE_TYPE': engine_type,
        'IS_PERSISTENT': 'postgresql' in db_engine,
        'INFRASTRUCTURE_MODE': status_mode
    }
