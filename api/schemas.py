"""
Pydantic schemas for Gmail integration API validation
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr


class UserResponse(BaseModel):
    """User information response"""
    id: int
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    created_at: datetime


class OAuthTokenResponse(BaseModel):
    """OAuth token information response"""
    provider: str
    email_address: str
    token_expiry: Optional[datetime] = None
    needs_reauth: bool = False


class EmailResponse(BaseModel):
    """Email data response"""
    id: int
    message_id: str
    thread_id: Optional[str] = None
    history_id: Optional[str] = None
    subject: Optional[str] = None
    sender: Optional[str] = None
    recipient: Optional[str] = None
    received_at: Optional[datetime] = None
    body: Optional[str] = None
    snippet: Optional[str] = None
    is_deleted: bool = False
    category: Optional[str] = None
    priority: Optional[str] = None
    summary: Optional[str] = None
    llm_status: Optional[str] = None
    llm_processed_at: Optional[datetime] = None
    llm_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class EmailListResponse(BaseModel):
    """Paginated email list response"""
    emails: List[EmailResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class SyncStateResponse(BaseModel):
    """Gmail sync state response"""
    last_history_id: Optional[str] = None
    last_synced_at: Optional[datetime] = None


class SyncResponse(BaseModel):
    """Email sync response"""
    success: bool
    message: str
    emails_processed: int
    emails_stored: int
    errors: int
    sync_state: Optional[SyncStateResponse] = None


class AuthResponse(BaseModel):
    """Authentication response"""
    success: bool
    message: str
    user: Optional[UserResponse] = None
    auth_url: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    database: bool = True
    redis: bool = True
    gmail_api: bool = True


class SearchRequest(BaseModel):
    """Email search request"""
    query: str = Field(..., description="Gmail search query")
    limit: int = Field(50, ge=1, le=100, description="Maximum number of results")


class PaginationRequest(BaseModel):
    """Pagination request"""
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=200, description="Number of items per page")


class SyncRequest(BaseModel):
    """Manual sync request"""
    force_full_sync: bool = Field(False, description="Force full sync instead of incremental")
    max_results: int = Field(100, ge=1, le=500, description="Maximum number of emails to sync")


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class GmailCredentials(BaseModel):
    """Gmail credentials for token exchange"""
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    scopes: List[str] = []


class UserInfo(BaseModel):
    """Google user information"""
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    verified_email: bool = False


class TokenExchangeResponse(BaseModel):
    """Token exchange response"""
    user_info: UserInfo
    credentials: GmailCredentials


class EmailSearchResponse(BaseModel):
    """Email search response"""
    emails: List[EmailResponse]
    query: str
    total_found: int
    search_time_ms: Optional[int] = None


class BatchSyncResponse(BaseModel):
    """Batch sync response for multiple users"""
    total_users: int
    successful_syncs: int
    failed_syncs: int
    results: List[Dict[str, Any]]


class GmailStatsResponse(BaseModel):
    """Gmail statistics response"""
    total_emails: int
    unread_emails: int
    deleted_emails: int
    last_sync: Optional[datetime] = None
    sync_status: str = "unknown"  # active, error, never_synced


class WebhookPayload(BaseModel):
    """Gmail push notification webhook payload"""
    message_id: str
    history_id: str
    user_id: str
    timestamp: datetime


class WebhookVerification(BaseModel):
    """Gmail webhook verification request"""
    challenge: str
    verification_token: str
