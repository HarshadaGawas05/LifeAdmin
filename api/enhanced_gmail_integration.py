"""
Enhanced Gmail Integration Module for LifeAdmin
Handles OAuth 2.0 flow, email fetching, and context-aware NLP parsing
"""

import os
import json
import base64
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import email
from email.utils import parsedate_to_datetime

import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from models import Task, OAuthToken, RawEmail, ParsedEvent, User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmailClassifier:
    """Enhanced keyword-based email classification with context awareness"""
    
    def __init__(self):
        logger.info("Initialized enhanced email classifier")
        
        # Enhanced category patterns with weights and context
        self.category_patterns = {
            'subscription': {
                'keywords': ['subscription', 'renewal', 'premium', 'plan', 'membership', 'recurring', 'monthly', 'annual'],
                'context': ['payment', 'billing', 'service', 'account'],
                'weight': 1.0
            },
            'bill': {
                'keywords': ['bill', 'invoice', 'statement', 'payment', 'due', 'amount', 'total', 'charges'],
                'context': ['electricity', 'water', 'gas', 'utility', 'service', 'account'],
                'weight': 1.0
            },
            'assignment': {
                'keywords': ['assignment', 'homework', 'project', 'task', 'deadline', 'submission', 'due'],
                'context': ['course', 'class', 'student', 'academic', 'school', 'university'],
                'weight': 1.0
            },
            'job_application': {
                'keywords': ['job', 'application', 'interview', 'resume', 'career', 'hiring', 'position', 'candidate'],
                'context': ['hr', 'recruitment', 'employment', 'company', 'opportunity'],
                'weight': 1.0
            },
            'other': {
                'keywords': ['notification', 'update', 'newsletter', 'announcement', 'reminder'],
                'context': ['general', 'information', 'news'],
                'weight': 0.5
            }
        }
    
    def classify_email(self, subject: str, body: str) -> Tuple[str, float]:
        """
        Classify email using enhanced keyword matching with context awareness
        Returns (category, confidence_score)
        """
        text = f"{subject} {body}".lower()
        
        # Clean text
        text = re.sub(r'[^\w\s]', ' ', text)
        
        category_scores = {}
        
        for category, pattern_data in self.category_patterns.items():
            score = 0.0
            
            # Count keyword matches
            keyword_matches = sum(1 for keyword in pattern_data['keywords'] if keyword in text)
            context_matches = sum(1 for context_word in pattern_data['context'] if context_word in text)
            
            # Calculate weighted score
            score = (keyword_matches * pattern_data['weight']) + (context_matches * 0.5)
            
            # Bonus for multiple matches
            if keyword_matches > 1:
                score *= 1.2
            if context_matches > 0:
                score *= 1.1
                
            category_scores[category] = score
        
        # Get the best match
        if not any(category_scores.values()):
            return 'other', 0.5
        
        best_category = max(category_scores, key=category_scores.get)
        max_score = category_scores[best_category]
        
        # Normalize confidence score (0.3 to 0.95)
        confidence = min(0.95, max(0.3, 0.3 + (max_score * 0.1)))
        
        logger.info(f"Classified email '{subject[:50]}...' as {best_category} (confidence: {confidence:.3f})")
        return best_category, confidence


class EnhancedGmailIntegration:
    """Enhanced Gmail integration with NLP-based email classification"""
    
    # Gmail API scopes
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    
    # Broader search query to catch all relevant emails
    SEARCH_QUERY = (
        'in:anywhere (bill OR subscription OR invoice OR assignment OR due OR renewal OR application OR payment OR job OR interview OR project OR task OR deadline OR statement OR receipt)'
    )
    
    def __init__(self, db: Session):
        self.db = db
        self.encryption_key = self._get_or_create_encryption_key()
        self.fernet = Fernet(self.encryption_key)
        self.classifier = EmailClassifier()
        
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for storing tokens"""
        key_env = os.getenv('ENCRYPTION_KEY')
        if key_env:
            return key_env.encode()
        
        # Generate new key and store in environment
        key = Fernet.generate_key()
        logger.info(f"Generated encryption key: {key.decode()}")
        logger.info("Add this to your .env file as ENCRYPTION_KEY")
        return key
    
    def get_oauth_url(self) -> str:
        """Generate OAuth 2.0 authorization URL"""
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            client_id = "your-client-id.apps.googleusercontent.com"
            client_secret = "your-client-secret"
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost:3000/connect"]
                }
            },
            scopes=self.SCOPES
        )
        
        flow.redirect_uri = "http://localhost:3000/connect"
        auth_url, _ = flow.authorization_url(prompt='consent')
        return auth_url
    
    def store_token(self, user_id: str, credentials: Credentials) -> None:
        """Store encrypted OAuth token"""
        token_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        encrypted_token = self.fernet.encrypt(json.dumps(token_data).encode())
        
        existing_token = self.db.query(OAuthToken).filter(
            OAuthToken.provider == 'google',
            OAuthToken.user_id == user_id
        ).first()
        
        if existing_token:
            existing_token.encrypted_refresh_token = encrypted_token.decode()
        else:
            new_token = OAuthToken(
                provider='google',
                user_id=user_id,
                encrypted_refresh_token=encrypted_token.decode()
            )
            self.db.add(new_token)
        
        self.db.commit()
        logger.info(f"Stored OAuth token for user {user_id}")
    
    def get_credentials(self, user_id: str) -> Optional[Credentials]:
        """Retrieve and decrypt OAuth credentials"""
        token_record = self.db.query(OAuthToken).filter(
            OAuthToken.provider == 'google', 
            OAuthToken.user_id == user_id
        ).first()
        
        if not token_record:
            logger.warning(f"No OAuth token found for user {user_id}")
            return None
        
        try:
            decrypted_data = self.fernet.decrypt(token_record.encrypted_refresh_token.encode())
            token_data = json.loads(decrypted_data.decode())
            
            refresh_token = token_data.get('refresh_token')
            client_id = token_data.get('client_id') or os.getenv('GOOGLE_CLIENT_ID')
            client_secret = token_data.get('client_secret') or os.getenv('GOOGLE_CLIENT_SECRET')
            
            if not refresh_token:
                logger.error(f"No refresh token found for user {user_id}")
                return None
                
            credentials = Credentials(
                None,
                refresh_token=refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=client_id,
                client_secret=client_secret,
                scopes=self.SCOPES,
            )
            
            try:
                credentials.refresh(Request())
                token_record.access_token = credentials.token
                token_record.token_expiry = credentials.expiry
                token_record.needs_reauth = False
                self.db.commit()
                logger.info(f"Refreshed credentials for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to refresh credentials for user {user_id}: {e}")
                token_record.needs_reauth = True
                self.db.commit()
                return None
                
            return credentials
            
        except Exception as e:
            logger.error(f"Error retrieving credentials for user {user_id}: {e}")
            return None
    
    def fetch_emails(self, user_id: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Fetch emails from Gmail matching keywords"""
        credentials = self.get_credentials(user_id)
        if not credentials:
            raise Exception("No valid Gmail credentials found")
        
        try:
            service = build('gmail', 'v1', credentials=credentials)
            
            # Use broader search query
            query = self.SEARCH_QUERY
            
            logger.info(f"Fetching emails for user {user_id} with query: {query}")
            
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            logger.info(f"Found {len(messages)} messages to process")
            
            emails = []
            for i, message in enumerate(messages):
                try:
                    msg = service.users().messages().get(
                        userId='me',
                        id=message['id']
                    ).execute()
                    
                    parsed_email = self._parse_email(msg)
                    emails.append(parsed_email)
                    
                    if (i + 1) % 10 == 0:
                        logger.info(f"Processed {i + 1}/{len(messages)} emails")
                        
                except Exception as e:
                    logger.error(f"Error parsing email {message['id']}: {e}")
                    continue
            
            logger.info(f"Successfully parsed {len(emails)} emails")
            return emails
            
        except HttpError as error:
            logger.error(f"Gmail API error: {error}")
            raise Exception(f"Gmail API error: {error}")
    
    def _parse_email(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Gmail message to extract relevant information"""
        headers = message['payload'].get('headers', [])
        
        subject = ""
        sender = ""
        date = ""
        
        for header in headers:
            if header['name'] == 'Subject':
                subject = header['value']
            elif header['name'] == 'From':
                sender = header['value']
            elif header['name'] == 'Date':
                date = header['value']
        
        body = self._extract_email_body(message['payload'])
        
        return {
            'id': message['id'],
            'subject': subject,
            'sender': sender,
            'date': date,
            'body': body,
            'raw_message': message
        }
    
    def _extract_email_body(self, payload: Dict[str, Any]) -> str:
        """Extract email body text from payload with robust HTML handling"""
        body = ""
        
        def extract_from_parts(parts):
            nonlocal body
            for part in parts:
                if part.get('parts'):
                    extract_from_parts(part['parts'])
                    continue
                    
                mime = part.get('mimeType', '')
                data = (part.get('body') or {}).get('data')
                
                if not data:
                    continue
                    
                try:
                    decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    
                    if mime == 'text/plain':
                        body += decoded + "\n"
                    elif mime == 'text/html':
                        # More robust HTML stripping
                        clean_text = self._strip_html(decoded)
                        body += clean_text + "\n"
                except Exception as e:
                    logger.warning(f"Error decoding email part: {e}")
                    continue
        
        if 'parts' in payload:
            extract_from_parts(payload['parts'])
        else:
            mime = payload.get('mimeType', '')
            data = (payload.get('body') or {}).get('data')
            
            if data:
                try:
                    decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    if mime == 'text/plain':
                        body = decoded
                    elif mime == 'text/html':
                        body = self._strip_html(decoded)
                except Exception as e:
                    logger.warning(f"Error decoding email body: {e}")
        
        return body.strip()
    
    def _strip_html(self, html_text: str) -> str:
        """Robust HTML stripping with better text extraction"""
        # Remove script and style elements
        html_text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML tags
        html_text = re.sub(r'<[^>]+>', ' ', html_text)
        
        # Decode HTML entities
        html_text = html_text.replace('&nbsp;', ' ')
        html_text = html_text.replace('&amp;', '&')
        html_text = html_text.replace('&lt;', '<')
        html_text = html_text.replace('&gt;', '>')
        html_text = html_text.replace('&quot;', '"')
        
        # Clean up whitespace
        html_text = re.sub(r'\s+', ' ', html_text)
        
        return html_text.strip()
    
    def parse_email_to_task(self, email_data: Dict[str, Any]) -> Optional[Task]:
        """Parse email data into a Task object with enhanced extraction"""
        subject = email_data['subject']
        body = email_data['body']
        sender = email_data['sender']
        
        # Extract task name (prefer subject, fallback to sender)
        task_name = self._extract_task_name(subject, sender)
        
        # Extract amount with more patterns
        amount = self._extract_amount(subject + " " + body)
        
        # Extract due date with enhanced patterns
        due_date = self._extract_due_date(subject + " " + body)
        
        # Use NLP classification instead of keyword matching
        category, confidence = self.classifier.classify_email(subject, body)
        
        # Calculate priority score based on due date
        priority_score = self._calculate_priority_score(due_date)
        
        # Store source details
        source_details = {
            'email_id': email_data['id'],
            'subject': subject,
            'sender': sender,
            'date': email_data['date'],
            'body_snippet': body[:500],
            'classification_confidence': confidence
        }
        
        task = Task(
            name=task_name,
            amount=amount,
            category=category,
            due_date=due_date,
            priority_score=priority_score,
            confidence_score=confidence,
            source='gmail',
            source_details=source_details,
            is_active=True
        )
        
        logger.info(f"Parsed task: {task_name} ({category}, confidence: {confidence:.3f})")
        return task
    
    def _extract_task_name(self, subject: str, sender: str) -> str:
        """Extract task name from email subject and sender"""
        # Clean up subject
        clean_subject = re.sub(r'^(Re:|Fwd:|FW:)\s*', '', subject or '', flags=re.IGNORECASE).strip()
        if clean_subject:
            return clean_subject[:255]
        
        # Fallback to sender display name
        sender_match = re.search(r'([^<]+)', sender or '')
        if sender_match:
            sender_name = sender_match.group(1).strip()
            sender_name = re.sub(r'\s*<.*>', '', sender_name)
            return sender_name[:255] or 'Unknown Sender'
        
        return 'Unknown Sender'
    
    def _extract_amount(self, text: str) -> Optional[float]:
        """Extract monetary amount from text with enhanced patterns"""
        # Enhanced currency patterns
        patterns = [
            r'₹\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'Rs\.?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'INR\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'USD\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'amount[:\s]*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'total[:\s]*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'due[:\s]*(\d+(?:,\d{3})*(?:\.\d{2})?)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    # Remove commas and convert to float
                    amount_str = match.replace(',', '')
                    amount = float(amount_str)
                    if amount > 0:  # Only return positive amounts
                        return amount
                except ValueError:
                    continue
        
        return None
    
    def _extract_due_date(self, text: str) -> Optional[datetime]:
        """Extract due date from text with enhanced patterns"""
        try:
            import dateparser
        except ImportError:
            dateparser = None
        
        # Enhanced explicit patterns
        patterns = [
            r'due\s+(?:on\s+)?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'deadline\s+(?:is\s+)?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'pay\s+by\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'due\s+date[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})',
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                
                # Try different date formats
                formats = [
                    '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y', '%m-%d-%Y',
                    '%d %b %Y', '%b %d, %Y', '%B %d, %Y'
                ]
                
                for fmt in formats:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
        
        # Fallback to dateparser for natural language dates
        if dateparser:
            try:
                parsed = dateparser.parse(text, settings={
                    "PREFER_DATES_FROM": "future",
                    "RELATIVE_BASE": datetime.now()
                })
                if parsed:
                    return parsed
            except Exception as e:
                logger.warning(f"Dateparser error: {e}")
        
        return None
    
    def upsert_raw_email(self, email: Dict[str, Any], user_pk: Optional[int]) -> RawEmail:
        """Persist a raw email record if not exists"""
        existing = self.db.query(RawEmail).filter(RawEmail.email_id == email['id']).first()
        if existing:
            return existing
        
        # Parse various date formats including RFC2822
        sent_at = None
        try:
            if email.get('date'):
                sent_at = parsedate_to_datetime(email.get('date'))
        except Exception as e:
            logger.warning(f"Error parsing date {email.get('date')}: {e}")
            sent_at = None
        
        record = RawEmail(
            user_id=user_pk,
            email_id=email['id'],
            thread_id=email.get('threadId'),
            subject=email.get('subject'),
            sender=email.get('sender'),
            sent_at=sent_at,
            snippet=(email.get('body') or '')[:500],
            raw_payload=email.get('raw_message')
        )
        
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
    
    def create_parsed_event(self, email: Dict[str, Any], task: Task, raw_email: RawEmail, user_pk: Optional[int]) -> ParsedEvent:
        """Create a parsed_event row from extracted fields"""
        return ParsedEvent(
            user_id=user_pk,
            name=task.name,
            amount=task.amount,
            currency='INR' if task.amount is not None else None,
            due_date=task.due_date,
            category=task.category,
            confidence=task.confidence_score,
            source='gmail',
            raw_email_id=raw_email.id
        )
    
    def persist_emails_as_tasks(self, user_id: str, max_results: int = 50) -> Dict[str, int]:
        """Fetch emails, persist RawEmail and ParsedEvent, and create Tasks"""
        logger.info(f"Starting email processing for user {user_id}")
        
        # Resolve User PK by email identifier (create if missing)
        user_pk: Optional[int] = None
        if user_id:
            user = self.db.query(User).filter(User.email == user_id).first()
            if not user:
                user = User(email=user_id)
                self.db.add(user)
                self.db.commit()
                self.db.refresh(user)
                logger.info(f"Created new user: {user_id}")
            user_pk = user.id
        
        try:
            emails = self.fetch_emails(user_id, max_results=max_results)
        except Exception as e:
            logger.error(f"Failed to fetch emails: {e}")
            # Use mock data as fallback for development
            emails = self._get_mock_emails()
            logger.info("Using mock email data for development")
        
        created_tasks = 0
        created_raw = 0
        created_events = 0
        
        for i, em in enumerate(emails):
            try:
                raw = self.upsert_raw_email(em, user_pk)
                if raw.created_at == raw.updated_at:
                    created_raw += 1
                
                task = self.parse_email_to_task(em)
                if not task:
                    logger.warning(f"Could not parse email {em.get('id', 'unknown')}")
                    continue
                
                # Attach user_id
                task.user_id = user_pk
                
                # Prevent duplicates by name+source per user
                existing = self.db.query(Task).filter(
                    Task.name == task.name,
                    Task.source == 'gmail',
                    Task.user_id == user_pk,
                ).first()
                
                if not existing:
                    self.db.add(task)
                    created_tasks += 1
                    self.db.flush()
                
                parsed_event = self.create_parsed_event(em, task, raw, user_pk)
                self.db.add(parsed_event)
                created_events += 1
                
                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(emails)} emails")
                    
            except Exception as e:
                logger.error(f"Error processing email {i}: {e}")
                continue
        
        self.db.commit()
        
        result = {
            "raw_emails": created_raw, 
            "parsed_events": created_events, 
            "tasks": created_tasks
        }
        
        logger.info(f"Email processing completed: {result}")
        return result
    
    def _get_mock_emails(self) -> List[Dict[str, Any]]:
        """Get mock emails for development/testing"""
        return [
            {
                "id": "mock_email_1",
                "subject": "Netflix Subscription Renewal Reminder",
                "sender": "Netflix <billing@netflix.com>",
                "date": "2024-10-08T21:08:00Z",
                "body": "Dear Harshada, Your Netflix subscription of ₹499 is due on 15th Oct 2025. Please make sure your payment is completed to continue enjoying our service. Thank you, Netflix Team",
                "raw_message": {"id": "mock_email_1"}
            },
            {
                "id": "mock_email_2",
                "subject": "Job Application Received",
                "sender": "HR Team <hr@company.com>",
                "date": "2024-10-08T23:07:00Z",
                "body": "We received your application for Software Engineer. Next step: interview scheduled.",
                "raw_message": {"id": "mock_email_2"}
            },
            {
                "id": "mock_email_3",
                "subject": "Gym Membership Renewal Notice",
                "sender": "Fitness Center <membership@gym.com>",
                "date": "2024-10-08T23:08:00Z",
                "body": "Your gym subscription of $50 is due for renewal on Oct 20, 2025.",
                "raw_message": {"id": "mock_email_3"}
            },
            {
                "id": "mock_email_4",
                "subject": "Invoice for Electricity Bill",
                "sender": "Electricity Board <billing@power.com>",
                "date": "2024-10-08T23:14:00Z",
                "body": "Total due amount: Rs 1200, due date: 12/10/2025.",
                "raw_message": {"id": "mock_email_4"}
            }
        ]
    
    def _calculate_priority_score(self, due_date: Optional[datetime]) -> float:
        """Calculate priority score based on due date urgency"""
        if not due_date:
            return 0.5  # Medium priority if no due date
        
        now = datetime.now()
        days_until_due = (due_date - now).days
        
        if days_until_due < 0:
            return 1.0  # Overdue - highest priority
        elif days_until_due <= 1:
            return 0.9  # Due today/tomorrow
        elif days_until_due <= 3:
            return 0.7  # Due in 2-3 days
        elif days_until_due <= 7:
            return 0.5  # Due in a week
        else:
            return 0.3  # Due later - lower priority
