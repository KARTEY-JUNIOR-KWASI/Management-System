from .models import Notification, SchoolConfiguration

def school_config(request):
    """Injects institutional metadata globally."""
    config = SchoolConfiguration.get_config()
    return {'school_config': config}

def unread_notifications(request):
    if request.user.is_authenticated:
        from analytics.models import Notification as AnalyticsNotification
        # Use the Analytics Notification model for individual unread tracking
        unread = AnalyticsNotification.objects.filter(recipient=request.user, is_read=False).order_by('-created_at')
        return {
            'unread_notifications': unread[:5],  # Top 5 for dropdown
            'unread_notifications_count': unread.count()
        }
    return {}

def student_financial_status(request):
    """Injects a global debt marker for students to trigger the intelligent prompt."""
    if request.user.is_authenticated and request.user.role == 'student':
        from finance.models import Invoice
        from django.db.models import Sum
        debt = Invoice.objects.filter(
            student__user=request.user, 
            status__in=['unpaid', 'partial']
        ).aggregate(Sum('balance_due'))['balance_due__sum'] or 0
        return {
            'has_unpaid_fees': float(debt) > 0,
            'unpaid_fees_amount': debt
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
