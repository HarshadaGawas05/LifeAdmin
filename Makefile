.PHONY: up down seed demo test logs clean migrate

# Start all services
up:
	docker-compose up -d

# Stop all services
down:
	docker-compose down

# Seed database with mock data
seed:
	docker-compose exec api python -c "import requests; requests.post('http://localhost:8000/tasks/seed')"
## Run Alembic migrations
migrate:
	docker-compose exec api alembic upgrade head

# Run full demo workflow
demo: up
	@echo "Waiting for services to start..."
	@sleep 10
	@echo "Seeding mock data..."
	@make seed
	@echo "Demo ready! Visit http://localhost:3000/connect"

# Run tests
test:
	docker-compose exec api python -m pytest tests/ -v

# View logs from all services
logs:
	docker-compose logs -f

# Clean up everything
clean:
	docker-compose down -v
	docker system prune -f

# Build and start services
build:
	docker-compose build

# Restart specific service
restart-api:
	docker-compose restart api

restart-worker:
	docker-compose restart worker

restart-frontend:
	docker-compose restart frontend

