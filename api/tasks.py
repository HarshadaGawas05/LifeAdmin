"""
Celery background tasks for Gmail integration
Handles auto-sync, token refresh, and periodic maintenance
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from celery import Celery
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User, OAuthToken, GmailSyncState, RawEmail
from gmail_service import GmailService
from auth import GoogleOAuthManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import Celery instance
from celery_app import celery


def get_db_session() -> Session:
    """Get database session for background tasks"""
    return SessionLocal()


@celery.task(bind=True, max_retries=3)
def sync_user_emails(self, user_email: str, force_full_sync: bool = False, max_results: int = 100):
    """
    Sync emails for a specific user
    Handles both full and incremental sync using the new robust methods
    """
    db = get_db_session()
    try:
        logger.info(f"Starting email sync for user: {user_email}")
        
        # Check if user exists and has valid credentials
        oauth_manager = GoogleOAuthManager(db)
        if not oauth_manager.is_user_authenticated(user_email):
            logger.warning(f"User {user_email} not authenticated, skipping sync")
            return {
                "success": False,
                "message": "User not authenticated",
                "user_email": user_email
            }
        
        gmail_service = GmailService(db)
        
        if force_full_sync:
            # Perform full sync using the new method
            logger.info(f"Performing FULL sync for {user_email}")
            result = gmail_service.full_sync_user_emails(user_email, max_results)
            
            return {
                "success": result.get("success", False),
                "message": result.get("message", "Full sync completed"),
                "user_email": user_email,
                "emails_processed": result.get("total_processed", 0),
                "emails_stored": result.get("new_emails", 0),
                "deleted_emails": result.get("deleted_emails", 0),
                "gmail_emails": result.get("gmail_emails", 0)
            }
        
        else:
            # Perform incremental sync using the new method
            logger.info(f"Performing INCREMENTAL sync for {user_email}")
            result = gmail_service.incremental_sync_user_emails(user_email)
            
            return {
                "success": result.get("success", False),
                "message": result.get("message", "Incremental sync completed"),
                "user_email": user_email,
                "emails_processed": result.get("emails_processed", 0),
                "emails_stored": result.get("emails_stored", 0),
                "history_id": result.get("history_id")
            }
    
    except Exception as e:
        logger.error(f"Error syncing emails for {user_email}: {e}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries * 60  # 2, 4, 8 minutes
            logger.info(f"Retrying sync for {user_email} in {retry_delay} seconds")
            raise self.retry(countdown=retry_delay)
        
        return {
            "success": False,
            "message": f"Failed to sync emails for {user_email}: {str(e)}",
            "user_email": user_email,
            "error": str(e)
        }
    
    finally:
        db.close()


@celery.task
def sync_all_users_emails():
    """
    Sync emails for all authenticated users
    Runs every 5 minutes via Celery Beat
    """
    db = get_db_session()
    try:
        logger.info("Starting batch email sync for all users")
        
        # Get all users with valid Gmail credentials
        authenticated_users = db.query(User).join(OAuthToken).filter(
            OAuthToken.provider == 'google',
            OAuthToken.needs_reauth == False
        ).all()
        
        if not authenticated_users:
            logger.info("No authenticated users found for sync")
            return {
                "success": True,
                "message": "No users to sync",
                "total_users": 0,
                "successful_syncs": 0,
                "failed_syncs": 0
            }
        
        # Start sync tasks for each user
        task_results = []
        for user in authenticated_users:
            task = sync_user_emails.delay(user.email, force_full_sync=False)
            task_results.append({
                "user_email": user.email,
                "task_id": task.id
            })
        
        logger.info(f"Started sync tasks for {len(authenticated_users)} users")
        
        return {
            "success": True,
            "message": f"Started sync for {len(authenticated_users)} users",
            "total_users": len(authenticated_users),
            "task_results": task_results
        }
    
    except Exception as e:
        logger.error(f"Error starting batch sync: {e}")
        return {
            "success": False,
            "message": f"Failed to start batch sync: {str(e)}",
            "error": str(e)
        }
    
    finally:
        db.close()


@celery.task
def refresh_expired_tokens():
    """
    Refresh expired OAuth tokens for all users
    Runs every hour via Celery Beat
    """
    db = get_db_session()
    try:
        logger.info("Starting token refresh for all users")
        
        # Get all users with Google OAuth tokens
        oauth_tokens = db.query(OAuthToken).filter(
            OAuthToken.provider == 'google'
        ).all()
        
        refreshed_count = 0
        failed_count = 0
        
        for token in oauth_tokens:
            try:
                # Try to get valid credentials (this will refresh if needed)
                oauth_manager = GoogleOAuthManager(db)
                credentials = oauth_manager.get_valid_credentials(token.email_address)
                
                if credentials:
                    refreshed_count += 1
                    logger.info(f"Refreshed token for {token.email_address}")
                else:
                    failed_count += 1
                    logger.warning(f"Failed to refresh token for {token.email_address}")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Error refreshing token for {token.email_address}: {e}")
                continue
        
        logger.info(f"Token refresh completed: {refreshed_count} refreshed, {failed_count} failed")
        
        return {
            "success": True,
            "message": f"Token refresh completed: {refreshed_count} refreshed, {failed_count} failed",
            "refreshed_count": refreshed_count,
            "failed_count": failed_count
        }
    
    except Exception as e:
        logger.error(f"Error during token refresh: {e}")
        return {
            "success": False,
            "message": f"Token refresh failed: {str(e)}",
            "error": str(e)
        }
    
    finally:
        db.close()


@celery.task
def cleanup_old_emails(days_to_keep: int = 90):
    """
    Clean up old emails to manage database size
    Runs weekly via Celery Beat
    """
    db = get_db_session()
    try:
        logger.info(f"Starting cleanup of emails older than {days_to_keep} days")
        
        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Count emails to be deleted
        old_emails_count = db.query(RawEmail).filter(
            RawEmail.received_at < cutoff_date,
            RawEmail.is_deleted == True  # Only delete already marked as deleted
        ).count()
        
        if old_emails_count == 0:
            logger.info("No old emails to clean up")
            return {
                "success": True,
                "message": "No old emails to clean up",
                "deleted_count": 0
            }
        
        # Delete old deleted emails
        deleted_count = db.query(RawEmail).filter(
            RawEmail.received_at < cutoff_date,
            RawEmail.is_deleted == True
        ).delete()
        
        db.commit()
        
        logger.info(f"Cleaned up {deleted_count} old emails")
        
        return {
            "success": True,
            "message": f"Cleaned up {deleted_count} old emails",
            "deleted_count": deleted_count
        }
    
    except Exception as e:
        logger.error(f"Error during email cleanup: {e}")
        db.rollback()
        return {
            "success": False,
            "message": f"Email cleanup failed: {str(e)}",
            "error": str(e)
        }
    
    finally:
        db.close()


@celery.task
def health_check():
    """
    Perform health check on Gmail integration
    Runs every 15 minutes via Celery Beat
    """
    db = get_db_session()
    try:
        logger.info("Starting Gmail integration health check")
        
        # Check database connection
        db_status = True
        try:
            from sqlalchemy import text
            db.execute(text("SELECT 1"))
        except Exception as e:
            db_status = False
            logger.error(f"Database health check failed: {e}")
        
        # Check Redis connection
        redis_status = True
        try:
            from celery_app import celery
            celery.control.inspect().stats()
        except Exception as e:
            redis_status = False
            logger.error(f"Redis health check failed: {e}")
        
        # Check Gmail API access
        gmail_status = True
        try:
            # Test with a single user
            # Explicit select_from to avoid ambiguity in SQLAlchemy 2.x
            test_user = (
                db.query(User)
                .select_from(User)
                .join(OAuthToken, OAuthToken.email_address == User.email)
                .filter(
                    OAuthToken.provider == 'google',
                    OAuthToken.needs_reauth == False
                )
                ).first()
            
            if test_user:
                oauth_manager = GoogleOAuthManager(db)
                credentials = oauth_manager.get_valid_credentials(test_user.email)
                if not credentials:
                    gmail_status = False
                    logger.warning("Gmail API health check failed: no valid credentials")
        except Exception as e:
            gmail_status = False
            logger.error(f"Gmail API health check failed: {e}")
        
        overall_status = db_status and redis_status and gmail_status
        
        logger.info(f"Health check completed: DB={db_status}, Redis={redis_status}, Gmail={gmail_status}")
        
        return {
            "success": overall_status,
            "message": "Health check completed",
            "database": db_status,
            "redis": redis_status,
            "gmail_api": gmail_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "message": f"Health check failed: {str(e)}",
            "error": str(e)
        }
    
    finally:
        db.close()


@celery.task
def process_email_classification():
    """
    Process pending email classifications
    Runs every 30 minutes via Celery Beat
    """
    db = get_db_session()
    try:
        logger.info("Starting email classification processing")
        
        # Get pending emails for classification
        pending_emails = db.query(RawEmail).filter(
            RawEmail.llm_status == 'pending'
        ).limit(50).all()
        
        if not pending_emails:
            logger.info("No pending emails for classification")
            return {
                "success": True,
                "message": "No pending emails for classification",
                "processed_count": 0
            }
        
        processed_count = 0
        error_count = 0
        
        for email in pending_emails:
            try:
                # Here you would integrate with your LLM classification service
                # For now, we'll just mark as processed
                email.llm_status = 'classified'
                email.llm_processed_at = datetime.utcnow()
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error classifying email {email.id}: {e}")
                email.llm_status = 'failed'
                email.llm_error = str(e)
                error_count += 1
                continue
        
        db.commit()
        
        logger.info(f"Email classification completed: {processed_count} processed, {error_count} errors")
        
        return {
            "success": True,
            "message": f"Email classification completed: {processed_count} processed, {error_count} errors",
            "processed_count": processed_count,
            "error_count": error_count
        }
    
    except Exception as e:
        logger.error(f"Email classification failed: {e}")
        db.rollback()
        return {
            "success": False,
            "message": f"Email classification failed: {str(e)}",
            "error": str(e)
        }
    
    finally:
        db.close()


@celery.task
def sync_deleted_emails_all_users():
    """
    Check for deleted emails for all authenticated users
    Runs every 10 minutes via Celery Beat
    """
    db = get_db_session()
    try:
        logger.info("Starting deleted emails sync for all users")
        
        # Get all users with valid Gmail credentials
        authenticated_users = db.query(User).join(OAuthToken).filter(
            OAuthToken.provider == 'google',
            OAuthToken.needs_reauth == False
        ).all()
        
        if not authenticated_users:
            logger.info("No authenticated users found for deleted emails sync")
            return {
                "success": True,
                "message": "No users to sync",
                "total_users": 0,
                "total_deleted": 0
            }
        
        total_deleted = 0
        successful_users = 0
        failed_users = 0
        
        for user in authenticated_users:
            try:
                gmail_service = GmailService(db)
                result = gmail_service.sync_deleted_emails(user.email)
                
                if result.get("errors", 0) == 0:
                    successful_users += 1
                    total_deleted += result.get("deleted", 0)
                    logger.info(f"Successfully synced deleted emails for {user.email}: {result.get('deleted', 0)} deleted")
                else:
                    failed_users += 1
                    logger.warning(f"Failed to sync deleted emails for {user.email}: {result.get('errors', 0)} errors")
                
            except Exception as e:
                failed_users += 1
                logger.error(f"Error syncing deleted emails for {user.email}: {e}")
                continue
        
        logger.info(f"Deleted emails sync completed: {successful_users} successful, {failed_users} failed, {total_deleted} total deleted")
        
        return {
            "success": True,
            "message": f"Deleted emails sync completed: {successful_users} successful, {failed_users} failed",
            "total_users": len(authenticated_users),
            "successful_users": successful_users,
            "failed_users": failed_users,
            "total_deleted": total_deleted
        }
    
    except Exception as e:
        logger.error(f"Deleted emails sync failed: {e}")
        return {
            "success": False,
            "message": f"Deleted emails sync failed: {str(e)}",
            "error": str(e)
        }
    
    finally:
        db.close()
