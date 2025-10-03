from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import os
from datetime import datetime, timedelta
import random

from database import get_db, create_tables
from models import Transaction, RecurringSubscription
from recurrence_detector import RecurrenceDetector
from receipt_parser import ReceiptParser
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

# Initialize parser
parser = ReceiptParser()


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

