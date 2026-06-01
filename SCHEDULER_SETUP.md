# PDF Scheduler Setup

## Overview
This setup uses APScheduler to automatically extract tables from a PDF once daily and uses Ollama vision models to process the extracted images.

**Note:** Ollama must be running on your system or accessible at the default endpoint (`http://localhost:11434`).

## Files Created
- `pdf_vision_extractor.py` - PDF download and Ollama vision extraction
- `pdf_scheduler.py` - Scheduler implementation
- `requirements.txt` - Updated with ollama and dependencies

## Installation

### Prerequisites

**Install Ollama:**
- Download from [ollama.com](https://ollama.com)
- Install and run: `ollama serve` (keeps Ollama running on `localhost:11434`)

**Install Python dependencies:**
```bash
pip install -r requirements.txt
```

### Pull Ollama Models

Before running the scheduler, pull the vision model:

```bash
ollama pull qwen2.5-vl:3b
```

Other available vision models:
- `qwen2.5-vl:3b` - Recommended, improved accuracy and speed (default)
- `qwen2-vl:2b` - Lightweight, fast but less accurate
- `llava:7b` - More capable but larger
- `llava:13b` - Largest, best accuracy

## Configuration

### PDF URL
The PDF URL is configurable via the `PDF_URL` environment variable. 

**Default:** `http://example.com/latest_software.pdf`

### Running Locally

1. Create a `.env` file in the project root:
```
API_KEY=your_api_key_here
PDF_URL=http://your-server.com/your_software.pdf
```

2. Run the app:
```bash
python app.py
```

Or with uvicorn:
```bash
uvicorn app:app --host 127.0.0.1 --port 8484
```

### Running with Docker

**Option 1: Host Ollama, containerized FastAPI**

Start Ollama on your host (outside Docker):
```bash
ollama serve  # Runs on localhost:11434
ollama pull qwen2.5-vl:3b
```

Then run the FastAPI app in Docker:
```bash
docker build -t monitoring-app .

docker run -e PDF_URL="http://your-server.com/your_software.pdf" \
           -e API_KEY="your_api_key" \
           -e OLLAMA_BASE_URL="http://host.docker.internal:11434" \
           -p 8484:8484 \
           monitoring-app
```

**Option 2: Full Docker setup (Recommended)**

Create a `docker-compose.yml`:

```yaml
version: '3.8'
services:
  # Ollama service (vision model)
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0:11434
    command: serve

  # FastAPI monitoring app
  monitoring-app:
    build: .
    depends_on:
      - ollama
    ports:
      - "8484:8484"
    environment:
      - API_KEY=your_api_key_here
      - PDF_URL=http://your-server.com/your_software.pdf
      - OLLAMA_BASE_URL=http://ollama:11434
    volumes:
      - ./extractions:/app/extractions

volumes:
  ollama_data:
```

Start everything:
```bash
docker-compose up -d

# Pull the model (only needed first time)
docker-compose exec ollama ollama pull qwen2.5-vl:3b
```

## Usage

### Standalone Script
Run the scheduler as a standalone service:
```bash
python pdf_scheduler.py
```

This will:
- Start the scheduler running in the background
- Execute daily at 9:00 AM by default
- Save results to `./extractions/` directory as JSON files
- Keep running until you press Ctrl+C

### API Endpoints

**Manually trigger extraction immediately:**
```bash
POST /api/extraction/trigger
```

**Get extraction status:**
```bash
GET /api/extraction/status
```

Response:
```json
{
  "next_run": "2026-04-28 09:00:00",
  "job_id": "pdf_extraction",
  "current_url": "http://your-server.com/your_software.pdf"
}
```

**Update PDF URL at runtime:**
```bash
POST /api/extraction/update-url
Content-Type: application/json

{"url": "http://new-server.com/pdf.pdf"}
```

## Configuration Options

### Change Extraction Time
Edit `app.py` startup_event and change the hour/minute:
```python
pdf_scheduler.start(hour=14, minute=30)  # Run at 2:30 PM daily
```

### Change Output Directory
The extractions are saved to `./extractions/` by default. Change in `app.py`:
```python
output_dir=os.path.join(BASE_DIR, "custom_path")
```

## Output Format
Results are saved as:
- `extractions/extraction_YYYYMMDD_HHMMSS.json`
- Each file contains the full SGLang API response

## Monitoring
Check logs for:
- Scheduled run times
- Extraction status
- Error messages

Example log output:
```
2026-04-27 09:00:00 - __main__ - INFO - Starting PDF extraction from http://your-server.com/pdf.pdf
2026-04-27 09:00:15 - __main__ - INFO - Extraction saved to extractions/extraction_20260427_090015.json
```

## Troubleshooting

**Ollama not installed?**
- Download from [ollama.com](https://ollama.com)
- Run `ollama serve` to start the service

**Model not found?**
```bash
ollama pull qwen2.5-vl:3b
```

**Connection error to Ollama?**
- Verify Ollama is running: `ollama serve`
- Check it's accessible: `curl http://localhost:11434/api/tags`
- If using Docker, use `OLLAMA_BASE_URL=http://host.docker.internal:11434` (Mac/Windows) or `http://ollama:11434` (in docker-compose)

**PDF download fails?**
- Check the PDF URL is accessible
- Verify network connectivity
- Check firewall/proxy settings

**Results not saving?**
- Verify `./extractions/` directory is writable
- Check disk space
- Review error logs

**Environment variable not being read?**
- Make sure variable is set before starting the app
- Use `echo $PDF_URL` to verify it's set (Linux/Mac)
- Use `echo %PDF_URL%` to verify it's set (Windows)
- In Docker, use `-e` flag or docker-compose environment section

**Ollama running out of memory?**
- Try smaller models if qwen2.5-vl:3b is too large
- Or use `qwen2-vl:2b` for limited resources
- Check available VRAM: `nvidia-smi` (for GPU acceleration)
