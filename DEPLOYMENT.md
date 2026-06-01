# Deployment Guide - Version Monitor

Complete guide to run the Version Monitor application on a server and dockerize it.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Docker Setup](#docker-setup)
4. [Server Deployment](#server-deployment)
5. [Production Best Practices](#production-best-practices)

---

## Prerequisites

### For Local Development
- Python 3.11+
- pip (Python package manager)

### For Docker Deployment
- Docker 20.10+
- Docker Compose 1.29+ (optional but recommended)

**Install Docker:**
- **Windows/Mac:** [Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Linux:**
  ```bash
  curl -fsSL https://get.docker.com -o get-docker.sh
  sudo sh get-docker.sh
  ```

---

## Local Development

### Step 1: Install Dependencies
```bash
cd c:/Users/jakub.rogowski/Monitoring_App
pip install -r requirements.txt
```

### Step 2: Run the Application
```bash
python app.py
```

**Output:**
```
Starting Version Monitor server...
Open http://127.0.0.1:8383 in your browser
```

Access at: `http://127.0.0.1:8383`

---

## Docker Setup

### Step 1: Verify Docker Installation
```bash
docker --version
docker run hello-world
```

### Step 2: Build the Docker Image

**Navigate to project directory:**
```bash
cd c:/Users/jakub.rogowski/Monitoring_App
```

**Build the image:**
```bash
docker build -t version-monitor:latest .
```

**Expected output:**
```
[+] Building 45.2s (12/12) FINISHED
 => Successfully tagged version-monitor:latest
```

### Step 3: Run the Container

**Basic run:**
```bash
docker run -p 8383:8383 \
  --name version-monitor \
  version-monitor:latest
```

**With API key:**
```bash
docker run -p 8383:8383 \
  -e API_KEY="your-secret-key" \
  --name version-monitor \
  version-monitor:latest
```

**With persistent database volume:**
```bash
docker run -p 8383:8383 \
  -v version-monitor-data:/app \
  --name version-monitor \
  version-monitor:latest
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8383
```

Access at: `http://localhost:8383`

### Step 4: Verify Container is Running
```bash
docker ps
```

Output should show your container:
```
CONTAINER ID  IMAGE                PORTS              NAMES
abc123def456  version-monitor:latest  0.0.0.0:8383->8383/tcp  version-monitor
```

### Step 5: View Logs
```bash
docker logs version-monitor
docker logs -f version-monitor  # Follow logs
```

### Step 6: Stop/Restart Container
```bash
docker stop version-monitor
docker start version-monitor
docker restart version-monitor
```

---

## Docker Compose (Easier Management)

### Step 1: Create Environment File
```bash
cp .env.example .env
```

Edit `.env` and set your API_KEY if needed:
```
API_KEY=your-secret-key-here
```

### Step 2: Start with Docker Compose
```bash
docker-compose up -d
```

**Flags:**
- `-d` = run in background (detached)
- `-v` = verbose output
- `--build` = rebuild image before starting

### Step 3: View Status
```bash
docker-compose ps
docker-compose logs -f
```

### Step 4: Stop Services
```bash
docker-compose down
docker-compose down -v  # Also remove volumes
```

---

## Server Deployment

### Option 1: Linux Server (Ubuntu/Debian)

#### Setup VPS/Server

1. **SSH into server:**
```bash
ssh root@your-server-ip
```

2. **Update system:**
```bash
apt update && apt upgrade -y
```

3. **Install Docker & Docker Compose:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker
```

4. **Clone or upload your application:**
```bash
# Option A: Clone from git
git clone https://github.com/your-repo/monitoring-app.git
cd monitoring-app

# Option B: Upload files
scp -r ./Monitoring_App root@your-server-ip:/root/
cd monitoring-app
```

5. **Create environment file:**
```bash
cat > .env << EOF
API_KEY=your-production-key
EOF
```

6. **Start application:**
```bash
docker-compose up -d
```

7. **Verify it's running:**
```bash
docker-compose ps
curl http://localhost:8383
```

#### Access from Remote
- Local machine: `http://your-server-ip:8383`
- Or setup reverse proxy (see below)

---

### Option 2: Nginx Reverse Proxy (Production)

#### Install Nginx
```bash
sudo apt install nginx -y
sudo systemctl enable nginx
```

#### Create Nginx Config
```bash
sudo nano /etc/nginx/sites-available/version-monitor
```

**Add this configuration:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8383;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### Enable Config
```bash
sudo ln -s /etc/nginx/sites-available/version-monitor /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### Access
- `http://your-domain.com`

---

### Option 3: SSL/HTTPS with Let's Encrypt

#### Install Certbot
```bash
sudo apt install certbot python3-certbot-nginx -y
```

#### Generate Certificate
```bash
sudo certbot --nginx -d your-domain.com
```

#### Auto-renewal
```bash
sudo systemctl enable certbot.timer
```

---

## Production Best Practices

### 1. Use Docker Compose with Multiple Services

**Example with Nginx:**
```yaml
version: '3.8'

services:
  app:
    build: .
    container_name: version-monitor
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8383/api/status"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: version-monitor-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - app
    restart: unless-stopped
```

### 2. Persistent Data

**Create named volume:**
```bash
docker volume create version-monitor-data
```

**Use in docker-compose:**
```yaml
volumes:
  - version-monitor-data:/app/data
```

### 3. Environment Variables

**Create .env file for production:**
```bash
API_KEY=your-production-secret-key
```

**Reference in docker-compose:**
```yaml
env_file:
  - .env
```

### 4. Logging

**View logs:**
```bash
docker-compose logs app
docker-compose logs app -f --tail 100
```

**Persistent logging:**
```bash
docker-compose logs app > app.log
```

### 5. Backups

**Backup database:**
```bash
docker exec version-monitor cp devices.db ./backup/devices.db.$(date +%Y%m%d)
```

### 6. Resource Limits

**In docker-compose:**
```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

### 7. Auto-restart on Failure

**Already set in docker-compose:**
```yaml
restart: unless-stopped
```

---

## Troubleshooting

### Container won't start
```bash
docker-compose logs app
docker ps -a  # See stopped containers
```

### Port already in use
```bash
# Find process using port 8383
sudo lsof -i :8383
# Kill it or use different port in docker-compose.yml
```

### Database issues
```bash
# Remove old container and volume
docker-compose down -v
docker volume rm version-monitor-data
docker-compose up -d
```

### Access denied errors
```bash
# Check file permissions
docker exec version-monitor ls -la
# Fix if needed
docker exec version-monitor chown -R appuser:appuser /app
```

---

## Quick Reference Commands

```bash
# Build image
docker build -t version-monitor:latest .

# Run container
docker run -p 8383:8383 --name version-monitor version-monitor:latest

# Docker Compose
docker-compose up -d          # Start
docker-compose down           # Stop
docker-compose logs -f        # View logs
docker-compose ps             # Status

# Container management
docker ps                      # List running
docker ps -a                   # List all
docker exec -it <name> bash   # Enter shell
docker stop <name>            # Stop
docker rm <name>              # Remove
```

---

## Questions?

For issues or questions:
1. Check logs: `docker-compose logs app`
2. Verify config: `cat docker-compose.yml`
3. Test endpoint: `curl http://localhost:8383/api/status`
