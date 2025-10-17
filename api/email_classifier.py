"""
Email Classification Service using Google Gemini 1.5 Flash
Handles email categorization, priority scoring, and summary generation
"""

import os
import json
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

import google.generativeai as genai
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models import RawEmail, LLMStatus, ClassificationLog

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmailCategory(str, Enum):
    """Email categories for classification"""
    JOB_APPLICATION = "Job Application"
    SUBSCRIPTION = "Subscription"
    RENEWAL = "Renewal"
    BILL = "Bill"
    REMINDER = "Reminder"
    OFFER = "Offer"
    SPAM = "Spam"
    OTHER = "Other"


class EmailPriority(str, Enum):
    """Email priority levels"""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class EmailClassificationRequest(BaseModel):
    """Request model for email classification"""
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Email body content")


class EmailClassificationResponse(BaseModel):
    """Response model for email classification"""
    category: EmailCategory = Field(..., description="Email category")
    priority: EmailPriority = Field(..., description="Email priority level")
    summary: str = Field(..., description="Concise summary of the email")


class EmailClassifier:
    """Email classification service using Gemini 1.5 Flash"""
    
    def __init__(self):
        """Initialize the classifier with Gemini API"""
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def classify_email(self, subject: str, body: str, db: Session = None, email_id: int = None, user_id: int = None) -> EmailClassificationResponse:
        """
        Classify an email using Gemini 1.5 Flash
        
        Args:
            subject: Email subject line
            body: Email body content
            db: Database session for logging (optional)
            email_id: Email ID for logging (optional)
            user_id: User ID for logging (optional)
            
        Returns:
            EmailClassificationResponse with category, priority, and summary
            
        Raises:
            Exception: If classification fails
        """
        start_time = time.time()
        
        try:
            # Prepare the structured prompt
            system_instruction = (
                "You are an expert email sorter for a productivity application. "
                "Analyze the subject and body of the following email. Strictly adhere to the provided JSON schema for your response."
            )

            response = self.model.generate_content(
                [
                    system_instruction,
                    {
                        "role": "user",
                        "parts": [
                            f"Subject: {subject[:500]}",
                            f"Body: {body[:4000]}"
                        ]
                    }
                ],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=256,
                    response_mime_type="application/json",
                    response_schema=EmailClassificationResponse
                )
            )

            # The SDK returns structured JSON directly
            payload = response.text
            data = json.loads(payload)
            result = EmailClassificationResponse(**data)
            
            # Log successful classification
            if db:
                self._log_classification(
                    db, email_id, user_id, subject, body[:200],
                    "success", None, result.model_dump(), 
                    int((time.time() - start_time) * 1000)
                )
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            result = self._create_fallback_response(subject)
            
            # Log error
            if db:
                self._log_classification(
                    db, email_id, user_id, subject, body[:200],
                    "failed", f"JSON decode error: {str(e)}", None,
                    int((time.time() - start_time) * 1000)
                )
            
            return result
        except Exception as e:
            logger.error(f"Classification error: {e}")
            result = self._create_fallback_response(subject)
            
            # Log error
            if db:
                self._log_classification(
                    db, email_id, user_id, subject, body[:200],
                    "failed", f"Classification error: {str(e)}", None,
                    int((time.time() - start_time) * 1000)
                )
            
            return result
    
    # Legacy JSON extraction helpers removed due to structured output usage
    
    def _create_fallback_response(self, subject: str) -> EmailClassificationResponse:
        """Create a fallback response when classification fails"""
        return EmailClassificationResponse(
            category=EmailCategory.OTHER,
            priority=EmailPriority.LOW,
            summary=subject[:100]  # Use subject as summary
        )
    
    def _log_classification(self, db: Session, email_id: int, user_id: int, subject: str, 
                          body_snippet: str, status: str, error_message: str, 
                          response_data: Dict, processing_time_ms: int):
        """Log classification attempt to database"""
        try:
            log_entry = ClassificationLog(
                email_id=email_id,
                user_id=user_id,
                subject=subject,
                body_snippet=body_snippet,
                status=status,
                error_message=error_message,
                response_data=response_data,
                processing_time_ms=processing_time_ms
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log classification: {e}")
            # Don't raise the exception to avoid breaking the main classification process
    
    def classify_and_store(self, db: Session, raw_email: RawEmail) -> bool:
        """
        Classify an email and store the results in the database
        
        Args:
            db: Database session
            raw_email: RawEmail record to classify
            
        Returns:
            bool: True if classification was successful, False otherwise
        """
        try:
            # Skip if already classified
            if raw_email.llm_status == LLMStatus.CLASSIFIED:
                return True
            
            # Get email content
            subject = raw_email.subject or ""
            body = raw_email.snippet or ""
            
            # Classify the email
            classification = self.classify_email(
                subject, body, db, raw_email.id, raw_email.user_id
            )
            
            # Update the raw email record
            raw_email.category = classification.category.value
            raw_email.priority = classification.priority.value
            raw_email.summary = classification.summary
            raw_email.llm_status = LLMStatus.CLASSIFIED
            raw_email.llm_processed_at = datetime.utcnow()
            raw_email.llm_error = None
            
            # Commit changes
            db.commit()
            
            logger.info(f"Successfully classified email {raw_email.id}: {classification.category.value}")
            return True
            
        except Exception as e:
            # Retry once
            logger.warning(f"Classification failed for email {raw_email.id}, retrying once: {e}")
            try:
                classification = self.classify_email(
                    raw_email.subject or "",
                    raw_email.snippet or "",
                    db,
                    raw_email.id,
                    raw_email.user_id,
                )
                raw_email.category = classification.category.value
                raw_email.priority = classification.priority.value
                raw_email.summary = classification.summary
                raw_email.llm_status = LLMStatus.CLASSIFIED
                raw_email.llm_processed_at = datetime.utcnow()
                raw_email.llm_error = None
                db.commit()
                logger.info(f"Successfully classified on retry {raw_email.id}")
                return True
            except Exception as e2:
                # Mark as failed after retry
                raw_email.llm_status = LLMStatus.FAILED
                raw_email.llm_processed_at = datetime.utcnow()
                raw_email.llm_error = str(e2)
                db.commit()
                logger.error(f"Failed to classify email {raw_email.id} after retry: {e2}")
                return False
    
    def batch_classify_pending_emails(self, db: Session, limit: int = 50) -> Dict[str, int]:
        """
        Classify all pending emails in batches
        
        Args:
            db: Database session
            limit: Maximum number of emails to process
            
        Returns:
            Dict with counts of processed, successful, and failed classifications
        """
        # Get pending emails
        pending_emails = db.query(RawEmail).filter(
            RawEmail.llm_status == LLMStatus.PENDING
        ).limit(limit).all()
        
        processed = 0
        successful = 0
        failed = 0
        
        for email in pending_emails:
            processed += 1
            if self.classify_and_store(db, email):
                successful += 1
            else:
                failed += 1
        
        logger.info(f"Batch classification completed: {processed} processed, {successful} successful, {failed} failed")
        
        return {
            "processed": processed,
            "successful": successful,
            "failed": failed
        }
