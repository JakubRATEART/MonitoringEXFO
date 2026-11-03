# Production Dockerfile for EXFO Version Monitor
FROM python:3.11-slim

# Set environment variables for production execution
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

# Set working directory
WORKDIR /app

# Create a non-root system user and group for security
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/bash -m appuser

# Copy requirements file first for layer caching
COPY requirements.txt .

# Install dependencies as root
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app.py web_monitor.py monitor_config.py ./
COPY templates/ ./templates/
COPY static/ ./static/

# Ensure application directory and SQLite database files are owned and writable by appuser
RUN chown -R appuser:appgroup /app && \
    chmod -R 775 /app

# Switch to non-root user
USER appuser

# Expose server port
EXPOSE 8000

# Health check using built-in urllib (does not depend on external tools)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)" || exit 1

# Launch Uvicorn with proxy headers enabled for reverse proxy / load balancer support
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
