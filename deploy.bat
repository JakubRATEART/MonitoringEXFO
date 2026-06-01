@echo off
REM Version Monitor - Quick Docker Setup Script for Windows

echo.
echo ============================================
echo Version Monitor - Docker Quick Setup
echo ============================================
echo.

REM Check Docker installation
where docker >nul 2>nul
if errorlevel 1 (
    echo Error: Docker is not installed or not in PATH
    echo Please install Docker Desktop from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('docker --version') do set DOCKER_VERSION=%%i
echo [OK] Docker found: %DOCKER_VERSION%

REM Check Docker Compose
where docker-compose >nul 2>nul
if errorlevel 1 (
    echo [WARN] Docker Compose not found (should be included with Docker Desktop)
)

echo [OK] Docker Compose found
echo.

REM Build image
echo [*] Building Docker image...
docker build -t version-monitor:latest .
if errorlevel 1 (
    echo [ERROR] Failed to build image
    pause
    exit /b 1
)
echo [OK] Image built successfully
echo.

REM Create environment file if it doesn't exist
if not exist .env (
    echo [*] Creating .env file from template...
    copy .env.example .env
    echo [OK] .env created (edit it to add API_KEY if needed)
)

echo.
echo [*] Starting container with Docker Compose...
docker-compose up -d

echo.
echo [OK] Version Monitor is running!
echo.
echo [INFO] Access the application at: http://localhost:8383
echo.
echo [COMMANDS]
echo   View logs:         docker-compose logs -f
echo   Stop app:          docker-compose down
echo   Restart app:       docker-compose restart
echo   Container status:  docker-compose ps
echo.
pause
