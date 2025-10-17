"""
Email classification API routes
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import time
import logging

from database import get_db
from models import RawEmail, LLMStatus
from email_classifier import EmailClassifier, EmailClassificationRequest, EmailClassificationResponse
from celery_app import celery

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/emails", tags=["emails"])


@router.post("/classify", response_model=EmailClassificationResponse)
async def classify_email(
    request: EmailClassificationRequest,
    classifier: EmailClassifier = Depends(lambda: EmailClassifier())
):
    """
    Classify a single email using Gemini 1.5 Flash
    
    This endpoint accepts email subject and body, then returns:
    - Category (Job Application, Subscription, etc.)
    - Priority (High, Medium, Low)
    - Summary (concise description)
    """
    try:
        classification = classifier.classify_email(
            subject=request.subject,
            body=request.body
        )
        return classification
    except Exception as e:
        logger.error(f"Email classification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


# Root-level endpoint compatible with requirement: /classify_email
@router.post("/classify_email")
async def classify_email_simple(
    request: EmailClassificationRequest,
    db: Session = Depends(get_db),
    classifier: EmailClassifier = Depends(lambda: EmailClassifier()),
):
    """
    Classify an email payload and persist to the nearest matching RawEmail if found; otherwise create a minimal record.
    Returns the JSON classification output and sets llm_status accordingly.
    """
    try:
        # Try to find an unclassified RawEmail matching subject snippet
        email = (
            db.query(RawEmail)
            .filter(RawEmail.subject == request.subject)
            .first()
        )

        if not email:
            # Create minimal RawEmail record
            email = RawEmail(
                email_id=f"manual-{int(time.time())}",
                subject=request.subject,
                snippet=(request.body or "")[:500],
                llm_status=LLMStatus.PENDING,
            )
            db.add(email)
            db.commit()
            db.refresh(email)

        success = classifier.classify_and_store(db, email)
        if not success:
            raise HTTPException(status_code=500, detail="Classification failed")

        return {
            "category": email.category,
            "priority": email.priority,
            "summary": email.summary,
            "email_id": email.id,
            "status": email.llm_status.value,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Simple classify_email failed: {e}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


@router.get("/", response_model=List[Dict[str, Any]])
async def get_emails(
    category: str = None,
    priority: str = None,
    status: str = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Get emails with optional filtering by category, priority, and LLM status
    
    Returns emails grouped by category and sorted by priority
    """
    try:
        query = db.query(RawEmail)
        
        # Apply filters
        if category:
            query = query.filter(RawEmail.category == category)
        if priority:
            query = query.filter(RawEmail.priority == priority)
        if status:
            query = query.filter(RawEmail.llm_status == LLMStatus(status))
        
        # Order by category, then priority (High -> Medium -> Low)
        priority_order = {
            "High": 1,
            "Medium": 2,
            "Low": 3
        }
        
        emails = query.limit(limit).all()
        
        # Convert to dict and sort
        email_dicts = [email.to_dict() for email in emails]
        email_dicts.sort(key=lambda x: (
            x.get("category", "Other"),
            priority_order.get(x.get("priority", "Low"), 3)
        ))
        
        return email_dicts
        
    except Exception as e:
        logger.error(f"Failed to fetch emails: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch emails: {str(e)}")


@router.get("/categories")
async def get_email_categories(db: Session = Depends(get_db)):
    """
    Get all email categories with counts
    """
    try:
        from sqlalchemy import func
        
        # Get category counts
        category_counts = db.query(
            RawEmail.category,
            func.count(RawEmail.id).label('count')
        ).filter(
            RawEmail.llm_status == LLMStatus.CLASSIFIED
        ).group_by(RawEmail.category).all()
        
        return {
            "categories": [
                {
                    "name": category or "Unclassified",
                    "count": count
                }
                for category, count in category_counts
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch categories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch categories: {str(e)}")


@router.post("/classify-pending")
async def classify_pending_emails(
    background_tasks: BackgroundTasks,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Trigger background classification of pending emails
    
    This endpoint starts a background task to classify all emails
    with llm_status = 'pending'
    """
    try:
        # Add background task
        background_tasks.add_task(
            _classify_pending_emails_background,
            db,
            limit
        )
        
        return {
            "message": f"Started background classification of up to {limit} pending emails",
            "status": "started"
        }
        
    except Exception as e:
        logger.error(f"Failed to start classification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start classification: {str(e)}")


@router.post("/classify/{email_id}")
async def classify_specific_email(
    email_id: int,
    db: Session = Depends(get_db),
    classifier: EmailClassifier = Depends(lambda: EmailClassifier())
):
    """
    Classify a specific email by ID
    """
    try:
        # Get the email
        email = db.query(RawEmail).filter(RawEmail.id == email_id).first()
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Classify it
        success = classifier.classify_and_store(db, email)
        
        if success:
            return {
                "message": "Email classified successfully",
                "email_id": email_id,
                "category": email.category,
                "priority": email.priority,
                "summary": email.summary
            }
        else:
            raise HTTPException(status_code=500, detail="Classification failed")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to classify email {email_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


async def _classify_pending_emails_background(db: Session, limit: int):
    """
    Background task to classify pending emails using Celery
    """
    try:
        # Import the Celery task from main.py
        from main import classify_pending_emails
        
        # Trigger the Celery task
        task = classify_pending_emails.delay(limit)
        logger.info(f"Started Celery task {task.id} for classifying {limit} emails")
        
        return {"task_id": task.id, "status": "started"}
    except Exception as e:
        logger.error(f"Failed to start background classification: {e}")
        # Fallback to direct classification
        try:
            classifier = EmailClassifier()
            results = classifier.batch_classify_pending_emails(db, limit)
            logger.info(f"Direct classification completed: {results}")
            return results
        except Exception as e2:
            logger.error(f"Direct classification also failed: {e2}")
            raise e2
