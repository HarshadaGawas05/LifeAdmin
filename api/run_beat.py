#!/usr/bin/env python3
"""
Script to run the Celery Beat scheduler
"""

from celery_app import celery
from celery_beat_schedule import beat_schedule, timezone

if __name__ == '__main__':
    celery.conf.beat_schedule = beat_schedule
    celery.conf.timezone = timezone
    celery.start()

