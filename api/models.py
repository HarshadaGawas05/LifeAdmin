from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional
import json

Base = declarative_base()


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

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "category": self.category,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "priority_score": self.priority_score,
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

