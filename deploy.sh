#!/bin/bash

# Version Monitor - Quick Docker Setup Script

set -e

echo "🚀 Version Monitor - Docker Quick Setup"
echo "========================================"
echo ""

# Check Docker installation
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first:"
    echo "   https://docs.docker.com/get-docker/"
    exit 1
fi

echo "✅ Docker found: $(docker --version)"

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "⚠️  Docker Compose not found. Installing..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

echo "✅ Docker Compose found: $(docker-compose --version)"
echo ""

# Build image
echo "📦 Building Docker image..."
docker build -t version-monitor:latest .
echo "✅ Image built successfully"
echo ""

# Create environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env created (edit it to add API_KEY if needed)"
fi

echo ""
echo "🐳 Starting container with Docker Compose..."
docker-compose up -d

echo ""
echo "✅ Version Monitor is running!"
echo ""
echo "📍 Access the application at: http://localhost:8383"
echo ""
echo "📊 Commands:"
echo "   View logs:     docker-compose logs -f"
echo "   Stop app:      docker-compose down"
echo "   Restart app:   docker-compose restart"
echo "   Container status: docker-compose ps"
echo ""
