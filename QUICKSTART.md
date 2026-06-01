# Quick Start Guide - Docker Deployment

## Prerequisites
- Docker installed ([get.docker.com](https://get.docker.com) for Linux, [Docker Desktop](https://www.docker.com/products/docker-desktop) for Windows/Mac)

## Fastest Way to Run

### Windows
```powershell
.\deploy.bat
```

### Linux/Mac
```bash
chmod +x deploy.sh
./deploy.sh
```

## Manual Steps

### 1️⃣ Build Image
```bash
docker build -t version-monitor:latest .
```

### 2️⃣ Start Container
```bash
docker-compose up -d
```

### 3️⃣ Access App
Open browser to: **http://localhost:8383**

---

## Common Commands

| Command | What it does |
|---------|------------|
| `docker-compose up -d` | Start app in background |
| `docker-compose down` | Stop app |
| `docker-compose logs -f` | View live logs |
| `docker-compose ps` | Show status |
| `docker-compose restart` | Restart app |
| `docker exec -it version-monitor bash` | Open shell inside container |

---

## With Linux/Mac Make

```bash
make up        # Start
make down      # Stop
make logs      # View logs
make restart   # Restart
make backup    # Backup database
make clean     # Remove everything
```

---

## Environment Variables

Create `.env` file:
```bash
cp .env.example .env
```

Edit and add:
```
API_KEY=your-secret-key
```

---

## Server Deployment (VPS/Cloud)

### 1. SSH to server
```bash
ssh user@your-server-ip
```

### 2. Clone app
```bash
git clone <repo> && cd monitoring-app
```

### 3. Setup environment
```bash
cp .env.example .env
# Edit .env with your settings
nano .env
```

### 4. Start
```bash
docker-compose up -d
```

### 5. Access
- Direct: `http://server-ip:8383`
- With Nginx: `http://your-domain.com`

---

## Production Setup (with Nginx + SSL)

### Install Nginx
```bash
sudo apt install nginx certbot python3-certbot-nginx
```

### Update docker-compose.yml
Map to port 8000 (internal only):
```yaml
ports:
  - "127.0.0.1:8000:8383"
```

### Configure Nginx
```bash
sudo tee /etc/nginx/sites-available/monitor << EOF
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/monitor /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Get SSL Certificate
```bash
sudo certbot --nginx -d your-domain.com
```

### Restart
```bash
docker-compose restart
```

---

## Troubleshooting

**Container won't start?**
```bash
docker-compose logs app
```

**Port 8383 already in use?**
```bash
# Change in docker-compose.yml:
ports:
  - "8384:8383"
```

**Permission denied?**
```bash
# Linux/Mac:
sudo docker-compose up -d
```

**Database lost after restart?**
```bash
# Add to docker-compose.yml:
volumes:
  - app-data:/app

volumes:
  app-data:
```

---

## For Full Documentation
See `DEPLOYMENT.md` in the project root.
