# Gmail Integration Module for LifeAdmin

A comprehensive Gmail integration module that provides OAuth2 authentication, email fetching, incremental sync using Gmail History API, and background processing for LifeAdmin.

## Features

- **Google OAuth2 Authentication**: Secure token management with automatic refresh
- **Initial Email Sync**: Fetch last 30 days of emails on first connection
- **Incremental Sync**: Use Gmail History API for efficient updates
- **Background Processing**: Celery tasks for auto-sync and maintenance
- **Email Management**: Store, search, and manage emails in PostgreSQL
- **RESTful API**: Clean FastAPI endpoints for frontend integration
- **Error Handling**: Graceful handling of expired tokens and API limits

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI        │    │   Gmail API     │
│   (Next.js)     │◄──►│   (Python)       │◄──►│   (Google)      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │   PostgreSQL     │
                       │   (Database)     │
                       └──────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │   Celery + Redis │
                       │   (Background)   │
                       └──────────────────┘
```

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    name VARCHAR,
    picture VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Raw Emails Table
```sql
CREATE TABLE raw_emails (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    message_id VARCHAR UNIQUE,
    thread_id VARCHAR,
    history_id BIGINT,
    subject TEXT,
    sender TEXT,
    recipient TEXT,
    snippet TEXT,
    body TEXT,
    received_at TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Gmail Sync State Table
```sql
CREATE TABLE gmail_sync_state (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    last_history_id BIGINT,
    last_synced_at TIMESTAMP DEFAULT NOW()
);
```

## API Endpoints

### Authentication
- `GET /gmail/auth/url` - Get Google OAuth authorization URL
- `GET /gmail/auth/callback` - Handle OAuth callback
- `DELETE /gmail/auth/revoke` - Revoke user authentication

### Email Management
- `GET /gmail/emails` - Get user's emails (paginated)
- `POST /gmail/search` - Search emails using Gmail API
- `GET /gmail/emails/{email_id}` - Get specific email details

### Sync Operations
- `POST /gmail/sync` - Trigger manual sync for user
- `POST /gmail/sync/all` - Trigger sync for all users
- `GET /gmail/sync-state` - Get sync state for user

### Statistics & Health
- `GET /gmail/stats` - Get Gmail statistics for user
- `GET /gmail/health` - Check Gmail integration health

## Setup Instructions

### 1. Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (optional)

### 2. Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Gmail API
4. Create OAuth 2.0 credentials:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:8000/auth/google/callback`
5. Download credentials JSON file

### 3. Environment Configuration

Copy `api/env.example` to `api/.env` and configure:

```bash
# Database Configuration
DATABASE_URL=postgresql://lifeadmin:lifeadmin@localhost:5432/lifeadmin
REDIS_URL=redis://localhost:6379/0

# Google OAuth2 Configuration
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Security Configuration
ENCRYPTION_KEY=your-32-character-encryption-key-here
APP_JWT_SECRET=your-jwt-secret-key-here

# Frontend Configuration
FRONTEND_URL=http://localhost:3000
```

### 4. Database Setup

```bash
# Create database
createdb lifeadmin

# Run migrations
cd api
alembic upgrade head
```

### 5. Installation

#### Option A: Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api
```

#### Option B: Local Development

```bash
# Install dependencies
cd api
pip install -r requirements.txt

# Start Redis
redis-server

# Start Celery worker
celery -A celery_app worker --loglevel=info

# Start Celery beat (in another terminal)
celery -A celery_app beat --loglevel=info

# Start FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Make Commands

Create a `Makefile` in the project root:

```makefile
.PHONY: help install dev test clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	cd api && pip install -r requirements.txt
	cd frontend && npm install

dev: ## Start development environment
	docker-compose up -d postgres redis
	cd api && uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-full: ## Start full development environment with all services
	docker-compose up -d

test: ## Run tests
	cd api && python -m pytest tests/

clean: ## Clean up containers and volumes
	docker-compose down -v
	docker system prune -f

migrate: ## Run database migrations
	cd api && alembic upgrade head

seed: ## Seed database with sample data
	cd api && python -c "from main import *; print('Database seeded')"

logs: ## View application logs
	docker-compose logs -f api worker

health: ## Check service health
	curl http://localhost:8000/gmail/health
```

## Usage Examples

### 1. User Authentication Flow

```python
# Get authorization URL
response = requests.get("http://localhost:8000/gmail/auth/url")
auth_url = response.json()["auth_url"]

# User visits auth_url and authorizes
# Google redirects to callback with code

# Exchange code for tokens
response = requests.get(
    "http://localhost:8000/gmail/auth/callback",
    params={"code": "authorization_code"}
)
```

### 2. Email Sync

```python
# Trigger manual sync
response = requests.post(
    "http://localhost:8000/gmail/sync",
    params={"user_email": "user@example.com"},
    json={"force_full_sync": False, "max_results": 100}
)
```

### 3. Get User Emails

```python
# Get paginated emails
response = requests.get(
    "http://localhost:8000/gmail/emails",
    params={
        "user_email": "user@example.com",
        "page": 1,
        "page_size": 50
    }
)
emails = response.json()["emails"]
```

### 4. Search Emails

```python
# Search emails
response = requests.post(
    "http://localhost:8000/gmail/search",
    params={"user_email": "user@example.com"},
    json={"query": "from:netflix.com subscription", "limit": 20}
)
```

## Background Tasks

The system includes several background tasks managed by Celery:

- **Email Sync** (every 5 minutes): Sync emails for all authenticated users
- **Token Refresh** (every hour): Refresh expired OAuth tokens
- **Health Check** (every 15 minutes): Monitor system health
- **Email Classification** (every 30 minutes): Process pending email classifications
- **Cleanup** (weekly): Remove old deleted emails

## Error Handling

The system gracefully handles:

- **Expired Tokens**: Automatic refresh with fallback to re-authentication
- **API Rate Limits**: Exponential backoff and retry logic
- **Network Issues**: Retry mechanisms with circuit breakers
- **Database Errors**: Transaction rollback and error logging

## Security Considerations

- **Token Encryption**: OAuth tokens are encrypted using Fernet
- **Secure Storage**: Credentials stored in environment variables
- **HTTPS**: Use HTTPS in production for OAuth callbacks
- **Token Expiry**: Automatic token refresh and cleanup

## Monitoring & Logging

- **Structured Logging**: JSON format for easy parsing
- **Health Checks**: Regular system health monitoring
- **Metrics**: Email sync statistics and performance metrics
- **Error Tracking**: Comprehensive error logging and alerting

## Troubleshooting

### Common Issues

1. **OAuth Errors**: Check client ID/secret and redirect URI
2. **Database Connection**: Verify PostgreSQL is running and accessible
3. **Redis Connection**: Ensure Redis is running for Celery
4. **Token Refresh**: Check encryption key and token storage

### Debug Commands

```bash
# Check service health
curl http://localhost:8000/gmail/health

# View Celery tasks
celery -A celery_app inspect active

# Check database connection
psql -h localhost -U lifeadmin -d lifeadmin -c "SELECT 1;"

# View logs
docker-compose logs -f api worker
```

## Production Deployment

1. **Environment Variables**: Set all required environment variables
2. **Database**: Use managed PostgreSQL service
3. **Redis**: Use managed Redis service
4. **SSL**: Configure HTTPS for OAuth callbacks
5. **Monitoring**: Set up application monitoring and alerting
6. **Scaling**: Use multiple Celery workers for high throughput

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
