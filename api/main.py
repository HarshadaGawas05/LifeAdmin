from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
import os
from datetime import datetime, timedelta
import random
import json

from database import get_db
from models import Transaction, RecurringSubscription, Task, OAuthToken, RawEmail, ParsedEvent, Action, User
from recurrence_detector import RecurrenceDetector
from enhanced_recurrence_detector import EnhancedRecurrenceDetector
from receipt_parser import ReceiptParser
from production_gmail_integration import ProductionGmailIntegration
from celery_app import celery
from routes.email_routes import router as email_router
import jwt
import requests

# IMPORTANT: Do not auto-create tables here. Use Alembic migrations to manage schema.

app = FastAPI(
    title="LifeAdmin API",
    description="Life administration tool for managing recurring subscriptions",
    version="1.0.0"
)

# Add CORS middleware
allowed_frontend = os.getenv("FRONTEND_URL") or os.getenv("NEXT_PUBLIC_FRONTEND_URL") or "http://localhost:3000"
additional_origins = ["http://frontend:3000", "http://127.0.0.1:3000"]
origins = list({allowed_frontend, *additional_origins})
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include email classification routes
app.include_router(email_router)

# Initialize parsers and detectors
parser = ReceiptParser()
enhanced_detector = None  # Will be initialized with db session
@app.get("/me")
async def me(db: Session = Depends(get_db), request: Request = None):
    session_jwt = request.cookies.get("session") if request else None
    if not session_jwt:
        return {"email": None, "needs_reauth": False}
    try:
        payload = jwt.decode(session_jwt, os.getenv("APP_JWT_SECRET", "dev-secret"), algorithms=["HS256"])
        email = payload.get("sub")
        tok = db.query(OAuthToken).filter(OAuthToken.provider=='google', OAuthToken.email_address==email).first()
        user = db.query(User).filter(User.email == email).first()
        return {"email": email, "needs_reauth": bool(tok.needs_reauth) if tok else False, "user_id": user.id if user else None}
    except Exception:
        return {"email": None, "needs_reauth": False}
# ======== Auth (Google OAuth) ========

@app.get("/auth/google/start")
async def auth_google_start():
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    scope = " ".join([
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "openid",
    ])
    # Guard: if client_id is missing or placeholder, send user back with error
    if not client_id or "your-client-id" in client_id:
        frontend_url = os.getenv('FRONTEND_URL') or os.getenv('NEXT_PUBLIC_FRONTEND_URL','http://localhost:3000')
        return RedirectResponse(url=f"{frontend_url}/auth/callback?status=error&reason=invalid_client_id")
    # URL-encode parameters explicitly to avoid 400 invalid_request
    enc_redirect = requests.utils.quote(redirect_uri, safe="")
    enc_scope = requests.utils.quote(scope, safe="")
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={enc_redirect}&"
        "response_type=code&"
        f"scope={enc_scope}&"
        "access_type=offline&prompt=consent&include_granted_scopes=true"
    )
    return RedirectResponse(url=auth_url)


@app.get("/auth/google/callback")
async def auth_google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        from google.oauth2.credentials import Credentials
        code = request.query_params.get("code")
        if not code:
            raise HTTPException(status_code=400, detail="Missing code")
        token_uri = "https://oauth2.googleapis.com/token"
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
        data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        token_res = requests.post(token_uri, data=data)
        if token_res.status_code != 200:
            raise HTTPException(status_code=400, detail="Token exchange failed")
        token_json = token_res.json()

        access_token = token_json.get("access_token")
        refresh_token = token_json.get("refresh_token")
        expires_in = token_json.get("expires_in")
        scope = token_json.get("scope")

        # Fetch userinfo
        userinfo = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        ).json()
        email = userinfo.get("email")
        picture = userinfo.get("picture")
        name = userinfo.get("name") or email

        # Encrypt and store token
        enc_key = os.getenv("ENCRYPTION_KEY").encode()
        from cryptography.fernet import Fernet
        f = Fernet(enc_key)
        token_payload = json.dumps({
            "refresh_token": refresh_token or "",
            "client_id": client_id,
            "client_secret": client_secret,
            "scopes": scope.split(" ") if isinstance(scope, str) else scope,
            "token_uri": token_uri,
        }).encode()
        encrypted_refresh = f.encrypt(token_payload).decode()

        # Upsert User
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email, name=name, picture=picture)
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.name = name
            user.picture = picture
        # Upsert OAuth token
        existing = db.query(OAuthToken).filter(OAuthToken.provider == 'google', OAuthToken.email_address == email).first()
        if existing:
            existing.access_token = access_token
            existing.encrypted_refresh_token = encrypted_refresh
            existing.token_expiry = datetime.utcnow() + timedelta(seconds=expires_in or 3600)
            existing.scope = scope
            existing.needs_reauth = False
            existing.user_id = email
        else:
            db.add(OAuthToken(
                provider='google',
                user_id=email,
                email_address=email,
                access_token=access_token,
                encrypted_refresh_token=encrypted_refresh,
                token_expiry=datetime.utcnow() + timedelta(seconds=expires_in or 3600),
                scope=scope,
                needs_reauth=False,
            ))
        db.commit()

        # Issue session JWT
        jwt_secret = os.getenv("APP_JWT_SECRET", "dev-secret")
        token = jwt.encode({"sub": email, "name": name, "picture": picture}, jwt_secret, algorithm="HS256")
        frontend_url = os.getenv('FRONTEND_URL') or os.getenv('NEXT_PUBLIC_FRONTEND_URL','http://localhost:3000')
        response = RedirectResponse(url=f"{frontend_url}/auth/callback?status=success")
        response.set_cookie("session", token, httponly=True, secure=False, samesite="Lax")
        return response
    except Exception as e:
        frontend_url = os.getenv('FRONTEND_URL') or os.getenv('NEXT_PUBLIC_FRONTEND_URL','http://localhost:3000')
        return RedirectResponse(url=f"{frontend_url}/auth/callback?status=error")


@app.post("/auth/google/revoke")
async def auth_google_revoke(db: Session = Depends(get_db), request: Request = None):
    try:
        session_jwt = request.cookies.get("session") if request else None
        email = None
        if session_jwt:
            try:
                email = jwt.decode(session_jwt, os.getenv("APP_JWT_SECRET", "dev-secret"), algorithms=["HS256"]).get("sub")
            except Exception:
                email = None
        if not email:
            raise HTTPException(status_code=401, detail="Unauthorized")
        tok = db.query(OAuthToken).filter(OAuthToken.provider=='google', OAuthToken.email_address==email).first()
        if tok and tok.access_token:
            try:
                requests.get("https://accounts.google.com/o/oauth2/revoke", params={"token": tok.access_token})
            except Exception:
                pass
        if tok:
            db.delete(tok)
            db.commit()
        resp = JSONResponse({"status": "revoked"})
        resp.delete_cookie("session")
        return resp
    except Exception:
        resp = JSONResponse({"status": "revoked"})
        resp.delete_cookie("session")
        return resp


# ======== Gmail Sync ========

@app.post("/sync/gmail")
async def sync_gmail(user_id: str = None, limit: int = 50, db: Session = Depends(get_db), request: Request = None):
    try:
        # Resolve user from session if not provided
        resolved_user_id = user_id
        if not resolved_user_id and request:
            session_jwt = request.cookies.get("session")
            if session_jwt:
                try:
                    resolved_user_id = jwt.decode(session_jwt, os.getenv("APP_JWT_SECRET", "dev-secret"), algorithms=["HS256"]).get("sub")
                except Exception:
                    resolved_user_id = None
        if not resolved_user_id:
            resolved_user_id = "demo_user"
        gmail = ProductionGmailIntegration(db)
        stats = gmail.sync_actionable_emails(resolved_user_id, max_results=limit)
        # Update recurrence confidence
        detector = EnhancedRecurrenceDetector(db)
        updated = detector.update_task_confidence_scores()
        return {"synced": stats, "confidence_updates": updated}
    except Exception as e:
        # In dev/demo, return graceful error info instead of 500
        return {"error": "gmail_sync_failed", "detail": str(e)}


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


# Background task for email classification
@celery.task
def classify_pending_emails(limit: int = 50):
    """Background task to classify pending emails"""
    from database import SessionLocal
    from email_classifier import EmailClassifier
    
    db = SessionLocal()
    try:
        classifier = EmailClassifier()
        results = classifier.batch_classify_pending_emails(db, limit)
        return results
    except Exception as e:
        logger.error(f"Background email classification failed: {e}")
        return {"error": str(e)}
    finally:
        db.close()


# ==================== NEW ENDPOINTS FOR MVP ====================

@app.get("/tasks")
async def get_tasks(
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Paginated tasks sorted by priority desc"""
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 200:
        page_size = 50
    # Filter by session user if available
    session_email = None
    if request:
        session_jwt = request.cookies.get("session")
        if session_jwt:
            try:
                session_email = jwt.decode(session_jwt, os.getenv("APP_JWT_SECRET", "dev-secret"), algorithms=["HS256"]).get("sub")
            except Exception:
                session_email = None
    base = db.query(Task).filter(Task.is_active == True)
    if session_email:
        user = db.query(User).filter(User.email == session_email).first()
        if user:
            base = base.filter(Task.user_id == user.id)
    total = base.count()
    items = base.order_by(Task.priority_score.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {
        "tasks": [t.to_dict() for t in items],
        "count": total,
        "page": page,
        "page_size": page_size,
        "total_monthly_spend": sum(t.amount or 0 for t in items if t.amount)
    }


@app.post("/tasks/seed")
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
    
    return {"message": f"Seeded {len(mock_tasks)} mock tasks", "tasks_created": len(mock_tasks)}


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
        gmail = ProductionGmailIntegration(db)
        
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
        gmail = ProductionGmailIntegration(db)
        
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


class TaskActionBody(BaseModel):
    action: str
    snooze_days: Optional[int] = 7


@app.post("/tasks/{task_id}/action")
async def task_action(task_id: int, body: TaskActionBody, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if body.action == 'cancel':
        task.is_active = False
    elif body.action == 'snooze':
        if task.due_date:
            task.due_date = task.due_date + timedelta(days=body.snooze_days or 7)
        task.priority_score = max(0.1, (task.priority_score or 0.5) - 0.2)
    elif body.action == 'autopay':
        pass
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    db.add(Action(task_id=task.id, action=body.action, payload=body.model_dump()))
    db.commit()
    db.refresh(task)
    return task.to_dict()


@app.get("/task/{task_id}/source")
async def task_source(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    # Find parsed_event via name and latest raw email
    parsed = db.query(ParsedEvent).filter(ParsedEvent.name == task.name).order_by(ParsedEvent.created_at.desc()).first()
    raw = None
    if parsed and parsed.raw_email_id:
        raw = db.query(RawEmail).filter(RawEmail.id == parsed.raw_email_id).first()
    return {
        "task": task.to_dict(),
        "raw_email": {
            "subject": raw.subject if raw else None,
            "sender": raw.sender if raw else None,
            "snippet": raw.snippet if raw else None,
            "sent_at": raw.sent_at.isoformat() if (raw and raw.sent_at) else None,
        }
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


@app.post("/test/classify")
async def test_classify_email(
    subject: str = "Netflix Monthly Subscription - ₹499",
    body: str = "Your Netflix subscription has been renewed for ₹499. Next billing date: February 15, 2024."
):
    """Test endpoint for email classification"""
    try:
        from email_classifier import EmailClassifier
        
        classifier = EmailClassifier()
        result = classifier.classify_email(subject, body)
        
        return {
            "message": "Classification successful",
            "input": {"subject": subject, "body": body},
            "result": result.dict()
        }
    except Exception as e:
        return {
            "error": str(e),
            "message": "Classification failed"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

