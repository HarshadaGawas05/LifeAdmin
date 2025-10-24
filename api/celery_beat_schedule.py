"""
Celery Beat configuration for periodic tasks
"""

from celery.schedules import crontab

# Celery Beat schedule configuration
beat_schedule = {
    # Gmail integration tasks
    'sync-all-users-emails': {
        'task': 'tasks.sync_all_users_emails',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    
    'refresh-expired-tokens': {
        'task': 'tasks.refresh_expired_tokens',
        'schedule': crontab(minute=0),  # Every hour at minute 0
    },
    
    'gmail-health-check': {
        'task': 'tasks.health_check',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    
    'process-email-classification': {
        'task': 'tasks.process_email_classification',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    
    'sync-deleted-emails': {
        'task': 'tasks.sync_deleted_emails_all_users',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
    
    'cleanup-old-emails': {
        'task': 'tasks.cleanup_old_emails',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),  # Sunday at 2 AM
    },
    
    # Existing tasks
    'detect-recurring-subscriptions': {
        'task': 'main.periodic_recurrence_detection',
        'schedule': 60.0,  # Run every 60 seconds for demo
        # In production, you might want to run this less frequently:
        # 'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
}

# Timezone for scheduled tasks
timezone = 'UTC'

