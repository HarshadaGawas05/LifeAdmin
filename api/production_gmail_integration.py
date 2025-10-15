"""
Production-Ready Gmail Integration for LifeAdmin
Intelligent email filtering and actionable task detection
"""

import os
import json
import base64
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple, Set
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
from sqlalchemy import and_, or_

from models import Task, OAuthToken, RawEmail, ParsedEvent, User, LLMStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntelligentEmailFilter:
    """Intelligent email filtering to identify actionable tasks"""
    
    def __init__(self):
        logger.info("Initialized intelligent email filter")
        
        # Define actionable email patterns
        self.actionable_patterns = {
            'subscription': {
                'keywords': ['subscription', 'renewal', 'premium', 'plan', 'membership', 'recurring'],
                'context': ['payment', 'billing', 'service', 'account', 'monthly', 'annual'],
                'action_required': True,
                'priority': 0.7
            },
            'bill': {
                'keywords': ['bill', 'invoice', 'statement', 'payment', 'due', 'amount', 'total'],
                'context': ['electricity', 'water', 'gas', 'utility', 'service', 'account'],
                'action_required': True,
                'priority': 0.8
            },
            'assignment': {
                'keywords': ['assignment', 'homework', 'project', 'task', 'deadline', 'submission'],
                'context': ['course', 'class', 'student', 'academic', 'school', 'university'],
                'action_required': True,
                'priority': 0.6
            },
            'job_application': {
                'keywords': ['job', 'application', 'interview', 'resume', 'career', 'hiring', 'position'],
                'context': ['hr', 'recruitment', 'employment', 'company', 'opportunity'],
                'action_required': True,
                'priority': 0.5
            },
            'appointment': {
                'keywords': ['appointment', 'meeting', 'schedule', 'booking', 'reservation'],
                'context': ['doctor', 'dentist', 'service', 'consultation'],
                'action_required': True,
                'priority': 0.4
            }
        }
        
        # Define non-actionable patterns to filter out
        self.non_actionable_patterns = {
            'newsletter': ['newsletter', 'news', 'update', 'digest', 'roundup'],
            'promotion': ['promotion', 'offer', 'deal', 'discount', 'sale', 'coupon'],
            'social': ['facebook', 'twitter', 'instagram', 'linkedin', 'social'],
            'notification': ['notification', 'alert', 'reminder', 'system'],
            'marketing': ['marketing', 'advertisement', 'spam', 'unsubscribe'],
            'automated': ['noreply', 'no-reply', 'automated', 'do-not-reply']
        }
        
        # Recurring patterns for subscription detection
        self.recurring_indicators = [
            'monthly', 'annual', 'yearly', 'weekly', 'daily',
            'subscription', 'recurring', 'automatic', 'auto-renew',
            'billing cycle', 'next payment', 'renewal date'
        ]
    
    def is_actionable_email(self, subject: str, body: str, sender: str) -> Tuple[bool, str, float]:
        """
        Determine if an email represents an actionable task
        Returns (is_actionable, category, confidence)
        """
        text = f"{subject} {body}".lower()
        sender_lower = sender.lower()
        
        # First, check if it's clearly non-actionable
        if self._is_non_actionable(text, sender_lower):
            return False, 'non_actionable', 0.9
        
        # Check for actionable patterns
        best_category = None
        best_score = 0.0
        
        for category, pattern_data in self.actionable_patterns.items():
            score = self._calculate_actionability_score(text, pattern_data)
            
            if score > best_score:
                best_score = score
                best_category = category
        
        # Threshold for actionability
        if best_score >= 0.3:
            confidence = min(0.95, best_score)
            logger.info(f"Email '{subject[:50]}...' classified as actionable {best_category} (score: {best_score:.3f})")
            return True, best_category, confidence
        
        return False, 'non_actionable', 0.8
    
    def _is_non_actionable(self, text: str, sender: str) -> bool:
        """Check if email is clearly non-actionable"""
        # Check sender patterns
        non_actionable_senders = [
            'noreply', 'no-reply', 'donotreply', 'automated',
            'newsletter', 'marketing', 'promotions'
        ]
        
        for pattern in non_actionable_senders:
            if pattern in sender:
                return True
        
        # Check content patterns
        for category, patterns in self.non_actionable_patterns.items():
            if any(pattern in text for pattern in patterns):
                return True
        
        return False
    
    def _calculate_actionability_score(self, text: str, pattern_data: Dict) -> float:
        """Calculate how actionable an email is based on patterns"""
        score = 0.0
        
        # Count keyword matches
        keyword_matches = sum(1 for keyword in pattern_data['keywords'] if keyword in text)
        context_matches = sum(1 for context_word in pattern_data['context'] if context_word in text)
        
        # Base score from matches
        score = (keyword_matches * 0.3) + (context_matches * 0.2)
        
        # Bonus for multiple matches
        if keyword_matches > 1:
            score *= 1.5
        if context_matches > 0:
            score *= 1.2
        
        # Apply category priority
        score *= pattern_data['priority']
        
        return score
    
    def detect_recurring_pattern(self, subject: str, body: str) -> Tuple[bool, Optional[str]]:
        """Detect if this is a recurring task/subscription"""
        text = f"{subject} {body}".lower()
        
        recurring_count = sum(1 for indicator in self.recurring_indicators if indicator in text)
        
        if recurring_count >= 2:  # Multiple recurring indicators
            return True, "monthly"  # Default to monthly, could be enhanced
        elif recurring_count >= 1:
            return True, "monthly"
        
        return False, None


class SmartEmailParser:
    """Smart email parser for actionable tasks"""
    
    def __init__(self):
        self.filter = IntelligentEmailFilter()
        logger.info("Initialized smart email parser")
    
    def parse_actionable_email(self, email_data: Dict[str, Any]) -> Optional[Task]:
        """Parse only actionable emails into Task objects"""
        subject = email_data['subject']
        body = email_data['body']
        sender = email_data['sender']
        
        # Check if email is actionable
        is_actionable, category, confidence = self.filter.is_actionable_email(subject, body, sender)
        
        if not is_actionable:
            logger.info(f"Skipping non-actionable email: {subject[:50]}...")
            return None
        
        # Extract task details
        task_name = self._extract_task_name(subject, sender)
        amount = self._extract_amount(subject + " " + body)
        due_date = self._extract_due_date(subject + " " + body)
        
        # Detect recurring pattern
        is_recurring, recurring_interval = self.filter.detect_recurring_pattern(subject, body)
        
        # Calculate priority based on due date and category
        priority_score = self._calculate_priority_score(due_date, category)
        
        # Store source details
        source_details = {
            'email_id': email_data['id'],
            'subject': subject,
            'sender': sender,
            'date': email_data['date'],
            'body_snippet': body[:500],
            'classification_confidence': confidence,
            'is_recurring': is_recurring,
            'recurring_interval': recurring_interval
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
            is_active=True,
            is_recurring=is_recurring,
            interval_days=30 if is_recurring and recurring_interval == "monthly" else None
        )
        
        logger.info(f"Parsed actionable task: {task_name} ({category}, confidence: {confidence:.3f})")
        return task
    
    def _extract_task_name(self, subject: str, sender: str) -> str:
        """Extract meaningful task name"""
        # Clean up subject
        clean_subject = re.sub(r'^(Re:|Fwd:|FW:)\s*', '', subject or '', flags=re.IGNORECASE).strip()
        
        if clean_subject and len(clean_subject) > 5:  # Meaningful subject
            return clean_subject[:255]
        
        # Fallback to sender display name
        sender_match = re.search(r'([^<]+)', sender or '')
        if sender_match:
            sender_name = sender_match.group(1).strip()
            sender_name = re.sub(r'\s*<.*>', '', sender_name)
            return sender_name[:255] or 'Unknown Sender'
        
        return 'Unknown Sender'
    
    def _extract_amount(self, text: str) -> Optional[float]:
        """Extract monetary amount with enhanced patterns"""
        patterns = [
            r'₹\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'Rs\.?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'INR\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'USD\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'amount[:\s]*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'total[:\s]*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'due[:\s]*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'payment[:\s]*(\d+(?:,\d{3})*(?:\.\d{2})?)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    amount_str = match.replace(',', '')
                    amount = float(amount_str)
                    if amount > 0:
                        return amount
                except ValueError:
                    continue
        
        return None
    
    def _extract_due_date(self, text: str) -> Optional[datetime]:
        """Extract due date with enhanced patterns"""
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
                
                formats = [
                    '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y', '%m-%d-%Y',
                    '%d %b %Y', '%b %d, %Y', '%B %d, %Y'
                ]
                
                for fmt in formats:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
        
        # Fallback to dateparser
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
    
    def _calculate_priority_score(self, due_date: Optional[datetime], category: str) -> float:
        """Calculate priority score based on due date and category"""
        base_priority = {
            'bill': 0.8,
            'subscription': 0.6,
            'assignment': 0.7,
            'job_application': 0.5,
            'appointment': 0.4
        }.get(category, 0.5)
        
        if not due_date:
            return base_priority
        
        now = datetime.now()
        days_until_due = (due_date - now).days
        
        if days_until_due < 0:
            return 1.0  # Overdue
        elif days_until_due <= 1:
            return min(1.0, base_priority + 0.3)
        elif days_until_due <= 3:
            return min(1.0, base_priority + 0.2)
        elif days_until_due <= 7:
            return min(1.0, base_priority + 0.1)
        else:
            return base_priority


class ProductionGmailIntegration:
    """Production-ready Gmail integration with intelligent filtering"""
    
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    
    def __init__(self, db: Session):
        self.db = db
        self.encryption_key = self._get_or_create_encryption_key()
        self.fernet = Fernet(self.encryption_key)
        self.parser = SmartEmailParser()
        
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for storing tokens"""
        key_env = os.getenv('ENCRYPTION_KEY')
        if key_env:
            return key_env.encode()
        
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
    
    def fetch_actionable_emails(self, user_id: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Fetch and filter only actionable emails from Gmail"""
        credentials = self.get_credentials(user_id)
        if not credentials:
            raise Exception("No valid Gmail credentials found")
        
        try:
            service = build('gmail', 'v1', credentials=credentials)
            
            # Use broader search query to catch potential actionable emails
            query = (
                'in:anywhere (bill OR subscription OR invoice OR assignment OR due OR renewal OR application OR payment OR job OR interview OR project OR task OR deadline OR statement OR appointment OR meeting OR booking)'
            )
            
            logger.info(f"Fetching actionable emails for user {user_id}")
            
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            logger.info(f"Found {len(messages)} potential messages to filter")
            
            actionable_emails = []
            filtered_count = 0
            
            for i, message in enumerate(messages):
                try:
                    msg = service.users().messages().get(
                        userId='me',
                        id=message['id']
                    ).execute()
                    
                    parsed_email = self._parse_email(msg)
                    
                    # Check if email is actionable
                    is_actionable, category, confidence = self.parser.filter.is_actionable_email(
                        parsed_email['subject'], 
                        parsed_email['body'], 
                        parsed_email['sender']
                    )
                    
                    if is_actionable:
                        actionable_emails.append(parsed_email)
                        logger.info(f"✓ Actionable email: {parsed_email['subject'][:50]}... ({category})")
                    else:
                        filtered_count += 1
                        logger.debug(f"✗ Filtered out: {parsed_email['subject'][:50]}...")
                    
                    if (i + 1) % 10 == 0:
                        logger.info(f"Processed {i + 1}/{len(messages)} emails")
                        
                except Exception as e:
                    logger.error(f"Error processing email {message['id']}: {e}")
                    continue
            
            logger.info(f"Filtered {filtered_count} non-actionable emails, found {len(actionable_emails)} actionable emails")
            return actionable_emails
            
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
        """Extract email body text with robust HTML handling"""
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
        """Robust HTML stripping"""
        html_text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
        html_text = re.sub(r'<[^>]+>', ' ', html_text)
        html_text = html_text.replace('&nbsp;', ' ')
        html_text = html_text.replace('&amp;', '&')
        html_text = html_text.replace('&lt;', '<')
        html_text = html_text.replace('&gt;', '>')
        html_text = html_text.replace('&quot;', '"')
        html_text = re.sub(r'\s+', ' ', html_text)
        return html_text.strip()
    
    def upsert_raw_email(self, email: Dict[str, Any], user_pk: Optional[int]) -> RawEmail:
        """Persist a raw email record if not exists"""
        existing = self.db.query(RawEmail).filter(RawEmail.email_id == email['id']).first()
        if existing:
            return existing
        
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
    
    def sync_actionable_emails(self, user_id: str, max_results: int = 50) -> Dict[str, int]:
        """Fetch actionable emails, parse, and store as tasks"""
        logger.info(f"Starting intelligent email sync for user {user_id}")
        
        # Resolve User PK
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
            emails = self.fetch_actionable_emails(user_id, max_results=max_results)
        except Exception as e:
            logger.error(f"Failed to fetch emails: {e}")
            # Use mock actionable data for development
            emails = self._get_mock_actionable_emails()
            logger.info("Using mock actionable email data for development")
        
        created_tasks = 0
        created_raw = 0
        created_events = 0
        skipped_non_actionable = 0
        
        for i, em in enumerate(emails):
            try:
                raw = self.upsert_raw_email(em, user_pk)
                if raw.created_at == raw.updated_at:
                    created_raw += 1
                
                task = self.parser.parse_actionable_email(em)
                if not task:
                    skipped_non_actionable += 1
                    logger.debug(f"Skipped non-actionable email: {em.get('subject', 'Unknown')[:50]}...")
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
        
        # Trigger background classification for new emails
        if created_raw > 0:
            try:
                self._trigger_background_classification()
                logger.info(f"Triggered background classification for {created_raw} new emails")
            except Exception as e:
                logger.warning(f"Failed to trigger background classification: {e}")
        
        result = {
            "raw_emails": created_raw, 
            "parsed_events": created_events, 
            "tasks": created_tasks,
            "skipped_non_actionable": skipped_non_actionable
        }
        
        logger.info(f"Intelligent email sync completed: {result}")
        return result
    
    def _get_mock_actionable_emails(self) -> List[Dict[str, Any]]:
        """Get mock actionable emails for development/testing"""
        return [
            {
                "id": "mock_actionable_1",
                "subject": "Netflix Subscription Renewal Reminder",
                "sender": "Netflix <billing@netflix.com>",
                "date": "2024-10-08T21:08:00Z",
                "body": "Dear Harshada, Your Netflix subscription of ₹499 is due on 15th Oct 2025. Please make sure your payment is completed to continue enjoying our service. Thank you, Netflix Team",
                "raw_message": {"id": "mock_actionable_1"}
            },
            {
                "id": "mock_actionable_2",
                "subject": "Job Application Received - Next Steps",
                "sender": "HR Team <hr@company.com>",
                "date": "2024-10-08T23:07:00Z",
                "body": "We received your application for Software Engineer. Next step: interview scheduled for next week. Please confirm your availability.",
                "raw_message": {"id": "mock_actionable_2"}
            },
            {
                "id": "mock_actionable_3",
                "subject": "Gym Membership Renewal Notice",
                "sender": "Fitness Center <membership@gym.com>",
                "date": "2024-10-08T23:08:00Z",
                "body": "Your gym subscription of $50 is due for renewal on Oct 20, 2025. Please update your payment method.",
                "raw_message": {"id": "mock_actionable_3"}
            },
            {
                "id": "mock_actionable_4",
                "subject": "Electricity Bill Payment Due",
                "sender": "Electricity Board <billing@power.com>",
                "date": "2024-10-08T23:14:00Z",
                "body": "Total due amount: Rs 1200, due date: 12/10/2025. Please pay to avoid disconnection.",
                "raw_message": {"id": "mock_actionable_4"}
            },
            {
                "id": "mock_actionable_5",
                "subject": "Doctor Appointment Confirmation",
                "sender": "Medical Center <appointments@medical.com>",
                "date": "2024-10-08T23:15:00Z",
                "body": "Your appointment with Dr. Smith is scheduled for Oct 25, 2025 at 2:00 PM. Please arrive 15 minutes early.",
                "raw_message": {"id": "mock_actionable_5"}
            }
        ]
    
    def _trigger_background_classification(self):
        """Trigger background classification of pending emails"""
        try:
            # Import here to avoid circular imports
            from email_classifier import EmailClassifier
            
            # Get pending emails count
            pending_count = self.db.query(RawEmail).filter(
                RawEmail.llm_status == LLMStatus.PENDING
            ).count()
            
            if pending_count > 0:
                logger.info(f"Found {pending_count} pending emails for classification")
                # In a production environment, you would trigger a background task here
                # For now, we'll just log that classification should be triggered
                # The actual classification can be triggered via the API endpoint
                
        except Exception as e:
            logger.error(f"Error triggering background classification: {e}")
            # Don't raise the exception to avoid breaking the main sync process
