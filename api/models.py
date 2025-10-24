from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON, UniqueConstraint, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional
import json
import enum

Base = declarative_base()


class LLMStatus(enum.Enum):
    """Enum for LLM processing status"""
    PENDING = "pending"
    CLASSIFIED = "classified"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    picture = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
        }

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    merchant = Column(String(255), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    description = Column(Text)
    source = Column(String(255), nullable=False)  # "upload", "gmail", "mock"
    source_details = Column(Text)  # Additional source information
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationship to recurring subscriptions
    recurring_subscription_id = Column(Integer, ForeignKey("recurring_subscriptions.id"), nullable=True)
    recurring_subscription = relationship("RecurringSubscription", back_populates="transactions")


class RecurringSubscription(Base):
    __tablename__ = "recurring_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    merchant = Column(String(255), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    interval_days = Column(Integer, nullable=False)  # Median interval in days
    last_paid_date = Column(DateTime, nullable=False)
    next_due_date = Column(DateTime, nullable=False)
    confidence_score = Column(Float, nullable=False)  # 0.0 to 1.0
    source_transparency = Column(Text, nullable=False)  # Human-readable source info
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationship to transactions
    transactions = relationship("Transaction", back_populates="recurring_subscription")

    def to_dict(self):
        return {
            "id": self.id,
            "merchant": self.merchant,
            "amount": self.amount,
            "interval": f"{self.interval_days} days",
            "last_paid_date": self.last_paid_date.isoformat(),
            "next_due_date": self.next_due_date.isoformat(),
            "confidence_score": self.confidence_score,
            "source": self.source_transparency,
            "is_active": self.is_active
        }


class Task(Base):
    """Unified model for tasks, subscriptions, bills, and assignments"""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    name = Column(String(255), nullable=False, index=True)
    amount = Column(Float, nullable=True)  # Optional for non-financial tasks
    category = Column(String(100), nullable=False)  # "bill", "subscription", "assignment", "job_application"
    due_date = Column(DateTime, nullable=True)
    priority_score = Column(Float, default=0.0)  # 0.0 to 1.0 based on urgency
    confidence_score = Column(Float, default=0.0)  # 0.0 to 1.0 based on recurrence
    source = Column(String(255), nullable=False)  # "gmail", "upload", "mock"
    source_details = Column(JSON)  # Store parsed email data, receipt info, etc.
    is_active = Column(Boolean, default=True)
    is_recurring = Column(Boolean, default=False)
    interval_days = Column(Integer, nullable=True)  # For recurring tasks
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User")

    def to_dict(self):
        # Compute priority level based on due_date
        priority_level = None
        if self.due_date:
            days = (self.due_date - datetime.utcnow()).days
            if days <= 1:
                priority_level = "High"
            elif days <= 3:
                priority_level = "Medium"
            else:
                priority_level = "Low"

        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "category": self.category,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "priority_score": self.priority_score,
            "priority_level": priority_level,
            "confidence_score": self.confidence_score,
            "source": self.source,
            "source_details": self.source_details,
            "is_active": self.is_active,
            "is_recurring": self.is_recurring,
            "interval_days": self.interval_days
        }


class GmailToken(Base):
    """Store encrypted Gmail OAuth tokens"""
    __tablename__ = "gmail_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), nullable=False, unique=True, index=True)
    encrypted_token = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class OAuthToken(Base):
    """Generic OAuth token storage (encrypted refresh token)"""
    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True)
    provider = Column(String(50), index=True)  # e.g., 'google'
    user_id = Column(String(255), index=True)
    email_address = Column(String(255), index=True)
    access_token = Column(Text, nullable=True)
    encrypted_refresh_token = Column(Text, nullable=False)
    token_expiry = Column(DateTime, nullable=True)
    scope = Column(Text, nullable=True)
    needs_reauth = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint('provider', 'user_id', name='uq_provider_user'),
    )


class RawEmail(Base):
    """Stores raw Gmail message metadata/snippet for auditing and source display"""
    __tablename__ = "raw_emails"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    message_id = Column(String(255), nullable=False, unique=True, index=True)  # Gmail message id
    thread_id = Column(String(255), nullable=True, index=True)
    history_id = Column(String(255), nullable=True, index=True)  # Gmail history ID
    subject = Column(String(1024), nullable=True)
    sender = Column(String(512), nullable=True)
    recipient = Column(String(512), nullable=True)  # Added recipient field
    received_at = Column(DateTime, nullable=True)  # Renamed from sent_at
    body = Column(Text, nullable=True)  # Added body field
    snippet = Column(Text, nullable=True)
    raw_payload = Column(JSON, nullable=True)
    is_deleted = Column(Boolean, default=False, index=True)  # Track deleted emails
    
    # LLM Classification Fields
    category = Column(String(100), nullable=True, index=True)  # Job Application, Subscription, etc.
    priority = Column(String(20), nullable=True, index=True)   # High, Medium, Low
    summary = Column(Text, nullable=True)                      # AI-generated summary
    llm_status = Column(Enum(LLMStatus), default=LLMStatus.PENDING, index=True)
    llm_processed_at = Column(DateTime, nullable=True)
    llm_error = Column(Text, nullable=True)                    # Store error details if classification fails
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User")

    def to_dict(self):
        """Convert RawEmail to dictionary for API responses"""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            "history_id": self.history_id,
            "subject": self.subject,
            "sender": self.sender,
            "recipient": self.recipient,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "body": self.body,
            "snippet": self.snippet,
            "is_deleted": self.is_deleted,
            "category": self.category,
            "priority": self.priority,
            "summary": self.summary,
            "llm_status": self.llm_status.value if self.llm_status else None,
            "llm_processed_at": self.llm_processed_at.isoformat() if self.llm_processed_at else None,
            "llm_error": self.llm_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ParsedEvent(Base):
    """Parsed signals extracted from raw emails to power tasks and detection"""
    __tablename__ = "parsed_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    name = Column(String(255), nullable=False, index=True)
    amount = Column(Float, nullable=True)
    currency = Column(String(8), nullable=True)
    due_date = Column(DateTime, nullable=True)
    category = Column(String(100), nullable=True)
    confidence = Column(Float, default=0.0)
    source = Column(String(50), default='gmail', nullable=False)
    raw_email_id = Column(Integer, ForeignKey("raw_emails.id"), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    raw_email = relationship("RawEmail")
    user = relationship("User")


class Action(Base):
    """Stores user actions taken on tasks (cancel, snooze, autopay)"""
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), index=True)
    action = Column(String(50), nullable=False)  # cancel|snooze|autopay
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    task = relationship("Task")


class ClassificationLog(Base):
    """Logs classification attempts and errors for debugging"""
    __tablename__ = "classification_logs"

    id = Column(Integer, primary_key=True)
    email_id = Column(Integer, ForeignKey("raw_emails.id"), index=True, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    subject = Column(String(1024), nullable=True)
    body_snippet = Column(Text, nullable=True)
    status = Column(String(20), nullable=False)  # success, failed, retry
    error_message = Column(Text, nullable=True)
    response_data = Column(JSON, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())

    email = relationship("RawEmail")
    user = relationship("User")


class GmailSyncState(Base):
    """Tracks Gmail sync state for incremental updates"""
    __tablename__ = "gmail_sync_state"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    last_history_id = Column(String(255), nullable=True)  # Gmail history ID for incremental sync
    last_synced_at = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User")

