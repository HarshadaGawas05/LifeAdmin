# Gmail Sync System - Production Guide

## Overview

This guide explains the robust Gmail integration system that provides both full and incremental synchronization with Gmail, ensuring your LifeAdmin dashboard always reflects the current state of your Gmail inbox while preserving task references.

## Core Features

### 1. Full Sync (Force Mode)
- Fetches ALL emails from Gmail
- Inserts new emails not present in database
- Marks emails as `is_deleted = TRUE` if they exist in DB but are missing in Gmail
- Preserves task references for deleted emails
- Updates sync state with current Gmail history ID

### 2. Incremental Sync (Normal Mode)
- Uses Gmail History API with `last_history_id`
- Fetches only new, modified, and deleted messages since last sync
- Efficient and fast for regular updates
- Handles `messageAdded`, `messageDeleted`, and `messageModified` events

### 3. Dashboard Behavior
- Shows emails where `is_deleted = FALSE`
- Automatically reflects new emails and deletions
- Preserves deleted emails that have linked tasks

## API Endpoints

### POST /gmail/sync/deleted
Comprehensive sync endpoint with query parameters:

**Parameters:**
- `user_email` (required): User email to sync
- `force_full_sync` (optional, default: false): Force full sync instead of incremental
- `max_results` (optional, default: 1000): Maximum emails to process (1-5000)

**Examples:**
```bash
# Incremental sync (default)
curl -X POST "http://localhost:8000/gmail/sync/deleted?user_email=user@example.com"

# Full sync
curl -X POST "http://localhost:8000/gmail/sync/deleted?user_email=user@example.com&force_full_sync=true&max_results=2000"
```

### POST /gmail/sync
Background task trigger (legacy endpoint):
```bash
curl -X POST "http://localhost:8000/gmail/sync?user_email=user@example.com" \
  -H "Content-Type: application/json" \
  -d '{"force_full_sync": true, "max_results": 1000}'
```

## Makefile Commands

### Quick Commands
```bash
# Incremental sync
make gmail-sync-deleted USER_EMAIL=user@example.com

# Full sync
make gmail-sync-full USER_EMAIL=user@example.com

# Check health
make health

# View logs
make logs
```

## Celery Background Tasks

### Automatic Sync
- **Incremental sync**: Every 5 minutes
- **Deleted email check**: Every 10 minutes
- **Token refresh**: Every hour

### Manual Trigger
```python
from tasks import sync_user_emails

# Incremental sync
task = sync_user_emails.delay("user@example.com", force_full_sync=False)

# Full sync
task = sync_user_emails.delay("user@example.com", force_full_sync=True, max_results=1000)
```

## Database Schema

### raw_emails Table
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
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### gmail_sync_state Table
```sql
CREATE TABLE gmail_sync_state (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    last_history_id BIGINT,
    last_synced_at TIMESTAMP DEFAULT NOW()
);
```

## Error Handling

### Gmail API Errors
- **Rate limits**: Automatic backoff and retry
- **Token expiry**: Automatic refresh
- **Network errors**: Retry with exponential backoff
- **Invalid credentials**: Mark user as needing reauth

### Database Errors
- **Connection issues**: Graceful degradation
- **Constraint violations**: Skip problematic records
- **Transaction failures**: Rollback and retry

### Logging
All operations are logged with structured JSON:
```json
{
  "level": "INFO",
  "message": "Full sync completed for user@example.com",
  "user_email": "user@example.com",
  "gmail_emails": 150,
  "new_emails": 5,
  "deleted_emails": 3,
  "total_processed": 155
}
```

## Production Deployment

### 1. Environment Variables
```bash
# Gmail OAuth
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/gmail/auth/callback

# Database
DATABASE_URL=postgresql://lifeadmin:lifeadmin@postgres:5432/lifeadmin

# Redis
REDIS_URL=redis://redis:6379/0

# Encryption
ENCRYPTION_KEY=your_32_byte_encryption_key
```

### 2. Docker Compose
```yaml
services:
  api:
    build: ./api
    environment:
      - DATABASE_URL=postgresql://lifeadmin:lifeadmin@postgres:5432/lifeadmin
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis

  worker:
    build: ./api
    command: celery -A celery_app.celery worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://lifeadmin:lifeadmin@postgres:5432/lifeadmin
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=lifeadmin
      - POSTGRES_USER=lifeadmin
      - POSTGRES_PASSWORD=lifeadmin

  redis:
    image: redis:7-alpine
```

### 3. Start Services
```bash
# Build and start
docker compose build
docker compose up -d

# Check health
curl http://localhost:8000/gmail/health

# View logs
docker compose logs -f worker
```

## Monitoring

### Health Check
```bash
curl http://localhost:8000/gmail/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-23T08:38:38.869034",
  "database": true,
  "redis": true,
  "gmail_api": true
}
```

### Sync Statistics
```bash
curl "http://localhost:8000/gmail/stats?user_email=user@example.com"
```

### Log Monitoring
```bash
# View all logs
docker compose logs -f

# View worker logs only
docker compose logs -f worker

# View API logs only
docker compose logs -f api
```

## Troubleshooting

### Common Issues

1. **Deleted emails still showing**
   - Run full sync: `make gmail-sync-full USER_EMAIL=user@example.com`
   - Check logs for errors

2. **New emails not appearing**
   - Check incremental sync is running (every 5 minutes)
   - Verify Gmail API credentials are valid
   - Check worker logs for errors

3. **Sync failing**
   - Check health endpoint
   - Verify database connection
   - Check Gmail API quota limits
   - Review worker logs for specific errors

4. **Tasks disappearing**
   - Deleted emails with linked tasks are preserved
   - Check `is_deleted` flag in database
   - Verify task-email relationships

### Debug Commands
```bash
# Check database
docker compose exec postgres psql -U lifeadmin -d lifeadmin -c "SELECT COUNT(*) FROM raw_emails WHERE is_deleted = false;"

# Check sync state
docker compose exec postgres psql -U lifeadmin -d lifeadmin -c "SELECT * FROM gmail_sync_state;"

# Test Gmail API
curl "http://localhost:8000/gmail/auth/url"
```

## Performance Considerations

### Full Sync
- Use sparingly (only when needed)
- Limit `max_results` to reasonable numbers
- Run during off-peak hours
- Monitor Gmail API quota

### Incremental Sync
- Very efficient for regular updates
- Minimal API calls
- Fast execution (usually < 30 seconds)

### Database Optimization
- Indexes on `message_id`, `user_id`, `is_deleted`
- Regular cleanup of old deleted emails
- Monitor database size and performance

## Security

### Token Encryption
- All OAuth tokens are encrypted before storage
- Uses Fernet symmetric encryption
- Encryption key stored in environment variables

### API Security
- User authentication required for all endpoints
- Rate limiting on API endpoints
- Input validation and sanitization

### Data Privacy
- Emails stored locally in your database
- No data sent to third parties
- Full control over your data

## Support

For issues or questions:
1. Check the logs first
2. Verify health endpoint
3. Test with manual sync commands
4. Review this documentation

The system is designed to be robust and self-healing, but manual intervention may be needed for edge cases or API quota issues.
