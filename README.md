# Splicer Firmware Monitor
TESTTETSTTEST
Simple monitoring app that:
- Downloads a PDF containing firmware versions
- Extracts version info for a list of monitored devices
- Stores the accepted (stored) version in a local SQLite DB
- Highlights devices when the detected version differs from the stored value
- Allows acknowledging a detected change which updates the DB
 
Quick start

1. Create and activate your Python environment (you already have a venv configured for this workspace).

2. Install requirements (if not already installed):

```powershell
C:/Users/jakub.rogowski/Monitoring_App/.venv/Scripts/python.exe -m pip install -r requirements.txt
```

3. Run the server:

```powershell
C:/Users/jakub.rogowski/Monitoring_App/.venv/Scripts/python.exe -m uvicorn app:app --reload
```

4. Open http://127.0.0.1:8000 in your browser.

Notes
- The list of monitored products/URLs is in `app.py` (variable `MONITORED_MAP`).
- The SQLite DB is saved as `devices.db` in the project root.
- Acknowledge will update the stored version for that model to the detected one from the latest scan.

Note: The app was updated to monitor web pages instead of the original PDF-based splicer list. The scraping module `web_monitor.py` uses heuristics to find version tokens near the product names on each page.

API key protected LAN API
------------------------

This project can serve a small LAN API protected by a single API key. Set the `API_KEY` environment variable on the server before starting the app. Example (PowerShell):

```powershell
$env:API_KEY = 'my-secret-key'
# start server accessible on LAN for development
. .\.venv\Scripts\Activate.ps1; uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Protected endpoints (example):
- `GET /api/v1/devices` — returns the devices status JSON. Requires header `X-Credentials: <API_KEY>`.
- `GET /api/v1/keys/validate` — simple validation endpoint to check the provided API key.

Example request from PowerShell (replace with your host IP and API key):

```powershell
# without header -> will return 401
# Invoke-RestMethod -Uri 'http://192.168.1.10:8000/api/v1/devices'

# with header
Invoke-RestMethod -Uri 'http://192.168.1.10:8000/api/v1/devices' -Headers @{ 'X-Credentials' = 'my-secret-key' }
```

Notes:
- For development you can use `uvicorn --host 0.0.0.0` to expose the server on the LAN. In production place a TLS-terminating reverse proxy (nginx, Caddy, Traefik) in front of the app and store secrets securely (e.g., environment variables or a secrets manager).
- Each request is logged with a masked API key and a timing header `X-Process-Time` is added to responses.
