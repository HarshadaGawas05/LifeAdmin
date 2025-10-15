# LifeAdmin MVP

A comprehensive life administration tool for managing recurring subscriptions, bills, assignments, and tasks. Built with modern web technologies and designed for production scalability.

## 🚀 Features

### Core Functionality
- **Unified Task Management**: Handle subscriptions, bills, assignments, and job applications in one place
- **Gmail Integration**: Automatically import tasks from emails with OAuth 2.0
- **Receipt Upload**: Parse receipt files to extract transaction data
- **Recurrence Detection**: Smart detection of recurring patterns with confidence scoring
- **Priority Scoring**: Automatic priority calculation based on due dates and urgency
- **Source Transparency**: Full visibility into data sources and parsing details

### Dashboard Features
- **Task Overview**: View all tasks with filtering by category, source, and status
- **Monthly Spend Tracking**: Monitor total monthly expenses
- **Action Buttons**: Cancel, snooze, or setup auto-pay for tasks
- **Confidence Indicators**: Visual confidence scores for recurrence detection
- **Source Inspector**: Detailed view of parsed email data and source information

### Technical Features
- **Privacy-First**: Gmail tokens encrypted at rest
- **Production-Ready**: Docker containerization with health checks
- **Scalable Architecture**: FastAPI backend with Celery for background processing
- **Modern Frontend**: Next.js with Tailwind CSS
- **Vector Search**: Qdrant integration for similarity matching (optional)

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Database      │
│   (Next.js)     │◄──►│   (FastAPI)     │◄──►│   (PostgreSQL)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       ▼                       │
         │              ┌─────────────────┐              │
         │              │   Background    │              │
         │              │   (Celery)      │              │
         │              └─────────────────┘              │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Gmail API     │    │   Redis Cache   │    │   Qdrant Vector │
│   (OAuth 2.0)   │    │                 │    │   (Optional)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🛠️ Tech Stack

### Backend
- **Python 3.11** - Core runtime
- **FastAPI** - Web framework with automatic API documentation
- **SQLAlchemy** - ORM for database operations
- **PostgreSQL** - Primary database
- **Redis** - Caching and background job queue
- **Celery** - Background task processing
- **Google API Client** - Gmail integration
- **Cryptography** - Token encryption
- **Pandas** - Data analysis for recurrence detection

### Frontend
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS** - Utility-first CSS framework
- **Axios** - HTTP client for API communication

### Infrastructure
- **Docker** - Containerization
- **Docker Compose** - Multi-container orchestration
- **Qdrant** - Vector database for similarity search (optional)

## 📋 Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone <repository-url>
cd LifeAdmin
```

### 2. Environment Setup
```bash
# Copy environment template
cp env.example .env

# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Add the generated key to .env as ENCRYPTION_KEY
```

### 3. Start the Application
```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

### 4. Access the Application
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Qdrant Dashboard**: http://localhost:6333/dashboard

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://lifeadmin:lifeadmin@postgres:5432/lifeadmin` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `QDRANT_URL` | Qdrant connection string | `http://qdrant:6333` |
| `ENCRYPTION_KEY` | Encryption key for Gmail tokens | Required |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Required for Gmail |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | Required for Gmail |
| `NEXT_PUBLIC_API_URL` | Frontend API URL | `http://localhost:8000` |

### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Gmail API
4. Create OAuth 2.0 credentials
5. Add authorized redirect URIs:
   - `http://localhost:3000/connect` (development)
   - `https://yourdomain.com/connect` (production)
6. Copy client ID and secret to `.env` file

## 📊 Usage

### 1. Connect Data Sources

#### Mock Data (Recommended for Testing)
- Click "Use Mock Data" on the connect page
- Creates sample subscriptions, bills, and tasks
- Perfect for testing the dashboard functionality

#### Gmail Integration
- Click "Connect Gmail (Demo)" on the connect page
- In production, this would open OAuth flow
- Currently uses mock email data for demonstration
- Parses emails for bills, subscriptions, assignments, and job applications

#### Receipt Upload
- Upload `.txt` or `.eml` files
- Automatically extracts merchant, amount, and date
- Creates transaction records for analysis

### 2. Dashboard Features

#### Task Management
- View all tasks with filtering options
- See confidence scores for recurrence detection
- Monitor priority scores based on due dates
- Track monthly spending totals

#### Actions
- **Cancel**: Mark task as inactive (mock implementation)
- **Snooze**: Extend due date by specified days
- **Auto-pay**: Setup automatic payments (mock implementation)

#### Source Transparency
- Click "View Source" to see parsed email data
- View confidence and priority scores
- Inspect source details and parsing information

### 3. Recurrence Detection

The system automatically:
- Groups similar tasks by name
- Analyzes patterns in due dates and amounts
- Calculates confidence scores based on consistency
- Identifies recurring subscriptions and bills
- Updates confidence scores as more data is collected

## 🔒 Privacy & Security

### Data Protection
- Gmail OAuth tokens are encrypted at rest
- All data stays in your local database
- No external API calls for task management
- Source transparency shows exactly what data was parsed

### Gmail Integration
- Uses OAuth 2.0 for secure authentication
- Only reads emails (no write permissions)
- Tokens are encrypted and stored locally
- Can be disconnected at any time

## 🧪 Testing

### Mock Data
The application includes comprehensive mock data for testing:
- Netflix subscription (₹499/month)
- Spotify Premium (₹199/month)
- PayTM Electricity Bill (₹1200/month)
- Project Assignment (due in 7 days)
- Job Application (Google, due in 14 days)

### API Testing
Use the built-in API documentation at http://localhost:8000/docs to test endpoints.

## 🚀 Production Deployment

### Docker Deployment
```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up -d

# Scale services
docker-compose -f docker-compose.prod.yml up -d --scale worker=3
```

### Security
- Tokens encrypted with `cryptography.Fernet` using `ENCRYPTION_KEY` from `.env` stored in `oauth_tokens`.
- Request only minimum Gmail scope: `https://www.googleapis.com/auth/gmail.readonly`.
- To delete user data: remove rows from `oauth_tokens`, `raw_emails`, `parsed_events`, and related `tasks`.

### Environment Configuration
- Set production environment variables
- Configure proper database credentials
- Set up SSL certificates
- Configure domain names
- Set up monitoring and logging

### Database Migration
```bash
# Run database migrations
docker-compose exec api alembic upgrade head

# Create initial data
docker-compose exec api python -c "from main import seed_mock_tasks; seed_mock_tasks()"
```

## 🔧 Development

### Local Development Setup
```bash
# Backend development
cd api
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend development
cd frontend
npm install
npm run dev

# Database setup
createdb lifeadmin
python -c "from database import create_tables; create_tables()"
```

### Code Structure
```
LifeAdmin/
├── api/                    # Backend API
│   ├── main.py            # FastAPI application
│   ├── models.py          # Database models
│   ├── gmail_integration.py # Gmail OAuth and parsing
│   ├── enhanced_recurrence_detector.py # Recurrence detection
│   ├── receipt_parser.py  # Receipt parsing logic
│   └── requirements.txt   # Python dependencies
├── frontend/              # Frontend application
│   ├── app/              # Next.js app directory
│   │   ├── page.tsx      # Homepage
│   │   ├── connect/      # Data connection page
│   │   └── dashboard/    # Task dashboard
│   ├── package.json      # Node.js dependencies
│   └── tailwind.config.js # Tailwind configuration
├── docker-compose.yml    # Container orchestration
└── README.md            # This file
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

### Common Issues

#### Docker Issues
```bash
# Reset containers
docker-compose down -v
docker system prune -f
docker-compose up -d
```

#### Database Issues
```bash
# Reset database
docker-compose down -v
docker-compose up -d
```

#### Gmail Integration Issues
- Verify OAuth credentials in `.env`
- Check redirect URIs in Google Cloud Console
- Ensure Gmail API is enabled

### Getting Help
- Check the API documentation at http://localhost:8000/docs
- Review the source code comments
- Open an issue on GitHub

## 🎯 Roadmap

### Phase 1 (Current)
- ✅ Gmail OAuth integration
- ✅ Task management system
- ✅ Recurrence detection
- ✅ Dashboard with actions
- ✅ Source transparency

### Phase 2 (Future)
- [ ] Real Gmail API integration
- [ ] Plaid financial data integration
- [ ] PayTM bill integration
- [ ] Automated payment execution
- [ ] Mobile app
- [ ] Advanced analytics
- [ ] Team collaboration features

## 🙏 Acknowledgments

- Built with FastAPI and Next.js
- Uses Google Gmail API for email integration
- Powered by PostgreSQL and Redis
- Styled with Tailwind CSS
- Containerized with Docker

---

**LifeAdmin MVP** - Take control of your recurring subscriptions and expenses with intelligent automation and transparency.