# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY web_monitor.py .
COPY pdf_scheduler.py .
COPY pdf_vision_extractor.py .
COPY monitor_config.py .
COPY utils.py .
COPY templates/ templates/
COPY static/ static/

# Create directories with proper permissions before switching user
RUN mkdir -p extractions && \
    chmod 777 extractions && \
    chmod 777 /app

# Create a non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Switch to non-root user - commented out for volume mount compatibility
# USER appuser

# Ensure runtime database directory is writable
RUN chmod 777 /app

# Environment variables (can be overridden at runtime)
ENV API_KEY=""
ENV PDF_URL="http://example.com/latest_software.pdf"
ENV OLLAMA_BASE_URL="http://localhost:11434"

# Expose port (app always runs on 8484)
EXPOSE 8484

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://127.0.0.1:8484/api/status', timeout=5)" || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8484"]
