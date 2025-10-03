# LifeAdmin Project Structure

```
lifeadmin/
├── api/                          # FastAPI Backend
│   ├── Dockerfile               # API container configuration
│   ├── requirements.txt         # Python dependencies
│   ├── env.example             # Environment variables template
│   ├── main.py                 # FastAPI application entry point
│   ├── models.py               # SQLAlchemy database models
│   ├── database.py             # Database connection and session management
│   ├── recurrence_detector.py  # Recurring subscription detection logic
│   ├── receipt_parser.py       # Receipt parsing utilities
│   ├── celery_app.py           # Celery configuration
│   ├── celery_beat_schedule.py # Periodic task scheduling
│   ├── run_worker.py           # Celery worker runner
│   ├── run_beat.py             # Celery beat scheduler runner
│   └── tests/                  # Test suite
│       ├── __init__.py
│       └── test_recurrence_detection.py
│
├── frontend/                    # Next.js Frontend
│   ├── Dockerfile              # Frontend container configuration
│   ├── package.json            # Node.js dependencies
│   ├── next.config.js          # Next.js configuration
│   ├── tailwind.config.js      # Tailwind CSS configuration
│   ├── postcss.config.js       # PostCSS configuration
│   ├── tsconfig.json           # TypeScript configuration
│   └── app/                    # Next.js 13+ app directory
│       ├── globals.css         # Global styles
│       ├── layout.tsx          # Root layout component
│       ├── page.tsx            # Home page
│       ├── connect/            # Data connection page
│       │   └── page.tsx
│       └── dashboard/          # Dashboard page
│           └── page.tsx
│
├── scripts/                     # Helper Scripts
│   ├── seed_plaid.py           # CSV import script
│   └── sample_transactions.csv # Sample transaction data
│
├── docker-compose.yml          # Multi-service orchestration
├── Makefile                    # Development commands
├── setup.sh                    # Linux/Mac setup script
├── setup.bat                   # Windows setup script
├── .gitignore                  # Git ignore rules
├── README.md                   # Project documentation
└── PROJECT_STRUCTURE.md        # This file
```

## Service Architecture

### Backend Services
- **API (FastAPI)**: REST API server on port 8000
- **Worker (Celery)**: Background task processor
- **Database (PostgreSQL)**: Primary data storage on port 5432
- **Cache (Redis)**: Task queue and caching on port 6379
- **Vector DB (Qdrant)**: Vector storage for future ML features on port 6333

### Frontend Services
- **Frontend (Next.js)**: React application on port 3000

## Key Features Implemented

### Backend Features
✅ **Receipt Upload & Parsing**: Multipart file upload with text/EML parsing
✅ **Recurrence Detection**: Algorithm to detect monthly recurring subscriptions
✅ **Mock Data Seeding**: Pre-populated sample subscriptions
✅ **Background Tasks**: Celery worker for async processing
✅ **Source Transparency**: Track origin of each detected subscription
✅ **REST API**: Complete CRUD operations for subscriptions
✅ **Database Models**: SQLAlchemy models for transactions and subscriptions

### Frontend Features
✅ **Connect Page**: Mock Gmail, file upload, and mock data options
✅ **Dashboard**: Subscription overview with spending analytics
✅ **Action Buttons**: Cancel, Snooze, Auto-pay with mock confirmations
✅ **Source Inspector**: Modal showing subscription source details
✅ **Responsive Design**: Tailwind CSS with mobile-friendly layout
✅ **TypeScript**: Full type safety throughout the application

### DevOps Features
✅ **Docker Compose**: One-command local development setup
✅ **Health Checks**: Service health monitoring
✅ **Environment Configuration**: Flexible environment variable setup
✅ **Automated Setup**: Platform-specific setup scripts
✅ **Testing**: Pytest test suite for core functionality
✅ **Documentation**: Comprehensive README and project structure docs

## Data Flow

1. **Data Ingestion**: Users upload receipts or use mock data
2. **Parsing**: Receipt parser extracts merchant, amount, date
3. **Storage**: Transactions stored in PostgreSQL
4. **Detection**: Background worker runs recurrence detection algorithm
5. **Aggregation**: Detected subscriptions stored with confidence scores
6. **Display**: Frontend fetches and displays subscription dashboard
7. **Actions**: Users can cancel, snooze, or setup auto-pay (mock)

## Technology Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy, Celery, Redis
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, Axios
- **Database**: PostgreSQL 15
- **Cache/Queue**: Redis 7
- **Vector DB**: Qdrant
- **Containerization**: Docker, Docker Compose
- **Testing**: Pytest, Jest (ready for frontend tests)

