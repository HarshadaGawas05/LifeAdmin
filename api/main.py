from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
from datetime import datetime, timedelta
import random
import json

from database import get_db, create_tables
from models import Transaction, RecurringSubscription, Task, GmailToken
from recurrence_detector import RecurrenceDetector
from enhanced_recurrence_detector import EnhancedRecurrenceDetector
from receipt_parser import ReceiptParser
from gmail_integration import GmailIntegration
from celery_app import celery

# Create database tables
create_tables()

app = FastAPI(
    title="LifeAdmin API",
    description="Life administration tool for managing recurring subscriptions",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize parsers and detectors
parser = ReceiptParser()
enhanced_detector = None  # Will be initialized with db session


@app.get("/")
async def root():
    return {"message": "LifeAdmin API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/seed/mock_subs")
async def seed_mock_subscriptions(db: Session = Depends(get_db)):
    """Seed database with mock recurring subscriptions"""
    
    # Clear existing mock data
    db.query(Transaction).filter(Transaction.source == "mock").delete()
    db.query(RecurringSubscription).delete()
    db.commit()
    
    # Create mock transactions for the last 3 months
    mock_transactions = [
        {
            "merchant": "Netflix",
            "amount": 499.0,
            "description": "Netflix subscription",
            "source": "mock",
            "source_details": "Mock data for demo"
        },
        {
            "merchant": "Spotify",
            "amount": 199.0,
            "description": "Spotify Premium subscription",
            "source": "mock",
            "source_details": "Mock data for demo"
        },
        {
            "merchant": "MSEB Electricity",
            "amount": 1200.0,
            "description": "Monthly electricity bill",
            "source": "mock",
            "source_details": "Mock data for demo"
        }
    ]
    
    # Create transactions for the last 3 months
    base_date = datetime.now() - timedelta(days=90)
    
    for transaction_data in mock_transactions:
        for month in range(3):
            transaction_date = base_date + timedelta(days=month * 30 + random.randint(-3, 3))
            
            transaction = Transaction(
                merchant=transaction_data["merchant"],
                amount=transaction_data["amount"],
                date=transaction_date,
                description=transaction_data["description"],
                source=transaction_data["source"],
                source_details=transaction_data["source_details"]
            )
            db.add(transaction)
    
    db.commit()
    
    # Run recurrence detection
    detector = RecurrenceDetector(db)
    detected_subscriptions = detector.detect_recurring_subscriptions()
    
    return {
        "message": f"Seeded {len(mock_transactions) * 3} mock transactions",
        "detected_subscriptions": len(detected_subscriptions)
    }


@app.post("/upload/receipt")
async def upload_receipt(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and parse a receipt file"""
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Read file content
    content = await file.read()
    
    # Parse based on file type
    if file.filename.endswith('.eml'):
        parsed_data = parser.parse_eml_file(content)
    else:
        # Assume text file
        text_content = content.decode('utf-8', errors='ignore')
        parsed_data = parser.parse_text_receipt(text_content)
    
    # Create transaction record
    transaction = Transaction(
        merchant=parsed_data.get("merchant", "Unknown Merchant"),
        amount=parsed_data.get("amount", 0.0),
        date=parsed_data.get("date", datetime.now()),
        description=f"Receipt from {file.filename}",
        source="upload",
        source_details=f"Uploaded file: {file.filename}"
    )
    
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    # Trigger recurrence detection in background
    detect_recurrence.delay()
    
    return {
        "message": "Receipt uploaded and parsed successfully",
        "transaction_id": transaction.id,
        "parsed_data": {
            "merchant": transaction.merchant,
            "amount": transaction.amount,
            "date": transaction.date.isoformat()
        }
    }


@app.get("/dashboard")
async def get_dashboard(db: Session = Depends(get_db)):
    """Get dashboard data with detected recurring subscriptions"""
    
    # Get all active recurring subscriptions
    subscriptions = db.query(RecurringSubscription).filter(
        RecurringSubscription.is_active == True
    ).all()
    
    # Calculate total monthly spend
    total_monthly_spend = sum(sub.amount for sub in subscriptions)
    
    # Convert to dict format
    subscriptions_data = [sub.to_dict() for sub in subscriptions]
    
    return {
        "total_monthly_spend": total_monthly_spend,
        "subscriptions": subscriptions_data,
        "count": len(subscriptions_data)
    }


@app.get("/transactions")
async def get_transactions(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get recent transactions"""
    
    transactions = db.query(Transaction).order_by(
        Transaction.date.desc()
    ).limit(limit).all()
    
    return [
        {
            "id": t.id,
            "merchant": t.merchant,
            "amount": t.amount,
            "date": t.date.isoformat(),
            "description": t.description,
            "source": t.source,
            "source_details": t.source_details
        }
        for t in transactions
    ]


@app.post("/subscriptions/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: int,
    db: Session = Depends(get_db)
):
    """Cancel a subscription (mock implementation)"""
    
    subscription = db.query(RecurringSubscription).filter(
        RecurringSubscription.id == subscription_id
    ).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    subscription.is_active = False
    db.commit()
    
    return {
        "message": "Cancel flow will be implemented — we will automate cancellation.",
        "subscription_id": subscription_id,
        "merchant": subscription.merchant
    }


@app.post("/subscriptions/{subscription_id}/snooze")
async def snooze_subscription(
    subscription_id: int,
    days: int = 7,
    db: Session = Depends(get_db)
):
    """Snooze a subscription (mock implementation)"""
    
    subscription = db.query(RecurringSubscription).filter(
        RecurringSubscription.id == subscription_id
    ).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Update next due date
    subscription.next_due_date = subscription.next_due_date + timedelta(days=days)
    db.commit()
    
    return {
        "message": f"Snooze flow will be implemented — we will remind you in {days} days.",
        "subscription_id": subscription_id,
        "merchant": subscription.merchant,
        "new_due_date": subscription.next_due_date.isoformat()
    }


@app.post("/subscriptions/{subscription_id}/auto-pay")
async def setup_auto_pay(
    subscription_id: int,
    db: Session = Depends(get_db)
):
    """Setup auto-pay for a subscription (mock implementation)"""
    
    subscription = db.query(RecurringSubscription).filter(
        RecurringSubscription.id == subscription_id
    ).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    return {
        "message": "Auto-pay flow will be implemented — we will set up automatic payments.",
        "subscription_id": subscription_id,
        "merchant": subscription.merchant
    }


# Celery task for background recurrence detection
@celery.task
def detect_recurrence():
    """Background task to detect recurring subscriptions"""
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        detector = RecurrenceDetector(db)
        detected_subscriptions = detector.detect_recurring_subscriptions()
        return f"Detected {len(detected_subscriptions)} recurring subscriptions"
    finally:
        db.close()


# Periodic task to run recurrence detection every minute (for demo)
@celery.task
def periodic_recurrence_detection():
    """Periodic task to detect recurring subscriptions"""
    return detect_recurrence.delay()


# ==================== NEW ENDPOINTS FOR MVP ====================

@app.get("/tasks")
async def get_tasks(
    category: Optional[str] = None,
    source: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """Get all tasks/subscriptions with filtering options"""
    
    query = db.query(Task)
    
    if active_only:
        query = query.filter(Task.is_active == True)
    
    if category:
        query = query.filter(Task.category == category)
    
    if source:
        query = query.filter(Task.source == source)
    
    tasks = query.order_by(Task.priority_score.desc(), Task.due_date.asc()).all()
    
    return {
        "tasks": [task.to_dict() for task in tasks],
        "count": len(tasks),
        "total_monthly_spend": sum(task.amount or 0 for task in tasks if task.amount)
    }


@app.post("/mock_tasks")
async def seed_mock_tasks(db: Session = Depends(get_db)):
    """Seed database with mock tasks/subscriptions for testing"""
    
    # Clear existing mock tasks
    db.query(Task).filter(Task.source == "mock").delete()
    db.commit()
    
    # Create mock tasks
    mock_tasks = [
        {
            "name": "Netflix Premium",
            "amount": 499.0,
            "category": "subscription",
            "due_date": datetime.now() + timedelta(days=5),
            "priority_score": 0.7,
            "confidence_score": 0.9,
            "source": "mock",
            "source_details": {
                "description": "Mock Netflix subscription",
                "interval_days": 30,
                "last_paid": "2024-01-01"
            },
            "is_recurring": True,
            "interval_days": 30
        },
        {
            "name": "Spotify Premium",
            "amount": 199.0,
            "category": "subscription",
            "due_date": datetime.now() + timedelta(days=12),
            "priority_score": 0.5,
            "confidence_score": 0.8,
            "source": "mock",
            "source_details": {
                "description": "Mock Spotify subscription",
                "interval_days": 30,
                "last_paid": "2024-01-01"
            },
            "is_recurring": True,
            "interval_days": 30
        },
        {
            "name": "PayTM Electricity Bill",
            "amount": 1200.0,
            "category": "bill",
            "due_date": datetime.now() + timedelta(days=3),
            "priority_score": 0.8,
            "confidence_score": 0.7,
            "source": "mock",
            "source_details": {
                "description": "Mock electricity bill",
                "interval_days": 30,
                "last_paid": "2024-01-01"
            },
            "is_recurring": True,
            "interval_days": 30
        },
        {
            "name": "Project Assignment",
            "amount": None,
            "category": "assignment",
            "due_date": datetime.now() + timedelta(days=7),
            "priority_score": 0.6,
            "confidence_score": 0.4,
            "source": "mock",
            "source_details": {
                "description": "Mock project assignment",
                "course": "CS101",
                "professor": "Dr. Smith"
            },
            "is_recurring": False
        },
        {
            "name": "Job Application - Google",
            "amount": None,
            "category": "job_application",
            "due_date": datetime.now() + timedelta(days=14),
            "priority_score": 0.4,
            "confidence_score": 0.3,
            "source": "mock",
            "source_details": {
                "description": "Mock job application",
                "company": "Google",
                "position": "Software Engineer"
            },
            "is_recurring": False
        }
    ]
    
    for task_data in mock_tasks:
        task = Task(**task_data)
        db.add(task)
    
    db.commit()
    
    return {
        "message": f"Seeded {len(mock_tasks)} mock tasks",
        "tasks_created": len(mock_tasks)
    }


@app.get("/gmail/auth")
async def gmail_auth(db: Session = Depends(get_db)):
    """Get Gmail OAuth authorization URL"""
    gmail = GmailIntegration(db)
    auth_url = gmail.get_oauth_url()
    
    return {
        "auth_url": auth_url,
        "message": "Visit this URL to authorize Gmail access"
    }


@app.post("/gmail/callback")
async def gmail_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Gmail OAuth callback"""
    try:
        # Get authorization code from request
        form_data = await request.form()
        code = form_data.get("code")
        
        if not code:
            raise HTTPException(status_code=400, detail="No authorization code provided")
        
        # Exchange code for credentials
        gmail = GmailIntegration(db)
        
        # For demo purposes, create mock credentials
        # In production, you would exchange the code for real credentials
        from google.oauth2.credentials import Credentials
        
        mock_credentials = Credentials(
            token="mock_token",
            refresh_token="mock_refresh_token",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="mock_client_id",
            client_secret="mock_client_secret",
            scopes=gmail.SCOPES
        )
        
        # Store credentials
        gmail.store_token("demo_user", mock_credentials)
        
        return {
            "message": "Gmail authorization successful",
            "status": "connected"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gmail authorization failed: {str(e)}")


@app.post("/gmail/fetch")
async def fetch_gmail_emails(
    user_id: str = "demo_user",
    max_results: int = 50,
    db: Session = Depends(get_db)
):
    """Fetch and parse emails from Gmail"""
    try:
        gmail = GmailIntegration(db)
        
        # For demo purposes, create mock email data
        mock_emails = [
            {
                "id": "mock_email_1",
                "subject": "Netflix Monthly Subscription - ₹499",
                "sender": "Netflix <billing@netflix.com>",
                "date": "2024-01-15T10:30:00Z",
                "body": "Your Netflix subscription has been renewed for ₹499. Next billing date: February 15, 2024."
            },
            {
                "id": "mock_email_2",
                "subject": "Spotify Premium Renewal",
                "sender": "Spotify <no-reply@spotify.com>",
                "date": "2024-01-10T14:20:00Z",
                "body": "Your Spotify Premium subscription has been renewed for ₹199. Thank you for being a premium member!"
            },
            {
                "id": "mock_email_3",
                "subject": "Electricity Bill Due - PayTM",
                "sender": "PayTM <bills@paytm.com>",
                "date": "2024-01-20T09:15:00Z",
                "body": "Your electricity bill of ₹1200 is due on January 25, 2024. Pay now to avoid late fees."
            },
            {
                "id": "mock_email_4",
                "subject": "CS101 Assignment Due Next Week",
                "sender": "Dr. Smith <smith@university.edu>",
                "date": "2024-01-18T16:45:00Z",
                "body": "Reminder: Your CS101 project assignment is due on January 25, 2024. Please submit via the online portal."
            },
            {
                "id": "mock_email_5",
                "subject": "Job Application Update - Google",
                "sender": "Google Careers <careers@google.com>",
                "date": "2024-01-22T11:30:00Z",
                "body": "Thank you for your application. We will review your materials and get back to you within 2 weeks."
            }
        ]
        
        # Parse emails into tasks
        tasks_created = 0
        for email_data in mock_emails:
            task = gmail.parse_email_to_task(email_data)
            if task:
                # Check if task already exists
                existing_task = db.query(Task).filter(
                    Task.name == task.name,
                    Task.source == "gmail"
                ).first()
                
                if not existing_task:
                    db.add(task)
                    tasks_created += 1
        
        db.commit()
        
        # Run recurrence detection
        enhanced_detector = EnhancedRecurrenceDetector(db)
        enhanced_detector.update_task_confidence_scores()
        
        return {
            "message": f"Fetched {len(mock_emails)} emails and created {tasks_created} new tasks",
            "emails_processed": len(mock_emails),
            "tasks_created": tasks_created
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gmail fetch failed: {str(e)}")


@app.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """Cancel a task (mock implementation)"""
    
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.is_active = False
    db.commit()
    
    return {
        "message": "Cancel flow will be implemented — we will automate cancellation.",
        "task_id": task_id,
        "task_name": task.name
    }


@app.post("/tasks/{task_id}/snooze")
async def snooze_task(
    task_id: int,
    days: int = 7,
    db: Session = Depends(get_db)
):
    """Snooze a task (mock implementation)"""
    
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update due date
    if task.due_date:
        task.due_date = task.due_date + timedelta(days=days)
    
    # Update priority score
    task.priority_score = max(0.1, task.priority_score - 0.2)
    
    db.commit()
    
    return {
        "message": f"Snooze flow will be implemented — we will remind you in {days} days.",
        "task_id": task_id,
        "task_name": task.name,
        "new_due_date": task.due_date.isoformat() if task.due_date else None
    }


@app.post("/tasks/{task_id}/auto-pay")
async def setup_auto_pay(
    task_id: int,
    db: Session = Depends(get_db)
):
    """Setup auto-pay for a task (mock implementation)"""
    
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "message": "Auto-pay flow will be implemented — we will set up automatic payments.",
        "task_id": task_id,
        "task_name": task.name
    }


@app.get("/recurrence/analyze")
async def analyze_recurrence(db: Session = Depends(get_db)):
    """Analyze recurrence patterns and update confidence scores"""
    
    enhanced_detector = EnhancedRecurrenceDetector(db)
    
    # Update confidence scores
    updated_count = enhanced_detector.update_task_confidence_scores()
    
    # Generate report
    report = enhanced_detector.generate_recurrence_report()
    
    return {
        "message": f"Updated {updated_count} tasks with new confidence scores",
        "updated_count": updated_count,
        "report": report
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

