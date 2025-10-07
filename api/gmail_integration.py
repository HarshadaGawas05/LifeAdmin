"""
Gmail Integration Module for LifeAdmin MVP
Handles OAuth 2.0 flow, email fetching, and parsing
"""

import os
import json
import base64
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import email

import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from models import Task, GmailToken


class GmailIntegration:
    """Handles Gmail OAuth and email processing"""
    
    # Gmail API scopes
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    
    # Keywords to search for in emails
    SEARCH_KEYWORDS = [
        'bill', 'subscription', 'invoice', 'assignment', 'due', 
        'payment', 'renewal', 'receipt', 'statement', 'reminder'
    ]
    
    def __init__(self, db: Session):
        self.db = db
        self.encryption_key = self._get_or_create_encryption_key()
        self.fernet = Fernet(self.encryption_key)
        
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for storing tokens"""
        key_env = os.getenv('ENCRYPTION_KEY')
        if key_env:
            return key_env.encode()
        
        # Generate new key and store in environment
        key = Fernet.generate_key()
        print(f"Generated encryption key: {key.decode()}")
        print("Add this to your .env file as ENCRYPTION_KEY")
        return key
    
    def get_oauth_url(self) -> str:
        """Generate OAuth 2.0 authorization URL"""
        # Get credentials from environment or use default
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            # Use default credentials for demo
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
        # Serialize credentials
        token_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        # Encrypt token data
        encrypted_token = self.fernet.encrypt(json.dumps(token_data).encode())
        
        # Store in database
        existing_token = self.db.query(GmailToken).filter(
            GmailToken.user_id == user_id
        ).first()
        
        if existing_token:
            existing_token.encrypted_token = encrypted_token.decode()
            existing_token.expires_at = credentials.expiry
        else:
            new_token = GmailToken(
                user_id=user_id,
                encrypted_token=encrypted_token.decode(),
                expires_at=credentials.expiry
            )
            self.db.add(new_token)
        
        self.db.commit()
    
    def get_credentials(self, user_id: str) -> Optional[Credentials]:
        """Retrieve and decrypt OAuth credentials"""
        token_record = self.db.query(GmailToken).filter(
            GmailToken.user_id == user_id
        ).first()
        
        if not token_record:
            return None
        
        try:
            # Decrypt token data
            decrypted_data = self.fernet.decrypt(token_record.encrypted_token.encode())
            token_data = json.loads(decrypted_data.decode())
            
            # Create credentials object
            credentials = Credentials.from_authorized_user_info(token_data, self.SCOPES)
            
            # Refresh if expired
            if credentials.expired:
                credentials.refresh(Request())
                self.store_token(user_id, credentials)
            
            return credentials
        except Exception as e:
            print(f"Error retrieving credentials: {e}")
            return None
    
    def fetch_emails(self, user_id: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Fetch emails from Gmail matching keywords"""
        credentials = self.get_credentials(user_id)
        if not credentials:
            raise Exception("No valid Gmail credentials found")
        
        try:
            service = build('gmail', 'v1', credentials=credentials)
            
            # Build search query
            query_parts = []
            for keyword in self.SEARCH_KEYWORDS:
                query_parts.append(f'"{keyword}"')
            
            query = ' OR '.join(query_parts)
            
            # Fetch messages
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            # Fetch full message details
            emails = []
            for message in messages:
                try:
                    msg = service.users().messages().get(
                        userId='me',
                        id=message['id']
                    ).execute()
                    
                    emails.append(self._parse_email(msg))
                except Exception as e:
                    print(f"Error parsing email {message['id']}: {e}")
                    continue
            
            return emails
            
        except HttpError as error:
            print(f"Gmail API error: {error}")
            raise Exception(f"Gmail API error: {error}")
    
    def _parse_email(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Gmail message to extract relevant information"""
        headers = message['payload'].get('headers', [])
        
        # Extract headers
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
        
        # Extract body
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
        """Extract email body text from payload"""
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body']['data']
                    body += base64.urlsafe_b64decode(data).decode('utf-8')
                elif part['mimeType'] == 'text/html':
                    data = part['body']['data']
                    html_body = base64.urlsafe_b64decode(data).decode('utf-8')
                    # Simple HTML to text conversion
                    body += re.sub('<[^<]+?>', '', html_body)
        else:
            if payload['mimeType'] == 'text/plain':
                data = payload['body']['data']
                body = base64.urlsafe_b64decode(data).decode('utf-8')
            elif payload['mimeType'] == 'text/html':
                data = payload['body']['data']
                html_body = base64.urlsafe_b64decode(data).decode('utf-8')
                body = re.sub('<[^<]+?>', '', html_body)
        
        return body
    
    def parse_email_to_task(self, email_data: Dict[str, Any]) -> Optional[Task]:
        """Parse email data into a Task object"""
        subject = email_data['subject']
        body = email_data['body']
        sender = email_data['sender']
        
        # Extract task name (usually from subject)
        task_name = self._extract_task_name(subject, sender)
        
        # Extract amount
        amount = self._extract_amount(subject + " " + body)
        
        # Extract due date
        due_date = self._extract_due_date(subject + " " + body)
        
        # Determine category
        category = self._determine_category(subject, body)
        
        # Calculate priority score based on due date
        priority_score = self._calculate_priority_score(due_date)
        
        # Store source details
        source_details = {
            'email_id': email_data['id'],
            'subject': subject,
            'sender': sender,
            'date': email_data['date'],
            'body_snippet': body[:500]  # Store first 500 chars
        }
        
        return Task(
            name=task_name,
            amount=amount,
            category=category,
            due_date=due_date,
            priority_score=priority_score,
            confidence_score=0.5,  # Default confidence, will be updated by recurrence detection
            source='gmail',
            source_details=source_details,
            is_active=True
        )
    
    def _extract_task_name(self, subject: str, sender: str) -> str:
        """Extract task name from email subject and sender"""
        # Clean up subject
        subject = re.sub(r'Re:|Fwd:|FW:', '', subject, flags=re.IGNORECASE)
        subject = subject.strip()
        
        # Extract company/service name from sender
        sender_match = re.search(r'([^<]+)', sender)
        if sender_match:
            sender_name = sender_match.group(1).strip()
            # Remove common email suffixes
            sender_name = re.sub(r'\s*<.*>', '', sender_name)
            return sender_name
        
        return subject[:50]  # Fallback to subject
    
    def _extract_amount(self, text: str) -> Optional[float]:
        """Extract monetary amount from text"""
        # Look for currency patterns
        patterns = [
            r'₹\s*(\d+(?:\.\d{2})?)',
            r'Rs\.?\s*(\d+(?:\.\d{2})?)',
            r'INR\s*(\d+(?:\.\d{2})?)',
            r'\$(\d+(?:\.\d{2})?)',
            r'USD\s*(\d+(?:\.\d{2})?)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        
        return None
    
    def _extract_due_date(self, text: str) -> Optional[datetime]:
        """Extract due date from text"""
        # Common date patterns
        patterns = [
            r'due\s+(?:on\s+)?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'deadline\s+(?:is\s+)?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'pay\s+by\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    date_str = match.group(1)
                    # Try different date formats
                    for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y', '%m-%d-%Y']:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except ValueError:
                            continue
                except Exception:
                    continue
        
        return None
    
    def _determine_category(self, subject: str, body: str) -> str:
        """Determine task category based on content"""
        text = (subject + " " + body).lower()
        
        if any(word in text for word in ['subscription', 'renewal', 'premium', 'plan']):
            return 'subscription'
        elif any(word in text for word in ['bill', 'invoice', 'statement', 'payment']):
            return 'bill'
        elif any(word in text for word in ['assignment', 'homework', 'project', 'task']):
            return 'assignment'
        elif any(word in text for word in ['job', 'application', 'interview', 'resume']):
            return 'job_application'
        else:
            return 'other'
    
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
