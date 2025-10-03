#!/usr/bin/env python3
"""
Script to run the Celery worker
"""

from celery_app import celery

if __name__ == '__main__':
    celery.start()

