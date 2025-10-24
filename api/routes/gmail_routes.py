"""
Gmail integration API routes
Handles OAuth, sync, and email management endpoints
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models import User, RawEmail, GmailSyncState
from auth import GoogleOAuthManager
from gmail_service import GmailService
from schemas import (
    AuthResponse, SyncResponse, EmailListResponse, SyncStateResponse,
    SearchRequest, PaginationRequest, SyncRequest, HealthResponse,
    EmailSearchResponse, GmailStatsResponse, ErrorResponse
)
from tasks import sync_user_emails, health_check

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gmail", tags=["Gmail Integration"])


@router.get("/auth/url", response_model=AuthResponse)
async def get_auth_url():
    """
    Get Google OAuth2 authorization URL
    Redirects user to Google consent page
    """
    try:
        # Create a temporary OAuth manager to get the URL
        from database import SessionLocal
        db = SessionLocal()
        try:
            oauth_manager = GoogleOAuthManager(db)
            auth_url = oauth_manager.get_authorization_url()
            
            return AuthResponse(
                success=True,
                message="Authorization URL generated successfully",
                auth_url=auth_url
            )
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error generating auth URL: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate authorization URL: {str(e)}")


@router.get("/auth/callback", response_model=AuthResponse)
async def handle_auth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    db: Session = Depends(get_db)
):
    """
    Handle Google OAuth2 callback
    Exchange authorization code for tokens
    """
    try:
        oauth_manager = GoogleOAuthManager(db)
        result = oauth_manager.exchange_code_for_tokens(code)
        
        return AuthResponse(
            success=True,
            message="Authentication successful",
            user=result['user_info']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling auth callback: {e}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")


@router.post("/sync", response_model=SyncResponse)
async def sync_emails(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_email: str = Query(..., description="User email to sync")
):
    """
    Trigger manual Gmail sync for a user
    Supports both full and incremental sync
    """
    try:
        # Check if user is authenticated
        oauth_manager = GoogleOAuthManager(db)
        if not oauth_manager.is_user_authenticated(user_email):
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        # Start background sync task
        task = sync_user_emails.delay(
            user_email, 
            force_full_sync=request.force_full_sync,
            max_results=request.max_results
        )
        
        return SyncResponse(
            success=True,
            message=f"Sync started for {user_email}",
            emails_processed=0,  # Will be updated by background task
            emails_stored=0,
            errors=0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting sync for {user_email}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start sync: {str(e)}")


@router.post("/sync/deleted", response_model=SyncResponse)
async def sync_deleted_emails_endpoint(
    user_email: str = Query(..., description="User email"),
    force_full_sync: bool = Query(False, description="Force full sync instead of incremental"),
    max_results: int = Query(1000, ge=1, le=5000, description="Maximum emails to process"),
    db: Session = Depends(get_db)
):
    """
    Comprehensive Gmail sync endpoint:
    - force_full_sync=true: Full sync (fetch all emails, mark missing as deleted)
    - force_full_sync=false: Incremental sync (use History API)
    """
    try:
        # Check if user is authenticated
        oauth_manager = GoogleOAuthManager(db)
        if not oauth_manager.is_user_authenticated(user_email):
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        gmail_service = GmailService(db)
        
        if force_full_sync:
            # Perform full sync
            result = gmail_service.full_sync_user_emails(user_email, max_results)
        else:
            # Perform incremental sync
            result = gmail_service.incremental_sync_user_emails(user_email)
        
        if result.get("success", False):
            return SyncResponse(
                success=True,
                message=result.get("message", "Sync completed"),
                emails_processed=result.get("emails_processed", result.get("total_processed", 0)),
                emails_stored=result.get("emails_stored", result.get("new_emails", 0)),
                errors=0
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "Sync failed"))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing emails for {user_email}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync emails: {str(e)}")


@router.get("/emails", response_model=EmailListResponse)
async def get_emails(
    user_email: str = Query(..., description="User email"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Number of emails per page"),
    db: Session = Depends(get_db)
):
    """
    Get user's emails from database with pagination
    """
    try:
        # Check if user is authenticated
        oauth_manager = GoogleOAuthManager(db)
        if not oauth_manager.is_user_authenticated(user_email):
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        gmail_service = GmailService(db)
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get emails
        emails = gmail_service.get_user_emails(user_email, limit=page_size, offset=offset)
        
        # Get total count
        user = db.query(User).filter(User.email == user_email).first()
        total_count = db.query(RawEmail).filter(
            RawEmail.user_id == user.id,
            RawEmail.is_deleted == False
        ).count()
        
        return EmailListResponse(
            emails=emails,
            total=total_count,
            page=page,
            page_size=page_size,
            has_more=(offset + page_size) < total_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting emails for {user_email}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get emails: {str(e)}")


@router.post("/search", response_model=EmailSearchResponse)
async def search_emails(
    request: SearchRequest,
    user_email: str = Query(..., description="User email"),
    db: Session = Depends(get_db)
):
    """
    Search emails using Gmail API
    """
    try:
        # Check if user is authenticated
        oauth_manager = GoogleOAuthManager(db)
        if not oauth_manager.is_user_authenticated(user_email):
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        gmail_service = GmailService(db)
        
        # Search emails
        emails = gmail_service.search_emails(user_email, request.query, request.limit)
        
        return EmailSearchResponse(
            emails=emails,
            query=request.query,
            total_found=len(emails)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching emails for {user_email}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search emails: {str(e)}")


@router.get("/sync-state", response_model=SyncStateResponse)
async def get_sync_state(
    user_email: str = Query(..., description="User email"),
    db: Session = Depends(get_db)
):
    """
    Get Gmail sync state for a user
    """
    try:
        # Check if user is authenticated
        oauth_manager = GoogleOAuthManager(db)
        if not oauth_manager.is_user_authenticated(user_email):
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        gmail_service = GmailService(db)
        sync_state = gmail_service.get_sync_state(user_email)
        
        if sync_state:
            return SyncStateResponse(**sync_state)
        else:
            return SyncStateResponse()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sync state for {user_email}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sync state: {str(e)}")


@router.get("/stats", response_model=GmailStatsResponse)
async def get_gmail_stats(
    user_email: str = Query(..., description="User email"),
    db: Session = Depends(get_db)
):
    """
    Get Gmail statistics for a user
    """
    try:
        # Check if user is authenticated
        oauth_manager = GoogleOAuthManager(db)
        if not oauth_manager.is_user_authenticated(user_email):
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get email counts
        total_emails = db.query(RawEmail).filter(RawEmail.user_id == user.id).count()
        unread_emails = db.query(RawEmail).filter(
            RawEmail.user_id == user.id,
            RawEmail.is_deleted == False
        ).count()
        deleted_emails = db.query(RawEmail).filter(
            RawEmail.user_id == user.id,
            RawEmail.is_deleted == True
        ).count()
        
        # Get last sync time
        sync_state = db.query(GmailSyncState).filter(
            GmailSyncState.user_id == user.id
        ).first()
        
        last_sync = sync_state.last_synced_at if sync_state else None
        sync_status = "active" if sync_state else "never_synced"
        
        return GmailStatsResponse(
            total_emails=total_emails,
            unread_emails=unread_emails,
            deleted_emails=deleted_emails,
            last_sync=last_sync,
            sync_status=sync_status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stats for {user_email}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.delete("/auth/revoke")
async def revoke_auth(
    user_email: str = Query(..., description="User email"),
    db: Session = Depends(get_db)
):
    """
    Revoke Gmail authentication for a user
    """
    try:
        oauth_manager = GoogleOAuthManager(db)
        success = oauth_manager.revoke_tokens(user_email)
        
        if success:
            return {"success": True, "message": f"Authentication revoked for {user_email}"}
        else:
            raise HTTPException(status_code=404, detail="No authentication found for user")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking auth for {user_email}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to revoke authentication: {str(e)}")


@router.get("/health", response_model=HealthResponse)
async def gmail_health_check():
    """
    Check Gmail integration health
    """
    try:
        # Run health check task
        task = health_check.delay()
        result = task.get(timeout=30)  # 30 second timeout
        
        return HealthResponse(
            status="healthy" if result.get("success") else "unhealthy",
            timestamp=datetime.utcnow(),
            database=result.get("database", False),
            redis=result.get("redis", False),
            gmail_api=result.get("gmail_api", False)
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            database=False,
            redis=False,
            gmail_api=False
        )


@router.post("/sync/all")
async def sync_all_users(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Trigger sync for all authenticated users
    """
    try:
        from tasks import sync_all_users_emails
        
        # Start background task
        task = sync_all_users_emails.delay()
        
        return {
            "success": True,
            "message": "Batch sync started for all users",
            "task_id": task.id
        }
        
    except Exception as e:
        logger.error(f"Error starting batch sync: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start batch sync: {str(e)}")




@router.get("/emails/{email_id}")
async def get_email_details(
    email_id: str,
    user_email: str = Query(..., description="User email"),
    db: Session = Depends(get_db)
):
    """
    Get detailed information for a specific email
    """
    try:
        # Check if user is authenticated
        oauth_manager = GoogleOAuthManager(db)
        if not oauth_manager.is_user_authenticated(user_email):
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get email
        email = db.query(RawEmail).filter(
            RawEmail.message_id == email_id,
            RawEmail.user_id == user.id
        ).first()
        
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        return email.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting email details for {email_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get email details: {str(e)}")
