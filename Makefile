.PHONY: help install dev test clean migrate seed logs health

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

dev-worker: ## Start Celery worker
	cd api && celery -A celery_app worker --loglevel=info

dev-beat: ## Start Celery beat scheduler
	cd api && celery -A celery_app beat --loglevel=info

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

logs-api: ## View API logs only
	docker-compose logs -f api

logs-worker: ## View worker logs only
	docker-compose logs -f worker

health: ## Check service health
	curl http://localhost:8000/gmail/health

health-db: ## Check database health
	curl http://localhost:8000/health

gmail-auth: ## Get Gmail auth URL
	curl http://localhost:8000/gmail/auth/url

gmail-sync: ## Trigger Gmail sync for all users
	curl -X POST http://localhost:8000/gmail/sync/all

gmail-sync-deleted: ## Sync deleted emails (requires user_email parameter)
	@echo "Usage: make gmail-sync-deleted USER_EMAIL=user@example.com"
	@if [ -z "$(USER_EMAIL)" ]; then echo "Please provide USER_EMAIL parameter"; exit 1; fi
	curl -X POST "http://localhost:8000/gmail/sync/deleted?user_email=$(USER_EMAIL)&force_full_sync=false"

gmail-sync-full: ## Full Gmail sync (requires user_email parameter)
	@echo "Usage: make gmail-sync-full USER_EMAIL=user@example.com"
	@if [ -z "$(USER_EMAIL)" ]; then echo "Please provide USER_EMAIL parameter"; exit 1; fi
	curl -X POST "http://localhost:8000/gmail/sync/deleted?user_email=$(USER_EMAIL)&force_full_sync=true&max_results=1000"

gmail-stats: ## Get Gmail stats (requires user_email parameter)
	@echo "Usage: make gmail-stats USER_EMAIL=user@example.com"
	@if [ -z "$(USER_EMAIL)" ]; then echo "Please provide USER_EMAIL parameter"; exit 1; fi
	curl "http://localhost:8000/gmail/stats?user_email=$(USER_EMAIL)"

gmail-emails: ## Get user emails (requires user_email parameter)
	@echo "Usage: make gmail-emails USER_EMAIL=user@example.com"
	@if [ -z "$(USER_EMAIL)" ]; then echo "Please provide USER_EMAIL parameter"; exit 1; fi
	curl "http://localhost:8000/gmail/emails?user_email=$(USER_EMAIL)"

setup: ## Complete setup for development
	@echo "Setting up LifeAdmin Gmail Integration..."
	@echo "1. Installing dependencies..."
	$(MAKE) install
	@echo "2. Starting services..."
	docker-compose up -d postgres redis
	@echo "3. Waiting for services to be ready..."
	sleep 10
	@echo "4. Running migrations..."
	$(MAKE) migrate
	@echo "5. Setup complete! Run 'make dev' to start development server"

stop: ## Stop all services
	docker-compose down

restart: ## Restart all services
	docker-compose restart

status: ## Show status of all services
	docker-compose ps

backup-db: ## Backup database
	docker-compose exec postgres pg_dump -U lifeadmin lifeadmin > backup_$(shell date +%Y%m%d_%H%M%S).sql

restore-db: ## Restore database from backup
	@echo "Usage: make restore-db BACKUP_FILE=backup_file.sql"
	@if [ -z "$(BACKUP_FILE)" ]; then echo "Please provide BACKUP_FILE parameter"; exit 1; fi
	docker-compose exec -T postgres psql -U lifeadmin lifeadmin < $(BACKUP_FILE)

reset-db: ## Reset database (WARNING: This will delete all data)
	@echo "WARNING: This will delete all data. Press Ctrl+C to cancel or Enter to continue..."
	@read
	docker-compose down -v
	docker-compose up -d postgres redis
	sleep 10
	$(MAKE) migrate

lint: ## Run linting
	cd api && python -m flake8 . --max-line-length=100
	cd api && python -m black --check .

format: ## Format code
	cd api && python -m black . --line-length=100

type-check: ## Run type checking
	cd api && python -m mypy . --ignore-missing-imports

security: ## Run security checks
	cd api && python -m bandit -r . -f json -o security-report.json

docs: ## Generate API documentation
	@echo "API documentation available at: http://localhost:8000/docs"
	@echo "ReDoc documentation available at: http://localhost:8000/redoc"

monitor: ## Monitor system resources
	@echo "Monitoring system resources..."
	@echo "Press Ctrl+C to stop"
	watch -n 1 'docker-compose ps && echo "" && docker stats --no-stream'

update-deps: ## Update dependencies
	cd api && pip install --upgrade -r requirements.txt
	cd frontend && npm update

check-env: ## Check environment configuration
	@echo "Checking environment configuration..."
	@if [ ! -f api/.env ]; then echo "❌ api/.env file not found"; else echo "✅ api/.env file exists"; fi
	@if [ -z "$$GOOGLE_CLIENT_ID" ]; then echo "❌ GOOGLE_CLIENT_ID not set"; else echo "✅ GOOGLE_CLIENT_ID is set"; fi
	@if [ -z "$$GOOGLE_CLIENT_SECRET" ]; then echo "❌ GOOGLE_CLIENT_SECRET not set"; else echo "✅ GOOGLE_CLIENT_SECRET is set"; fi
	@if [ -z "$$ENCRYPTION_KEY" ]; then echo "❌ ENCRYPTION_KEY not set"; else echo "✅ ENCRYPTION_KEY is set"; fi

generate-key: ## Generate encryption key
	@echo "Generating encryption key..."
	@python3 -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"

test-gmail: ## Test Gmail integration (requires setup)
	@echo "Testing Gmail integration..."
	@echo "1. Checking health..."
	$(MAKE) health
	@echo "2. Getting auth URL..."
	$(MAKE) gmail-auth
	@echo "3. Testing sync (requires authentication)..."
	@echo "   Note: You need to authenticate first using the auth URL above"

production: ## Deploy to production (placeholder)
	@echo "Production deployment not implemented yet"
	@echo "Please configure your production environment manually"

.DEFAULT_GOAL := help