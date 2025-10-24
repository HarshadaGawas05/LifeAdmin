"""
Gmail API Service Wrapper for LifeAdmin
Handles email fetching, parsing, and incremental sync using History API
"""

import os
import json
import base64
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email import encoders
from email.utils import parsedate_to_datetime
import re

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from models import User, RawEmail, GmailSyncState
from auth import GoogleOAuthManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GmailService:
    """Gmail API service wrapper with History API support for incremental sync"""
    
    def __init__(self, db: Session):
        self.db = db
        self.oauth_manager = GoogleOAuthManager(db)
        self.service = None
    
    def _get_service(self, email: str) -> Any:
        """Get authenticated Gmail service instance"""
        if self.service is None:
            credentials = self.oauth_manager.get_valid_credentials(email)
            if not credentials:
                raise Exception(f"No valid credentials found for user: {email}")
            
            self.service = build('gmail', 'v1', credentials=credentials)
        
        return self.service
    
    def fetch_initial_emails(self, email: str, days_back: int = 30, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch initial batch of emails for first sync
        Returns list of parsed email data
        """
        try:
            service = self._get_service(email)
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Build search query for recent emails
            query = f"after:{start_date.strftime('%Y/%m/%d')} before:{end_date.strftime('%Y/%m/%d')}"
            
            logger.info(f"Fetching initial emails for {email} from last {days_back} days")
            
            # Paginate message list and fetch details
            emails: List[Dict[str, Any]] = []
            fetched_count = 0
            page_token: Optional[str] = None
            while True:
                list_call = service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=min(500, max_results - fetched_count),
                    pageToken=page_token
                )
                results = list_call.execute()
                messages = results.get('messages', [])
                logger.info(f"Fetched list batch: {len(messages)} messages (total so far: {fetched_count + len(messages)})")

                for message in messages:
                    if fetched_count >= max_results:
                        break
                    try:
                        email_data = self._fetch_message_details(service, message['id'])
                        if email_data:
                            emails.append(email_data)
                            fetched_count += 1
                    except Exception as e:
                        logger.error(f"Error processing message {message['id']}: {e}")
                        continue

                page_token = results.get('nextPageToken')
                if not page_token or fetched_count >= max_results:
                    break
            
            logger.info(f"Successfully parsed {len(emails)} emails")
            return emails
            
        except HttpError as e:
            logger.error(f"Gmail API error during initial fetch: {e}")
            raise Exception(f"Gmail API error: {e}")
        except Exception as e:
            logger.error(f"Error fetching initial emails: {e}")
            raise Exception(f"Failed to fetch emails: {e}")
    
    def fetch_all_emails(self, email: str, max_results: int = 1000) -> List[Dict[str, Any]]:
        """
        Fetch ALL emails from Gmail for full sync
        Returns list of parsed email data
        """
        try:
            service = self._get_service(email)
            
            logger.info(f"Fetching ALL emails for {email} (max: {max_results})")
            
            # Paginate all messages and fetch details
            emails: List[Dict[str, Any]] = []
            fetched_count = 0
            page_token: Optional[str] = None
            while True:
                list_call = service.users().messages().list(
                    userId='me',
                    maxResults=min(500, max_results - fetched_count),
                    pageToken=page_token
                )
                results = list_call.execute()
                messages = results.get('messages', [])
                logger.info(f"Fetched list batch: {len(messages)} messages (total so far: {fetched_count + len(messages)})")

                for message in messages:
                    if fetched_count >= max_results:
                        break
                    try:
                        email_data = self._fetch_message_details(service, message['id'])
                        if email_data:
                            emails.append(email_data)
                            fetched_count += 1
                    except Exception as e:
                        logger.error(f"Error processing message {message['id']}: {e}")
                        continue

                page_token = results.get('nextPageToken')
                if not page_token or fetched_count >= max_results:
                    break
            
            logger.info(f"Successfully parsed {len(emails)} emails from Gmail")
            return emails
            
        except HttpError as e:
            logger.error(f"Gmail API error during full fetch: {e}")
            raise Exception(f"Gmail API error: {e}")
        except Exception as e:
            logger.error(f"Error fetching all emails: {e}")
            raise Exception(f"Failed to fetch all emails: {e}")
    
    def fetch_incremental_emails(self, email: str, last_history_id: Optional[str] = None) -> Tuple[List[Dict[str, Any]], str]:
        """
        Fetch new and modified emails using Gmail History API
        Returns (emails, new_history_id)
        """
        try:
            service = self._get_service(email)
            
            # Initialize baseline if no last_history_id provided
            if not last_history_id:
                profile = service.users().getProfile(userId='me').execute()
                baseline_history_id = profile.get('historyId')
                if not baseline_history_id:
                    raise Exception("Could not get initial historyId from Gmail profile")
                logger.info(f"Initialized baseline historyId from profile: {baseline_history_id}")
                return [], str(baseline_history_id)

            logger.info(f"Fetching incremental emails for {email} from history ID: {last_history_id}")

            emails: List[Dict[str, Any]] = []
            deleted_count = 0
            new_history_id = str(last_history_id)
            page_token: Optional[str] = None

            while True:
                try:
                    request = service.users().history().list(
                        userId='me',
                        startHistoryId=last_history_id,
                        historyTypes=['messageAdded', 'messageDeleted'],
                        maxResults=500,
                        pageToken=page_token
                    )
                    response = request.execute()
                except HttpError as e:
                    # If history is too old/invalid, reset baseline and return no changes
                    if e.resp.status == 404:
                        logger.warning(f"History ID {last_history_id} invalid/expired; resetting baseline from profile")
                        profile = service.users().getProfile(userId='me').execute()
                        baseline_history_id = profile.get('historyId')
                        return [], str(baseline_history_id)
                    raise

                history = response.get('history', [])
                for history_entry in history:
                    try:
                        for message_added in history_entry.get('messagesAdded', []):
                            message_id = message_added['message']['id']
                            email_data = self._fetch_message_details(service, message_id)
                            if email_data:
                                emails.append(email_data)

                        for message_deleted in history_entry.get('messagesDeleted', []):
                            message_id = message_deleted['message']['id']
                            if self._mark_email_deleted(message_id):
                                deleted_count += 1

                        new_history_id = history_entry.get('id', new_history_id)
                    except Exception as e:
                        logger.error(f"Error processing history entry: {e}")
                        continue

                page_token = response.get('nextPageToken')
                if not page_token:
                    break

            logger.info(f"Processed {len(emails)} emails from history, marked {deleted_count} as deleted; new_history_id={new_history_id}")
            return emails, new_history_id
            
        except HttpError as e:
            logger.error(f"Gmail API error during incremental fetch: {e}")
            raise Exception(f"Gmail API error: {e}")
        except Exception as e:
            logger.error(f"Error fetching incremental emails: {e}")
            raise Exception(f"Failed to fetch incremental emails: {e}")
    
    def _fetch_message_details(self, service: Any, message_id: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed message information"""
        try:
            message = service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            return self._parse_message(message)
            
        except HttpError as e:
            logger.error(f"Error fetching message {message_id}: {e}")
            return None
    
    def _parse_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse Gmail message into structured data"""
        try:
            headers = message['payload'].get('headers', [])
            
            # Extract headers
            subject = ""
            sender = ""
            recipient = ""
            date = ""
            thread_id = message.get('threadId', '')
            
            for header in headers:
                name = header['name'].lower()
                value = header['value']
                
                if name == 'subject':
                    subject = value
                elif name == 'from':
                    sender = value
                elif name == 'to':
                    recipient = value
                elif name == 'date':
                    date = value
            
            # Extract body
            body = self._extract_email_body(message['payload'])
            
            # Parse date
            received_at = None
            if date:
                try:
                    received_at = parsedate_to_datetime(date)
                except Exception as e:
                    logger.warning(f"Error parsing date '{date}': {e}")
            
            return {
                'message_id': message['id'],
                'thread_id': thread_id,
                'history_id': message.get('historyId'),
                'subject': subject,
                'sender': sender,
                'recipient': recipient,
                'body': body,
                'received_at': received_at,
                'raw_message': message
            }
            
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            return None
    
    def _extract_email_body(self, payload: Dict[str, Any]) -> str:
        """Extract email body text with robust HTML handling"""
        body = ""
        
        def extract_from_parts(parts):
            nonlocal body
            for part in parts:
                if part.get('parts'):
                    extract_from_parts(part['parts'])
                    continue
                
                mime_type = part.get('mimeType', '')
                data = (part.get('body') or {}).get('data')
                
                if not data:
                    continue
                
                try:
                    decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    
                    if mime_type == 'text/plain':
                        body += decoded + "\n"
                    elif mime_type == 'text/html':
                        clean_text = self._strip_html(decoded)
                        body += clean_text + "\n"
                except Exception as e:
                    logger.warning(f"Error decoding email part: {e}")
                    continue
        
        if 'parts' in payload:
            extract_from_parts(payload['parts'])
        else:
            mime_type = payload.get('mimeType', '')
            data = (payload.get('body') or {}).get('data')
            
            if data:
                try:
                    decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    if mime_type == 'text/plain':
                        body = decoded
                    elif mime_type == 'text/html':
                        body = self._strip_html(decoded)
                except Exception as e:
                    logger.warning(f"Error decoding email body: {e}")
        
        return body.strip()
    
    def _strip_html(self, html_text: str) -> str:
        """Strip HTML tags and clean text"""
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
    
    def _mark_email_deleted(self, message_id: str) -> bool:
        """Mark email as deleted in database"""
        try:
            raw_email = self.db.query(RawEmail).filter(
                RawEmail.message_id == message_id
            ).first()
            
            if raw_email and not raw_email.is_deleted:
                raw_email.is_deleted = True
                self.db.commit()
                logger.info(f"Marked email {message_id} as deleted")
                return True
            elif raw_email and raw_email.is_deleted:
                logger.debug(f"Email {message_id} already marked as deleted")
                return False
            else:
                logger.warning(f"Email {message_id} not found in database")
                return False
            
        except Exception as e:
            logger.error(f"Error marking email {message_id} as deleted: {e}")
            return False
    
    def store_emails(self, emails: List[Dict[str, Any]], user_email: str) -> Dict[str, int]:
        """
        Store emails in database
        Returns count of stored emails
        """
        try:
            # Get user
            user = self.db.query(User).filter(User.email == user_email).first()
            if not user:
                logger.error(f"User not found: {user_email}")
                return {"stored": 0, "errors": len(emails)}
            
            stored_count = 0
            error_count = 0
            
            for email_data in emails:
                try:
                    # Check if email already exists
                    existing = self.db.query(RawEmail).filter(
                        RawEmail.message_id == email_data['message_id']
                    ).first()
                    
                    if existing:
                        # Update existing record
                        existing.subject = email_data['subject']
                        existing.sender = email_data['sender']
                        existing.recipient = email_data['recipient']
                        existing.body = email_data['body']
                        existing.received_at = email_data['received_at']
                        existing.raw_payload = email_data['raw_message']
                        existing.is_deleted = False
                        existing.updated_at = datetime.utcnow()
                    else:
                        # Create new record
                        raw_email = RawEmail(
                            user_id=user.id,
                            message_id=email_data['message_id'],
                            thread_id=email_data['thread_id'],
                            history_id=email_data['history_id'],
                            subject=email_data['subject'],
                            sender=email_data['sender'],
                            recipient=email_data['recipient'],
                            body=email_data['body'],
                            received_at=email_data['received_at'],
                            raw_payload=email_data['raw_message'],
                            is_deleted=False
                        )
                        self.db.add(raw_email)
                    
                    stored_count += 1
                    
                except Exception as e:
                    logger.error(f"Error storing email {email_data.get('message_id', 'unknown')}: {e}")
                    error_count += 1
                    continue
            
            self.db.commit()
            logger.info(f"Stored {stored_count} emails, {error_count} errors")
            
            return {
                "stored": stored_count,
                "errors": error_count
            }
            
        except Exception as e:
            logger.error(f"Error storing emails: {e}")
            self.db.rollback()
            raise Exception(f"Failed to store emails: {e}")
    
    def update_sync_state(self, user_email: str, history_id: str) -> None:
        """Update Gmail sync state for user"""
        try:
            user = self.db.query(User).filter(User.email == user_email).first()
            if not user:
                logger.error(f"User not found: {user_email}")
                return
            
            sync_state = self.db.query(GmailSyncState).filter(
                GmailSyncState.user_id == user.id
            ).first()
            
            if sync_state:
                sync_state.last_history_id = history_id
                sync_state.last_synced_at = datetime.utcnow()
            else:
                sync_state = GmailSyncState(
                    user_id=user.id,
                    last_history_id=history_id,
                    last_synced_at=datetime.utcnow()
                )
                self.db.add(sync_state)
            
            self.db.commit()
            logger.info(f"Updated sync state for {user_email}: history_id={history_id}")
            
        except Exception as e:
            logger.error(f"Error updating sync state for {user_email}: {e}")
            self.db.rollback()
    
    def get_sync_state(self, user_email: str) -> Optional[Dict[str, Any]]:
        """Get current sync state for user"""
        try:
            user = self.db.query(User).filter(User.email == user_email).first()
            if not user:
                return None
            
            sync_state = self.db.query(GmailSyncState).filter(
                GmailSyncState.user_id == user.id
            ).first()
            
            if sync_state:
                return {
                    "last_history_id": sync_state.last_history_id,
                    "last_synced_at": sync_state.last_synced_at.isoformat() if sync_state.last_synced_at else None
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting sync state for {user_email}: {e}")
            return None
    
    def get_user_emails(self, user_email: str, limit: int = 50, offset: int = 0, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """Get stored emails for user with pagination.
        Dashboard rule: show emails where is_deleted = False
        """
        try:
            user = self.db.query(User).filter(User.email == user_email).first()
            if not user:
                return []
            
            query = self.db.query(RawEmail).filter(RawEmail.user_id == user.id)
            
            if not include_deleted:
                # Show not-deleted emails only
                # Dashboard rule: only show emails where is_deleted = False
                query = query.filter(RawEmail.is_deleted == False)
            
            emails = query.order_by(
                RawEmail.received_at.desc()
            ).offset(offset).limit(limit).all()
            
            return [email.to_dict() for email in emails]
            
        except Exception as e:
            logger.error(f"Error getting emails for {user_email}: {e}")
            return []
    
    def get_user_emails_with_tasks(self, user_email: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get emails for user including deleted ones that have linked tasks.
        This preserves task references even for deleted emails.
        """
        try:
            user = self.db.query(User).filter(User.email == user_email).first()
            if not user:
                return []
            
            from models import ParsedEvent, Task
            
            # Show not-deleted OR any email that has a linked parsed_event -> task
            linked_raw_ids_subq = (
                self.db.query(ParsedEvent.raw_email_id)
                .select_from(ParsedEvent)
                .join(Task, Task.name == ParsedEvent.name)
                .filter(Task.user_id == user.id)
                .subquery()
            )
            
            query = self.db.query(RawEmail).filter(
                RawEmail.user_id == user.id
            ).filter(
                (RawEmail.is_deleted == False) |
                (RawEmail.id.in_(linked_raw_ids_subq))
            )
            
            emails = query.order_by(
                RawEmail.received_at.desc()
            ).offset(offset).limit(limit).all()
            
            return [email.to_dict() for email in emails]
            
        except Exception as e:
            logger.error(f"Error getting emails with tasks for {user_email}: {e}")
            return []
    
    def search_emails(self, user_email: str, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search emails using Gmail API"""
        try:
            service = self._get_service(user_email)
            
            # Search for messages
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=limit
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            for message in messages:
                email_data = self._fetch_message_details(service, message['id'])
                if email_data:
                    emails.append(email_data)
            
            return emails
            
        except Exception as e:
            logger.error(f"Error searching emails for {user_email}: {e}")
            return []
    
    def sync_deleted_emails(self, user_email: str) -> Dict[str, int]:
        """
        Check for emails that exist in database but not in Gmail
        and mark them as deleted
        """
        try:
            service = self._get_service(user_email)
            user = self.db.query(User).filter(User.email == user_email).first()
            if not user:
                return {"checked": 0, "deleted": 0, "errors": 0}
            
            # Get all non-deleted emails from database
            db_emails = self.db.query(RawEmail).filter(
                RawEmail.user_id == user.id,
                RawEmail.is_deleted == False
            ).all()
            
            logger.info(f"Checking {len(db_emails)} emails for deletion status")
            
            deleted_count = 0
            error_count = 0
            
            for email in db_emails:
                try:
                    # Try to fetch the email from Gmail
                    message = service.users().messages().get(
                        userId='me',
                        id=email.message_id
                    ).execute()
                    
                    # If we get here, the email still exists
                    logger.debug(f"Email {email.message_id} still exists in Gmail")
                    
                except HttpError as e:
                    if e.resp.status == 404:
                        # Email not found in Gmail, mark as deleted
                        email.is_deleted = True
                        deleted_count += 1
                        logger.info(f"Email {email.message_id} not found in Gmail, marking as deleted")
                    else:
                        logger.error(f"Error checking email {email.message_id}: {e}")
                        error_count += 1
                        continue
                except Exception as e:
                    logger.error(f"Unexpected error checking email {email.message_id}: {e}")
                    error_count += 1
                    continue
            
            self.db.commit()
            
            logger.info(f"Sync deleted emails completed: {deleted_count} marked as deleted, {error_count} errors")
            
            return {
                "checked": len(db_emails),
                "deleted": deleted_count,
                "errors": error_count
            }
            
        except Exception as e:
            logger.error(f"Error syncing deleted emails for {user_email}: {e}")
            return {"checked": 0, "deleted": 0, "errors": 1}
    
    def full_sync_user_emails(self, user_email: str, max_results: int = 1000) -> Dict[str, Any]:
        """
        Perform full Gmail sync for a user:
        1. Fetch ALL emails from Gmail
        2. Insert new emails not in DB
        3. Mark emails as deleted if they exist in DB but not in Gmail
        4. Preserve task references for deleted emails
        """
        try:
            logger.info(f"Starting FULL sync for user: {user_email}")
            
            # Get user
            user = self.db.query(User).filter(User.email == user_email).first()
            if not user:
                raise Exception(f"User not found: {user_email}")
            
            # Fetch all emails from Gmail
            gmail_emails = self.fetch_all_emails(user_email, max_results)
            gmail_message_ids = {email['message_id'] for email in gmail_emails}
            
            logger.info(f"Gmail has {len(gmail_message_ids)} emails")
            
            # Get all emails from database for this user
            db_emails = self.db.query(RawEmail).filter(RawEmail.user_id == user.id).all()
            db_message_ids = {email.message_id for email in db_emails}
            
            logger.info(f"Database has {len(db_message_ids)} emails")
            
            # Process new emails from Gmail
            new_emails = []
            for gmail_email in gmail_emails:
                if gmail_email['message_id'] not in db_message_ids:
                    new_emails.append(gmail_email)
            
            # Store new emails
            new_count = 0
            for email_data in new_emails:
                try:
                    raw_email = RawEmail(
                        user_id=user.id,
                        message_id=email_data['message_id'],
                        thread_id=email_data['thread_id'],
                        history_id=email_data['history_id'],
                        subject=email_data['subject'],
                        sender=email_data['sender'],
                        recipient=email_data['recipient'],
                        body=email_data['body'],
                        received_at=email_data['received_at'],
                        raw_payload=email_data['raw_message'],
                        is_deleted=False
                    )
                    self.db.add(raw_email)
                    new_count += 1
                except Exception as e:
                    logger.error(f"Error storing new email {email_data['message_id']}: {e}")
                    continue
            
            # Mark emails as deleted if they exist in DB but not in Gmail
            deleted_count = 0
            for db_email in db_emails:
                if db_email.message_id not in gmail_message_ids and not db_email.is_deleted:
                    # Check if this email has linked tasks before marking as deleted
                    from models import ParsedEvent, Task
                    has_linked_tasks = (
                        self.db.query(ParsedEvent)
                        .select_from(ParsedEvent)
                        .join(Task, Task.name == ParsedEvent.name)
                        .filter(
                            ParsedEvent.raw_email_id == db_email.id,
                            Task.user_id == user.id
                        )
                        .first()
                    ) is not None
                    
                    if has_linked_tasks:
                        logger.info(f"Email {db_email.message_id} has linked tasks, keeping but marking as deleted")
                    else:
                        logger.info(f"Email {db_email.message_id} not in Gmail, marking as deleted")
                    
                    db_email.is_deleted = True
                    deleted_count += 1
            
            # Update sync state with current history ID
            if gmail_emails:
                # Get the latest history ID from Gmail
                service = self._get_service(user_email)
                profile = service.users().getProfile(userId='me').execute()
                current_history_id = profile.get('historyId')
                
                if current_history_id:
                    self.update_sync_state(user_email, current_history_id)
            
            self.db.commit()
            
            result = {
                "success": True,
                "message": f"Full sync completed for {user_email}",
                "gmail_emails": len(gmail_emails),
                "new_emails": new_count,
                "deleted_emails": deleted_count,
                "total_processed": len(gmail_emails) + deleted_count
            }
            
            logger.info(f"Full sync completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in full sync for {user_email}: {e}")
            self.db.rollback()
            return {
                "success": False,
                "message": f"Full sync failed for {user_email}: {str(e)}",
                "error": str(e)
            }
    
    def incremental_sync_user_emails(self, user_email: str) -> Dict[str, Any]:
        """
        Perform incremental Gmail sync for a user using History API:
        1. Get last history ID from sync state
        2. Fetch changes since last sync
        3. Process added, modified, and deleted messages
        4. Update sync state
        """
        try:
            logger.info(f"Starting INCREMENTAL sync for user: {user_email}")
            
            # Get last sync state
            sync_state = self.get_sync_state(user_email)
            last_history_id = sync_state.get("last_history_id") if sync_state else None
            
            # Fetch incremental changes
            emails, new_history_id = self.fetch_incremental_emails(user_email, last_history_id)
            
            # Store new/modified emails
            stored_count = 0
            for email_data in emails:
                try:
                    # Check if email exists
                    existing = self.db.query(RawEmail).filter(
                        RawEmail.message_id == email_data['message_id']
                    ).first()
                    
                    if existing:
                        # Update existing email
                        existing.subject = email_data['subject']
                        existing.sender = email_data['sender']
                        existing.recipient = email_data['recipient']
                        existing.body = email_data['body']
                        existing.received_at = email_data['received_at']
                        existing.raw_payload = email_data['raw_message']
                        existing.is_deleted = False
                        existing.updated_at = datetime.utcnow()
                    else:
                        # Create new email
                        user = self.db.query(User).filter(User.email == user_email).first()
                        if not user:
                            logger.error(f"User not found: {user_email}")
                            continue
                        
                        raw_email = RawEmail(
                            user_id=user.id,
                            message_id=email_data['message_id'],
                            thread_id=email_data['thread_id'],
                            history_id=email_data['history_id'],
                            subject=email_data['subject'],
                            sender=email_data['sender'],
                            recipient=email_data['recipient'],
                            body=email_data['body'],
                            received_at=email_data['received_at'],
                            raw_payload=email_data['raw_message'],
                            is_deleted=False
                        )
                        self.db.add(raw_email)
                    
                    stored_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing email {email_data.get('message_id', 'unknown')}: {e}")
                    continue
            
            # Update sync state
            self.update_sync_state(user_email, new_history_id)
            
            self.db.commit()
            
            result = {
                "success": True,
                "message": f"Incremental sync completed for {user_email}",
                "emails_processed": len(emails),
                "emails_stored": stored_count,
                "history_id": new_history_id
            }
            
            logger.info(f"Incremental sync completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in incremental sync for {user_email}: {e}")
            self.db.rollback()
            return {
                "success": False,
                "message": f"Incremental sync failed for {user_email}: {str(e)}",
                "error": str(e)
            }
