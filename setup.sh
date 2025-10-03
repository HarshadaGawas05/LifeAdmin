#!/bin/bash

# LifeAdmin Setup Script
echo "🚀 Setting up LifeAdmin MVP..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p api/logs
mkdir -p frontend/logs

# Set up environment files
echo "⚙️  Setting up environment files..."
if [ ! -f api/.env ]; then
    cp api/env.example api/.env
    echo "✅ Created api/.env from template"
fi

# Build and start services
echo "🔨 Building and starting services..."
docker-compose build

echo "🚀 Starting all services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 15

# Check if services are running
echo "🔍 Checking service health..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API service is running"
else
    echo "❌ API service is not responding"
fi

if curl -f http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Frontend service is running"
else
    echo "❌ Frontend service is not responding"
fi

# Seed with mock data
echo "🌱 Seeding database with mock data..."
sleep 5
curl -X POST http://localhost:8000/seed/mock_subs

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📱 Access your application:"
echo "   Frontend: http://localhost:3000"
echo "   API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "🔧 Available commands:"
echo "   make up     - Start all services"
echo "   make down   - Stop all services"
echo "   make seed   - Seed with mock data"
echo "   make demo   - Run full demo"
echo "   make logs   - View logs"
echo "   make test   - Run tests"
echo ""
echo "📖 Next steps:"
echo "   1. Visit http://localhost:3000/connect"
echo "   2. Click 'Use Mock Data' to seed sample subscriptions"
echo "   3. Go to http://localhost:3000/dashboard to view your subscriptions"
echo ""

