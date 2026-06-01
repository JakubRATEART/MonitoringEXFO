.PHONY: help build up down logs restart clean status shell backup

help:
	@echo "Version Monitor - Docker Commands"
	@echo "=================================="
	@echo ""
	@echo "make build      - Build Docker image"
	@echo "make up         - Start containers"
	@echo "make down       - Stop containers"
	@echo "make restart    - Restart containers"
	@echo "make logs       - View container logs"
	@echo "make ps         - Show container status"
	@echo "make shell      - Access container shell"
	@echo "make backup     - Backup database"
	@echo "make clean      - Remove containers & volumes"
	@echo ""

build:
	@echo "🔨 Building Docker image..."
	docker build -t version-monitor:latest .
	@echo "✅ Build complete"

up:
	@echo "🚀 Starting containers..."
	docker-compose up -d
	@echo "✅ Containers started"
	@echo "📍 Access at http://localhost:8383"

down:
	@echo "🛑 Stopping containers..."
	docker-compose down
	@echo "✅ Containers stopped"

restart:
	@echo "🔄 Restarting containers..."
	docker-compose restart
	@echo "✅ Containers restarted"

logs:
	docker-compose logs -f

ps:
	docker-compose ps

shell:
	docker exec -it version-monitor /bin/bash

backup:
	@echo "💾 Backing up database..."
	@mkdir -p backups
	docker exec version-monitor cp devices.db /app/backup_$$(date +%Y%m%d_%H%M%S).db
	@echo "✅ Backup created"

clean:
	@echo "🧹 Cleaning up..."
	docker-compose down -v
	docker rmi version-monitor:latest
	@echo "✅ Cleaned up"

status:
	@echo "📊 System Status"
	@echo "================="
	@docker-compose ps
	@echo ""
	@echo "📈 Container Stats"
	@docker stats --no-stream version-monitor || echo "Container not running"
