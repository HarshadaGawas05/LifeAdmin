# LifeAdmin MVP

A comprehensive life administration tool that helps you track and manage recurring subscriptions and expenses.

## Features

- **Receipt Upload**: Upload receipts and automatically parse transaction data
- **Gmail Integration**: Connect Gmail to automatically import receipts (demo mode)
- **Recurrence Detection**: Automatically detect recurring subscriptions from transaction history
- **Dashboard**: View all subscriptions with spending analytics and management actions
- **Source Transparency**: Track the origin of each detected subscription

## Quick Start

### Option 1: Automated Setup (Recommended)

**Windows:**
```cmd
setup.bat
```

**Linux/Mac:**
```bash
chmod +x setup.sh
./setup.sh
```

### Option 2: Manual Setup

1. **Start all services**:
   ```bash
   make up
   ```

2. **Seed with mock data**:
   ```bash
   make seed
   ```

3. **Visit the application**:
   - Frontend: http://localhost:3000
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

4. **Demo workflow**:
   - Go to http://localhost:3000/connect
   - Click "Use Mock Data" to seed sample subscriptions
   - Navigate to http://localhost:3000/dashboard to view detected subscriptions

## Architecture

- **Frontend**: Next.js + TypeScript + Tailwind CSS
- **Backend**: FastAPI + SQLAlchemy + Celery
- **Database**: PostgreSQL
- **Cache/Queue**: Redis
- **Vector DB**: Qdrant (for future ML features)
- **Containerization**: Docker Compose

## Development

### Prerequisites

- Docker and Docker Compose
- Git
- Make (optional, for using Makefile commands)

### Available Commands

- `make up` or `docker-compose up -d` - Start all services
- `make down` or `docker-compose down` - Stop all services
- `make seed` - Seed database with mock data
- `make demo` - Run full demo workflow
- `make test` - Run tests
- `make logs` - View logs from all services
- `make clean` - Clean up everything (removes volumes)

### Windows Users

If you don't have Make installed, you can use these Docker Compose commands directly:

```cmd
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Seed mock data
curl -X POST http://localhost:8000/seed/mock_subs
```

### Project Structure

```
lifeadmin/
├── api/                 # FastAPI backend
├── frontend/           # Next.js frontend
├── docker-compose.yml  # Service orchestration
├── Makefile           # Development commands
└── scripts/           # Helper scripts
```

## API Endpoints

- `POST /seed/mock_subs` - Seed database with mock subscriptions
- `POST /upload/receipt` - Upload and parse receipt files
- `GET /dashboard` - Get dashboard data with detected subscriptions

## Environment Variables

See individual service directories for environment configuration.
