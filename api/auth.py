"""
Google OAuth2 Authentication Module for LifeAdmin
Handles OAuth flow, token management, and credential refresh
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode

import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import User, OAuthToken

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GoogleOAuthManager:
    """Manages Google OAuth2 authentication flow and token storage"""
    
    # Required Gmail scopes
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'openid'
    ]
    
    def __init__(self, db: Session):
        self.db = db
        self.encryption_key = self._get_or_create_encryption_key()
        self.fernet = Fernet(self.encryption_key)
        
        # OAuth configuration
        self.client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self.redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:8000/auth/google/callback')
        
        if not self.client_id or not self.client_secret:
            logger.warning("Google OAuth credentials not configured. Using placeholder values.")
            self.client_id = "your-client-id.apps.googleusercontent.com"
            self.client_secret = "your-client-secret"
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for storing tokens securely"""
        key_env = os.getenv('ENCRYPTION_KEY')
        if key_env:
            return key_env.encode()
        
        # Generate new key for development
        key = Fernet.generate_key()
        logger.warning(f"Generated new encryption key: {key.decode()}")
        logger.warning("Add this to your .env file as ENCRYPTION_KEY")
        return key
    
    def get_authorization_url(self) -> str:
        """
        Generate Google OAuth2 authorization URL
        Returns the URL to redirect users to for consent
        """
        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.redirect_uri]
                    }
                },
                scopes=self.SCOPES
            )
            
            flow.redirect_uri = self.redirect_uri
            
            # Generate authorization URL with consent prompt
            auth_url, state = flow.authorization_url(
                access_type='offline',
                prompt='consent',
                include_granted_scopes='true'
            )
            
            logger.info(f"Generated authorization URL for user")
            return auth_url
            
        except Exception as e:
            logger.error(f"Error generating authorization URL: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate authorization URL")
    
    def exchange_code_for_tokens(self, authorization_code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens
        Returns user information and token data
        """
        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.redirect_uri]
                    }
                },
                scopes=self.SCOPES
            )
            
            flow.redirect_uri = self.redirect_uri
            
            # Exchange code for tokens
            flow.fetch_token(code=authorization_code)
            credentials = flow.credentials
            
            # Get user information
            user_info = self._get_user_info(credentials)
            
            # Store tokens securely
            self._store_user_tokens(user_info['email'], credentials)
            
            logger.info(f"Successfully authenticated user: {user_info['email']}")
            
            return {
                'user_info': user_info,
                'credentials': {
                    'access_token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'expires_at': credentials.expiry.isoformat() if credentials.expiry else None,
                    'scopes': credentials.scopes
                }
            }
            
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {e}")
            raise HTTPException(status_code=400, detail=f"Token exchange failed: {str(e)}")
    
    def _get_user_info(self, credentials: Credentials) -> Dict[str, Any]:
        """Get user information from Google API"""
        try:
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            
            return {
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'picture': user_info.get('picture'),
                'verified_email': user_info.get('verified_email', False)
            }
            
        except HttpError as e:
            logger.error(f"Error fetching user info: {e}")
            raise HTTPException(status_code=400, detail="Failed to fetch user information")
    
    def _store_user_tokens(self, email: str, credentials: Credentials) -> None:
        """Store encrypted OAuth tokens in database"""
        try:
            # Create or update user
            user = self.db.query(User).filter(User.email == email).first()
            if not user:
                user = User(
                    email=email,
                    name=credentials.id_token.get('name') if hasattr(credentials, 'id_token') else None,
                    picture=credentials.id_token.get('picture') if hasattr(credentials, 'id_token') else None
                )
                self.db.add(user)
                self.db.commit()
                self.db.refresh(user)
                logger.info(f"Created new user: {email}")
            else:
                # Update user info
                user.name = credentials.id_token.get('name') if hasattr(credentials, 'id_token') else user.name
                user.picture = credentials.id_token.get('picture') if hasattr(credentials, 'id_token') else user.picture
                self.db.commit()
            
            # Prepare token data for encryption
            token_data = {
                'access_token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }
            
            # Encrypt token data
            encrypted_tokens = self.fernet.encrypt(json.dumps(token_data).encode())
            
            # Store or update OAuth token
            oauth_token = self.db.query(OAuthToken).filter(
                OAuthToken.provider == 'google',
                OAuthToken.email_address == email
            ).first()
            
            if oauth_token:
                oauth_token.access_token = credentials.token
                oauth_token.encrypted_refresh_token = encrypted_tokens.decode()
                oauth_token.token_expiry = credentials.expiry
                oauth_token.scope = ','.join(credentials.scopes) if credentials.scopes else None
                oauth_token.needs_reauth = False
                oauth_token.user_id = str(user.id)
            else:
                oauth_token = OAuthToken(
                    provider='google',
                    user_id=str(user.id),
                    email_address=email,
                    access_token=credentials.token,
                    encrypted_refresh_token=encrypted_tokens.decode(),
                    token_expiry=credentials.expiry,
                    scope=','.join(credentials.scopes) if credentials.scopes else None,
                    needs_reauth=False
                )
                self.db.add(oauth_token)
            
            self.db.commit()
            logger.info(f"Stored OAuth tokens for user: {email}")
            
        except Exception as e:
            logger.error(f"Error storing tokens for user {email}: {e}")
            self.db.rollback()
            raise HTTPException(status_code=500, detail="Failed to store authentication tokens")
    
    def get_valid_credentials(self, email: str) -> Optional[Credentials]:
        """
        Get valid Gmail API credentials for a user
        Automatically refreshes tokens if needed
        """
        try:
            oauth_token = self.db.query(OAuthToken).filter(
                OAuthToken.provider == 'google',
                OAuthToken.email_address == email
            ).first()
            
            if not oauth_token:
                logger.warning(f"No OAuth token found for user: {email}")
                return None
            
            # Check if token needs refresh
            if oauth_token.needs_reauth:
                logger.warning(f"Token needs re-authentication for user: {email}")
                return None
            
            # Decrypt stored tokens
            try:
                decrypted_data = self.fernet.decrypt(oauth_token.encrypted_refresh_token.encode())
                token_data = json.loads(decrypted_data.decode())
            except Exception as e:
                logger.error(f"Failed to decrypt tokens for user {email}: {e}")
                oauth_token.needs_reauth = True
                self.db.commit()
                return None
            
            # Create credentials object
            credentials = Credentials(
                token=oauth_token.access_token,
                refresh_token=token_data.get('refresh_token'),
                token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                client_id=token_data.get('client_id', self.client_id),
                client_secret=token_data.get('client_secret', self.client_secret),
                scopes=token_data.get('scopes', self.SCOPES)
            )
            
            # Check if token is expired and refresh if needed
            if credentials.expired and credentials.refresh_token:
                try:
                    credentials.refresh(Request())
                    
                    # Update stored access token
                    oauth_token.access_token = credentials.token
                    oauth_token.token_expiry = credentials.expiry
                    self.db.commit()
                    
                    logger.info(f"Refreshed access token for user: {email}")
                    
                except Exception as e:
                    logger.error(f"Failed to refresh token for user {email}: {e}")
                    oauth_token.needs_reauth = True
                    self.db.commit()
                    return None
            
            return credentials
            
        except Exception as e:
            logger.error(f"Error getting credentials for user {email}: {e}")
            return None
    
    def revoke_tokens(self, email: str) -> bool:
        """
        Revoke OAuth tokens for a user
        Returns True if successful, False otherwise
        """
        try:
            oauth_token = self.db.query(OAuthToken).filter(
                OAuthToken.provider == 'google',
                OAuthToken.email_address == email
            ).first()
            
            if not oauth_token:
                logger.warning(f"No OAuth token found for user: {email}")
                return False
            
            # Revoke access token if available
            if oauth_token.access_token:
                try:
                    import requests
                    requests.post(
                        'https://oauth2.googleapis.com/revoke',
                        params={'token': oauth_token.access_token}
                    )
                except Exception as e:
                    logger.warning(f"Failed to revoke access token: {e}")
            
            # Remove token from database
            self.db.delete(oauth_token)
            self.db.commit()
            
            logger.info(f"Revoked tokens for user: {email}")
            return True
            
        except Exception as e:
            logger.error(f"Error revoking tokens for user {email}: {e}")
            self.db.rollback()
            return False
    
    def is_user_authenticated(self, email: str) -> bool:
        """Check if user has valid authentication tokens"""
        oauth_token = self.db.query(OAuthToken).filter(
            OAuthToken.provider == 'google',
            OAuthToken.email_address == email,
            OAuthToken.needs_reauth == False
        ).first()
        
        return oauth_token is not None
