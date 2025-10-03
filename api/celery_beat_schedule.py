"""
Celery Beat configuration for periodic tasks
"""

from celery.schedules import crontab

# Celery Beat schedule configuration
beat_schedule = {
    'detect-recurring-subscriptions': {
        'task': 'main.periodic_recurrence_detection',
        'schedule': 60.0,  # Run every 60 seconds for demo
        # In production, you might want to run this less frequently:
        # 'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
}

# Timezone for scheduled tasks
timezone = 'UTC'

