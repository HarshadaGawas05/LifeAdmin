@echo off
echo 🚀 Setting up LifeAdmin MVP...

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not installed. Please install Docker first.
    exit /b 1
)

REM Check if Docker Compose is installed
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker Compose is not installed. Please install Docker Compose first.
    exit /b 1
)

REM Create necessary directories
echo 📁 Creating directories...
if not exist "api\logs" mkdir api\logs
if not exist "frontend\logs" mkdir frontend\logs

REM Set up environment files
echo ⚙️  Setting up environment files...
if not exist "api\.env" (
    copy "api\env.example" "api\.env"
    echo ✅ Created api\.env from template
)

REM Build and start services
echo 🔨 Building and starting services...
docker-compose build

echo 🚀 Starting all services...
docker-compose up -d

REM Wait for services to be ready
echo ⏳ Waiting for services to start...
timeout /t 15 /nobreak >nul

REM Check if services are running
echo 🔍 Checking service health...
curl -f http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo ❌ API service is not responding
) else (
    echo ✅ API service is running
)

curl -f http://localhost:3000 >nul 2>&1
if errorlevel 1 (
    echo ❌ Frontend service is not responding
) else (
    echo ✅ Frontend service is running
)

REM Seed with mock data
echo 🌱 Seeding database with mock data...
timeout /t 5 /nobreak >nul
curl -X POST http://localhost:8000/seed/mock_subs

echo.
echo 🎉 Setup complete!
echo.
echo 📱 Access your application:
echo    Frontend: http://localhost:3000
echo    API: http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo.
echo 🔧 Available commands:
echo    make up     - Start all services
echo    make down   - Stop all services
echo    make seed   - Seed with mock data
echo    make demo   - Run full demo
echo    make logs   - View logs
echo    make test   - Run tests
echo.
echo 📖 Next steps:
echo    1. Visit http://localhost:3000/connect
echo    2. Click 'Use Mock Data' to seed sample subscriptions
echo    3. Go to http://localhost:3000/dashboard to view your subscriptions
echo.
pause

