# EXFO Version Monitor

Web application for monitoring software and firmware versions of EXFO devices and applications directly from the EXFO website.

## Features
- Scrapes the latest software/firmware versions from official EXFO pages (`apps.exfo.com`)
- Compares detected versions with stored/acknowledged versions in a local SQLite database (`devices.db`)
- Visual status indicators:
  - 🟢 **Green**: Up to date (detected version matches stored version)
  - 🔴 **Red**: Outdated / New version detected
  - 🟠 **Orange**: Unknown / Version not found
- Supports manual refresh and background polling
- One-click version acknowledgement and storing
- Protected LAN REST API with `X-Credentials` header authentication

## Quick Start

### Running Locally with Python

1. Install requirements:
```bash
pip install -r requirements.txt
```

2. Start the server:
```bash
python -m uvicorn app:app --reload --port 8000
```

3. Open http://127.0.0.1:8000 in your browser.

### Running with Docker

```bash
docker-compose up -d
```
Access the application at http://localhost:8000.

## Configuration
- Monitored products and URLs are configured in `monitor_config.py` (`MONITORED_MAP`).
- SQLite database is saved as `devices.db`.
- Set `API_KEY` in environment or `.env` to protect API endpoints.
